# -*- coding: utf-8 -*-
from __future__ import annotations

"""
行业轮动策略 V4 — 主线趋势策略

核心变化（2026-07-04 V2 → V4）：
  1. 因子权重：趋势 55% + 资金 30% + 估值 15%（V2 是 25/30/45，错配严重）
  2. 出场逻辑：取消固定止盈 +25%，改为趋势断裂(MA60) + 移动止损 + RS反转
  3. 入场逻辑：三层确认（强度+稳定性+价格位置），不再看排名对比
  4. 市场状态：BULL/NEUTRAL/BEAR 三态分类，替代 V2 的熊市防御
  5. 仓位管理：分批建仓 + 确认加仓 + 动态上限，替代 V2 的永远满仓 5 个
  6. 板块去重：简化，同板块只取 1 个（V2 取 2 个且有替换逻辑）
  7. 冷却期：保留，但出场后天数因缘由 10 天变为 10/20 天（看是否止损）

数据流：
  on_bar(bar) → 分离 ETF bar 和行业指数 bar
    → V2 的每 N 天触发 _rebalance() → 替换为 _run_v4_rebalance()
    → 五层结构：
      Layer 0: 市场状态判定
      Layer 1: 主题评分（复用 IndustryScoringService）
      Layer 2: 入场确认（新三层逻辑）
      Layer 3: 建仓执行（分批买入）
      Layer 4: 持有管理（加仓/移动止损更新）
      Layer 5: 出场检查（趋势断裂+移动止损+RS反转）
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from core.engines.types.entities import BarData
from modules.strategy.constants import StrategyType, SignalDirection, SignalType
from modules.strategy.enums.sector_groups import get_sector
from modules.strategy.models import TradingSignal
from modules.strategy.services.etf_industry_mapper import EtfIndustryMapper, EtfSelection
from modules.strategy.services.industry_scoring_service import (
    IndustryScore,
    IndustryScoringService,
    ScoringConfig,
)
from modules.strategy.strategies.base.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class IndustryRotationStrategy(BaseStrategy):
    """
    申万行业轮动策略 V4 — 主线趋势策略。

    策略类型：ROTATION
    继承 BaseStrategy，遵循 on_bar 驱动模式。

    核心原则：
      - 平时空仓等待，主线确认后集中重仓
      - 让赢家奔跑（不设固定止盈）
      - 市场环境三态分类决定仓位上限
      - 分批建仓 + 确认加仓
    """

    strategy_type: StrategyType = StrategyType.ROTATION

    # =============================================================================
    # 默认参数
    #
    # 策略所有可调节参数集中在此处。前缀 v4_ 的属于 V4 新增参数，
    # 其余为基础参数（调仓频率、冷却期等）。
    # 外部可通过 parameters dict 覆盖任意一项。
    # =============================================================================
    DEFAULT_PARAMS: Dict[str, Any] = {
        # —— 策略基础 ——
        "rebalance_frequency": 5,           # 调仓间隔（交易日数），每 N 天执行一次 _run_v4_rebalance
        "cooling_period": 10,               # 正常出场后的冷却天数，冷却期内同行业禁止再次买入
        "min_history": 20,                  # 预热期要求的最小数据天数，不足则跳过调仓
        "max_sector_limit": 1,              # 同一板块最多选几个行业（设为 1 确保主线不重复）
        "rs_benchmark": "000300.SH",        # 相对强弱计算用的基准指数代码（沪深 300）

        # —— 因子大类权重（三类权重之和必须等于 1.0） ——
        "trend_weight": 0.90,               # IC 测试确认：仅加速度(A2)为正贡献，其余因子为负或接近零
        "volume_weight": 0.10,              # B 因子 IC ≈ -0.02~0，保留极低权重仅作为排序 tiebreaker
        "valuation_weight": 0.00,           # 估值作为硬过滤，不参与评分

        # —— 动量参数 ——
        # A2 动量加速度使用 momentum_windows[0]/[1] 计算 R_short − R_long
        # 默认 [10, 30, 60] → A2 = 10d_ret - 30d_ret（IC = +0.0698 ★）
        "momentum_windows": [10, 30, 60],
        "momentum_weights": [0.40, 0.35, 0.25],
        "momentum_accel_short": 10,
        "momentum_accel_long": 30,
        "rs_window": 30,

        # —— 量价参数 ——
        "vol_ratio_short": 5,               # 量比计算的短期窗口（日均量）
        "vol_ratio_long": 60,               # 量比计算的长期窗口（日均量）
        "vol_price_window": 20,             # 价量配合度计算窗口（日）
        "turnover_short": 5,                # 换手率短期窗口
        "turnover_long": 20,                # 换手率长期窗口

        # —— 估值参数（估值因子降为硬过滤，不再参与评分排序） ——
        "pe_percentile_years": 5,           # PE 历史分位回溯年数
        "pb_percentile_years": 5,           # PB 历史分位回溯年数
        "v4_pe_overheat_threshold": 0.95,   # PE 历史分位 > 95% 时视为过热，禁止入场

        # —— 风控 ——
        "stop_loss": -0.12,                 # 硬止损线（-12%），作为移动止损的最后兜底

        # —— Layer 0: 市场状态（仓位上限） ——
        "v4_neutral_down_max_pos": 0.30,    # NEUTRAL 下跌市总仓位上限（大盘 MA20<MA60 时启用）
        "v4_neutral_max_pos": 0.60,         # NEUTRAL 非下跌市总仓位上限

        # —— Layer 0: 市场状态 ——
        "v4_bull_width_min": 8,             # BULL 判定：至少需要 N 个行业多头排列。原值 12 过高导致 BULL 几乎不可达
        "v4_bear_width_max": 4,             # BEAR 判定：最多允许 N 个行业多头排列。原值 6 过宽

        # —— Layer 2: 入场确认 ——
        "v4_confirm_min_score": 0.45,       # 入场最低综合得分（原0.50，略降低让更多候选进入），0-1
        "v4_confirm_min_trend": 0.35,       # 入场最低趋势得分（原0.40），0-1
        "v4_confirm_max_deviation": 0.20,   # 价格偏离 MA20 的最大允许比例（原0.15），超此值等回踩
        "v4_confirm_stability_days": 10,    # 趋势稳定性回溯天数（原15）

        # —— Layer 3: 建仓 ——
        "v4_batch_1": 0.25,                # 首批建仓仓位（原0.15），总资金的25%
        "v4_batch_1_max": 0.40,            # 置信度加权后首批最多可加到40%
        "v4_batch_2": 0.15,                # 二批加仓仓位（累计至40%）
        "v4_batch_3": 0.15,                # 三批加仓仓位（累计至55%，建仓完成）
        "v4_batch_2_tolerance": 0.03,      # 二批建仓时的价格偏离容忍度：价格在成本 ±3% 内可加

        # —— 主线数量与替换 ——
        "v4_max_holdings": 3,              # 同时持有的最大主线数量（原隐含为2）
        "v4_replace_min_diff": 0.08,       # 替换触发的最小得分差：新候选 > 最差持仓 + 此值

        # —— Layer 4: 趋势加仓 ——
        "v4_add_threshold_1": 0.15,         # 首次趋势加仓阈值：浮盈超过 15% 时确认趋势成立，加仓
        "v4_add_threshold_2": 0.30,         # 二次趋势加仓阈值：浮盈超过 30% 时极度确认，再加仓
        "v4_add_size_1": 0.15,              # 首次加仓量（加至约 60%）
        "v4_add_size_2": 0.10,              # 二次加仓量（加至约 70%，接近上限）
        "v4_position_max": 0.60,            # 单主线绝对仓位上限（总资金的 60%）

        # —— Layer 5: 出场 ——
        "v4_trail_stop_ratio": 0.16,        # 移动止损回撤比例（正常仓位）：从持仓最高点回落 16% 出场
        "v4_heavy_stop_ratio": 0.14,        # 重仓时回撤比例收紧到 14%（仓位 > 50% 时启用）
        "v4_rs_sell_60d": -0.05,           # RS 反转修正阈值（60 日）：跑输 5% 以上收紧 trailing stop
        "v4_rs_sell_20d": -0.03,           # RS 反转修正阈值（20 日）：跑输 3% 以上收紧 trailing stop
        "v4_exit_cooldown_stop": 20,        # 移动止损出场后的冷却天数（比正常出场多一倍）

        # —— 调试 ——
        "factor_override": {},              # 手动覆写因子值 {行业代码: {因子名: 值}}，仅供调试
        "verbose_logging": False,           # 是否输出详细日志（排名、评分明细等）
    }

    # 子因子权重：根据 factor_ic_test 实际 IC 数据调整（2026-07-05）
    #
    # IC 测试结果 (2022-01 ~ 2025-12, 170 个测试日期):
    #   A1 (多窗口动量)  Mean IC = -0.0496  → 负贡献，移除
    #   A2 (加速度)      Mean IC = +0.0698  → 唯一强正因子，主导
    #   A3 (相对强弱)    Mean IC = -0.0615  → 负贡献，移除
    #   B1/B2/B3         Mean IC ≈ -0.02~0 → 几乎无预测力，保留极小权重复核
    #   C1/C2            Mean IC ≈ +0.02   → 弱正，硬过滤即可
    #
    # 策略：趋势只保留加速度(A2)，量价降到极低权重，估值仅做硬过滤。
    SUB_FACTOR_WEIGHTS: Dict[str, Dict[str, float]] = {
        "trend": {"A1": 0.00, "A2": 1.00, "A3": 0.00},
        "volume": {"B1": 0.40, "B2": 0.35, "B3": 0.25},
        "valuation": {"C1": 0.55, "C2": 0.45},
    }

    def __init__(
        self,
        name: str = "主线趋势V4",
        strategy_type: StrategyType = StrategyType.ROTATION,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        # 合并参数
        merged = dict(self.DEFAULT_PARAMS)
        if parameters:
            merged.update(parameters)
        super().__init__(name=name, strategy_type=strategy_type, parameters=merged)

        # ---- 参数提取（保留 V4 需要的，删除 V2 不再使用的） ----
        self.rebalance_frequency: int = int(merged["rebalance_frequency"])
        self.cooling_period: int = int(merged["cooling_period"])
        self.min_history: int = int(merged["min_history"])
        self.max_sector_limit: int = int(merged["max_sector_limit"])
        self.stop_loss: float = float(merged["stop_loss"])
        self.factor_override: Dict = merged.get("factor_override", {}) or {}
        self.verbose_logging: bool = bool(merged.get("verbose_logging", False))

        # ---- 运行时状态（V4 保留） ----
        self._bar_count: int = 0
        self._warmup_warned: bool = False
        self._degraded_warned: bool = False
        self._first_rebalance_logged: bool = False
        self._last_rebalance_date: str = ""
        self._last_trade_date: str = ""        # 最近交易日
        self._current_holdings: Dict[str, str] = {}  # {ETF代码: 行业名}
        self._industry_data_cache: Dict[str, pd.DataFrame] = {}  # {行业代码: DataFrame}
        self._benchmark_cache: Optional[pd.DataFrame] = None     # 基准指数
        self._prev_scores: Dict[str, float] = {}                 # 上期各行业得分
        self._cooling_list: Dict[str, int] = {}                  # {行业名: 剩余冷却天数}
        self._entry_prices: Dict[str, float] = {}                # {ETF代码: 买入价}
        self._data_cache: Dict[str, pd.DataFrame] = {}           # ETF 数据缓存
        self._code_to_industry_name: Dict[str, str] = {}         # {行业代码: 行业名}，加速排名查找

        # ---- V4 运行时状态（新增） ----
        # Layer 0: 市场状态
        self._v4_regime: str = "NEUTRAL"      # BULL / NEUTRAL / BEAR
        self._v4_max_position: float = self.parameters.get("v4_neutral_max_pos", 0.60)  # 当前允许的最大总仓位

        # Layer 1: 主题评分
        self._v4_trend_history: Dict[str, list] = {}  # {行业代码: [近15天趋势得分]}

        # Layer 2: 入场确认
        self._v4_candidates: list = []        # 当前候选主题

        # Layer 3+4: 仓位管理
        self._v4_positions: Dict[str, dict] = {}  # {ETF代码: {
            # "industry": "",              # 行业名
            # "weight": 0.0,              # 总仓位
            # "batches": [(price, qty, date), ...],  # 建仓批次
            # "avg_price": 0.0,           # 加权平均买入价
            # "high_price": 0.0,          # 持仓期间最高价
            # "state": "EMPTY|ENTERING|HOLDING|EXITING"
        # }}

        # ---- 延迟初始化的服务 ----
        self._scoring_service: Optional[IndustryScoringService] = None
        self._etf_mapper: Optional[EtfIndustryMapper] = None
        self._scoring_config: Optional[ScoringConfig] = None

        logger.info(
            f"主线趋势策略V4初始化: {name}, "
            f"rebalance={self.rebalance_frequency}, "
            f"趋势权重={self.parameters.get('trend_weight', 0.55)}"
        )

    # =============================================================================
    # 生命周期
    # =============================================================================

    def on_init(self) -> None:
        """校验参数 + 初始化服务 + 加载 ETF 池"""
        errors = self._validate_params()
        if errors:
            raise ValueError(f"策略参数校验失败: {'; '.join(errors)}")

        # 构建 ScoringConfig（V4 权重）
        cfg = ScoringConfig()
        for key in [
            "trend_weight", "volume_weight", "valuation_weight",
            "momentum_windows", "momentum_weights",
            "momentum_accel_short", "momentum_accel_long",
            "rs_window", "vol_ratio_short", "vol_ratio_long",
            "vol_price_window", "turnover_short", "turnover_long",
            "pe_percentile_years", "pb_percentile_years",
        ]:
            if key in self.parameters:
                setattr(cfg, key, self.parameters[key])

        # 子因子权重
        for cat, weights in self.SUB_FACTOR_WEIGHTS.items():
            for sub, w in weights.items():
                setattr(cfg, f"sub_weight_{sub.lower()}", w)

        sc_errors = cfg.validate()
        if sc_errors:
            raise ValueError(f"ScoringConfig 校验失败: {'; '.join(sc_errors)}")
        self._scoring_config = cfg

        # 初始化服务
        self._scoring_service = IndustryScoringService(cfg)
        self._etf_mapper = EtfIndustryMapper()

        # 设置 universe
        etf_codes = self._etf_mapper.get_all_etf_codes()
        sw_codes = EtfIndustryMapper.get_all_sw_codes()
        self._universe = etf_codes + sw_codes
        rs_bm = self.parameters.get("rs_benchmark", "")
        if rs_bm and rs_bm not in self._universe:
            self._universe.append(rs_bm)

        logger.info(
            f"主线趋势策略V4 初始化完成, "
            f"行业ETF候选={len(self._universe)}只"
        )

    async def on_start(self) -> None:
        """启动策略 — 从 DB 预热历史数据"""
        self._bar_count = 0
        self._last_rebalance_date = ""
        self._current_holdings.clear()
        self._industry_data_cache.clear()
        self._data_cache.clear()
        self._benchmark_cache = None
        self._prev_scores.clear()
        self._cooling_list.clear()
        self._entry_prices.clear()
        self._warmup_warned = False
        self._degraded_warned = False
        self._first_rebalance_logged = False
        # V4 状态重置
        self._v4_regime = "NEUTRAL"
        self._v4_max_position = self.parameters.get("v4_neutral_max_pos", 0.60)
        self._v4_trend_history.clear()
        self._v4_candidates.clear()
        self._v4_positions.clear()

        # 从 DB 加载历史数据预热缓存
        loaded = await self._preload_history()
        if loaded > 0:
            logger.info(
                f"主线趋势策略V4 已启动 — "
                f"历史预热: {len(self._industry_data_cache)} 个行业 / "
                f"{len(self._data_cache)} 只 ETF"
            )
        else:
            logger.info(f"主线趋势策略V4 已启动（等待 bar 累积）")

    async def _preload_history(self) -> int:
        """
        从 DB 加载历史数据预热缓存，返回总行数。

        为什么需要预热：
          策略启动时缓存是空的，需要等 bar 逐日累积才能凑够因子窗口。
          预加载直接把 DB 中最近 N 天的数据一次性装入，启动即就绪。

        加载范围：
          从 end_date 往前推 max_window * 1.2 天（留 20% 余量），
          确保所有动量窗口（最长 120 天）都有数据可用。
          例：最长窗口 120 天，则加载最近 120*1.2+1 ≈ 145 天的数据。
        """
        session_factory = getattr(self, "_db_session_factory", None)
        if session_factory is None:
            return 0

        from datetime import date as _dt, timedelta
        from modules.strategy.engines.data_feed_engine import DataFeedEngine as _DFE

        end_date = _dt.today()
        max_window = max(self.parameters.get("momentum_windows", [20, 60, 120]))
        lookback = int(max_window * 1.2) + 1
        start_date = end_date - timedelta(days=lookback)

        try:
            async with session_factory() as db:
                engine = _DFE(db, adj_type="qfq")

                # 加载 SW 行业指数数据
                sw_symbols = EtfIndustryMapper.get_all_sw_codes()
                sw_df = await engine.load_historical_data(
                    symbols=sw_symbols,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                )
                if not sw_df.empty:
                    for ts_code in sw_df["ts_code"].unique():
                        sub = sw_df[sw_df["ts_code"] == ts_code].copy()
                        sub = sub.sort_values("trade_date").reset_index(drop=True)
                        self._industry_data_cache[ts_code] = sub

                # 加载 ETF 数据
                etf_symbols = self._etf_mapper.get_all_etf_codes()
                etf_df = await engine.load_historical_data(
                    symbols=etf_symbols,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                )
                if not etf_df.empty:
                    for ts_code in etf_df["ts_code"].unique():
                        sub = etf_df[etf_df["ts_code"] == ts_code].copy()
                        sub = sub.sort_values("trade_date").reset_index(drop=True)
                        self._data_cache[ts_code] = sub

                total = len(sw_df) + len(etf_df)
                if total > 0:
                    logger.info(
                        f"历史预热完成: {len(sw_df)} 行 SW + {len(etf_df)} 行 ETF, "
                        f"{start_date} ~ {end_date}"
                    )
                return total

        except Exception as e:
            logger.warning(f"历史预热数据加载失败（非致命，将等待 bar 累积）: {e}")
            return 0

    def on_stop(self) -> None:
        """清理状态"""
        self._current_holdings.clear()
        self._industry_data_cache.clear()
        self._benchmark_cache = None
        self._prev_scores.clear()
        self._cooling_list.clear()
        self._entry_prices.clear()
        self._v4_trend_history.clear()
        self._v4_candidates.clear()
        self._v4_positions.clear()
        logger.info(f"主线趋势策略V4 已停止")

    # =============================================================================
    # 核心入口：on_bar（V4 版）
    # =============================================================================

    def on_bar(self, bar: BarData) -> List[TradingSignal]:
        """
        接收一根 K 线数据。

        两种类型的 bar：
          - ETF bar（.SH/.SZ 结尾）：缓存价格
          - 行业指数 bar（.SI 结尾）：缓存行业数据，用于因子计算

        V4 变化：调仓触发改为调用 _run_v4_rebalance() 而非 _rebalance()
        """
        signals: List[TradingSignal] = []
        ts_code = bar.ts_code

        try:
            is_industry = ts_code.endswith(".SI")

            if is_industry:
                # 行业指数 bar → 缓存
                if ts_code not in self._industry_data_cache:
                    logger.info(
                        f"首次接收行业指数数据: {ts_code}, "
                        f"close={bar.close}, trade_date={getattr(bar, 'trade_date', '?')}"
                    )
                self._append_industry_data(ts_code, bar)

            elif ts_code in self._universe or ts_code == self.parameters.get("rs_benchmark", ""):
                # ETF / 基准 bar → 缓存
                self._append_etf_price(ts_code, bar)
            else:
                return signals

            # 记录最近交易日
            trade_date = getattr(bar, "trade_date", "") or getattr(bar, "datetime", "")
            if isinstance(trade_date, str) and len(trade_date) >= 10:
                trade_date = trade_date[:10]
            self._last_trade_date = trade_date

            # 同一天不重复调仓
            if self._last_rebalance_date and trade_date == self._last_rebalance_date:
                return signals

            self._bar_count += 1

            # V4：调用 _run_v4_rebalance() 替代 _rebalance()
            if self._bar_count % self.rebalance_frequency == 0:
                signals = self._run_v4_rebalance()
                self._last_rebalance_date = trade_date

        except Exception as e:
            logger.error(
                f"主线趋势策略V4 on_bar 异常: {ts_code}: {e}", exc_info=True
            )

        return signals

    # =============================================================================
    # V4 主调仓方法：_run_v4_rebalance（替代 V2 的 _rebalance）
    #
    # 五层结构：
    #   Layer 0: 市场状态判定（三态分类决定仓位上限）
    #   Layer 5: 出场检查（先处理已有持仓）
    #   Layer 4: 加仓检查
    #   Layer 1: 主题评分（动量55%+资金30%+估值15%）
    #   Layer 2: 入场确认（三层筛选）
    #   Layer 3: 建仓执行（分批买入）
    # =============================================================================

    def _run_v4_rebalance(self) -> List[TradingSignal]:
        """
        V4 主调仓方法，替代 V2 的 _rebalance()。

        流程：
          1. 预热期检查（与 V2 相同）
          2. Layer 0: 市场状态检测
          3. Layer 5: 出场检查（先处理已有持仓，腾出空间）
          4. Layer 4: 加仓检查
          5. Layer 1: 主题评分
          6. Layer 2: 入场确认
          7. Layer 3: 建仓执行
          8. 更新状态（冷却期递减、得分记录）
        """
        signals: List[TradingSignal] = []

        if not self._scoring_service or self._industry_data_cache is None:
            return signals

        # ---- 预热期检查（与 V2 相同） ----
        windows = self.parameters.get("momentum_windows", [20, 60, 120])
        max_window = max(windows)
        min_window = min(windows)
        effective_min = max(self.min_history, min_window + 1)
        max_cache_days = max(
            (len(df) for df in self._industry_data_cache.values()), default=0
        )
        if max_cache_days < effective_min:
            if not self._warmup_warned:
                logger.info(
                    f"主线趋势策略V4: 预热期 — "
                    f"当前最多 {max_cache_days} 天数据, "
                    f"需要 {effective_min} 天, 跳过调仓"
                )
                self._warmup_warned = True
            return signals

        if not self._degraded_warned and max_cache_days < max_window + 1:
            available = [w for w in windows if max_cache_days >= w + 1]
            logger.warning(
                f"主线趋势策略V4: 因子降级运行 — "
                f"数据 {max_cache_days} 天, 可用窗口={available}"
            )
            self._degraded_warned = True

        # 同步基准数据
        rs_bm = self.parameters.get("rs_benchmark", "")
        if rs_bm and rs_bm in self._data_cache:
            self._benchmark_cache = self._data_cache[rs_bm]

        # P0-1：追踪本轮已卖出的 ETF，防止同一天卖出后又买入（订单验证失败）
        self._exited_etfs_this_round: Set[str] = set()

        # ===== Layer 0: 市场状态判定 =====
        self._detect_market_state()

        # ===== Layer 5 + 4: 处理已有持仓 =====
        for etf_code in list(self._current_holdings.keys()):
            industry_name = self._current_holdings[etf_code]

            # ---- Layer 5: 出场检查 ----
            exit_signal = self._check_v4_exit(etf_code)
            if exit_signal:
                logger.info(f"V4出场: {industry_name} — {exit_signal.reason}")
                signals.append(exit_signal)
                # P0-1：记录已卖出的 ETF，防止同一天再买入同一只
                self._exited_etfs_this_round.add(etf_code)
                # 清理状态
                if etf_code in self._current_holdings:
                    ind_name = self._current_holdings[etf_code]
                    # 止损出场冷却 20 天，正常出场 10 天
                    if exit_signal.signal_type == SignalType.STOP_LOSS:
                        self._cooling_list[ind_name] = self.parameters.get(
                            "v4_exit_cooldown_stop", 20
                        )
                    else:
                        self._cooling_list[ind_name] = self.cooling_period
                    del self._current_holdings[etf_code]
                if etf_code in self._entry_prices:
                    del self._entry_prices[etf_code]
                if etf_code in self._v4_positions:
                    del self._v4_positions[etf_code]
                continue

            # ---- Layer 4: 加仓检查 ----
            pos = self._v4_positions.get(etf_code)
            if pos and pos["state"] == "HOLDING":
                df = self._data_cache.get(etf_code)
                if df is not None and len(df) > 0:
                    current_price = float(df["close"].iloc[-1])
                    rank = self._get_v4_rank(etf_code)
                    add_signal = self._check_v4_add(etf_code, current_price, rank)
                    if add_signal:
                        signals.append(add_signal)

        # ===== Layer 1 + 2 + 3: 新入场 =====
        # BEAR 状态不建新仓
        if self._v4_regime == "BEAR":
            if self.verbose_logging:
                logger.debug("V4: BEAR 状态，不建新仓")
            self._update_prev_scores()
            self._decay_cooling()
            return signals

        # 计算当前仓位状态（不再提前 return，因为需要评分用于替换判断）
        _cur_weight = sum(pos.get("weight", 0.0) for pos in self._v4_positions.values())
        _remaining = self._v4_max_position - _cur_weight
        v4_max_h = int(self.parameters.get("v4_max_holdings", 3))
        _has_room = (_remaining >= 0.01) and (len(self._current_holdings) < v4_max_h)

        if self.verbose_logging:
            logger.debug(
                f"V4仓位: weight={_cur_weight:.0%} max={self._v4_max_position:.0%} "
                f"count={len(self._current_holdings)}/{v4_max_h} "
                f"has_room={_has_room}"
            )

        # ---- Layer 1: 主题评分 ----
        industry_scores = self._score_industries_v4()
        if not industry_scores:
            self._update_prev_scores()
            self._decay_cooling()
            return signals

        # ---- Layer 2: 入场确认 ----
        confirmed = []
        for score in industry_scores[:5]:  # 只看前 5 个候选
            df = self._industry_data_cache.get(score.industry_code)
            if df is None:
                continue
            ok, reason = self._confirm_entry(score, df)
            if ok:
                confirmed.append(score)
            elif self.verbose_logging:
                logger.debug(f"V4入场未通过: {score.industry_name} — {reason}")

        if not confirmed:
            self._update_prev_scores()
            self._decay_cooling()
            return signals

        # ---- 下跌市强过滤 ----
        bm_trend_down = False
        if self._benchmark_cache is not None and len(self._benchmark_cache) >= 20:
            bm_c = self._benchmark_cache["close"].values.astype(float)
            bm_trend_down = float(np.mean(bm_c[-20:])) < float(np.mean(bm_c[-60:])) if len(bm_c) >= 60 else False

        if bm_trend_down:
            filtered_confirmed = []
            for s in confirmed:
                df = self._industry_data_cache.get(s.industry_code)
                if df is None or len(df) < 61:
                    continue
                c = df["close"].values.astype(float)
                bm = self._benchmark_cache
                if bm is None or len(bm) < 61:
                    continue
                mkt = bm["close"].values.astype(float)
                rs_60d = (c[-1] / c[-61] - 1) - (mkt[-1] / mkt[-61] - 1)
                amount = df["amount"].values.astype(float) if "amount" in df.columns else df["vol"].values.astype(float) * c
                vol_20 = float(np.mean(amount[-20:]))
                vol_60 = float(np.mean(amount[-60:])) if len(amount) >= 60 else vol_20
                vol_ratio = vol_20 / max(vol_60, 1)
                if rs_60d > 0.05 and vol_ratio > 1.2 and s.trend_score > 0.5:
                    filtered_confirmed.append(s)
                elif self.verbose_logging:
                    logger.debug(f"  [下跌市过滤] {s.industry_name}: RS60={rs_60d:.2%} 量比={vol_ratio:.2f} 趋势={s.trend_score:.4f} — 不满足条件")
            confirmed = filtered_confirmed
            if not confirmed:
                if self.verbose_logging:
                    logger.debug("V4: 下跌市中无行业通过强过滤，自动空仓")
                self._update_prev_scores()
                self._decay_cooling()
                return signals

        # 唯一筛选（板块去重 + ETF 去重）
        used_etfs = set(self._current_holdings.keys())
        selected = self._select_unique_themes(confirmed, used_etfs)
        if not selected:
            self._update_prev_scores()
            self._decay_cooling()
            return signals

        # ---- Layer 3: 建仓 / 替换 ----
        if _has_room:
            # --- 有空间 → 直接建仓（置信度加权） ---
            for sel in selected:
                etf_code = sel["etf_code"]
                if not etf_code or etf_code in self._current_holdings:
                    continue
                if etf_code in self._exited_etfs_this_round:
                    if self.verbose_logging:
                        logger.debug(f"  [跳过] {sel['industry_name']}({etf_code}) 本轮已卖出，不再买入")
                    continue

                cooling_left = self._cooling_list.get(sel["industry_name"], 0)
                if cooling_left > 0:
                    logger.debug(f"冷却期: {sel['industry_name']} 剩余 {cooling_left} 天")
                    continue

                df = self._data_cache.get(etf_code)
                if df is None or len(df) == 0:
                    continue

                current_price = float(df["close"].iloc[-1])
                # 置信度加权首批仓位（得分越高仓位越重）
                batch_size = self._calc_confidence_weight(
                    next(s for s in confirmed if s.industry_code == sel["industry_code"])
                )

                self._current_holdings[etf_code] = sel["industry_name"]
                self._entry_prices[etf_code] = current_price
                self._v4_positions[etf_code] = {
                    "industry": sel["industry_name"],
                    "weight": batch_size,
                    "batches": [(current_price, batch_size, self._last_trade_date)],
                    "avg_price": current_price,
                    "high_price": current_price,
                    "state": "ENTERING",
                }

                signals.append(self._make_entry_signal_v4(
                    etf_code=etf_code,
                    industry_name=sel["industry_name"],
                    weight=batch_size,
                    reason=f"建仓: {sel['industry_name']} 排名#{sel['rank']} 置信度{batch_size:.0%}",
                ))

                logger.info(
                    f"V4建仓: {sel['industry_name']} → {etf_code}, "
                    f"仓位{batch_size:.0%}, 价格{current_price:.2f}"
                )

                if len(self._current_holdings) >= v4_max_h:
                    break
        else:
            # --- 仓位已满 → 尝试替换最差持仓 ---
            replaced_any = self._try_replace_holdings(confirmed, selected, signals)
            if not replaced_any and self.verbose_logging:
                logger.debug("V4: 仓位满且无合适的替换目标")

        # ---- 更新状态 ----
        self._update_prev_scores()
        self._decay_cooling()

        if signals and self.verbose_logging:
            logger.info(
                f"V4调仓信号数={len(signals)}, "
                f"持仓={sorted(self._current_holdings.keys())}"
            )

        return signals

    # =============================================================================
    # Layer 0: 市场状态判定
    # =============================================================================

    def _detect_market_state(self) -> None:
        """
        V4 Layer 0: 市场状态三分类。

        替代 V2 的 _check_market_regime() + _detect_regime()。

        两个维度：
          - 趋势方向：基准指数 MA20 vs MA60
          - 行业宽度：31 个行业中有多少个 MA20 > MA60

        输出：
          BULL   → 仓位上限 100%（允许满仓）
          NEUTRAL → 仓位上限 30%（谨慎试探）
          BEAR   → 仓位上限 0%（空仓防御）
        """
        bm = self._benchmark_cache
        if bm is None or len(bm) < 20:
            self._v4_regime = "NEUTRAL"
            self._v4_max_position = self.parameters.get("v4_neutral_max_pos", 0.60)
            return

        bm_close = bm["close"].values.astype(float)
        ma20 = float(np.mean(bm_close[-20:]))
        ma60 = float(np.mean(bm_close[-60:])) if len(bm_close) >= 60 else ma20

        # 行业宽度：31 个行业中有多少个处于短期多头排列
        width = 0
        for code, df in self._industry_data_cache.items():
            c = df["close"].values.astype(float)
            if len(c) >= 20:
                m20 = float(np.mean(c[-20:]))
                # 修复：数据不足 60 天时，用 MA10 > MA20 近似判断短期趋势方向
                # 原逻辑 m60 = m20 导致 m20 > m60 永远为 False，width 恒为 0
                if len(c) >= 60:
                    m60 = float(np.mean(c[-60:]))
                    if m20 > m60:
                        width += 1
                else:
                    m10 = float(np.mean(c[-10:]))
                    if m10 > m20:
                        width += 1

        bull_min = self.parameters.get("v4_bull_width_min", 12)
        bear_max = self.parameters.get("v4_bear_width_max", 6)

        if ma20 > ma60 and width >= bull_min:
            self._v4_regime = "BULL"
            self._v4_max_position = 1.0
            if self.verbose_logging:
                logger.info(f"V4市场状态: BULL (width={width}, MA20>{ma60:.0f})")
        elif ma20 < ma60 and width < bear_max:
            self._v4_regime = "BEAR"
            self._v4_max_position = 0.0
            if self.verbose_logging:
                logger.info(f"V4市场状态: BEAR (width={width}, MA20<{ma60:.0f})")
        elif ma20 < ma60:
            # 大盘在下跌趋势中，即使行业宽度尚可，也限制仓位
            self._v4_regime = "NEUTRAL"
            # 下跌市中的 NEUTRAL 仓位上限（防止在下跌市中过度买入）
            self._v4_max_position = self.parameters.get("v4_neutral_down_max_pos", 0.30)
            if self.verbose_logging:
                logger.info(f"V4市场状态: NEUTRAL-DOWN (width={width}, 仓位上限={self._v4_max_position:.0%}, MA20<{ma60:.0f})")
        else:
            self._v4_regime = "NEUTRAL"
            self._v4_max_position = self.parameters.get("v4_neutral_max_pos", 0.60)
            if self.verbose_logging:
                logger.info(f"V4市场状态: NEUTRAL (width={width}, 仓位上限={self._v4_max_position:.0%})")

    # =============================================================================
    # Layer 1: 主题评分
    # =============================================================================

    def _score_industries_v4(self) -> List[IndustryScore]:
        """
        V4 Layer 1: 主题评分。

        使用 V4 权重（动量55%+资金30%+估值15%）对 31 行业评分。
        动量 < 0.3 的行业直接排除（不在上升趋势中的不可能成为主线）。

        记录趋势得分历史供 Layer 2 使用。
        """
        if not self._scoring_service:
            return []

        try:
            scores = self._scoring_service.score_all(
                industry_data=self._industry_data_cache,
                benchmark_prices=self._benchmark_cache,
                prev_scores=self._prev_scores,
                factor_override=self.factor_override,
            )
        except Exception as e:
            logger.error(f"V4 评分异常: {e}")
            return []

        # 动量 < 0.3 排除（V4 核心过滤）
        filtered = [s for s in scores if s.trend_score >= 0.3]

        # 更新行业代码→名称映射（用于 _get_v4_rank 加速）
        for s in scores:
            self._code_to_industry_name[s.industry_code] = s.industry_name

        # 保存候选供 _get_v4_rank 查询排名（修复：从未填充导致加仓永不触发）
        self._v4_candidates = [
            (s.industry_code, s.industry_name, s.composite_score, i + 1)
            for i, s in enumerate(filtered)
        ]

        # 记录趋势得分历史
        for s in filtered:
            code = s.industry_code
            if code not in self._v4_trend_history:
                self._v4_trend_history[code] = []
            self._v4_trend_history[code].append(s.trend_score)
            max_history = self.parameters.get("v4_confirm_stability_days", 15)
            if len(self._v4_trend_history[code]) > max_history:
                self._v4_trend_history[code] = self._v4_trend_history[code][-max_history:]

        # 首次调仓输出诊断
        if not self._first_rebalance_logged and filtered:
            self._first_rebalance_logged = True
            top3 = filtered[:3]
            logger.info(
                f"V4首次调仓诊断: "
                f"行业={len(filtered)}个, "
                f"Top3: " + ", ".join(
                    f"{s.industry_name}(趋势={s.trend_score:.4f}, 综合={s.composite_score:.4f})"
                    for s in top3
                )
            )
            logger.info(
                f"V4市场状态: {self._v4_regime}, "
                f"仓位上限={self._v4_max_position:.0%}"
            )

        # verbose_logging 时输出 Top 10 因子明细（调试用）
        if self.verbose_logging and filtered:
            lines = [f"\n{'='*60}", "V4因子明细 — Top 10"]
            for i, s in enumerate(filtered[:10]):
                f = s.factors
                lines.append(
                    f"  #{i+1:2d} {s.industry_name:8s} "
                    f"综合={s.composite_score:.4f} "
                    f"趋势={s.trend_score:.4f} "
                    f"量价={s.volume_score:.4f} "
                    f"估值={s.valuation_score:.4f} | "
                    f"R20={f.get('A1',0):+.3f} "
                    f"RS60={f.get('A3',0):+.3f} "
                    f"量比={f.get('B1',0):.2f} "
                    f"价量={f.get('B2',0):+.2f} "
                    f"PE分位={f.get('C1',0):.2f} "
                    f"RSI={s.rsi:.0f}"
                )
            lines.append(f"{'='*60}")
            logger.info("\n".join(lines))

        return filtered

    # =============================================================================
    # Layer 2: 入场确认（三层筛选）
    # =============================================================================

    def _confirm_entry(self, score: IndustryScore, industry_df: pd.DataFrame) -> Tuple[bool, str]:
        """
        V4 Layer 2: 三层入场确认。

        替代 V2 的 _check_entry_conditions()。

        第一关：强度确认
          - 综合得分 >= 0.5
          - 趋势动量 >= 0.4

        第二关：趋势稳定性
          - 近 15 天趋势得分不能持续下降（防止一日脉冲）

        第三关：价格位置
          - 距离 MA20 偏离不超过 15%（防止追高）
          - V 形反转豁免：10 天前还在 MA20 下方，现在已突破

        Returns:
            (是否通过, 原因描述)
        """
        cfg = self.parameters

        # ---- 第一关：强度 ----
        min_score = cfg.get("v4_confirm_min_score", 0.5)
        min_trend = cfg.get("v4_confirm_min_trend", 0.4)

        if score.composite_score < min_score:
            return False, f"综合得分{score.composite_score:.4f}<{min_score}"
        if score.trend_score < min_trend:
            return False, f"趋势得分{score.trend_score:.4f}<{min_trend}"

        # ---- 估值硬过滤（替代估值大类权重）----
        # 估值不再参与排名打分（valuation_weight=0），而是作为一票否决制硬过滤：
        # PE 历史分位 > 95% → 过热预警，禁止入场
        if "pe" in industry_df.columns and industry_df["pe"].notna().any():
            pe_arr = industry_df["pe"].dropna().values.astype(float)
            pe_arr = pe_arr[pe_arr > 0]
            if len(pe_arr) >= 20:
                current_pe = pe_arr[-1]
                pe_pctile = float(np.mean(pe_arr <= current_pe))
                overheat = cfg.get("v4_pe_overheat_threshold", 0.95)
                if pe_pctile > overheat:
                    return False, f"PE分位{pe_pctile:.0%}>{overheat:.0%}，过热不追高"

        # ---- 第二关：趋势稳定性 ----
        code = score.industry_code
        history = self._v4_trend_history.get(code, [])
        if len(history) >= 4:
            # 最近 4 次趋势得分整体不能下降（简单检查：最近一次 > 最早一次）
            if history[-1] < history[-4]:
                # 允许适度波动，但不允许持续下降
                if history[-1] < history[-2] < history[-3]:
                    return False, "趋势得分连续下降，暂缓入场"

        # ---- 第三关：价格位置 + RSI 检查 ----
        close = industry_df["close"].values.astype(float)
        ma20 = float(np.mean(close[-20:]))
        if ma20 <= 0:
            return False, "MA20 异常（数据异常）"
        upside = close[-1] / ma20 - 1

        # RSI < 70 防止追高（P0-3：日志显示 RSI>70 入场全部亏损）
        if score.rsi >= 70:
            return False, f"RSI={score.rsi:.0f} >= 70，过热不追高"

        max_dev = cfg.get("v4_confirm_max_deviation", 0.15)
        if upside <= max_dev:
            return True, f"偏离MA20={upside:.1%} RSI={score.rsi:.0f}"

        # V 形反转豁免：价格刚从 MA20 下方突破（10 日前价格明显低于当前 MA20）
        # 真正的 V 形反转 = 10 天前价格还在 MA20 之下，现在已突破且站稳
        if len(close) >= 15 and upside <= 0.25:
            price_10d = close[-11]                     # 10 个交易日前（-1 是当天）
            if price_10d < ma20 * 0.98:                # 10 日前价格 < MA20 的 98%
                return True, f"V形反转豁免: 偏离MA20={upside:.1%} 10日前{price_10d:.2f}<MA20{ma20:.2f}*0.98"

        return False, f"偏离MA20 {upside:.1%}>{max_dev:.0%}，等回踩 RSI={score.rsi:.0f}"

    def _calc_confidence_weight(self, score: IndustryScore) -> float:
        """
        基于综合得分计算动态首批仓位权重（置信度加权）。

        规则：
          - 基础仓位：v4_batch_1（默认 25%）
          - 得分加成：综合得分每高于最低门槛 0.10，加 5% 仓位
          - 趋势加成：趋势得分每高于最低门槛 0.10，加 2.5% 仓位
          - 上限：v4_batch_1_max（默认 40%）

        Example:
            得分 = 0.85，趋势=0.80 → base=0.25 + (0.85-0.45)*0.10/0.10*0.05 + (0.80-0.35)*0.10/0.10*0.025
                                = 0.25 + 0.40/0.10*0.05 + 0.45/0.10*0.025
                                = 0.25 + 0.20 + 0.1125
                                = 0.36 → cap at 0.40
        """
        cfg = self.parameters
        base = float(cfg.get("v4_batch_1", 0.25))
        min_score = float(cfg.get("v4_confirm_min_score", 0.45))
        min_trend = float(cfg.get("v4_confirm_min_trend", 0.35))

        # 超过最低门槛的部分按比例加成
        score_bonus = max(0.0, score.composite_score - min_score) * 0.50  # 每超 0.1 加 5pp
        trend_bonus = max(0.0, score.trend_score - min_trend) * 0.25     # 每超 0.1 加 2.5pp
        cap = float(cfg.get("v4_batch_1_max", 0.40))

        weight = min(base + score_bonus + trend_bonus, cap)
        return round(weight, 2)

    def _select_unique_themes(self, confirmed_scores: List[IndustryScore], used_etfs: Set[str]) -> list:
        """
        V4 候选唯一筛选。

        替代 V2 的 _apply_sector_dedup() + EtfIndustryMapper.resolve()。

        规则（简化版）：
          - 同板块只取 1 个（V2 取 2 个且有替换逻辑，V4 精简）
          - 同 ETF 只取 1 个（通过 ETF-行业映射去重）
          - 最多保留 2 个（V4 集中原则：不分散）

        Args:
            confirmed_scores: 通过入场确认的行业评分列表（按得分降序）
            used_etfs: 当前已持有的 ETF 代码集合【V5 后续支持个股时扩展】

        Returns:
            [{"industry_code", "industry_name", "etf_code", "rank"}, ...]
        """
        selected = []
        used_sectors = set()

        for score in confirmed_scores:
            sector = get_sector(score.industry_name)
            if sector in used_sectors:
                continue

            # 找对应 ETF（先查 primary，再查 secondary）
            etf_codes = self._etf_mapper.get_industry_etf_candidates(score.industry_name)
            mapped_etf = None
            for etf in etf_codes:
                if etf not in used_etfs:
                    mapped_etf = etf
                    break

            if mapped_etf is None:
                continue  # 无可用的 ETF，跳过该行业

            selected.append({
                "industry_code": score.industry_code,
                "industry_name": score.industry_name,
                "etf_code": mapped_etf,
                "rank": len(selected) + 1,
            })
            used_sectors.add(sector)
            used_etfs.add(mapped_etf)

            # 最多选 N 个主线（由 v4_max_holdings 控制）
            v4_max = self.parameters.get("v4_max_holdings", 3)
            if len(selected) >= v4_max:
                break

        return selected

    # =============================================================================
    # Layer 3: 建仓执行（已整合在 _run_v4_rebalance 中）
    # =============================================================================

    # 建仓逻辑直接在 _run_v4_rebalance 的 Layer 3 部分实现，
    # 首次建仓使用参数 v4_batch_1（15%）。
    # 后续批次由 _check_v4_add 中的加仓逻辑接管。
    # 设计上分批买入（15%→30%→45%）的完整链路见 _check_v4_add。

    # =============================================================================
    # Layer 4: 持有管理（加仓）
    # =============================================================================

    def _check_v4_add(self, etf_code: str, current_price: float, rank: int) -> Optional[TradingSignal]:
        """
        V4 Layer 4: 加仓规则。

        在趋势已被确认后，扩大仓位以放大收益。
        V2 没有加仓逻辑，这是 V4 新增。

        条件（必须同时满足）：
          1. 仓位状态为 HOLDING（已完成建仓 3 批）
          2. 当前仓位 <= 60%（留安全边际）
          3. 浮盈 > 阈值（15% 或 30%）
          4. 排名仍在前 3（不是昙花一现）

        加仓幅度：
          - 浮盈 > 15% 且排名前 3 → 加 15%（仓位到约 60%）
          - 浮盈 > 30% 且排名前 3 → 再加 10%（仓位到上限 70%）
        """
        pos = self._v4_positions.get(etf_code)
        if not pos or pos["state"] in ("EMPTY", "EXITING"):
            if self.verbose_logging:
                logger.debug(f"  [加仓跳过] {etf_code}: state={pos['state'] if pos else 'NO_POS'}")
            return None

        pnl = current_price / pos["avg_price"] - 1
        industry_name = self._current_holdings.get(etf_code, "")

        # 每次进入时打印当前状态（调试用）
        if self.verbose_logging:
            n_batches = len(pos["batches"])
            logger.debug(
                f"  [加仓检查] {industry_name}: "
                f"state={pos['state']} batches={n_batches} "
                f"weight={pos['weight']:.0%} "
                f"pnl={pnl:.1%} "
                f"rank=#{rank}"
            )

        # ---- 首批建仓后的持续加仓（state=ENTERING 时也允许） ----
        # 总仓位上限
        max_pos = self.parameters.get("v4_position_max", 0.60)
        if pos["weight"] >= max_pos:
            return None

        # ================ 二批建仓（单批 → 两批） ================
        # 原逻辑：pnl ∈ [-3%, +8%]才加，≥+8%直接跳过导致死锁。
        # 修复：所有 pnl ≥ -6% 的路径都有明确出口。
        if len(pos["batches"]) == 1 and pos["state"] == "ENTERING":
            if pnl < -0.06:
                return self._exit_during_build(etf_code, industry_name, pnl)

            # pnl ≥ -6% → 加仓二批。原 pnl < 0.08 的上限去掉，
            # 避免"趋势强者反而被拒绝加仓"的死锁。
            add_sz2 = self.parameters.get("v4_batch_2", 0.15)
            pos["weight"] += add_sz2
            pos["batches"].append((current_price, add_sz2, self._last_trade_date))
            pos["avg_price"] = self._calc_v4_avg_price(pos["batches"])
            pos["high_price"] = max(pos["high_price"], current_price)

            # 浮盈 ≥ 5% → 趋势已确认，直接进入 HOLDING（跳过三批建仓）
            if pnl >= 0.05:
                pos["state"] = "HOLDING"
                logger.info(
                    f"V4二批建仓+HOLDING: {industry_name} +{add_sz2:.0%}, "
                    f"仓位{pos['weight']:.0%}, 浮盈{pnl:.1%}"
                )
            else:
                logger.info(
                    f"V4二批建仓: {industry_name} +{add_sz2:.0%}, "
                    f"仓位{pos['weight']:.0%}, 浮盈{pnl:.1%}"
                )

            return self._make_entry_signal_v4(
                etf_code, industry_name, add_sz2,
                reason=f"二批建仓: 浮盈{pnl:.1%} 排名#{rank}",
            )

        # ================ 三批建仓（两批 → 三批） ================
        # 原逻辑：pnl < 5% 时 fall-through 导致 state 无法过渡到 HOLDING。
        # 修复：pnl ∈ [-8%, +5%] 时虽不加三批，但推进到 HOLDING 状态。
        if len(pos["batches"]) == 2 and pos["state"] == "ENTERING":
            if pnl < -0.08:
                return self._exit_during_build(etf_code, industry_name, pnl)

            if pnl > 0.05:
                add_sz3 = self.parameters.get("v4_batch_3", 0.15)
                pos["weight"] += add_sz3
                pos["batches"].append((current_price, add_sz3, self._last_trade_date))
                pos["avg_price"] = self._calc_v4_avg_price(pos["batches"])
                pos["high_price"] = max(pos["high_price"], current_price)
                pos["state"] = "HOLDING"
                logger.info(
                    f"V4三批建仓完成: {industry_name} +{add_sz3:.0%}, "
                    f"仓位{pos['weight']:.0%}, 浮盈{pnl:.1%}"
                )
                return self._make_entry_signal_v4(
                    etf_code, industry_name, add_sz3,
                    reason=f"三批建仓完成: 浮盈{pnl:.1%} 排名#{rank}",
                )

            # pnl ≥ -8% 但 < +5%：趋势尚可但不满足三批条件，
            # 进入 HOLDING 让后续趋势加仓接管（避免死锁）。
            pos["state"] = "HOLDING"
            pos["high_price"] = max(pos["high_price"], current_price)
            logger.info(
                f"V4跳过三批 {(industry_name)}: 仓位{pos['weight']:.0%}, "
                f"浮盈{pnl:.1%}, 直接进入HOLDING"
            )
            return None

        # ---- HOLDING 状态的趋势加仓（浮盈>15%或>30%时加）----
        if pos["state"] == "HOLDING":
            # 浮盈 > 30%（超级确认），再加仓
            if pnl > self.parameters.get("v4_add_threshold_2", 0.30) and rank <= 3:
                add_sz = self.parameters.get("v4_add_size_2", 0.10)
                actual_add = min(add_sz, max_pos - pos["weight"])
                if actual_add > 0:
                    pos["weight"] += actual_add
                    pos["batches"].append((current_price, actual_add, self._last_trade_date))
                    pos["avg_price"] = self._calc_v4_avg_price(pos["batches"])
                    logger.info(
                        f"V4加仓(30%+): {industry_name} +{actual_add:.0%}, "
                        f"仓位{pos['weight']:.0%}, 浮盈{pnl:.1%}"
                    )
                    return self._make_entry_signal_v4(
                        etf_code, industry_name, actual_add,
                        reason=f"加仓(30%+确认): 浮盈{pnl:.1%} 排名#{rank}",
                    )
                elif self.verbose_logging:
                    logger.debug(f"  [加仓跳过] {industry_name}: pnl>30% 但仓位已达上限={max_pos:.0%}")
            elif self.verbose_logging:
                logger.debug(f"  [加仓跳过] {industry_name}: pnl>30% 但排名#{rank}>3")

            # 浮盈 > 15%（趋势确认），加仓
            if pnl > self.parameters.get("v4_add_threshold_1", 0.15) and rank <= 3:
                add_sz = self.parameters.get("v4_add_size_1", 0.15)
                actual_add = min(add_sz, max_pos - pos["weight"])
                if actual_add > 0:
                    pos["weight"] += actual_add
                    pos["batches"].append((current_price, actual_add, self._last_trade_date))
                    pos["avg_price"] = self._calc_v4_avg_price(pos["batches"])
                    logger.info(
                        f"V4加仓(趋势确认): {industry_name} +{actual_add:.0%}, "
                        f"仓位{pos['weight']:.0%}, 浮盈{pnl:.1%}"
                    )
                    return self._make_entry_signal_v4(
                        etf_code, industry_name, actual_add,
                        reason=f"加仓(趋势确认): 浮盈{pnl:.1%} 排名#{rank}",
                    )
            elif self.verbose_logging and rank > 3:
                logger.debug(f"  [加仓跳过] {industry_name}: pnl={pnl:.1%} 但排#{rank}>3")
            elif self.verbose_logging and pnl <= self.parameters.get("v4_add_threshold_1", 0.15):
                logger.debug(f"  [加仓跳过] {industry_name}: 盈{pnl:.1%}<{self.parameters.get('v4_add_threshold_1', 0.15):.0%} 或排#{rank}>3")

        return None

    def _exit_during_build(self, etf_code: str, industry_name: str, pnl: float) -> Optional[TradingSignal]:
        """建仓期间跌幅过大，提前止损退出"""
        self._cooling_list[industry_name] = self.parameters.get("v4_exit_cooldown_stop", 20)
        if etf_code in self._current_holdings:
            del self._current_holdings[etf_code]
        if etf_code in self._entry_prices:
            del self._entry_prices[etf_code]
        if etf_code in self._v4_positions:
            del self._v4_positions[etf_code]
        logger.warning(f"V4建仓期止损: {industry_name}, 亏损{pnl:.1%}")
        return self._make_exit_signal(
            etf_code, industry_name=industry_name,
            reason=f"建仓期止损: 亏损{pnl:.1%}",
            signal_type=SignalType.STOP_LOSS,
        )

    def _try_replace_holdings(
        self,
        confirmed: List[IndustryScore],
        selected: list,
        signals: List[TradingSignal],
    ) -> bool:
        """
        仓位已满时，尝试用最佳候选替换最差持仓。

        替换条件（必须同时满足）：
          1. 最佳候选的综合得分 > 最差持仓的得分 + v4_replace_min_diff
          2. 候选未在本轮被卖出、未在冷却期
          3. 最差持仓的仓位 < 40%（避免刚建仓就被替换）
          4. 候选行业不属于任何现有持仓行业（避免同行业替换）

        Args:
            confirmed: 通过入场确认的评分列表（降序）
            selected: _select_unique_themes 的唯一筛选结果
            signals: 当前信号列表（函数会追加替换的买卖信号）

        Returns:
            bool: 是否发生了替换
        """
        if not confirmed or not selected or len(self._current_holdings) == 0:
            return False

        cfg = self.parameters
        min_diff = float(cfg.get("v4_replace_min_diff", 0.08))
        v4_max_h = int(cfg.get("v4_max_holdings", 3))

        # 取最佳候选
        best_new = confirmed[0]
        # 从 selected 中找到对应的 ETF
        best_sel = None
        for sel in selected:
            if sel["industry_code"] == best_new.industry_code:
                best_sel = sel
                break
        if best_sel is None:
            return False

        best_etf = best_sel["etf_code"]

        # 跳过冷却期 / 本轮已卖出的候选
        if best_etf in self._exited_etfs_this_round:
            return False
        if self._cooling_list.get(best_new.industry_name, 0) > 0:
            return False
        # 跳过已经在持仓中的行业
        if best_new.industry_name in self._current_holdings.values():
            return False

        # 找持仓中得分最低的行业
        worst_etf = None
        worst_ind_name = None
        worst_score = float("inf")
        worst_weight = 0.0

        for etf_code, ind_name in self._current_holdings.items():
            pos = self._v4_positions.get(etf_code)
            w = pos.get("weight", 0.0) if pos else 0.0
            # 找到该行业代码
            ind_code = None
            for code, name in self._code_to_industry_name.items():
                if name == ind_name:
                    ind_code = code
                    break
            if ind_code and ind_code in self._prev_scores:
                score = self._prev_scores[ind_code]
                if score < worst_score:
                    worst_score = score
                    worst_etf = etf_code
                    worst_ind_name = ind_name
                    worst_weight = w

        if worst_etf is None:
            return False

        # 避免替换刚买入的仓位（weight < 40% 表示还在建仓期）
        if worst_weight < 0.40:
            if self.verbose_logging:
                logger.debug(
                    f"  [替换跳过] 最差持仓 {worst_ind_name} "
                    f"仓位仅{worst_weight:.0%} 不足40%，暂不替换"
                )
            return False

        # 替换条件：最佳候选的得分 > 最差持仓得分 + 阈值
        if best_new.composite_score <= worst_score + min_diff:
            if self.verbose_logging:
                logger.debug(
                    f"  [替换跳过] {best_new.industry_name}({best_new.composite_score:.3f}) "
                    f"未超过 {worst_ind_name}({worst_score:.3f}) + {min_diff:.2f}"
                )
            return False

        # ---- 执行替换 ----
        # 1) 平掉最差持仓
        exit_sig = self._make_exit_signal(
            worst_etf,
            industry_name=worst_ind_name,
            reason=f"替换: {best_new.industry_name}({best_new.composite_score:.3f}) > "
                   f"{worst_ind_name}({worst_score:.3f})",
        )
        signals.append(exit_sig)

        self._cooling_list[worst_ind_name] = self.cooling_period
        del self._current_holdings[worst_etf]
        if worst_etf in self._entry_prices:
            del self._entry_prices[worst_etf]
        if worst_etf in self._v4_positions:
            del self._v4_positions[worst_etf]

        # 2) 买入新候选
        df = self._data_cache.get(best_etf)
        if df is None or len(df) == 0:
            # 原始持仓已清理，新标的却无数据 → 收手
            return False

        current_price = float(df["close"].iloc[-1])
        batch_size = self._calc_confidence_weight(best_new)

        self._current_holdings[best_etf] = best_new.industry_name
        self._entry_prices[best_etf] = current_price
        self._v4_positions[best_etf] = {
            "industry": best_new.industry_name,
            "weight": batch_size,
            "batches": [(current_price, batch_size, self._last_trade_date)],
            "avg_price": current_price,
            "high_price": current_price,
            "state": "ENTERING",
        }

        signals.append(self._make_entry_signal_v4(
            etf_code=best_etf,
            industry_name=best_new.industry_name,
            weight=batch_size,
            reason=f"替换建仓: {best_new.industry_name} 替换 {worst_ind_name}",
        ))

        logger.info(
            f"V4替换: {best_new.industry_name} → {best_etf} "
            f"替换 {worst_ind_name} → {worst_etf}, "
            f"得分差{best_new.composite_score - worst_score:.3f}"
        )
        return True

    # =============================================================================
    # Layer 5: 出场检查
    # =============================================================================

    def _check_v4_exit(self, etf_code: str) -> Optional[TradingSignal]:
        """
        V4 Layer 5: 三条出场规则（OR 关系）。

        替代 V2 的 _check_stop_take_profit()（固定止盈+25%，固定止损-8%）。

        规则 1 [趋势断裂]：价格跌破 MA60
          → 最强信号，一旦触发立即出场
          → 无论盈亏，趋势坏了就是坏了

        规则 2 [移动止损]：从持仓最高点回撤超过阈值
          → 正常仓位(<=50%)：回撤 12% 出场
          → 重仓(>50%)：回撤 10% 出场（更敏感保护利润）

        规则 3 [RS 反转]：60日RS和20日RS同时持续为负
          → 辅助出场，主要用于 NEUTRAL 市场
          → 侧重保护：在趋势尚未完全断裂但已经跑输时提示风险
        """
        df = self._data_cache.get(etf_code)
        if df is None or len(df) < 60:
            return None

        close = df["close"].values.astype(float)
        entry_price = self._entry_prices.get(etf_code)
        if entry_price is None or entry_price <= 0:
            return None

        industry_name = self._current_holdings.get(etf_code, "")
        pos = self._v4_positions.get(etf_code)

        # 调试：每次出场检查打印当前关键数字
        if self.verbose_logging:
            max_p = pos["high_price"] if pos else entry_price
            dd = (max_p - close[-1]) / max_p if max_p > 0 else 0
            logger.debug(
                f"  [出场检查] {industry_name}: "
                f"价格={close[-1]:.2f} MA60={np.mean(close[-60:]):.2f} "
                f"最高={max_p:.2f} 回撤={dd:.1%}"
            )

        # ---- 规则 1: 趋势断裂（价格跌破 MA60）----
        ma60 = float(np.mean(close[-60:]))
        if close[-1] < ma60:
            return self._make_exit_signal(
                etf_code, industry_name=industry_name,
                reason=f"趋势断裂: 价格{close[-1]:.2f} < MA60{ma60:.2f}",
                signal_type=SignalType.EXIT,
            )

        # ---- 判断大盘是否处于下跌趋势（用于出场收紧）----
        _downtrend = False
        if self._benchmark_cache is not None and len(self._benchmark_cache) >= 60:
            _bm_c = self._benchmark_cache["close"].values.astype(float)
            _downtrend = float(np.mean(_bm_c[-20:])) < float(np.mean(_bm_c[-60:]))

        # ---- 计算 RS（用于修正 trailing stop 阈值，不直接触发出场）----
        # RS 反转不再作为独立出场规则（原 OR 关系让赢家过早被震出）。
        # 改为：RS 差 → 收紧移动止损阈值，让价格行为本身决定出场。
        _rs_penalty = 0.0
        bm = self._benchmark_cache
        if bm is not None and len(bm) >= 61 and len(close) >= 61:
            mkt = bm["close"].values.astype(float)
            rs_60d = (close[-1] / close[-61] - 1) - (mkt[-1] / mkt[-61] - 1)
            rs_20d = (close[-1] / close[-21] - 1) - (mkt[-1] / mkt[-21] - 1) if len(close) >= 21 else 0
            # RS 跑输越多，penalty 越大（最多收紧 5pp）
            _rs_worst = min(rs_60d, rs_20d)
            if _rs_worst < 0:
                _rs_penalty = min(abs(_rs_worst), 0.05)

        # ---- 规则 2: 移动止损（从最高点回撤）----
        # RS 不再直接触发出场，而是作为辅助收紧 trailing stop 阈值。
        if pos:
            high = pos.get("high_price", entry_price)
            # 更新最高价（每日追踪）
            if close[-1] > high:
                pos["high_price"] = close[-1]

            dd = (pos["high_price"] - close[-1]) / pos["high_price"]
            weight = pos.get("weight", 0.0)

            # 基本阈值：正常 16%，重仓 14%，下跌市 12%
            # 比原值（12%/10%/8%）更宽松，让趋势有更多回调空间
            if _downtrend:
                threshold = 0.12
            elif weight >= 0.50:
                threshold = self.parameters.get("v4_heavy_stop_ratio", 0.14)
            else:
                threshold = self.parameters.get("v4_trail_stop_ratio", 0.16)

            # RS 差修正：跑输越多阈值越紧（最多收紧 5pp）
            threshold = max(0.07, threshold - _rs_penalty)

            if dd > threshold:
                return self._make_exit_signal(
                    etf_code, industry_name=industry_name,
                    reason=f"移动止损: 从{pos['high_price']:.2f}回撤{dd:.1%}>{threshold:.0%}"
                           + ("(下跌市)" if _downtrend else "")
                           + (f"(RS修正-{_rs_penalty:.0%})" if _rs_penalty > 0.01 else ""),
                    signal_type=SignalType.STOP_LOSS,
                )
        # ---- 规则 3（已移除）：RS 反转不再直接触发出场 ----
        # 原规则 3 在下跌市中用 OR 条件同时检查 RS_60d 和 RS_20d，
        # 导致几乎所有持仓在市场下跌时被强制平仓。RS 作为阈值修正并入规则 2。

        return None

    # =============================================================================
    # 状态更新辅助
    # =============================================================================

    def _update_prev_scores(self) -> None:
        """
        保存本期所有行业综合得分，供下期计算 score_change（边际变化）。

        这个方法是轻量级的——只调用 score_all 获取得分，不生成交易信号。
        即使当期不调仓（BEAR 状态/已有 2 个方向），也要更新得分记录，
        否则下期 score_change 会因为 prev_scores 缺失而全部为 0。
        """
        if self._scoring_service and self._industry_data_cache:
            scores = self._scoring_service.score_all(
                industry_data=self._industry_data_cache,
                benchmark_prices=self._benchmark_cache,
                factor_override=self.factor_override,
            )
            self._prev_scores = {s.industry_code: s.composite_score for s in scores}

    def _decay_cooling(self) -> None:
        """
        每个调仓日递减所有行业的冷却期天数。

        冷却期的作用：
          出场后的行业短期内禁止再次入场，防止反复进出（反复止损）。
          正常出场冷却 10 天，止损出场冷却 20 天。
          到期后自动从冷却列表移除，允许再次入场。
        """
        for ind in list(self._cooling_list.keys()):
            self._cooling_list[ind] -= 1
            if self._cooling_list[ind] <= 0:
                del self._cooling_list[ind]

    def _get_v4_rank(self, etf_code: str) -> int:
        """
        获取某 ETF 对应行业在最近评分中的真实排名。

        P2-1：基于 _prev_scores 的全行业排序，而非 _v4_candidates 的过滤后排名。
        过滤后的候选可能只有 10-20 个行业，但真正的全行业排名才是加仓判断依据。

        V4 提速：使用 _code_to_industry_name 映射避免 O(n²) DataFrame 迭代。
        """
        industry_name = self._current_holdings.get(etf_code, "")
        if not industry_name or not self._prev_scores:
            return 999
        # 通过 _code_to_industry_name 反向查找当前持仓行业的代码
        held_code = None
        for code, name in self._code_to_industry_name.items():
            if name == industry_name:
                held_code = code
                break
        if held_code is None or held_code not in self._prev_scores:
            return 999
        # 按综合得分降序排列，找目标代码的排名（1-indexed）
        sorted_codes = sorted(
            self._prev_scores.keys(),
            key=lambda c: self._prev_scores[c],
            reverse=True,
        )
        for i, code in enumerate(sorted_codes):
            if code == held_code:
                return i + 1
        return 999

    @staticmethod
    def _calc_v4_avg_price(batches: list) -> float:
        """计算加权平均买入价"""
        total_qty = sum(q for _, q, _ in batches)
        if total_qty <= 0:
            return 0.0
        return sum(p * q for p, q, _ in batches) / total_qty

    # =============================================================================
    # 数据追加
    # =============================================================================

    def _append_etf_price(self, ts_code: str, bar: BarData) -> None:
        """
        将 ETF 或基准指数的 bar 数据追加到价格缓存 _data_cache。

        on_bar 每天收到数百根 bar，按 ts_code 分拆存入各自的 DataFrame。
        缓存最多保留 momentum_windows 最大值的 3 倍行数（约 360 行），
        防止长时间运行导致内存膨胀。

        Args:
            ts_code: ETF 代码或基准指数代码
            bar: K 线数据
        """
        if ts_code not in self._data_cache:
            self._data_cache[ts_code] = pd.DataFrame(columns=["close", "volume", "amount"])
        df = self._data_cache[ts_code]
        new_row = pd.DataFrame([{
            "close": bar.close,
            "volume": bar.volume,
            "amount": bar.amount,
        }])
        self._data_cache[ts_code] = pd.concat([df, new_row], ignore_index=True)

        # 限制缓存大小（防止长时间运行OOM）
        max_rows = max(self.parameters.get("momentum_windows", [120])) * 3
        if len(self._data_cache[ts_code]) > max_rows:
            self._data_cache[ts_code] = (
                self._data_cache[ts_code].tail(max_rows).reset_index(drop=True)
            )

    def _append_industry_data(self, ts_code: str, bar: BarData) -> None:
        """
        将行业指数（.SI 结尾）的 bar 数据追加到 _industry_data_cache。

        与 _append_etf_price 的区别：
          - ETF 缓存只需要 close/volume/amount（用于交易和流动性判断）
          - 行业缓存还需要 pe/pb/float_mv/pct_change（用于因子评分）
          - 行业缓存保留 5 年 + 100 天（用于 PE/PB 历史分位计算）

        on_bar 中收到 .SI 结尾的 ts_code 时走此路径。
        """
        if ts_code not in self._industry_data_cache:
            self._industry_data_cache[ts_code] = pd.DataFrame(
                columns=["close", "vol", "amount", "pe", "pb", "float_mv", "pct_change", "name"]
            )

        df = self._industry_data_cache[ts_code]
        name = getattr(bar, "name", "") or ""

        # pct_change: 从 BarData 可能不包含，从 close 估算
        # 有些数据源（如回测引擎）不推 pct_change，需要手动算
        pct_change = 0.0
        if len(df) > 0 and df["close"].iloc[-1] > 0:
            pct_change = float(bar.close / df["close"].iloc[-1] - 1.0) if df["close"].iloc[-1] > 0 else 0.0

        new_row = pd.DataFrame([{
            "close": bar.close,
            "vol": bar.volume,
            "amount": bar.amount,
            "pe": getattr(bar, "pe", None) or 0.0,
            "pb": getattr(bar, "pb", None) or 0.0,
            "float_mv": getattr(bar, "float_mv", None) or 0.0,
            "pct_change": getattr(bar, "pct_chg", pct_change),
            # ↑ pct_chg 是 BarData 的标准字段，部分数据源可能叫 pct_change
            "name": name,
        }])
        self._industry_data_cache[ts_code] = pd.concat([df, new_row], ignore_index=True)

        # 限制缓存大小：最多保留 5 年 + 100 天的数据（约 1360 行）
        # PE/PB 历史分位需要回溯 5 年，所以缓存比 ETF 数据保留更长
        max_rows_industry = (self.parameters.get("pe_percentile_years", 5) * 252) + 100
        if len(self._industry_data_cache[ts_code]) > max_rows_industry:
            self._industry_data_cache[ts_code] = (
                self._industry_data_cache[ts_code].tail(max_rows_industry).reset_index(drop=True)
            )

    # =============================================================================
    # 信号生成
    # =============================================================================

    def _make_entry_signal_v4(
        self,
        etf_code: str,
        industry_name: str,
        weight: float,
        reason: str,
    ) -> TradingSignal:
        """V4 版买入信号生成，支持指定权重"""
        df = self._data_cache.get(etf_code)
        price = float(df["close"].iloc[-1]) if df is not None and len(df) > 0 else 0.0

        sig = TradingSignal(
            id=self._gen_id(),
            strategy_id=self.name,
            strategy_name=self.name,
            ts_code=etf_code,
            signal_type=SignalType.ENTRY,
            direction=SignalDirection.LONG,
            price=price,
            quantity=0,
            amount=1.0,
            confidence=0.80,
            reason=f"{industry_name}: {reason}",
            timestamp=datetime.now(),
        )
        sig.weight = weight
        return sig

    def _make_exit_signal(
        self,
        etf_code: str,
        industry_name: str,
        reason: str,
        signal_type: SignalType = SignalType.EXIT,
        confidence: float = 0.80,
    ) -> TradingSignal:
        """生成出场信号 — quantity=0 触发 CloseAllSizer 全平"""
        df = self._data_cache.get(etf_code)
        price = float(df["close"].iloc[-1]) if df is not None and len(df) > 0 else 0.0

        return TradingSignal(
            id=self._gen_id(),
            strategy_id=self.name,
            strategy_name=self.name,
            ts_code=etf_code,
            signal_type=signal_type,
            direction=SignalDirection.CLOSE_LONG,
            price=price,
            quantity=0,
            amount=0.0,
            confidence=confidence,
            reason=f"{industry_name}: {reason}",
            timestamp=datetime.now(),
        )

    @staticmethod
    def _gen_id() -> str:
        """生成全局唯一信号 ID（UUID4 格式）"""
        import uuid
        return str(uuid.uuid4())

    # =============================================================================
    # 参数校验
    # =============================================================================

    def _validate_params(self) -> List[str]:
        """校验策略参数，返回错误列表"""
        errors: List[str] = []
        if self.rebalance_frequency < 1 or self.rebalance_frequency > 20:
            errors.append(f"rebalance_frequency={self.rebalance_frequency} 应在 [1, 20]")
        if self.cooling_period < 0 or self.cooling_period > 60:
            errors.append(f"cooling_period={self.cooling_period} 应在 [0, 60]")
        if self.stop_loss > 0 or self.stop_loss < -0.30:
            errors.append(f"stop_loss={self.stop_loss} 应在 [-0.30, 0]")
        # V4：因子大类权重之和校验
        tw = self.parameters.get("trend_weight", 0.55)
        vw = self.parameters.get("volume_weight", 0.30)
        vlw = self.parameters.get("valuation_weight", 0.15)
        if abs(tw + vw + vlw - 1.0) > 0.01:
            errors.append(f"大类权重之和应为1.0: trend={tw} + volume={vw} + valuation={vlw} = {tw+vw+vlw:.3f}")
        return errors

    # =============================================================================
    # 查询接口
    # =============================================================================

    def get_parameters(self) -> dict:
        """获取当前策略参数（用于前端展示）"""
        return {
            "strategy_version": "V4",
            # 策略基础
            "rebalance_frequency": self.rebalance_frequency,
            "cooling_period": self.cooling_period,
            "min_history": self.min_history,
            "max_sector_limit": self.max_sector_limit,
            "stop_loss": self.stop_loss,
            # 因子大类权重
            "trend_weight": self.parameters.get("trend_weight", 0.55),
            "volume_weight": self.parameters.get("volume_weight", 0.30),
            "valuation_weight": self.parameters.get("valuation_weight", 0.15),
            # V4 市场状态
            "v4_regime": self._v4_regime,
            "v4_max_position": self._v4_max_position,
            # V4 仓位
            "v4_position_max": self.parameters.get("v4_position_max", 0.60),
            # 调试
            "factor_override": self.parameters.get("factor_override", {}),
            "verbose_logging": self.verbose_logging,
            # 只读
            "universe_size": len(self._universe) if hasattr(self, "_universe") else 0,
        }

    def get_current_scores(self) -> Dict[str, float]:
        """获取最新一期各行业综合得分 {行业代码: 综合得分}，用于外部展示"""
        return dict(self._prev_scores) if self._prev_scores else {}

    def get_holdings(self) -> List[str]:
        """
        获取当前持仓 ETF 代码列表（按代码升序排列）。

        注意返回的是 ETF 代码（如 "159732.SZ"），不是行业名。
        行业名通过 _current_holdings[etf_code] 查询。
        """
        return sorted(self._current_holdings.keys())
