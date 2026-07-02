# -*- coding: utf-8 -*-
"""
行业轮动策略 V2

基于申万一级行业多因子评分的行业 ETF 轮动策略：

1. 对 31 个申万一级行业计算多因子综合得分（趋势动量 + 资金量价 + 估值空间）
2. 按得分排名，选出 Top 5 行业
3. 板块去重（同一板块最多 2 个行业）
4. 行业 → ETF 映射（粘性策略）
5. 对比持仓生成买卖信号（含缓冲区和冷却期）

典型用法：
  strategy = IndustryRotationStrategy(
      name="行业轮动V2",
      parameters={...}
  )
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
    申万行业轮动策略 V2。

    策略类型：ROTATION — 基于行业多因子排名的 ETF 轮动。
    继承 BaseStrategy，遵循 on_bar 驱动模式。

    数据流：
      on_bar(bar) → 分离 ETF bar 和行业指数 bar
        → 每 5 个交易日触发 _rebalance()
        → IndustryScoringService.score_all() → 行业排名
        → EtfIndustryMapper.resolve() → ETF 选择
        → 板块去重 + 缓冲区 + 冷却期
        → 生成 ENTRY / EXIT / STOP_LOSS / TAKE_PROFIT 信号
    """

    strategy_type: StrategyType = StrategyType.ROTATION

    # ---- 默认参数 ----
    DEFAULT_PARAMS: Dict[str, Any] = {
        # 策略基础
        "top_n": 5,
        "buffer_rank": 8,
        "rebalance_frequency": 5,
        "cooling_period": 10,
        "min_history": 250,
        # 风控
        "stop_loss": -0.08,
        "take_profit": 0.25,
        "take_profit_rsi": 70.0,
        "max_sector_limit": 2,
        # 入口阈值
        "entry_rsi_max": 75.0,
        "entry_vol_ratio_min": 0.8,
        # 出场阈值
        "exit_vol_ratio_min": 0.5,
        "exit_vol_duration": 3,
        # 板块去重
        "entry_score_gap": 0.05,
        # 因子权重（传给 ScoringConfig）
        "trend_weight": 0.45,
        "volume_weight": 0.30,
        "valuation_weight": 0.25,
        "momentum_windows": [20, 60, 120, 250],
        "momentum_weights": [0.15, 0.25, 0.35, 0.25],
        "momentum_accel_short": 20,
        "momentum_accel_long": 60,
        "rs_window": 60,
        "vol_ratio_short": 5,
        "vol_ratio_long": 60,
        "vol_price_window": 20,
        "turnover_short": 5,
        "turnover_long": 20,
        "pe_percentile_years": 5,
        "pb_percentile_years": 5,
        "pe_expansion_window": 60,
        "valuation_trap_threshold": 0.10,
        "rs_benchmark": "881001.WI",
        # 调试
        "factor_override": {},
        "verbose_logging": False,
    }

    # ---- 子因子权重（在 ScoringConfig 中） ----
    SUB_FACTOR_WEIGHTS: Dict[str, Dict[str, float]] = {
        "trend": {"A1": 0.50, "A2": 0.25, "A3": 0.25},
        "volume": {"B1": 0.40, "B2": 0.35, "B3": 0.25},
        "valuation": {"C1": 0.40, "C2": 0.35, "C3": 0.25},
    }

    def __init__(
        self,
        name: str = "行业轮动V2",
        strategy_type: StrategyType = StrategyType.ROTATION,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        # 合并参数
        merged = dict(self.DEFAULT_PARAMS)
        if parameters:
            merged.update(parameters)
        super().__init__(name=name, strategy_type=strategy_type, parameters=merged)

        # ---- 参数提取 ----
        self.top_n: int = int(merged["top_n"])
        self.buffer_rank: int = int(merged["buffer_rank"])
        self.rebalance_frequency: int = int(merged["rebalance_frequency"])
        self.cooling_period: int = int(merged["cooling_period"])
        self.min_history: int = int(merged["min_history"])
        self.stop_loss: float = float(merged["stop_loss"])
        self.take_profit: float = float(merged["take_profit"])
        self.take_profit_rsi: float = float(merged["take_profit_rsi"])
        self.max_sector_limit: int = int(merged["max_sector_limit"])
        self.entry_rsi_max: float = float(merged["entry_rsi_max"])
        self.entry_vol_ratio_min: float = float(merged["entry_vol_ratio_min"])
        self.exit_vol_ratio_min: float = float(merged["exit_vol_ratio_min"])
        self.exit_vol_duration: int = int(merged["exit_vol_duration"])
        self.entry_score_gap: float = float(merged["entry_score_gap"])
        self.factor_override: Dict = merged.get("factor_override", {}) or {}
        self.verbose_logging: bool = bool(merged.get("verbose_logging", False))

        # ---- 运行时状态 ----
        self._bar_count: int = 0
        self._last_rebalance_date: str = ""
        self._current_holdings: Dict[str, str] = {}  # {ETF代码: 行业名}
        self._industry_data_cache: Dict[str, pd.DataFrame] = {}  # {行业代码: DataFrame}
        self._benchmark_cache: Optional[pd.DataFrame] = None       # 基准指数
        self._prev_scores: Dict[str, float] = {}                   # 上周各行业得分
        self._cooling_list: Dict[str, int] = {}                    # {行业名: 剩余冷却天数}
        self._entry_prices: Dict[str, float] = {}                  # {ETF代码: 买入价} 用于止损止盈
        self._volume_below_threshold_days: Dict[str, int] = {}     # {行业代码: 量比低于阈值天数}

        # ---- 延迟初始化的服务 ----
        self._scoring_service: Optional[IndustryScoringService] = None
        self._etf_mapper: Optional[EtfIndustryMapper] = None
        self._scoring_config: Optional[ScoringConfig] = None

        logger.info(
            f"行业轮动策略初始化: {name}, top_n={self.top_n}, "
            f"buffer={self.buffer_rank}, rebalance={self.rebalance_frequency}"
        )

    # ==================== 生命周期 ====================

    def on_init(self) -> None:
        """校验参数 + 初始化服务 + 加载 ETF 池"""
        # 校验
        errors = self._validate_params()
        if errors:
            raise ValueError(f"策略参数校验失败: {'; '.join(errors)}")

        # 构建 ScoringConfig
        cfg = ScoringConfig()
        for key in [
            "trend_weight", "volume_weight", "valuation_weight",
            "momentum_windows", "momentum_weights",
            "momentum_accel_short", "momentum_accel_long",
            "rs_window", "vol_ratio_short", "vol_ratio_long",
            "vol_price_window", "turnover_short", "turnover_long",
            "pe_percentile_years", "pb_percentile_years",
            "pe_expansion_window", "valuation_trap_threshold",
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

        # 设置 universe（所有 ETF 候选代码）
        self._universe = self._etf_mapper.get_all_etf_codes()

        logger.info(
            f"行业轮动策略 {self.name} 初始化完成, "
            f"行业ETF候选={len(self._universe)}只"
        )

    def on_start(self) -> None:
        """清空状态，准备接收数据"""
        self._bar_count = 0
        self._last_rebalance_date = ""
        self._current_holdings.clear()
        self._industry_data_cache.clear()
        self._benchmark_cache = None
        self._prev_scores.clear()
        self._cooling_list.clear()
        self._entry_prices.clear()
        self._volume_below_threshold_days.clear()
        logger.info(f"行业轮动策略 {self.name} 已启动")

    def on_stop(self) -> None:
        """清理状态"""
        self._current_holdings.clear()
        self._industry_data_cache.clear()
        self._benchmark_cache = None
        self._prev_scores.clear()
        self._cooling_list.clear()
        self._entry_prices.clear()
        self._volume_below_threshold_days.clear()
        logger.info(f"行业轮动策略 {self.name} 已停止")

    # ==================== 核心逻辑 ====================

    def on_bar(self, bar: BarData) -> List[TradingSignal]:
        """
        接收一根 K 线数据。

        两种类型的 bar：
          - ETF bar（ts_code 以 .SH/.SZ 结尾）：缓存价格，用于流动性+交易
          - 行业指数 bar（ts_code 以 .SI 结尾）：缓存行业数据，用于因子计算

        触发条件：bar_count % rebalance_frequency == 0
        """
        signals: List[TradingSignal] = []
        ts_code = bar.ts_code

        try:
            is_industry = ts_code.endswith(".SI")

            if is_industry:
                # ---- 行业指数 bar → 缓存 ----
                self._append_industry_data(ts_code, bar)
            elif ts_code in self._universe or ts_code == self.parameters.get("rs_benchmark", ""):
                # ---- ETF / 基准 bar → 缓存 ----
                self._append_etf_price(ts_code, bar)
            else:
                return signals  # 不在关注范围内的 bar，忽略

            # ---- 调仓日判定 ----
            trade_date = getattr(bar, "trade_date", "") or getattr(bar, "datetime", "")
            if isinstance(trade_date, str) and len(trade_date) >= 10:
                trade_date = trade_date[:10]

            # 同一天不重复调仓
            if self._last_rebalance_date and trade_date == self._last_rebalance_date:
                return signals

            self._bar_count += 1

            if self._bar_count % self.rebalance_frequency == 0:
                signals = self._rebalance()
                self._last_rebalance_date = trade_date

        except Exception as e:
            logger.error(
                f"行业轮动策略 {self.name} on_bar 异常: {ts_code}: {e}", exc_info=True
            )

        return signals

    # ==================== 调仓 ====================

    def _rebalance(self) -> List[TradingSignal]:
        """
        主调仓逻辑：
          1. 行业评分排名
          2. 板块去重
          3. 行业 → ETF 映射
          4. 对比持仓 → 生成信号
          5. 止损止盈检查
        """
        signals: List[TradingSignal] = []

        if not self._scoring_service or self._industry_data_cache is None:
            logger.debug("评分服务或行业数据未就绪，跳过调仓")
            return signals

        try:
            # ---- Step 1: 行业评分排名 ----
            industry_scores = self._scoring_service.score_all(
                industry_data=self._industry_data_cache,
                benchmark_prices=self._benchmark_cache,
                prev_scores=self._prev_scores,
                factor_override=self.factor_override,
            )

            if self.verbose_logging:
                self._log_scores(industry_scores)

            # ---- Step 2: 板块去重 ----
            top_industries = self._apply_sector_dedup(industry_scores)

            if self.verbose_logging:
                self._log_top_selection(top_industries)

            # ---- Step 3: 行业 → ETF 映射 ----
            ranked = [
                (ind.industry_code, ind.industry_name, ind.composite_score, i + 1)
                for i, ind in enumerate(top_industries)
            ]
            holdings_etf_codes = set(self._current_holdings.keys())
            selections = self._etf_mapper.resolve(
                ranked_industries=ranked,
                current_holdings=holdings_etf_codes,
                etf_data_cache=self._data_cache,
            )

            # ---- Step 4: 对比持仓生成信号 ----
            new_etf_set = {s.ts_code for s in selections}

            # 卖出：当前持有但不在新选中的
            for etf_code, industry_name in list(self._current_holdings.items()):
                if etf_code not in new_etf_set:
                    signals.append(self._make_exit_signal(
                        etf_code,
                        industry_name=industry_name,
                        reason=f"排名跌出 Top {self.buffer_rank}",
                        signal_type=SignalType.ENTRY,
                    ))
                    # 加入冷却期
                    self._cooling_list[industry_name] = self.cooling_period

            # 买入：新选中但未持有
            for sel in selections:
                if sel.ts_code not in self._current_holdings:
                    # 冷却期检查
                    cooling_left = self._cooling_list.get(sel.industry_name, 0)
                    if cooling_left > 0:
                        logger.info(
                            f"行业 {sel.industry_name} 在冷却期（剩余 {cooling_left} 天），跳过"
                        )
                        continue

                    # 入场条件检查
                    can_enter, reason = self._check_entry_conditions(sel, industry_scores)
                    if can_enter:
                        signals.append(self._make_entry_signal(
                            sel=sel,
                            reason=f"进入 Top {self.top_n} — {reason}",
                        ))
                    else:
                        logger.info(f"入场条件不满足: {sel.industry_name} — {reason}")

            # 更新持仓记录
            new_holdings = {
                s.ts_code: s.industry_name
                for s in selections
                # 保留冷却期中的旧持仓
            }
            for etf, ind in self._current_holdings.items():
                if etf not in new_holdings:
                    # 持仓未卖出（缓冲区内），保留
                    pass

            # 记录买入价
            for s in selections:
                if s.is_new and s.ts_code not in self._entry_prices:
                    df = self._data_cache.get(s.ts_code)
                    if df is not None and len(df) > 0:
                        self._entry_prices[s.ts_code] = float(df["close"].iloc[-1])

            self._current_holdings = {
                s.ts_code: s.industry_name
                for s in selections
            }

            # ---- Step 5: 止损止盈检查 ----
            for etf_code in list(self._current_holdings.keys()):
                exit_signal = self._check_stop_take_profit(etf_code)
                if exit_signal:
                    signals.append(exit_signal)
                    # 止损/止盈后加入冷却期
                    if etf_code in self._current_holdings:
                        self._cooling_list[self._current_holdings[etf_code]] = self.cooling_period
                        del self._current_holdings[etf_code]
                    if etf_code in self._entry_prices:
                        del self._entry_prices[etf_code]

            # ---- 更新状态 ----
            # 保存本周得分用于下周的边际变化计算
            self._prev_scores = {s.industry_code: s.composite_score for s in industry_scores}

            # 递减冷却期
            for ind in list(self._cooling_list.keys()):
                self._cooling_list[ind] -= 1
                if self._cooling_list[ind] <= 0:
                    del self._cooling_list[ind]

            if signals:
                logger.info(
                    f"策略 {self.name} 调仓: {len(signals)} 个信号, "
                    f"持仓 → {sorted(self._current_holdings.keys())}"
                )

        except Exception as e:
            logger.error(f"策略 {self.name} 调仓异常: {e}", exc_info=True)

        return signals

    # ==================== 板块去重 ====================

    def _apply_sector_dedup(
        self,
        industry_scores: List[IndustryScore],
    ) -> List[IndustryScore]:
        """
        板块三层决策去重：
          L1: 得分差距 > entry_score_gap → 保留高分
          L2: 边际变化 → 要加速的、不要减速的
          L3: 因子余弦相似度 → 同一故事不重复下注
        """
        selected: List[IndustryScore] = []
        sector_counts: Dict[str, int] = {}

        for candidate in industry_scores:
            sector = get_sector(candidate.industry_name)

            if sector_counts.get(sector, 0) < self.max_sector_limit:
                selected.append(candidate)
                sector_counts[sector] = sector_counts.get(sector, 0) + 1
                if len(selected) >= self.buffer_rank:
                    break
            else:
                # 同一板块已满 → 检查是否替换
                worst_in_sector = self._find_worst_in_sector(selected, sector)
                if worst_in_sector and self._should_replace(worst_in_sector, candidate):
                    logger.info(
                        f"板块去重替换: {worst_in_sector.industry_name}"
                        f"({worst_in_sector.composite_score:.4f})"
                        f" → {candidate.industry_name}"
                        f"({candidate.composite_score:.4f})"
                    )
                    selected.remove(worst_in_sector)
                    selected.append(candidate)

        return selected[:self.buffer_rank]

    @staticmethod
    def _find_worst_in_sector(
        selected: List[IndustryScore],
        sector: str,
    ) -> Optional[IndustryScore]:
        """在已选行业中找指定板块内得分最低的"""
        sector_entries = [s for s in selected if get_sector(s.industry_name) == sector]
        if not sector_entries:
            return None
        return min(sector_entries, key=lambda s: s.composite_score)

    def _should_replace(
        self,
        incumbent: IndustryScore,
        challenger: IndustryScore,
    ) -> bool:
        """
        三层决策：判断是否用 challenger 替换 incumbent。
        """
        # L1: 得分差距
        gap = abs(incumbent.composite_score - challenger.composite_score)
        if gap > self.entry_score_gap:
            return challenger.composite_score > incumbent.composite_score

        # L2: 边际变化
        inc_change = incumbent.score_change
        chg_change = challenger.score_change
        if chg_change > 0 and inc_change < 0:
            return True  # 替换：要加速的
        if chg_change < 0 and inc_change > 0:
            return False  # 不换

        # L3: 因子相似度 > 0.9 → 保留高分
        fv1 = incumbent.factor_vector
        fv2 = challenger.factor_vector
        if fv1 is not None and fv2 is not None and len(fv1) > 0 and len(fv2) > 0:
            similarity = float(
                np.dot(fv1, fv2) / (np.linalg.norm(fv1) * np.linalg.norm(fv2) + 1e-12)
            )
            if similarity > 0.9:
                return challenger.composite_score > incumbent.composite_score

        return False  # 默认不换

    # ==================== 入场/出场条件 ====================

    def _check_entry_conditions(
        self,
        sel: EtfSelection,
        industry_scores: List[IndustryScore],
    ) -> Tuple[bool, str]:
        """
        入场 AND 条件检查：
          1. 排名在前 top_n
          2. 趋势确认：R20 > 0
          3. 量能确认：B1 > entry_vol_ratio_min
          4. RSI < entry_rsi_max
        """
        # 找到该行业的评分
        score = next(
            (s for s in industry_scores if s.industry_code == sel.industry_code),
            None,
        )
        if score is None:
            return False, "未找到行业评分"

        # 1. 排名
        if sel.rank > self.top_n:
            return False, f"排名 #{sel.rank} > {self.top_n}"

        # 2. 趋势：A1_raw > 0
        a1 = score.factors.get("A1", 0.0)
        if a1 <= 0:
            return False, f"短期动量 A1={a1:.4f} ≤ 0"

        # 3. 量能：B1_raw > entry_vol_ratio_min
        b1 = score.factors.get("B1", 0.0)
        if b1 < self.entry_vol_ratio_min:
            return False, f"量比 B1={b1:.2f} < {self.entry_vol_ratio_min}"

        # 4. RSI
        if score.rsi > self.entry_rsi_max:
            return False, f"RSI={score.rsi:.1f} > {self.entry_rsi_max}"

        return True, (
            f"排名 #{sel.rank} | A1={a1:.3f} | B1={b1:.2f} | RSI={score.rsi:.1f}"
        )

    def _check_stop_take_profit(self, etf_code: str) -> Optional[TradingSignal]:
        """
        出场 OR 条件：止损 / 止盈。

        Returns:
            TradingSignal 或 None
        """
        df = self._data_cache.get(etf_code)
        if df is None or len(df) == 0:
            return None

        current_price = float(df["close"].iloc[-1])
        entry_price = self._entry_prices.get(etf_code)
        if entry_price is None or entry_price <= 0:
            return None

        pnl_pct = (current_price / entry_price - 1.0)
        industry_name = self._current_holdings.get(etf_code, "")

        # 止损
        if pnl_pct <= self.stop_loss:
            return self._make_exit_signal(
                etf_code,
                industry_name=industry_name,
                reason=f"止损 — 亏损 {pnl_pct:.1%} ≥ {self.stop_loss:.1%}",
                signal_type=SignalType.STOP_LOSS,
            )

        # 止盈（需同时满足 RSI > 阈值）
        if pnl_pct >= self.take_profit:
            closes = df["close"].values.astype(float)
            rsi = IndustryScoringService._rsi(closes, 14)
            if rsi > self.take_profit_rsi:
                return self._make_exit_signal(
                    etf_code,
                    industry_name=industry_name,
                    reason=f"止盈 — 盈利 {pnl_pct:.1%} ≥ {self.take_profit:.1%} 且 RSI={rsi:.1f} > {self.take_profit_rsi}",
                    signal_type=SignalType.TAKE_PROFIT,
                )

        return None

    # ==================== 数据追加 ====================

    def _append_etf_price(self, ts_code: str, bar: BarData) -> None:
        """将 ETF 或基准的 bar 追加到价格缓存（继承自 BaseStrategy 的 _data_cache）"""
        if ts_code not in self._data_cache:
            self._data_cache[ts_code] = pd.DataFrame(columns=["close", "volume", "amount"])
        df = self._data_cache[ts_code]
        new_row = pd.DataFrame([{
            "close": bar.close,
            "volume": bar.volume,
            "amount": bar.amount,
        }])
        self._data_cache[ts_code] = pd.concat([df, new_row], ignore_index=True)

        # 限制缓存大小
        max_rows = max(self.parameters.get("momentum_windows", [250])) * 3
        if len(self._data_cache[ts_code]) > max_rows:
            self._data_cache[ts_code] = (
                self._data_cache[ts_code].tail(max_rows).reset_index(drop=True)
            )

    def _append_industry_data(self, ts_code: str, bar: BarData) -> None:
        """将行业指数 bar 追加到行业数据缓存"""
        if ts_code not in self._industry_data_cache:
            self._industry_data_cache[ts_code] = pd.DataFrame(
                columns=["close", "vol", "amount", "pe", "pb", "float_mv", "pct_change", "name"]
            )

        df = self._industry_data_cache[ts_code]
        name = getattr(bar, "name", "") or ""

        # pct_change: 从 BarData 可能不包含，从 close 估算
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
            "name": name,
        }])
        self._industry_data_cache[ts_code] = pd.concat([df, new_row], ignore_index=True)

        # 限制缓存大小
        max_rows = (self.parameters.get("pe_percentile_years", 5) * 252) + 100
        if len(self._industry_data_cache[ts_code]) > max_rows:
            self._industry_data_cache[ts_code] = (
                self._industry_data_cache[ts_code].tail(max_rows).reset_index(drop=True)
            )

    # ==================== 信号生成 ====================

    def _make_entry_signal(
        self,
        sel: EtfSelection,
        reason: str,
        confidence: float = 0.80,
    ) -> TradingSignal:
        """生成入场信号"""
        df = self._data_cache.get(sel.ts_code)
        price = float(df["close"].iloc[-1]) if df is not None and len(df) > 0 else 0.0

        return TradingSignal(
            id=self._gen_id(),
            strategy_id=self.name,
            strategy_name=self.name,
            ts_code=sel.ts_code,
            signal_type=SignalType.ENTRY,
            direction=SignalDirection.LONG,
            price=price,
            quantity=100,
            amount=price * 100 if price > 0 else 0,
            confidence=confidence,
            reason=f"{sel.industry_name}: {reason}",
            timestamp=datetime.now(),
        )

    def _make_exit_signal(
        self,
        etf_code: str,
        industry_name: str,
        reason: str,
        signal_type: SignalType = SignalType.ENTRY,
        confidence: float = 0.80,
    ) -> TradingSignal:
        """生成出场信号"""
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
            quantity=100,
            amount=price * 100 if price > 0 else 0,
            confidence=confidence,
            reason=f"{industry_name}: {reason}",
            timestamp=datetime.now(),
        )

    @staticmethod
    def _gen_id() -> str:
        import uuid
        return str(uuid.uuid4())

    # ==================== 参数校验 ====================

    def _validate_params(self) -> List[str]:
        """校验策略参数，返回错误列表"""
        errors: List[str] = []
        if self.top_n < 1 or self.top_n > 15:
            errors.append(f"top_n={self.top_n} 应在 [1, 15]")
        if self.buffer_rank <= self.top_n:
            errors.append(f"buffer_rank={self.buffer_rank} 应 > top_n={self.top_n}")
        if self.buffer_rank > 15:
            errors.append(f"buffer_rank={self.buffer_rank} 应 ≤ 15")
        if self.rebalance_frequency < 1 or self.rebalance_frequency > 20:
            errors.append(f"rebalance_frequency={self.rebalance_frequency} 应在 [1, 20]")
        if self.cooling_period < 0 or self.cooling_period > 60:
            errors.append(f"cooling_period={self.cooling_period} 应在 [0, 60]")
        if self.stop_loss > 0 or self.stop_loss < -0.30:
            errors.append(f"stop_loss={self.stop_loss} 应在 [-0.30, 0]")
        if self.take_profit < 0.10 or self.take_profit > 1.00:
            errors.append(f"take_profit={self.take_profit} 应在 [0.10, 1.00]")
        tw = self.parameters.get("trend_weight", 0)
        vw = self.parameters.get("volume_weight", 0)
        vlw = self.parameters.get("valuation_weight", 0)
        if abs(tw + vw + vlw - 1.0) > 0.01:
            errors.append(f"大类权重之和应为1.0: trend={tw} + volume={vw} + valuation={vlw} = {tw+vw+vlw:.3f}")
        return errors

    # ==================== 查询接口 ====================

    def get_parameters(self) -> dict:
        """获取当前策略参数（用于前端展示）"""
        return {
            "top_n": self.top_n,
            "buffer_rank": self.buffer_rank,
            "rebalance_frequency": self.rebalance_frequency,
            "cooling_period": self.cooling_period,
            "min_history": self.min_history,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "take_profit_rsi": self.take_profit_rsi,
            "max_sector_limit": self.max_sector_limit,
            "trend_weight": self.parameters.get("trend_weight", 0.45),
            "volume_weight": self.parameters.get("volume_weight", 0.30),
            "valuation_weight": self.parameters.get("valuation_weight", 0.25),
            "universe_size": len(self._universe),
        }

    def get_current_scores(self) -> Dict[str, float]:
        """获取最新一期各行业综合得分"""
        return dict(self._prev_scores) if self._prev_scores else {}

    def get_holdings(self) -> List[str]:
        """获取当前持仓 ETF 列表"""
        return sorted(self._current_holdings.keys())

    # ==================== 日志辅助 ====================

    def _log_scores(self, scores: List[IndustryScore]) -> None:
        """输出详细评分日志"""
        lines = [f"\n{'='*80}", f"行业轮动评分 — Top 10"]
        for i, s in enumerate(scores[:10]):
            lines.append(
                f"  #{i+1:2d} {s.industry_name:8s} "
                f"综合={s.composite_score:.4f} "
                f"趋势={s.trend_score:.4f} "
                f"量价={s.volume_score:.4f} "
                f"估值={s.valuation_score:.4f} "
                f"Δ={s.score_change:+.4f} "
                f"RSI={s.rsi:.0f}"
            )
        lines.append(f"{'='*80}")
        logger.info("\n".join(lines))

    def _log_top_selection(self, top_industries: List[IndustryScore]) -> None:
        """输出去重后的选中行业"""
        lines = ["去重后选中:"]
        for i, s in enumerate(top_industries[:self.top_n]):
            sector = get_sector(s.industry_name)
            lines.append(f"  #{i+1} {s.industry_name} [{sector}] 得分={s.composite_score:.4f}")
        logger.info("\n".join(lines))
