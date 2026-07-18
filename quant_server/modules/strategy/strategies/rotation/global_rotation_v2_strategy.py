# -*- coding: utf-8 -*-
"""
全球资产轮动策略 V2 — 双动量骨架（Antonacci Dual Momentum）

设计来源：
  - 多资产趋势轮动 V1 退役经验教训（2026-07-17）
  - 《全球资产轮动 V2 调研方案-2026-07》
  - Antonacci (2012) Dual Momentum

核心逻辑：
  1. 资产池 = 11 只混合 ETF（低相关基石 + 高弹性行业 + 中间层）
  2. 动量排名（对数回归 × R² + 尾端跳水惩罚 + 开盘暴跌过滤）
  3. 绝对动量门：候选收益 < 货基(511990) → 该仓位退守十年国债(511260)
  4. 月内硬止损：-10% 日频检查兜底（吸取 V1「出场与调仓耦合」教训）
  5. 美股双标的取成交额大者（QDII 溢价缓解）

与 V1 的核心差异：
  - 月频调仓（月份变更触发）vs 每 10 交易日
  - 简单收益率 vs 对数回归动量 × R²
  - 无入场过滤（无 RSRS/MA/FRAMA/量异常/市场状态）
  - 仅硬止损 vs 多层出场（无移动止损/趋势断裂/抛物线止盈/冷却期）
  - 5 个核心参数 vs 30+ 参数
  - 10 只大类资产标的 vs 28 只含行业 ETF

数据需求：
  - 仅 OHLCV 日线
  - 预热需 131 天（126 天动量 + 5 天跳过）
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

# 权重变化阈值：新旧权重相对差异超过此比例才触发调权信号
_WEIGHT_CHANGE_THRESHOLD = 0.20


class GlobalRotationV2Strategy(BaseStrategy):
    """
    全球资产轮动策略 V2 — 双动量骨架。

    策略类型：ROTATION
    继承 BaseStrategy，遵循 on_bar + on_bar_batch_end 驱动模式。

    决策频率：月频调仓 + 日频硬止损兜底。

    三级决策链：
      第一级 — 相对动量排名（12-1 月简单收益率，取 top 3）
      第二级 — 绝对动量门（候选 < 货基 → 退守十年国债）
      第三级 — 月内硬止损（-10%，日频检查，同日止损不补回）
    """

    strategy_type: StrategyType = StrategyType.ROTATION

    # =========================================================================
    # 资产池 — 混合池（宽基 + 行业 + 商品，12 只）
    #
    # 低相关基石（4 只）: 纳指 100、黄金、豆粕、十年国债
    #   跨资产低相关，轮动空间大 — 这是 V2 超额的核心来源
    # 高弹性行业（3 只）: 证券、半导体、中概互联
    #   年化波动 35-40%，牛市放大收益，熊市通过绝对动量门自动过滤
    # 中间层（3 只）: 日经、德国 DAX、创业板
    #   区域分散，与美股/A股不完全同步
    # 港股（1 只）: 恒生
    #   低估值高弹性，与 A 股波动节奏不同
    # 防御（1 只）: 十年国债（也是 DEFENSE_ASSET）
    #
    # 移除: 510300(从未进入 topN)、513500(被 513100 永久压制)
    # =========================================================================
    ASSET_POOL: List[str] = [
        # 低相关基石
        "513100.SH",  # 纳指100    (2013起) — 全球最强宽基
        "518880.SH",  # 黄金ETF    (2013起) — 全天候稳定器
        "159985.SZ",  # 豆粕ETF    (2019起) — 熊市避风港
        "511260.SH",  # 十年国债   (2017起) — 防御首选
        # 高弹性行业
        "512880.SH",  # 证券ETF    (2016起) — A股牛市放大器, 波动 35%+
        "512480.SH",  # 半导体ETF  (2019起) — 科技核心, 波动 38%+
        "513050.SH",  # 中概互联   (2017起) — 港股弹性之王, 波动 40%+
        # 中间层
        "513030.SH",  # 德国DAX    (2014起) — 欧洲暴露
        "513520.SH",  # 日经ETF    (2019起) — 亚太暴露
        "159915.SZ",  # 创业板     (2011起) — A股弹性代表
        # 港股
        "159920.SZ",  # 恒生ETF    (2012起) — 低估值高弹性
    ]

    # 美股单标的（池内仅纳指 1 只美股，无配对需求；保留列表结构便于未来扩展）
    US_PAIR: List[str] = []

    # 绝对动量比较基准 + 防御落脚点
    CASH_ANCHOR: str = "511990.SH"   # 货基ETF（无风险收益基准）
    DEFENSE_ASSET: str = "511260.SH"  # 十年国债（退守首选；已在 ASSET_POOL 中）

    # =========================================================================
    # 默认参数 — 周频优化版（四大优化整合）
    #   优化1: 周频调仓 "weekly" — 比月频快 4x 反应，比日频低噪音
    #   优化2: 对数回归动量 × R² — 区分"稳健上涨"和"脉冲暴涨"
    #   优化3: 尾端跳水惩罚 — 近3日有单日-5% → 不参与排名
    #   优化4: 开盘暴跌过滤 — 开盘跌 > 3% → slot 退守防御
    #   参数: 126d 动量窗口 + top4 + -12% 止损 + 绝对动量门开
    #   预期: 年化 8-11%, MDD 12-16%, Calmar 0.6-0.8
    # =========================================================================
    DEFAULT_PARAMS: Dict[str, Any] = {
        "momentum_window": 126,       # 动量计算窗口（≈6 个月交易日，配合周频）
        "skip_window": 5,             # 跳过最近窗口（≈1 周交易日）
        "max_holdings": 4,            # top N 持仓数
        "max_single_weight": 0.30,    # 单标的上限权重
        "stop_loss": -0.12,           # 硬止损线（日频检查）
        "min_history": 131,           # 预热最少天数 = momentum_window(126) + skip_window(5)
        "use_absolute_momentum": True,  # 周频需要绝对动量门过滤假信号
        "rebalance_frequency": "weekly",  # 调仓频率: "monthly" | "weekly" | N(每N个交易日)
        "verbose_logging": False,
    }

    def __init__(
        self,
        name: str = "全球资产轮动V2",
        strategy_type: StrategyType = StrategyType.ROTATION,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        merged = dict(self.DEFAULT_PARAMS)
        if parameters:
            merged.update(parameters)
        super().__init__(name=name, strategy_type=strategy_type, parameters=merged)

        # ---- 参数提取 ----
        self.momentum_window: int = int(merged["momentum_window"])
        self.skip_window: int = int(merged["skip_window"])
        self.max_holdings: int = int(merged["max_holdings"])
        self.max_single_weight: float = float(merged["max_single_weight"])
        self.stop_loss: float = float(merged["stop_loss"])
        self.min_history: int = int(merged["min_history"])
        self.use_absolute_momentum: bool = bool(merged.get("use_absolute_momentum", False))
        self.rebalance_frequency = merged.get("rebalance_frequency", "monthly")  # "monthly"|"weekly"|int
        self.verbose_logging: bool = bool(merged.get("verbose_logging", False))

        # ---- 运行时状态 ----
        self._last_rebalance_month: str = ""    # 上次调仓月份 "2024-07"
        self._last_rebalance_week: str = ""     # 上次调仓周 "2024-30" (ISO year-week)
        self._last_rebalance_days: int = 0      # 上次调仓时的 _bar_count（日频模式用）
        self._last_trade_date: str = ""

        # 持仓跟踪
        self._current_holdings: Dict[str, float] = {}   # {code: weight}
        self._entry_prices: Dict[str, float] = {}       # {code: entry_price}

        # 数据缓存
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._cache_last_date: Dict[str, str] = {}    # {code: "YYYY-MM-DD"} 时序守卫

        # [修复 #1] 当日止损黑名单 — 防止同日调仓重新买入刚止损的标的
        self._stopped_today: Set[str] = set()

        # 调仓计数器
        self._bar_count: int = 0

        # 预热状态
        self._warmup_warned: bool = False
        self._reset_warned: Set[str] = set()

        logger.info(
            f"全球资产轮动V2 初始化: {name}, "
            f"资产池={len(self.ASSET_POOL)}只, "
            f"持有上限={self.max_holdings}只, "
            f"动量窗口={self.momentum_window}天, "
            f"硬止损={self.stop_loss:.0%}, "
            f"绝对动量={'开' if self.use_absolute_momentum else '关'}, "
            f"调仓频率={self.rebalance_frequency}"
        )

    # =========================================================================
    # 生命周期
    # =========================================================================

    def on_init(self) -> None:
        """设置股票池 + 校验参数"""
        errors = self._validate_params()
        if errors:
            raise ValueError(f"策略参数校验失败: {'; '.join(errors)}")

        # universe = asset_pool + cash_anchor（用于绝对动量计算）
        self._universe = list(dict.fromkeys(self.ASSET_POOL + [self.CASH_ANCHOR]))

        logger.info(
            f"全球资产轮动V2 初始化完成, universe={len(self._universe)}只"
        )

    async def on_start(self) -> None:
        """重置状态 + 预热历史数据"""
        self._last_rebalance_month = ""
        self._last_rebalance_week = ""
        self._last_rebalance_days = 0
        self._last_trade_date = ""
        self._bar_count = 0
        self._current_holdings.clear()
        self._entry_prices.clear()
        self._data_cache.clear()
        self._cache_last_date.clear()
        self._reset_warned.clear()
        self._stopped_today.clear()
        self._warmup_warned = False

        loaded = await self._preload_history()
        if loaded > 0:
            logger.info(
                f"全球资产轮动V2 已启动 — 预热 {loaded} 条数据, "
                f"覆盖 {len(self._data_cache)} 只标的"
            )
        else:
            logger.info("全球资产轮动V2 已启动（等待 bar 累积）")

    async def _preload_history(self) -> int:
        """
        从 DB 加载历史数据预热缓存。

        复用 V1 (v1.5.1) 模式：
          - 从 2018-01-01 起全量预热（10 只 ETF 约 2 万行，成本可忽略）
          - 时序守卫自动截断回测起点之后的数据，防前视
        """
        session_factory = getattr(self, "_db_session_factory", None)
        if session_factory is None:
            return 0

        from datetime import date as _dt
        from modules.strategy.engines.data_feed_engine import DataFeedEngine as _DFE

        end_date = _dt.today()
        start_date = _dt(2018, 1, 1)

        try:
            async with session_factory() as db:
                engine = _DFE(db)
                symbols = list(dict.fromkeys(self._universe))
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
                        self._cache_last_date[ts_code] = (
                            str(sub["trade_date"].iloc[-1])[:10]
                            if len(sub) > 0 else ""
                        )
                    logger.info(
                        f"全球资产轮动V2 历史预热完成: {len(df)} 行, "
                        f"{start_date} ~ {end_date}"
                    )
                    return len(df)
        except Exception as e:
            logger.warning(f"历史预热失败（非致命，将等待 bar 累积）: {e}")
        return 0

    def on_stop(self) -> None:
        """清理状态"""
        self._data_cache.clear()
        self._cache_last_date.clear()
        self._reset_warned.clear()
        self._current_holdings.clear()
        self._entry_prices.clear()
        self._stopped_today.clear()
        logger.info("全球资产轮动V2 已停止")

    # =========================================================================
    # 核心入口
    # =========================================================================

    def on_bar(self, bar: BarData) -> List[TradingSignal]:
        """
        日频：仅缓存数据。

        调仓 + 止损检查均在 on_bar_batch_end 统一执行（~10 只 ETF 全部推送完毕后），
        确保「日频」语义正确且不会对同一持仓重复生成信号。
        """
        try:
            if bar.ts_code not in self._universe:
                return []

            self._append_data(bar.ts_code, bar)

            trade_date = str(getattr(bar, "trade_date", "") or "")[:10]
            if trade_date:
                self._last_trade_date = trade_date
        except Exception as e:
            logger.error(
                f"全球资产轮动V2 on_bar 异常: {bar.ts_code}: {e}", exc_info=True
            )
        return []

    def _should_rebalance(self, td: str) -> bool:
        """判断当前是否应触发调仓（支持月频/周频/日数频）。"""
        freq = self.rebalance_frequency
        if freq == "monthly":
            current_month = td[:7]
            return current_month != self._last_rebalance_month
        elif freq == "weekly":
            from datetime import date as _dt
            try:
                d = _dt.fromisoformat(td)
                current_week = d.isocalendar()[1]  # ISO week number
                current_year = d.isocalendar()[0]
                week_key = f"{current_year}-{current_week:02d}"
            except (ValueError, AttributeError):
                current_month = td[:7]
                return current_month != self._last_rebalance_month  # fallback to monthly
            return week_key != self._last_rebalance_week
        else:
            # 每 N 个交易日
            try:
                interval = int(freq)
            except (ValueError, TypeError):
                interval = 5
            if self._bar_count - self._last_rebalance_days >= interval:
                return True
            return False

    def _mark_rebalanced(self, td: str) -> None:
        """记录本次调仓的时间标记。"""
        freq = self.rebalance_frequency
        if freq == "monthly":
            self._last_rebalance_month = td[:7]
        elif freq == "weekly":
            from datetime import date as _dt
            try:
                d = _dt.fromisoformat(td)
                week_key = f"{d.isocalendar()[0]}-{d.isocalendar()[1]:02d}"
                self._last_rebalance_week = week_key
            except (ValueError, AttributeError):
                self._last_rebalance_month = td[:7]
        else:
            self._last_rebalance_days = self._bar_count

    def on_bar_batch_end(self, trade_date: Any = None) -> List[TradingSignal]:
        """
        当日批次结束回调。

        执行顺序：
          1. 日频硬止损检查（先于调仓）
          2. 调仓（按 rebalance_frequency 触发：monthly/weekly/N天数）
        """
        signals: List[TradingSignal] = []
        try:
            td = str(trade_date)[:10] if trade_date else self._last_trade_date
            if not td:
                return signals
            self._last_trade_date = td

            # 交易日计数
            self._bar_count += 1

            # [修复 #1] 清空当日止损黑名单（新的一天）
            self._stopped_today.clear()

            # ---- Step 1: 日频硬止损 ----
            stop_signals = self._daily_stop_check()
            signals.extend(stop_signals)

            # ---- Step 2: 调仓（按频率触发） ----
            if self._should_rebalance(td):
                rebalance_signals = self._run_rebalance(td)
                signals.extend(rebalance_signals)
                self._mark_rebalanced(td)

        except Exception as e:
            logger.error(
                f"全球资产轮动V2 on_bar_batch_end 异常: {trade_date}: {e}",
                exc_info=True,
            )
        return signals

    # =========================================================================
    # 日频硬止损
    # =========================================================================

    def _daily_stop_check(self) -> List[TradingSignal]:
        """检查所有现有持仓的硬止损（日频）。"""
        signals: List[TradingSignal] = []
        for code in list(self._current_holdings.keys()):
            entry_price = self._entry_prices.get(code)
            if entry_price is None or entry_price <= 0:
                continue

            current_price = self._get_price(code)
            if current_price <= 0:
                continue

            # [修复 #7] 新鲜度守卫：数据非当日 → 跳过止损检查（避免用旧价格误判）
            if not self._is_fresh(code):
                continue

            pnl = current_price / entry_price - 1.0
            if pnl <= self.stop_loss:
                exit_sig = self._make_exit_signal(
                    code,
                    reason=f"月内硬止损: 浮亏{pnl:.1%} ≤ {self.stop_loss:.0%}",
                    signal_type=SignalType.STOP_LOSS,
                )
                if exit_sig:
                    signals.append(exit_sig)
                    # [修复 #4] 仅在信号成功生成后清除状态
                    del self._current_holdings[code]
                    self._entry_prices.pop(code, None)
                    # [修复 #1] 加入当日止损黑名单
                    self._stopped_today.add(code)

                    logger.warning(
                        f"V2 硬止损触发: {code} "
                        f"入场价{entry_price:.2f} 现价{current_price:.2f} "
                        f"浮亏{pnl:.1%}"
                    )

        return signals

    # =========================================================================
    # 月末调仓
    # =========================================================================

    def _run_rebalance(self, trade_date: str) -> List[TradingSignal]:
        """
        调仓主逻辑（支持月频/周频/日数频触发）。

        流程：
          1. 预热检查
          2. 对数回归动量 × R² 排名（优化2替代简单收益率）
          3. 美股双标取成交额大者（另一个剔除排名池）
          4. 按得分降序排名，取 top N
          5. 绝对动量门 + 开盘暴跌过滤：每个 slot 独立判断
          6. 计算目标仓位权重（等权 × slots）
          7. 与现有持仓对比，生成 ENTRY/EXIT 信号（含权重变化）
        """
        signals: List[TradingSignal] = []

        # ---- 预热检查 ----
        max_days = max((len(df) for df in self._data_cache.values()), default=0)
        if max_days < self.min_history:
            if not self._warmup_warned:
                self._warmup_warned = True
                logger.info(
                    f"全球资产轮动V2: 预热期 — {max_days}/{self.min_history} 天"
                )
            return signals

        # ---- Step 1: 动量排名 ----
        rankings = self._calc_momentum_rankings()
        if not rankings:
            logger.warning("全球资产轮动V2: 无有效动量排名数据，跳过调仓")
            return signals

        # ---- Step 2: 绝对动量基准（货基收益率） ----
        cash_return = self._calc_asset_return(self.CASH_ANCHOR)
        if cash_return is None:
            cash_return = 0.0
            logger.debug("全球资产轮动V2: 货基数据缺失，绝对动量门槛退化为 0")

        # ---- Step 3: 防御资产选择 ----
        defense_code = self._get_defense_asset(cash_return)

        # ---- Step 4: 每个 slot 独立决策 ----
        n_candidates = min(self.max_holdings, len(rankings))
        raw_slots: Dict[str, float] = {}  # {code: slot_count}

        for i in range(n_candidates):
            code, score = rankings[i]

            # [修复 #1 + #7] 跳过当日止损标的 + 数据非当日标的
            if code in self._stopped_today:
                raw_slots[defense_code] = raw_slots.get(defense_code, 0.0) + 1.0
                logger.info(
                    f"V2 调仓: {code} 当日已止损，slot 退守 {defense_code}"
                )
            elif self._is_open_crash(code):
                # [优化4] 开盘暴跌过滤：当日开盘跌 > 3%，slot 退守防御
                raw_slots[defense_code] = raw_slots.get(defense_code, 0.0) + 1.0
                logger.info(
                    f"V2 调仓: {code} 开盘暴跌，slot 退守 {defense_code}"
                )
            elif not self._is_fresh(code):
                # [修复 #7] 新鲜度守卫：停牌/无数据标的退守防御
                raw_slots[defense_code] = raw_slots.get(defense_code, 0.0) + 1.0
                logger.info(
                    f"V2 调仓: {code} 数据非当日，slot 退守 {defense_code}"
                )
            elif not self.use_absolute_momentum or score > cash_return:
                # Phase 3: 关闭绝对动量门时直接持有最强资产，不检查 vs 货基
                raw_slots[code] = raw_slots.get(code, 0.0) + 1.0
            else:
                raw_slots[defense_code] = raw_slots.get(defense_code, 0.0) + 1.0

        # 防御性兜底：若所有候选都被过滤，全仓退守防御资产
        total_slots = sum(raw_slots.values())
        if total_slots <= 0:
            raw_slots = {defense_code: 1.0}
            total_slots = 1.0

        # ---- Step 5: 仓位权重计算（等权 + 单标的上限） ----
        target_weights: Dict[str, float] = {}
        for code, slots in raw_slots.items():
            w = slots / total_slots
            target_weights[code] = min(w, self.max_single_weight)

        # [修复 #2 相关] 如果上限截断导致总权重 < 1.0，按比例重新分配给未达上限的资产
        # 若无未达上限资产（全部触及 max_single_weight），剩余权重留现金由 Broker 管理
        total_w = sum(target_weights.values())
        if total_w < 1.0 and total_w > 0:
            excess = 1.0 - total_w
            uncapped = [
                c for c in target_weights
                if target_weights[c] < self.max_single_weight
            ]
            if uncapped:
                add = excess / len(uncapped)
                for c in uncapped:
                    target_weights[c] = min(
                        target_weights[c] + add,
                        self.max_single_weight,
                    )
            else:
                # [修复 #2] 全部触及上限 → 剩余权重无法分配，留现金
                logger.warning(
                    "V2 调仓: 所有目标持仓触及单标上限 %.0f%%，"
                    "剩余 %.1f%% 权重留现金",
                    self.max_single_weight * 100,
                    excess * 100,
                )

        # ---- Step 6: 对比现有持仓，生成信号 ----
        old_holdings = self._current_holdings.copy()
        old_codes = set(old_holdings.keys())
        new_codes = set(target_weights.keys())

        # 退出不再持有的
        for code in old_codes - new_codes:
            exit_sig = self._make_exit_signal(code, reason="月末调仓退出")
            if exit_sig:
                signals.append(exit_sig)

        # 新建仓
        for code in new_codes - old_codes:
            current_price = self._get_price(code)
            if current_price <= 0:
                logger.warning(f"V2 调仓: {code} 无有效价格，跳过建仓")
                continue
            entry_sig = self._make_entry_signal(
                code,
                target_weights[code],
                reason=f"月末调仓建仓 动量排名{self._find_rank(code, rankings)}",
            )
            if entry_sig:
                signals.append(entry_sig)

        # [修复 #2] 权重调整：相同 code 但权重变化超过阈值 → EXIT+ENTRY
        for code in old_codes & new_codes:
            old_w = old_holdings.get(code, 0.0)
            new_w = target_weights.get(code, 0.0)
            if old_w <= 0:
                continue
            rel_change = abs(new_w - old_w) / old_w
            if rel_change > _WEIGHT_CHANGE_THRESHOLD:
                # 先退出旧仓位（旧权重），再以新权重建仓
                exit_sig = self._make_exit_signal(
                    code,
                    reason=f"权重调整: {old_w:.1%}→{new_w:.1%} (变化{rel_change:.0%})",
                )
                if exit_sig:
                    signals.append(exit_sig)
                entry_sig = self._make_entry_signal(
                    code, new_w,
                    reason=f"权重调整补仓: {new_w:.1%}",
                )
                if entry_sig:
                    signals.append(entry_sig)
                logger.info(
                    f"V2 权重调整: {code} {old_w:.1%}→{new_w:.1%}"
                )

        # 更新状态
        self._current_holdings = target_weights.copy()
        for code in new_codes:
            price = self._get_price(code)
            if price > 0:
                self._entry_prices[code] = price

        # 日志
        hold_str = ", ".join(
            f"{c}({w:.1%})" for c, w in target_weights.items()
        )
        logger.info(
            f"V2 月末调仓 {trade_date}: 持仓=[{hold_str}] "
            f"信号={len(signals)}条 "
            f"货基收益={cash_return:.2%} "
            f"防御资产={defense_code}"
        )

        return signals

    # =========================================================================
    # 动量排名
    # =========================================================================

    def _calc_momentum_rankings(self) -> List[Tuple[str, float]]:
        """
        计算 12-1 月简单收益率排名。

        收益公式：close[T-skip-1] / close[T-momentum-skip] - 1
        （跳过最近 skip_window 交易日，取之前 momentum_window 交易日）

        Returns:
            [(code, return), ...] 按收益率降序
        """
        # ---- 美股双标处理：取成交额大者 ----
        us_code = self._pick_us_etf()
        effective_pool: List[str] = []
        for code in self.ASSET_POOL:
            if code in self.US_PAIR:
                if code == us_code:
                    effective_pool.append(code)
                # else: 剔除另一个美股 ETF
            else:
                effective_pool.append(code)

        # ---- 计算收益率（优化2: 对数回归动量 × R²） ----
        results: List[Tuple[str, float]] = []
        for code in effective_pool:
            score = self._calc_log_regression_momentum(code)
            if score is None:
                continue
            results.append((code, score))

        results.sort(key=lambda x: x[1], reverse=True)

        if self.verbose_logging:
            top5 = [(c, f"{r:.2%}") for c, r in results[:5]]
            logger.info(f"V2 动量排名 top5: {top5}")

        return results

    def _calc_asset_return(self, code: str) -> Optional[float]:
        """
        计算单个资产 12-1 月简单收益率。

        Args:
            code: ETF 代码

        Returns:
            收益率（如 0.15 = +15%），数据不足返回 None
        """
        df = self._data_cache.get(code)
        if df is None:
            return None

        # [修复 #5] 统一的长度检查（移除了原 523 行和 531 行的冗余守卫）
        needed = self.momentum_window + self.skip_window
        if len(df) < needed:
            return None

        closes = df["close"].values.astype(np.float64)

        # close[-(skip_window+1)]: T - skip_window 日
        # close[-(momentum_window+skip_window)]: T - momentum_window - skip_window 日
        end_idx = -(self.skip_window + 1)
        start_idx = -(self.momentum_window + self.skip_window)

        end_price = closes[end_idx]
        start_price = closes[start_idx]

        if start_price <= 0 or np.isnan(start_price) or np.isnan(end_price):
            return None

        # [优化1] 尾端跳水惩罚：近3日有单日跌超 5% → 不参与排名
        if len(closes) >= 4:
            recent_daily = np.diff(closes[-4:]) / closes[-4:-1]
            if np.any(recent_daily < -0.05):
                return None

        return float(end_price / start_price - 1.0)

    def _calc_log_regression_momentum(self, code: str) -> Optional[float]:
        """
        [优化2] 对数加权线性回归动量 × R²。

        比简单收益率多一个维度：R² 衡量趋势的"纯净度"。
        R²≈1 = 价格沿一条直线稳定上涨（好）
        R²≈0 = 价格上下乱跳最终回到原点（差）

        得分 = 年化收益率 × R²（复用 V1 验证过的算法）
        """
        df = self._data_cache.get(code)
        if df is None:
            return None

        needed = self.momentum_window + self.skip_window
        if len(df) < needed:
            return None

        closes = df["close"].values.astype(np.float64)
        valid = closes[-(needed):]
        valid = valid[(valid > 0) & ~np.isnan(valid)]
        if len(valid) < needed // 2:
            return None

        # [优化1] 尾端跳水惩罚
        if len(valid) >= 4:
            recent_daily = np.diff(valid[-4:]) / valid[-4:-1]
            if np.any(recent_daily < -0.05):
                return None

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

            # 极端动量排除（年化 > 5x 可能是数据异常）
            if annualized > 5.0:
                return None

            return annualized * max(0.0, r2)
        except Exception:
            return None

    def _pick_us_etf(self) -> Optional[str]:
        """
        从美股双标（513100 纳指100 / 513500 标普500）中选近 20 日均成交额大者。

        Returns:
            胜出的 ETF 代码，若两者均无数据返回 None
        """
        best_code: Optional[str] = None
        best_avg_amount = -1.0

        for code in self.US_PAIR:
            df = self._data_cache.get(code)
            if df is None or len(df) < 20:
                continue
            # 优先用 amount（成交额），退化为 volume
            col = "amount" if "amount" in df.columns else "volume"
            values = df[col].values.astype(np.float64)[-20:]
            avg_val = float(np.mean(values))
            if avg_val > best_avg_amount:
                best_avg_amount = avg_val
                best_code = code

        if best_code and self.verbose_logging:
            other = [c for c in self.US_PAIR if c != best_code][0]
            logger.info(
                f"V2 美股双标: 选 {best_code} "
                f"(近20日均量={best_avg_amount:.0f}), 剔除 {other}"
            )

        return best_code

    def _get_defense_asset(self, cash_return: float) -> str:
        """
        选择防御资产：十年国债若优于货基则用国债，否则退守货基。

        防御资产在 ASSET_POOL 中也可能被选为「风险资产」（如果它排名靠前且
        通过绝对动量门），这不会造成逻辑冲突——此时防御资产同时获得风险仓位
        和防御仓位，权重聚合。
        """
        defense_return = self._calc_asset_return(self.DEFENSE_ASSET)
        if defense_return is not None and defense_return > cash_return:
            return self.DEFENSE_ASSET
        return self.CASH_ANCHOR

    # =========================================================================
    # [优化4] 开盘暴跌过滤
    # =========================================================================

    def _is_open_crash(self, code: str) -> bool:
        """检查当日开盘是否暴跌 > 3%（避免在崩盘日建仓）。"""
        df = self._data_cache.get(code)
        if df is None or len(df) < 2:
            return False
        if "open" not in df.columns:
            return False
        today_open = float(df["open"].iloc[-1])
        prev_close = float(df["close"].iloc[-2])
        if today_open <= 0 or prev_close <= 0:
            return False
        return (today_open - prev_close) / prev_close < -0.03

    @staticmethod
    def _find_rank(code: str, rankings: List[Tuple[str, float]]) -> str:
        """在排名列表中查找 code 的排名序号（仅用于日志）。"""
        for i, (c, _) in enumerate(rankings):
            if c == code:
                return f"#{i + 1}"
        return "N/A"

    # =========================================================================
    # 新鲜度守卫 [修复 #7]
    # =========================================================================

    def _is_fresh(self, code: str) -> bool:
        """
        检查标的的最新缓存数据日期是否等于当前交易日。

        防止停牌/节假日/数据缺失场景下用过期的旧价格做
        止损判断或动量排名。

        Returns:
            True 如果数据新鲜（最后一条 bar 日期匹配今日）
        """
        last_date = self._cache_last_date.get(code, "")
        return bool(last_date) and last_date == self._last_trade_date

    # =========================================================================
    # 数据追加（含时序守卫）
    # =========================================================================

    def _append_data(self, ts_code: str, bar: BarData) -> None:
        """
        缓存 ETF bar 数据（含时序守卫，复用 V1 v1.5.1 模式）。

        时序守卫逻辑：
          新 bar 日期 ≤ 缓存末日期（预热数据包含回测起点之后的「未来」）
          → 截断至新 bar 之前：保留更早历史作预热，砍掉未来部分防前视。
          实盘/模拟模式 bar 单调递增，不会触发。
        """
        bar_date = str(getattr(bar, "trade_date", "") or getattr(bar, "datetime", ""))[:10]

        # 时序守卫
        last = self._cache_last_date.get(ts_code)
        if last and bar_date and bar_date <= last:
            df_old = self._data_cache.get(ts_code)
            if df_old is not None and "trade_date" in df_old.columns:
                kept = df_old[df_old["trade_date"].astype(str).str[:10] < bar_date]
                self._data_cache[ts_code] = kept.reset_index(drop=True)
                self._cache_last_date[ts_code] = (
                    str(kept["trade_date"].iloc[-1])[:10] if len(kept) else ""
                )
                if ts_code not in self._reset_warned:
                    self._reset_warned.add(ts_code)
                    logger.info(
                        f"V2 时序守卫: {ts_code} 截断至 {bar_date} 之前 "
                        f"(保留预热 {len(kept)} 行, 原 {len(df_old)} 行)"
                    )
            else:
                self._data_cache.pop(ts_code, None)
                self._cache_last_date.pop(ts_code, None)
                if ts_code not in self._reset_warned:
                    self._reset_warned.add(ts_code)
                    logger.info(
                        f"V2 时序守卫: {ts_code} 缓存末日 {last} >= "
                        f"新bar {bar_date}，已重置缓存"
                    )

        # 初始化缓存 DataFrame
        if ts_code not in self._data_cache:
            self._data_cache[ts_code] = pd.DataFrame(
                columns=["close", "volume", "amount", "open", "high", "low"]
            )

        # 追加新行
        df = self._data_cache[ts_code]
        new_row = pd.DataFrame([{
            "close": bar.close,
            "volume": bar.volume,
            "amount": getattr(bar, "amount", 0.0),
            "open": getattr(bar, "open", bar.close),
            "high": getattr(bar, "high", bar.close),
            "low": getattr(bar, "low", bar.close),
        }])
        self._data_cache[ts_code] = pd.concat([df, new_row], ignore_index=True)
        if bar_date:
            self._cache_last_date[ts_code] = bar_date

        # 限制缓存大小（双倍动量窗口 + 缓冲）
        max_rows = self.momentum_window * 2 + 100
        if len(self._data_cache[ts_code]) > max_rows:
            self._data_cache[ts_code] = (
                self._data_cache[ts_code].tail(max_rows).reset_index(drop=True)
            )

    def _get_price(self, code: str) -> float:
        """获取最新收盘价"""
        df = self._data_cache.get(code)
        if df is not None and len(df) > 0:
            val = float(df["close"].iloc[-1])
            if np.isnan(val):
                return 0.0
            return val
        return 0.0

    # =========================================================================
    # 信号生成
    # =========================================================================

    def _make_entry_signal(
        self,
        ts_code: str,
        weight: float,
        reason: str = "",
    ) -> Optional[TradingSignal]:
        """生成买入信号（等权分配仓位权重）"""
        price = self._get_price(ts_code)
        if price <= 0:
            return None

        sig = TradingSignal(
            id=str(uuid.uuid4()),
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
        sig.weight = weight  # 由 Broker 读取作仓位分配
        return sig

    def _make_exit_signal(
        self,
        ts_code: str,
        reason: str = "",
        signal_type: SignalType = SignalType.EXIT,
    ) -> Optional[TradingSignal]:
        """生成卖出信号（quantity=0 触发全平）"""
        price = self._get_price(ts_code)
        if price <= 0:
            return None

        return TradingSignal(
            id=str(uuid.uuid4()),
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

    # =========================================================================
    # 参数校验
    # =========================================================================

    def _validate_params(self) -> List[str]:
        """校验策略参数范围"""
        errors: List[str] = []

        mw = self.momentum_window
        if mw < 60 or mw > 504:
            errors.append(f"momentum_window={mw} 应在 [60, 504]（3月~2年）")

        sw = self.skip_window
        if sw < 5 or sw > 63:
            errors.append(f"skip_window={sw} 应在 [5, 63]（1周~1季度）")

        mh = self.max_holdings
        if mh < 1 or mh > 10:
            errors.append(f"max_holdings={mh} 应在 [1, 10]")

        msw = self.max_single_weight
        if msw <= 0 or msw > 1.0:
            errors.append(f"max_single_weight={msw} 应在 (0, 1.0]")

        sl = self.stop_loss
        if sl > 0 or sl < -0.30:
            errors.append(f"stop_loss={sl} 应在 [-0.30, 0]")

        # [修复 #3] 强制 min_history ≥ momentum_window + skip_window
        # 否则预热通过但动量计算全部返回 None → 策略静默失效
        required_min = self.momentum_window + self.skip_window
        if self.min_history < required_min:
            errors.append(
                f"min_history={self.min_history} 必须 ≥ "
                f"momentum_window+skip_window={required_min}"
            )

        return errors

    # =========================================================================
    # 查询接口
    # =========================================================================

    def get_holdings(self) -> List[str]:
        """获取当前持仓标的代码列表"""
        return sorted(self._current_holdings.keys())

    def get_parameters(self) -> dict:
        """获取当前策略参数（用于前端展示）"""
        return {
            "strategy_version": "V2",
            "momentum_window": self.momentum_window,
            "skip_window": self.skip_window,
            "max_holdings": self.max_holdings,
            "max_single_weight": self.max_single_weight,
            "stop_loss": self.stop_loss,
            "use_absolute_momentum": self.use_absolute_momentum,
            "rebalance_frequency": self.rebalance_frequency,
            "asset_pool_size": len(self.ASSET_POOL),
            "current_holding_count": len(self._current_holdings),
            "last_rebalance_month": self._last_rebalance_month,
        }
