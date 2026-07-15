# -*- coding: utf-8 -*-
"""
多资产趋势轮动策略 V1 — 融合行业轮动 V4 + 多资产 ETF 轮动


做全球轮动

设计来源：
  - 行业轮动 V4（industry_rotation_strategy.py）：市场状态三分类 + 移动止损 + 冷却期
  - 多资产 ETF 轮动（multi_asset_rotation_strategy.py）：对数回归动量 + RSRS 阻速线

融合策略：
  1. 资产池 = 行业 ETF + 跨境 + 商品 + 债券（~35-45 只，仅需 OHLCV）
  2. 动量 = 加权对数线性回归斜率 × R²（来自多资产策略）
  3. 入场确认 = RSRS 阻速线 + 价格 > MA20
  4. 仓位 = 等权分配 top 2-3 只，每只 ≤ 40%
  5. 出场 = 趋势断裂(MA60) + 移动止损 + 硬止损（来自 V4）
  6. 市场状态 = BULL / NEUTRAL / BEAR 三态 + 动态仓位上限（来自 V4）
  7. 调仓 = 每 5 天（降低换手率）
  8. 冷却期 = 10/20 天（正常/止损）

数据需求：
  - 仅 OHLCV 日线（无 PE/PB/行业指数依赖）
  - 预热只需 25 天动量窗口 × 1.2 ≈ 30 天 → 启动即就绪
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from core.engines.types.entities import BarData
from modules.strategy.constants import StrategyType, SignalDirection, SignalType
from modules.strategy.models import TradingSignal
from modules.strategy.strategies.base.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class MultiAssetTrendStrategy(BaseStrategy):
    """
    多资产趋势轮动策略 V1。

    策略类型：ROTATION
    继承 BaseStrategy，遵循 on_bar 驱动模式。

    核心原则：
      - 跨资产池降低相关性，仅需 OHLCV 数据
      - 对数回归动量 × R² 评分
      - 等权持有 top 2-3，每 5 天调仓
      - 趋势断裂 + 移动止损出场
      - 市场状态三分类决定仓位上限
    """

    strategy_type: StrategyType = StrategyType.ROTATION

    # =========================================================================
    # ETF 候选池 — 跨资产低相关组合
    # =========================================================================
    DEFAULT_ETF_POOL: List[str] = [
        # ---- A 股宽基 / 行业 ----
        "510050.SH",  # 上证50
        "510300.SH",  # 沪深300
        "510500.SH",  # 中证500
        "159915.SZ",  # 创业板
        "588000.SH",  # 科创50
        "512100.SH",  # 中证1000
        # ---- 行业 ETF ----
        "512880.SH",  # 证券
        "512660.SH",  # 军工
        "512800.SH",  # 银行
        "512690.SH",  # 酒
        "516110.SH",  # 汽车
        "512980.SH",  # 传媒
        "159825.SZ",  # 农业
        "515210.SH",  # 钢铁
        "516950.SH",  # 基建
        "512480.SH",  # 半导体
        "515050.SH",  # 5G通信
        "512170.SH",  # 医疗
        "512710.SH",  # 军工龙头
        "159996.SZ",  # 家电
        "512580.SH",  # 碳中和
        # ---- 跨境 ----
        "513100.SH",  # 纳指100
        "513520.SH",  # 日经ETF
        "513020.SH",  # 港股科技
        "159941.SZ",  # 纳指ETF
        # ---- 商品 ----
        "518880.SH",  # 黄金ETF
        "501018.SH",  # 南方原油
        # ---- 债券 ----
        "511090.SH",  # 30年国债ETF
        "511260.SH",  # 10年国债ETF
    ]

    # =========================================================================
    # 默认参数
    # =========================================================================
    DEFAULT_PARAMS: Dict[str, Any] = {
        # —— 资产池（可自定义覆盖） ——
        "etf_pool": None,  # None 时使用 DEFAULT_ETF_POOL

        # —— 策略基础 ——
        "rebalance_frequency": 10,   # 调仓间隔（交易日）v1.4: 5→10，减半交易频率
        "cooling_period": 15,        # 正常出场后的冷却天数 v1.4: 10→15
        "min_history": 25,           # 预热最少天数（= momentum_days）
        "rs_benchmark": "000300.SH", # 基准指数
        "max_holdings": 3,           # 同时持有的最大标数量
        "max_single_weight": 0.30,   # 单标的上限仓位（v1.3: 40%→30% 降低集中度）

        # —— 动量参数（对数回归，v2.0 自适应） ——
        # 根据不同市场状态使用不同窗口：BULL=追强(短) / NEUTRAL=稳健(中) / 防御=保守(长)
        "momentum_days_bull": 15,     # BULL: 短期动量，快速追强
        "momentum_days_neutral": 40,  # NEUTRAL: 中期动量，过滤噪音
        "momentum_days_defensive": 60,# 防御市: 长期动量，只选最确定的
        "momentum_max_score": 5.0,   # 极端动量过滤上限（年化 5 倍排除）

        # —— 利润锁定 ——
        # v2.1: 抛物线止盈——浮盈越大，允许回撤越小（参考 stock_low_high_strategy）
        #   pnl≥80%→回落2%卖, ≥40%→4%, ≥20%→6%, ≥10%→8%
        "profit_parabolic": True,      # 启用抛物线止盈（覆盖固定阈值）
        "frama_efficiency_min": 0.25,  # FRAMA效率<0.25→该ETF不参与排名（震荡中）

        # —— RSRS 参数 ——
        "rsrs_window": 18,           # RSRS 当日斜率计算窗口
        "rsrs_lookback": 250,        # RSRS Beta 回溯天数
        "rsrs_beta_window": 20,      # RSRS Beta 滚动窗口
        "rsrs_strength_strong": 0.15,  # 强趋势确认阈值
        "rsrs_strength_weak": 0.03,    # 弱趋势确认阈值（需配合 MA20）

        # —— 量异常参数 ——
        "volume_check_days": 7,      # 量异常检测周期
        "volume_threshold": 2.0,     # 量异常阈值（超过均值 2 倍排除）

        # —— 入场附加过滤 ——
        "entry_min_ma20": True,      # 价格必须在 MA20 上方
        "entry_min_ma10": True,      # v1.3: 价格必须在 MA10 上方（短期趋势确认）
        "entry_min_ret_5d": 0.0,     # v1.3: 近5日累计收益必须 > 0（避免追跌）

        # —— 风控 ——
        "stop_loss": -0.12,          # 硬止损线（-12% 兜底）
        "min_hold_days": 25,          # 最低持有天数（v1.4: 20→25）

        # —— Layer 0: 市场状态 ——
        "v1_bull_width_min": 8,      # BULL：至少 N 个 ETF 多头排列
        "v1_bear_width_max": 4,      # BEAR：最多 N 个 ETF 多头排列
        "v1_neutral_max_pos": 0.60,  # NEUTRAL 仓位上限
        "v1_neutral_down_max_pos": 0.30,  # NEUTRAL 下跌市仓位上限

        # —— Layer 5: 出场 ——
        "v1_trail_stop_ratio": 0.16,     # 正常仓位移动止损回撤比例
        "v1_heavy_stop_ratio": 0.14,     # 重仓（>50%）收紧比例
        "v1_downtrend_stop_ratio": 0.12, # 下跌市收紧比例
        "v1_exit_cooldown_stop": 20,     # 止损出场冷却天数

        # —— 调试 ——
        "verbose_logging": False,
    }

    def __init__(
        self,
        name: str = "多资产趋势轮动V1",
        strategy_type: StrategyType = StrategyType.ROTATION,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        merged = dict(self.DEFAULT_PARAMS)
        if parameters:
            merged.update(parameters)
        super().__init__(name=name, strategy_type=strategy_type, parameters=merged)

        # ---- 参数提取 ----
        self.etf_pool: List[str] = (
            list(merged["etf_pool"])
            if merged.get("etf_pool")
            else list(self.DEFAULT_ETF_POOL)
        )
        self.rebalance_frequency: int = int(merged["rebalance_frequency"])
        self.cooling_period: int = int(merged["cooling_period"])
        self.min_history: int = int(merged["min_history"])
        self.stop_loss: float = float(merged["stop_loss"])
        self.verbose_logging: bool = bool(merged.get("verbose_logging", False))
        self.max_holdings: int = int(merged.get("max_holdings", 3))
        self.max_single_weight: float = float(merged.get("max_single_weight", 0.40))

        # ---- 运行时状态 ----
        self._bar_count: int = 0
        self._warmup_warned: bool = False
        self._last_rebalance_date: str = ""
        self._last_trade_date: str = ""

        # 持仓跟踪
        self._current_holdings: Dict[str, str] = {}  # {ETF代码: 标签}
        self._holding_weights: Dict[str, float] = {}  # {ETF代码: 仓位权重}
        self._entry_prices: Dict[str, float] = {}
        self._entry_dates: Dict[str, str] = {}        # {ETF代码: 入场日期}
        self._highest_prices: Dict[str, float] = {}
        self._cooling_list: Dict[str, int] = {}      # {ETF代码: 剩余冷却天数}

        # 数据缓存
        self._data_cache: Dict[str, pd.DataFrame] = {}       # {ETF代码: DataFrame}
        self._benchmark_cache: Optional[pd.DataFrame] = None

        # 评分缓存
        self._prev_scores: Dict[str, float] = {}     # 上期动量得分

        # ---- 市场状态 ----
        self._v1_regime: str = "NEUTRAL"
        self._v1_max_position: float = float(merged.get("v1_neutral_max_pos", 0.60))
        self._v1_width_history: List[int] = []  # v1.3: 最近 3 期宽度值，用于 BEAR 预警

        logger.info(
            f"多资产趋势轮动V1初始化: {name}, "
            f"ETF池={len(self.etf_pool)}只, "
            f"动量窗口={self.parameters.get('momentum_days', 25)}天, "
            f"调仓频率={self.rebalance_frequency}天"
        )

    # =========================================================================
    # 生命周期
    # =========================================================================

    def on_init(self) -> None:
        """设置股票池 + 校验参数"""
        errors = self._validate_params()
        if errors:
            raise ValueError(f"策略参数校验失败: {'; '.join(errors)}")

        self._universe = list(self.etf_pool)
        rs_bm = self.parameters.get("rs_benchmark", "")
        if rs_bm and rs_bm not in self._universe:
            self._universe.append(rs_bm)

        logger.info(
            f"多资产趋势轮动V1 初始化完成, ETF候选={len(self._universe)}只"
        )

    async def on_start(self) -> None:
        """重置状态 + 预热历史数据"""
        self._bar_count = 0
        self._last_rebalance_date = ""
        self._current_holdings.clear()
        self._holding_weights.clear()
        self._data_cache.clear()
        self._benchmark_cache = None
        self._prev_scores.clear()
        self._cooling_list.clear()
        self._entry_prices.clear()
        self._entry_dates.clear()
        self._highest_prices.clear()
        self._warmup_warned = False
        self._v1_regime = "NEUTRAL"
        self._v1_max_position = self.parameters.get("v1_neutral_max_pos", 0.60)
        self._v1_width_history.clear()

        loaded = await self._preload_history()
        if loaded > 0:
            logger.info(
                f"多资产趋势轮动V1 已启动 — 预热 {loaded} 条数据, "
                f"覆盖 {len(self._data_cache)} 只 ETF"
            )
        else:
            logger.info("多资产趋势轮动V1 已启动（等待 bar 累积）")

    async def _preload_history(self) -> int:
        """从 DB 加载 ETF 历史数据预热缓存"""
        session_factory = getattr(self, "_db_session_factory", None)
        if session_factory is None:
            return 0

        from datetime import date as _dt, timedelta
        from modules.strategy.engines.data_feed_engine import DataFeedEngine as _DFE

        end_date = _dt.today()
        lookback = int(self.parameters.get("momentum_days", 25) * 1.5) + 30
        start_date = end_date - timedelta(days=lookback)

        try:
            async with session_factory() as db:
                engine = _DFE(db)
                symbols = self.etf_pool.copy()
                rs_bm = self.parameters.get("rs_benchmark", "")
                if rs_bm and rs_bm not in symbols:
                    symbols.append(rs_bm)

                df = await engine.load_historical_data(
                    symbols=symbols,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                )
                if not df.empty:
                    for ts_code in df["ts_code"].unique():
                        sub = df[df["ts_code"] == ts_code].copy()
                        sub = sub.sort_values("trade_date").reset_index(drop=True)
                        self._data_cache[ts_code] = sub
                    logger.info(
                        f"ETF 历史预热完成: {len(df)} 行, {start_date} ~ {end_date}"
                    )
                    return len(df)
        except Exception as e:
            logger.warning(f"历史预热失败（非致命，将等待 bar 累积）: {e}")
        return 0

    def on_stop(self) -> None:
        """清理状态"""
        self._data_cache.clear()
        self._prev_scores.clear()
        self._current_holdings.clear()
        self._holding_weights.clear()
        self._benchmark_cache = None
        self._cooling_list.clear()
        self._entry_prices.clear()
        self._entry_dates.clear()
        self._highest_prices.clear()
        self._v1_width_history.clear()
        logger.info("多资产趋势轮动V1 已停止")

    # =========================================================================
    # 核心入口：on_bar
    # =========================================================================

    def on_bar(self, bar: BarData) -> List[TradingSignal]:
        """接收一根 K 线，缓存数据 + 定期调仓"""
        signals: List[TradingSignal] = []
        ts_code = bar.ts_code

        try:
            if ts_code not in self._universe:
                return signals

            self._append_data(ts_code, bar)

            trade_date = getattr(bar, "trade_date", "") or getattr(bar, "datetime", "")
            if isinstance(trade_date, str) and len(trade_date) >= 10:
                trade_date = trade_date[:10]
            self._last_trade_date = trade_date

            if self._last_rebalance_date and trade_date == self._last_rebalance_date:
                return signals

            self._bar_count += 1

            if self._bar_count % self.rebalance_frequency == 0:
                signals = self._run_rebalance()
                self._last_rebalance_date = trade_date

        except Exception as e:
            logger.error(
                f"多资产趋势轮动V1 on_bar 异常: {ts_code}: {e}", exc_info=True
            )

        return signals

    # =========================================================================
    # 主调仓
    # =========================================================================

    def _run_rebalance(self) -> List[TradingSignal]:
        """
        主调仓逻辑。

        流程：
          1. 预热检查
          2. Layer 0: 市场状态判定
          3. Layer 5: 出场检查（已有持仓）
          4. Layer 1: 动量评分
          5. Layer 2: 入场确认（量异常 + RSRS）
          6. Layer 3: 建仓（等权分配 top N）
        """
        signals: List[TradingSignal] = []

        # ---- 预热检查 ----
        max_days = max((len(df) for df in self._data_cache.values()), default=0)
        if max_days < self.min_history + 1:
            if not self._warmup_warned:
                self._warmup_warned = True
                logger.info(
                    f"多资产趋势轮动V1: 预热期 — {max_days}/{self.min_history} 天"
                )
            return signals

        # ---- 同步基准 ----
        rs_bm = self.parameters.get("rs_benchmark", "")
        if rs_bm and rs_bm in self._data_cache:
            self._benchmark_cache = self._data_cache[rs_bm]

        # 追踪本轮已卖出的 ETF
        self._exited_etfs_this_round: Set[str] = set()

        # ===== Layer 0: 市场状态 =====
        self._detect_market_state()

        # ===== Layer 5: 出场检查 =====
        for etf_code in list(self._current_holdings.keys()):
            exit_signal = self._check_exit(etf_code)
            if exit_signal:
                logger.info(f"V1出场: {etf_code} — {exit_signal.reason}")
                signals.append(exit_signal)

                is_half = getattr(exit_signal, "half_exit", False)
                if is_half:
                    # v2.0: 半仓止盈——减半仓位，保留剩余
                    if etf_code in self._holding_weights:
                        self._holding_weights[etf_code] *= 0.5
                    # 半仓不设冷却期，不出售 exited 列表（仍可被替换或继续持有）
                    continue

                self._exited_etfs_this_round.add(etf_code)
                label = self._current_holdings.get(etf_code, etf_code)
                cd = (
                    self.parameters.get("v1_exit_cooldown_stop", 20)
                    if exit_signal.signal_type == SignalType.STOP_LOSS
                    else self.cooling_period
                )
                self._cooling_list[etf_code] = cd
                del self._current_holdings[etf_code]
                if etf_code in self._holding_weights:
                    del self._holding_weights[etf_code]
                if etf_code in self._entry_prices:
                    del self._entry_prices[etf_code]
                if etf_code in self._entry_dates:
                    del self._entry_dates[etf_code]
                if etf_code in self._highest_prices:
                    del self._highest_prices[etf_code]

        # ===== BEAR 市：强制清仓 + 不建新仓 =====
        if self._v1_regime == "BEAR":
            # v1.2: BEAR 市不仅阻止新开仓，还强制清掉所有已有持仓
            for etf_code in list(self._current_holdings.keys()):
                signals.append(self._make_exit_signal(
                    etf_code,
                    reason=f"BEAR市强制清仓",
                    signal_type=SignalType.EXIT,
                ))
                self._cooling_list[etf_code] = self.cooling_period
                del self._current_holdings[etf_code]
                if etf_code in self._holding_weights:
                    del self._holding_weights[etf_code]
                if etf_code in self._entry_prices:
                    del self._entry_prices[etf_code]
                if etf_code in self._entry_dates:
                    del self._entry_dates[etf_code]
                if etf_code in self._highest_prices:
                    del self._highest_prices[etf_code]
            if signals:
                logger.info(f"V1 BEAR市清仓: {len(signals)} 个持仓")
            self._prev_scores.clear()  # v1.5: BEAR期间不保留旧得分，退出时重算
            self._decay_cooling()
            return signals

        # 计算当前仓位（v1.2: 市场状态仓位上限生效）
        cur_count = len(self._current_holdings)
        max_h = self.parameters.get("max_holdings", 3)
        max_single = self.max_single_weight
        cur_weight = sum(self._holding_weights.values())
        weight_room = self._v1_max_position - cur_weight
        has_room = (cur_count < max_h) and (weight_room >= 0.05)  # 至少 5% 空间才开新仓

        # ===== Layer 1: 动量评分 =====
        rankings = self._calc_momentum_rankings()
        if not rankings:
            self._decay_cooling()
            return signals

        # 保存当期得分
        self._prev_scores = {code: score for code, score in rankings}

        # ===== Layer 2: 入场确认 =====
        candidates = []
        for code, score in rankings[:8]:  # 只看前 8 个候选
            if code in self._current_holdings:
                candidates.append((code, score))
                continue
            if code in self._exited_etfs_this_round:
                continue
            if self._cooling_list.get(code, 0) > 0:
                continue

            # 量异常过滤
            if self._is_volume_abnormal(code):
                continue

            # RSRS 过滤
            if not self._pass_rsrs_filter(code):
                continue

            # v1.3: 短期趋势过滤——价格>MA10 + 近5日正收益，避免追跌
            if not self._check_short_term_trend(code):
                continue

            # v2.1: FRAMA效率过滤——震荡中的ETF不参与排名
            if self._frama_efficiency(code) < self.parameters.get("frama_efficiency_min", 0.25):
                continue

            candidates.append((code, score))

        if not candidates:
            self._decay_cooling()
            return signals

        # ===== Layer 3: 建仓 =====
        if has_room:
            slots = max_h - cur_count
            for code, score in candidates[:slots]:
                current_price = self._get_price(code)
                if current_price <= 0:
                    continue

                # 等权分配，置信度微调，受市场状态仓位上限约束
                weight = min(max_single, 1.0 / max_h)
                median_score = np.median([s for _, s in rankings[:10]])
                if score > median_score:
                    weight = min(max_single, weight + 0.05)
                # v1.2: 受剩余仓位空间约束
                weight = min(weight, weight_room)

                if weight < 0.05:
                    continue  # 空间不足，不勉强开仓

                self._current_holdings[code] = code
                self._holding_weights[code] = weight
                self._entry_prices[code] = current_price
                self._entry_dates[code] = self._last_trade_date
                self._highest_prices[code] = current_price

                signals.append(self._make_entry_signal(
                    code, weight,
                    reason=f"动量#{rankings.index((code, score)) + 1} 得分{score:.4f}",
                ))

                logger.info(
                    f"V1建仓: {code} 仓位{weight:.0%} "
                    f"价格{current_price:.2f} "
                    f"(总仓位上限={self._v1_max_position:.0%})"
                )

                weight_room -= weight
                if len(self._current_holdings) >= max_h or weight_room < 0.05:
                    break
        else:
            # ---- 仓位已满 → 替换最差持仓 ----
            self._try_replace(rankings, signals)

        # ---- 更新状态 ----
        self._decay_cooling()

        return signals

    # =========================================================================
    # Layer 0: 市场状态判定
    # =========================================================================

    def _detect_market_state(self) -> None:
        """
        三态分类：BULL / NEUTRAL / BEAR。

        用 ETF 池中多头排列（MA20 > MA60）的数量判断市场宽度。
        """
        bm = self._benchmark_cache
        if bm is None or len(bm) < 20:
            self._v1_regime = "NEUTRAL"
            self._v1_max_position = self.parameters.get("v1_neutral_max_pos", 0.60)
            return

        bm_close = bm["close"].values.astype(float)
        ma20 = float(np.mean(bm_close[-20:]))
        ma60 = float(np.mean(bm_close[-60:])) if len(bm_close) >= 60 else ma20

        # ETF 宽度
        width = 0
        for code, df in self._data_cache.items():
            if code not in self.etf_pool:
                continue
            c = df["close"].values.astype(float)
            if len(c) >= 20:
                m20 = float(np.mean(c[-20:]))
                if len(c) >= 60:
                    m60 = float(np.mean(c[-60:]))
                    if m20 > m60:
                        width += 1
                else:
                    m10 = float(np.mean(c[-10:]))
                    if m10 > m20:
                        width += 1

        bull_min = self.parameters.get("v1_bull_width_min", 8)
        bear_max = self.parameters.get("v1_bear_width_max", 4)

        # v1.3: 记录宽度历史（最近 3 期），用于 BEAR 预警
        self._v1_width_history.append(width)
        if len(self._v1_width_history) > 3:
            self._v1_width_history = self._v1_width_history[-3:]

        # v1.4: BEAR 预警——宽度连续下降时提前降至 15%
        # v1.3→v1.4: 从3期改为2期下降即触发，更敏感
        _width_declining = (
            len(self._v1_width_history) >= 2
            and self._v1_width_history[-1] < self._v1_width_history[-2]
        )

        if ma20 > ma60 and width >= bull_min:
            self._v1_regime = "BULL"
            self._v1_max_position = 1.0
        elif ma20 < ma60 and width < bear_max:
            self._v1_regime = "BEAR"
            self._v1_max_position = 0.0
        elif ma20 < ma60 and _width_declining:
            # 大盘下跌 + 宽度持续萎缩 → 高度预警，降至 15%
            self._v1_regime = "NEUTRAL"
            self._v1_max_position = 0.15
        elif ma20 < ma60:
            self._v1_regime = "NEUTRAL"
            self._v1_max_position = self.parameters.get("v1_neutral_down_max_pos", 0.30)
        else:
            self._v1_regime = "NEUTRAL"
            self._v1_max_position = self.parameters.get("v1_neutral_max_pos", 0.60)

        if self.verbose_logging:
            logger.info(
                f"V1市场状态: {self._v1_regime} "
                f"(width={width}, 仓位上限={self._v1_max_position:.0%})"
            )

    # =========================================================================
    # Layer 1: 动量评分（对数线性回归 × R²）
    # =========================================================================

    def _calc_momentum_rankings(self) -> List[Tuple[str, float]]:
        """
        加权对数线性回归动量（v2.0: 自适应窗口）。

        对每只 ETF：
          1. 取最近 N 天的收盘价（N = 市场状态决定）
          2. 对数变换后用加权线性回归拟合斜率
          3. 年化斜率 × R² 作为最终得分
          4. 尾端跳水（3 日有单日跌 >5%）→ 得分 -8
          5. 极端动量（年化 >5x）→ 排除
          6. 开盘暴跌（-3%）→ 当日不参与排名
        """
        results: List[Tuple[str, float]] = []
        # v2.0: 自适应窗口——BULL追强, NEUTRAL稳健, 防御保守
        if self._v1_max_position >= 0.60:
            days = self.parameters.get("momentum_days_bull", 15)
        elif self._v1_max_position >= 0.30:
            days = self.parameters.get("momentum_days_neutral", 40)
        else:
            days = self.parameters.get("momentum_days_defensive", 60)

        for code in self.etf_pool:
            df = self._data_cache.get(code)
            if df is None or len(df) < days + 1:
                continue

            closes = df["close"].values.astype(np.float64)

            # 开盘暴跌 > 3% → 当日排除
            if "open" in df.columns and len(df) >= 2:
                today_open = float(df["open"].iloc[-1])
                if today_open > 0:
                    day_drop = (closes[-1] - today_open) / today_open
                    if day_drop <= -0.03:
                        continue

            prices = closes[-(days + 1):]
            valid = prices[(prices > 0) & ~np.isnan(prices)]
            if len(valid) < days // 2:
                continue

            try:
                log_prices = np.log(valid)
                n = len(log_prices)
                x = np.arange(n)
                weights = np.linspace(1, 2, n)

                slope, intercept = np.polyfit(x, log_prices, 1, w=weights)
                annualized = float(np.exp(slope * 250) - 1)

                residuals = log_prices - (slope * x + intercept)
                ss_res = float(np.sum(weights * residuals ** 2))
                y_mean = float(np.mean(log_prices))
                ss_tot = float(np.sum(weights * (log_prices - y_mean) ** 2))
                r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

                score = annualized * max(0.0, r2)

                # 尾端跳水
                if len(valid) >= 4:
                    changes = valid[-4:][1:] / valid[-4:][:-1] - 1
                    if np.min(changes) < -0.05:
                        score = -8.0

                results.append((code, score))
            except Exception as _me:
                logger.warning(f"动量计算异常 {code}: {_me}")
                continue

        results.sort(key=lambda x: x[1], reverse=True)

        # 极端动量排除
        max_score = self.parameters.get("momentum_max_score", 5.0)
        results = [(c, s) for c, s in results if s < max_score]

        return results

    # =========================================================================
    # Layer 2: 入场确认
    # =========================================================================

    def _is_volume_abnormal(self, code: str) -> bool:
        """量异常检测：今日量 > N 日均量 × 阈值 → 排除"""
        df = self._data_cache.get(code)
        if df is None or len(df) < 10:
            return False

        days = int(self.parameters.get("volume_check_days", 7))
        threshold = float(self.parameters.get("volume_threshold", 2.0))
        vol = df["volume"].values.astype(np.float64)
        today_vol = vol[-1]
        avg_vol = float(np.mean(vol[-(days + 1):-1]))
        return bool(avg_vol > 0 and today_vol / avg_vol > threshold)

    def _pass_rsrs_filter(self, code: str) -> bool:
        """
        RSRS 阻速线趋势确认。

        - 当日斜率 > Beta → RSRS 正信号
        - 强度 > 0.15 → 直接通过
        - 强度 > 0.03 + 价格 > MA20 → 通过
        """
        df = self._data_cache.get(code)
        if df is None or len(df) < 30:
            return False

        closes = df["close"].values.astype(np.float64)
        highs = (
            df["high"].values.astype(np.float64)
            if "high" in df.columns
            else closes
        )
        lows = (
            df["low"].values.astype(np.float64)
            if "low" in df.columns
            else closes
        )

        # 当日斜率
        rsrs_window = int(self.parameters.get("rsrs_window", 18))
        if len(closes) < rsrs_window:
            return False
        slope = float(np.polyfit(
            lows[-rsrs_window:], highs[-rsrs_window:], 1
        )[0])

        # Beta 计算
        lookback = int(self.parameters.get("rsrs_lookback", 250))
        beta_window = int(self.parameters.get("rsrs_beta_window", 20))
        lookback = min(lookback, len(closes))

        slope_list = []
        for i in range(lookback - beta_window):
            seg_low = lows[i:i + beta_window]
            seg_high = highs[i:i + beta_window]
            if np.std(seg_low) == 0 or np.std(seg_high) == 0:
                continue
            slope_list.append(
                float(np.polyfit(seg_low, seg_high, 1)[0])
            )

        if len(slope_list) < 2:
            return False

        mean_slope = float(np.mean(slope_list))
        std_slope = float(np.std(slope_list))
        beta = mean_slope - 2 * std_slope

        if not (slope > beta):
            return False

        strength = (slope - beta) / abs(beta) if abs(beta) > 0.001 else 0.0

        if strength > self.parameters.get("rsrs_strength_strong", 0.15):
            return True

        above_ma20 = False
        if len(closes) >= 20:
            ma20 = float(np.mean(closes[-20:]))
            above_ma20 = closes[-1] >= ma20

        if strength > self.parameters.get("rsrs_strength_weak", 0.03) and above_ma20:
            return True

        # v1.1: 移除第三层 above_ma20 单独通过，该层过于宽松导致震荡市中
        # 所有 ETF 轮流站上 MA20 → RSRS 大量通过 → 频繁换仓
        return False

    def _frama_efficiency(self, code: str, window: int = 20) -> float:
        """
        v2.1: 分形效率比（FRAMA 核心指标）。

        效率比 = |收盘价位移| / 路径总波动 ∈ [0, 1]
          1.0 = 完美直线趋势（每天都往同一方向走）
          0.0 = 纯震荡（每天涨跌互抵，价格原地踏步）

        效率 > 0.5 → 强趋势
        效率 < 0.25 → 震荡（不宜交易）

        Args:
            code: ETF 代码
            window: 计算窗口（默认 20 天）

        Returns:
            效率比 ∈ [0, 1]
        """
        df = self._data_cache.get(code)
        if df is None or len(df) < window + 2:
            return 0.5  # 数据不足时不过滤

        closes = df["close"].values.astype(np.float64)[-(window + 1):]
        if len(closes) < window + 1 or closes[0] <= 0:
            return 0.5

        direction = abs(closes[-1] - closes[0])
        volatility = float(np.sum(np.abs(np.diff(closes))))
        if volatility <= 0:
            return 1.0

        return min(1.0, direction / volatility)

    def _check_short_term_trend(self, code: str) -> bool:
        """
        v1.3: 短期趋势确认——价格>MA10 且近5日累计收益>0。

        目的：过滤掉短期下跌中的 ETF，避免在回调中入场。
        在震荡市中，即使长期动量排名靠前，短期下跌的 ETF 也不应立即买入。
        """
        df = self._data_cache.get(code)
        if df is None or len(df) < 15:
            return True  # 数据不足时不过滤

        closes = df["close"].values.astype(np.float64)
        if len(closes) < 15:
            return True

        # 价格 > MA10
        if self.parameters.get("entry_min_ma10", True):
            ma10 = float(np.mean(closes[-10:]))
            if closes[-1] < ma10:
                return False

        # 近 5 日累计收益 > 0
        min_ret = self.parameters.get("entry_min_ret_5d", 0.0)
        if min_ret is not None and len(closes) >= 6:
            ret_5d = closes[-1] / closes[-6] - 1
            if ret_5d <= min_ret:
                return False

        return True

    # =========================================================================
    # Layer 5: 出场检查
    # =========================================================================

    def _check_exit(self, etf_code: str) -> Optional[TradingSignal]:
        """
        三条出场规则（OR 关系）：

        规则 0 [硬止损]：累计浮亏超过 stop_loss（-12%）— 不受数据长度限制
        规则 1 [移动止损]：从持仓最高点回撤超过阈值
        规则 2 [趋势断裂]：收盘价 < MA60 × 0.98 — 需 >= 60 天数据
        """
        df = self._data_cache.get(etf_code)
        if df is None or len(df) == 0:
            return None

        close = df["close"].values.astype(float)
        entry_price = self._entry_prices.get(etf_code)
        if entry_price is None or entry_price <= 0:
            return None

        # ---- 规则 0: 硬止损（不受数据长度限制，开仓首日即可触发） ----
        pnl = close[-1] / entry_price - 1
        if pnl < self.stop_loss:
            return self._make_exit_signal(
                etf_code,
                reason=f"硬止损: 浮亏{pnl:.1%}",
                signal_type=SignalType.STOP_LOSS,
            )

        # ---- v2.1: 抛物线止盈（替换固定阈值） ----
        # 参考 stock_low_high_strategy：浮盈越大，允许回撤越小。
        # 好处：+25%时不急着卖（还可以涨），但+80%时非常紧（2%回撤就卖）。
        if self.parameters.get("profit_parabolic", True):
            # 从持仓最高点回撤比例
            high = self._highest_prices.get(etf_code, entry_price)
            dd = (high - close[-1]) / high if high > 0 else 0

            if pnl >= 0.80:
                tp_threshold = 0.02
            elif pnl >= 0.40:
                tp_threshold = 0.04
            elif pnl >= 0.20:
                tp_threshold = 0.06
            elif pnl >= 0.10:
                tp_threshold = 0.08
            else:
                tp_threshold = None

            if tp_threshold is not None and dd >= tp_threshold:
                return self._make_exit_signal(
                    etf_code,
                    reason=f"抛物线止盈: 浮盈{pnl:.1%} 高点{high:.2f}回落{dd:.1%}>{tp_threshold:.0%}",
                    signal_type=SignalType.TAKE_PROFIT,
                )

            # 浮盈超50%且仍未触发抛物线 → 卖半仓锁定
            if pnl >= 0.50:
                sig = self._make_exit_signal(
                    etf_code,
                    reason=f"利润锁定(半仓): 浮盈{pnl:.1%}≥50%",
                    signal_type=SignalType.TAKE_PROFIT,
                )
                sig.half_exit = True
                return sig

        # 规则 1/2 需要 >= 60 天数据计算 MA60
        if len(df) < 60:
            return None

        # ---- 更新最高价（用于规则 1） ----
        high = self._highest_prices.get(etf_code, entry_price)
        if close[-1] > high:
            self._highest_prices[etf_code] = close[-1]

        # ---- 判断大盘下跌趋势 ----
        downtrend = False
        if self._benchmark_cache is not None and len(self._benchmark_cache) >= 60:
            bm_c = self._benchmark_cache["close"].values.astype(float)
            downtrend = float(np.mean(bm_c[-20:])) < float(np.mean(bm_c[-60:]))

        # ---- 规则 1: 移动止损（先于趋势断裂检查） ----
        dd = (self._highest_prices[etf_code] - close[-1]) / self._highest_prices[etf_code]

        if downtrend:
            threshold = self.parameters.get("v1_downtrend_stop_ratio", 0.12)
        else:
            threshold = self.parameters.get("v1_trail_stop_ratio", 0.16)

        if dd > threshold:
            return self._make_exit_signal(
                etf_code,
                reason=(
                    f"移动止损: 从{self._highest_prices[etf_code]:.2f}"
                    f"回撤{dd:.1%}>{threshold:.0%}"
                    + ("(下跌市)" if downtrend else "")
                ),
                signal_type=SignalType.STOP_LOSS,
            )

        # ---- 规则 2: 趋势断裂（价格 < MA60 × 0.98 缓冲） ----
        ma60 = float(np.mean(close[-60:]))
        if close[-1] < ma60 * 0.98:
            return self._make_exit_signal(
                etf_code,
                reason=f"趋势断裂: {close[-1]:.2f} < MA60{ma60:.2f}×0.98",
                signal_type=SignalType.EXIT,
            )

        return None

    # =========================================================================
    # 替换机制
    # =========================================================================

    def _try_replace(
        self,
        rankings: List[Tuple[str, float]],
        signals: List[TradingSignal],
    ) -> None:
        """仓位已满时，尝试用最佳候选替换最差持仓"""
        if not rankings or len(self._current_holdings) == 0:
            return

        # 最佳候选（不在持仓中、不在冷却期）
        best_code = None
        best_score = -float("inf")
        for code, score in rankings[:5]:
            if code in self._current_holdings:
                continue
            if self._cooling_list.get(code, 0) > 0:
                continue
            if self._is_volume_abnormal(code):
                continue
            if not self._pass_rsrs_filter(code):
                continue
            best_code = code
            best_score = score
            break

        if best_code is None:
            return

        # 最差持仓 — 用当期排名中的得分而非 _prev_scores
        # Bug 修复：_prev_scores 是上期数据，新建仓没有得分（= -inf），
        # 导致刚建仓就被替换。改用当期 rankings 查找持仓得分。
        current_scores = {code: score for code, score in rankings}
        min_hold = self.parameters.get("min_hold_days", 10)
        worst_code = None
        worst_score = float("inf")
        for code in self._current_holdings:
            # v1.1: 最低持有天数保护——持有不足 min_hold_days 的不参与替换
            entry_date = self._entry_dates.get(code, "")
            if entry_date and self._last_trade_date:
                try:
                    from datetime import date as _date
                    ed = _date.fromisoformat(entry_date)
                    td = _date.fromisoformat(self._last_trade_date)
                    if (td - ed).days < min_hold:
                        continue
                except (ValueError, TypeError):
                    pass
            sc = current_scores.get(code, None)
            if sc is None:
                # 当期未进入排名的持仓（数据不足）→ 跳过不参与替换比较
                continue
            if sc < worst_score:
                worst_score = sc
                worst_code = code

        if worst_code is None:
            return

        # v1.3: 替换阈值提高——要求 30% 以上相对提升
        min_diff = max(0.15, abs(worst_score) * 0.30)
        if best_score <= worst_score + min_diff:
            return

        # 执行替换
        exit_sig = self._make_exit_signal(
            worst_code,
            reason=f"替换: {best_code}({best_score:.3f}) > {worst_code}({worst_score:.3f})",
        )
        signals.append(exit_sig)

        self._cooling_list[worst_code] = self.cooling_period
        del self._current_holdings[worst_code]
        if worst_code in self._holding_weights:
            del self._holding_weights[worst_code]
        if worst_code in self._entry_prices:
            del self._entry_prices[worst_code]
        if worst_code in self._entry_dates:
            del self._entry_dates[worst_code]
        if worst_code in self._highest_prices:
            del self._highest_prices[worst_code]

        current_price = self._get_price(best_code)
        weight = min(self.max_single_weight, self._v1_max_position - sum(self._holding_weights.values()))
        if weight < 0.05:
            return  # v1.2: 仓位已达上限，不执行替换
        self._current_holdings[best_code] = best_code
        self._holding_weights[best_code] = weight
        self._entry_prices[best_code] = current_price
        self._entry_dates[best_code] = self._last_trade_date
        self._highest_prices[best_code] = current_price

        signals.append(self._make_entry_signal(
            best_code, weight,
            reason=f"替换建仓: {best_code} 替换 {worst_code}",
        ))

        logger.info(
            f"V1替换: {best_code} → 替换 {worst_code}, "
            f"得分差{best_score - worst_score:.3f}"
        )

    # =========================================================================
    # 状态更新
    # =========================================================================

    def _decay_cooling(self) -> None:
        """递减冷却期"""
        for code in list(self._cooling_list.keys()):
            self._cooling_list[code] -= 1
            if self._cooling_list[code] <= 0:
                del self._cooling_list[code]

    # =========================================================================
    # 数据追加
    # =========================================================================

    def _append_data(self, ts_code: str, bar: BarData) -> None:
        """缓存 ETF bar 数据"""
        if ts_code not in self._data_cache:
            self._data_cache[ts_code] = pd.DataFrame(
                columns=["close", "volume", "amount", "open", "high", "low"]
            )

        df = self._data_cache[ts_code]
        new_row = pd.DataFrame([{
            "close": bar.close,
            "volume": bar.volume,
            "amount": bar.amount,
            "open": getattr(bar, "open", bar.close),
            "high": getattr(bar, "high", bar.close),
            "low": getattr(bar, "low", bar.close),
        }])
        self._data_cache[ts_code] = pd.concat([df, new_row], ignore_index=True)

        # 限制缓存大小
        max_rows = self.parameters.get("momentum_days", 25) * 4 + 300
        if len(self._data_cache[ts_code]) > max_rows:
            self._data_cache[ts_code] = (
                self._data_cache[ts_code].tail(max_rows).reset_index(drop=True)
            )

    def _get_price(self, code: str) -> float:
        """获取最新收盘价"""
        df = self._data_cache.get(code)
        if df is not None and len(df) > 0:
            return float(df["close"].iloc[-1])
        return 0.0

    # =========================================================================
    # 信号生成
    # =========================================================================

    def _make_entry_signal(
        self, ts_code: str, weight: float, reason: str = ""
    ) -> Optional[TradingSignal]:
        """生成买入信号"""
        price = self._get_price(ts_code)
        if price <= 0:
            return None

        sig = TradingSignal(
            id=self._gen_id(),
            strategy_id=self.name,
            strategy_name=self.name,
            ts_code=ts_code,
            signal_type=SignalType.ENTRY,
            direction=SignalDirection.LONG,
            price=price,
            quantity=0,
            amount=1.0,
            confidence=0.80,
            reason=f"{ts_code}: {reason}",
            timestamp=datetime.now(),
        )
        sig.weight = weight
        return sig

    def _make_exit_signal(
        self,
        ts_code: str,
        reason: str = "",
        signal_type: SignalType = SignalType.EXIT,
    ) -> TradingSignal:
        """生成卖出信号 — quantity=0 触发全平"""
        price = self._get_price(ts_code)
        return TradingSignal(
            id=self._gen_id(),
            strategy_id=self.name,
            strategy_name=self.name,
            ts_code=ts_code,
            signal_type=signal_type,
            direction=SignalDirection.CLOSE_LONG,
            price=price,
            quantity=0,
            amount=0.0,
            confidence=0.80,
            reason=f"{ts_code}: {reason}",
            timestamp=datetime.now(),
        )

    @staticmethod
    def _gen_id() -> str:
        return str(uuid.uuid4())

    # =========================================================================
    # 参数校验
    # =========================================================================

    def _validate_params(self) -> List[str]:
        """校验策略参数"""
        errors: List[str] = []
        rf = self.rebalance_frequency
        if rf < 1 or rf > 20:
            errors.append(f"rebalance_frequency={rf} 应在 [1, 20]")
        cp = self.cooling_period
        if cp < 0 or cp > 60:
            errors.append(f"cooling_period={cp} 应在 [0, 60]")
        sl = self.stop_loss
        if sl > 0 or sl < -0.30:
            errors.append(f"stop_loss={sl} 应在 [-0.30, 0]")
        return errors

    # =========================================================================
    # 查询接口
    # =========================================================================

    def get_holdings(self) -> List[str]:
        """获取当前持仓 ETF 代码列表"""
        return sorted(self._current_holdings.keys())

    def get_parameters(self) -> dict:
        """获取当前策略参数（用于前端展示）"""
        return {
            "strategy_version": "V1",
            "rebalance_frequency": self.rebalance_frequency,
            "cooling_period": self.cooling_period,
            "min_history": self.min_history,
            "stop_loss": self.stop_loss,
            "etf_pool_size": len(self.etf_pool),
            "max_holdings": self.parameters.get("max_holdings", 3),
            "v1_regime": self._v1_regime,
            "v1_max_position": self._v1_max_position,
            "momentum_days": self.parameters.get("momentum_days", 25),
            "universe_size": len(self._universe) if hasattr(self, "_universe") else 0,
        }
