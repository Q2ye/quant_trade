# -*- coding: utf-8 -*-
"""
ETF 行业轮动策略

基于多时间窗口动量得分的行业 ETF 轮动策略：

1. 对候选 ETF 池中每只 ETF，计算多个回溯窗口的收益率（动量）
2. 按权重加权合成综合动量得分
3. 持有得分最高的 Top N 只 ETF
4. 定期（如每周）调仓：卖出排名掉出 Top N 的，买入新进入 Top N 的

典型用法：
  universe = ["510050.SH", "510300.SH", "510500.SH", "159915.SZ", "512880.SH"]
  # 分别代表：上证50、沪深300、中证500、创业板、证券ETF
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Set

import numpy as np
import pandas as pd

from core.engines.types.entities import BarData
from modules.strategy.constants import StrategyType, SignalDirection, SignalType
from modules.strategy.models import TradingSignal
from modules.strategy.strategies.base.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class EtfIndustryRotationStrategy(BaseStrategy):
    """
    ETF 行业轮动策略。

    策略类型：ROTATION — 基于排名驱动的轮动调仓。
    继承 BaseStrategy，遵循 on_bar 驱动模式。
    """

    # ---- 默认参数 ----
    DEFAULT_PARAMS = {
        "universe": [
            "510050.SH",   # 上证50
            "510300.SH",   # 沪深300
            "510500.SH",   # 中证500
            "159915.SZ",   # 创业板
            "512880.SH",   # 证券ETF
            "512100.SH",   # 中证1000
            "159845.SZ",   # 中证1000ETF
            "512690.SH",   # 酒ETF
            "516160.SH",   # 新能源ETF
            "512480.SH",   # 半导体ETF
        ],
        "momentum_windows": [20, 60, 120],
        "rank_weights": [0.3, 0.4, 0.3],
        "top_n": 3,
        "rebalance_frequency": 5,
        "min_history": 120,
    }

    def __init__(
        self,
        name: str = "ETF行业轮动策略",
        strategy_type: StrategyType = StrategyType.TECHNICAL,  # 运行时由 Registry 覆盖
        parameters: Optional[Dict] = None,
    ):
        merged = dict(self.DEFAULT_PARAMS)
        if parameters:
            merged.update(parameters)
        super().__init__(name=name, strategy_type=strategy_type, parameters=merged)

        # ---- 参数 ----
        self._etf_universe: List[str] = merged["universe"]
        self.momentum_windows: List[int] = merged["momentum_windows"]
        self.rank_weights: List[float] = merged["rank_weights"]
        self.top_n: int = merged["top_n"]
        self.rebalance_frequency: int = merged["rebalance_frequency"]
        self.min_history: int = merged["min_history"]

        # ---- 运行时状态 ----
        self._bar_count: int = 0
        self._last_rebalance_date: str = ''  # v2.4: 按交易日调仓，避免多 ETF 重复触发
        self._current_holdings: Set[str] = set()
        # _score_history 缓存每只 ETF 每个窗口的最新动量值，避免循环内重复计算
        self._score_cache: Dict[str, Dict[int, float]] = {}

        logger.info(
            f"ETF 行业轮动策略初始化: {name}, universe={len(self._etf_universe)} 只, "
            f"top_n={self.top_n}, rebalance={self.rebalance_frequency}"
        )

    # ==================== 生命周期 ====================

    def on_init(self) -> None:
        """策略初始化：校验参数 + 加载股票池"""
        # 校验参数
        if len(self.momentum_windows) != len(self.rank_weights):
            raise ValueError(
                f"动量窗口数 ({len(self.momentum_windows)}) 与权重数 "
                f"({len(self.rank_weights)}) 必须一致"
            )
        if abs(sum(self.rank_weights) - 1.0) > 1e-6:
            raise ValueError(f"排名权重之和必须为 1，当前: {sum(self.rank_weights)}")
        if self.top_n < 1 or self.top_n > len(self._etf_universe):
            raise ValueError(
                f"top_n ({self.top_n}) 必须在 1 到 {len(self._etf_universe)} 之间"
            )

        self._universe = self._etf_universe
        logger.info(f"ETF 行业轮动策略 {self.name} 初始化完成, universe={len(self._etf_universe)} 只")

    def on_start(self) -> None:
        """策略启动"""
        self._bar_count = 0
        self._last_rebalance_date = ''
        self._current_holdings.clear()
        logger.info(f"ETF 行业轮动策略 {self.name} 已启动")

    def on_stop(self) -> None:
        """策略停止"""
        self._current_holdings.clear()
        self._score_cache.clear()
        logger.info(f"ETF 行业轮动策略 {self.name} 已停止")

    # ==================== 核心逻辑 ====================

    def on_bar(self, bar: BarData) -> List[TradingSignal]:
        """
        接收一根 ETF 日线 K 线数据。

        每根 bar 追加到对应 ETF 的价格缓存中。
        当 bar_count % rebalance_frequency == 0 时触发调仓。
        """
        signals: List[TradingSignal] = []
        ts_code = bar.ts_code

        try:
            # 只处理 universe 内的 ETF
            if ts_code not in self._etf_universe:
                return signals

            # 追加收盘价到缓存
            self._append_price(ts_code, bar)

            # v2.4: 按交易日判断调仓（而非按 bar 计数，避免多 ETF 重复触发）
            trade_date = getattr(bar, 'trade_date', '') or getattr(bar, 'datetime', '')
            if isinstance(trade_date, str) and len(trade_date) >= 10:
                trade_date = trade_date[:10]  # YYYY-MM-DD

            self._bar_count += 1
            days_since = self._bar_count  # fallback

            if hasattr(self, '_last_rebalance_date') and self._last_rebalance_date:
                if trade_date == self._last_rebalance_date:
                    return []  # v2.4: 同一天不重复调仓

            # 是否触发调仓
            if self._bar_count % self.rebalance_frequency == 0:
                signals = self._rebalance()
                self._last_rebalance_date = trade_date  # v2.4: 记录最后调仓日期

        except Exception as e:
            logger.error(f"ETF 轮动策略 {self.name} on_bar 异常: {ts_code}: {e}")

        return signals

    # ==================== 动量评分 ====================

    def _calculate_momentum(self, ts_code: str) -> Optional[Dict[int, float]]:
        """
        计算单只 ETF 各窗口的动量（收益百分比）。

        Returns:
            {window_days: momentum_ratio, ...} 或 None（数据不足）
        """
        df = self._data_cache.get(ts_code)
        if df is None or len(df) < max(self.momentum_windows) + 1:
            return None

        closes = df["close"].values
        scores = {}
        for window in self.momentum_windows:
            if len(closes) < window + 1:
                scores[window] = None
                continue
            prev = closes[-window - 1]
            curr = closes[-1]
            if prev > 0:
                scores[window] = float(curr / prev - 1.0)
            else:
                scores[window] = 0.0
        return scores

    def _compute_composite_score(self, momentum: Dict[int, float]) -> float:
        """
        加权合成综合动量得分。
        缺失的窗口视为 0。
        """
        total = 0.0
        for window, weight in zip(self.momentum_windows, self.rank_weights):
            val = momentum.get(window)
            if val is not None:
                total += val * weight
        return total

    def _rank_etfs(self) -> List[str]:
        """
        对所有 universe ETF 计算综合得分并排名。

        Returns:
            按得分降序排列的 ETF 代码列表
        """
        scored: List[tuple] = []  # [(ts_code, composite_score), ...]

        for ts_code in self._etf_universe:
            momentum = self._calculate_momentum(ts_code)
            if momentum is None:
                continue
            composite = self._compute_composite_score(momentum)
            self._score_cache[ts_code] = momentum
            scored.append((ts_code, composite))

        # 按得分降序
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scored]

    # ==================== 调仓信号 ====================

    def _rebalance(self) -> List[TradingSignal]:
        """
        执行调仓：计算排名 → 对比持仓 → 生成买卖信号。
        """
        import uuid

        signals: List[TradingSignal] = []

        try:
            ranked = self._rank_etfs()
            new_top_n = set(ranked[:self.top_n])

            # 如果还没有任何持仓（首次调仓），全量买入 Top N
            if not self._current_holdings:
                for ts_code in new_top_n:
                    signals.append(self._make_signal(
                        ts_code, SignalDirection.LONG, SignalType.ENTRY,
                        reason=f"首次建仓 — 排名 {ranked.index(ts_code) + 1}/{len(ranked)}",
                    ))
                self._current_holdings = new_top_n
                logger.info(
                    f"策略 {self.name} 首次建仓: {len(signals)} 只 ETF → {sorted(new_top_n)}"
                )
                return signals

            # 卖出：当前持有但不在新 Top N 中
            to_sell = self._current_holdings - new_top_n
            for ts_code in to_sell:
                signals.append(self._make_signal(
                    ts_code, SignalDirection.CLOSE_LONG, SignalType.ENTRY,
                    reason=f"排名跌出 Top {self.top_n}",
                ))

            # 买入：新进入 Top N 但未持有
            to_buy = new_top_n - self._current_holdings
            for ts_code in to_buy:
                rank = ranked.index(ts_code) + 1 if ts_code in ranked else -1
                signals.append(self._make_signal(
                    ts_code, SignalDirection.LONG, SignalType.ENTRY,
                    reason=f"进入 Top {self.top_n} — 排名 {rank}/{len(ranked)}",
                ))

            # 更新持仓
            self._current_holdings = new_top_n

            if signals:
                logger.info(
                    f"策略 {self.name} 调仓: 卖出 {len(to_sell)} 只, "
                    f"买入 {len(to_buy)} 只, 持有 → {sorted(new_top_n)}"
                )

        except Exception as e:
            logger.error(f"策略 {self.name} 调仓异常: {e}", exc_info=True)

        return signals

    # ==================== 辅助 ====================

    def _append_price(self, ts_code: str, bar: BarData) -> None:
        """将一根 bar 追加到对应 ETF 的价格缓存中。"""
        if ts_code not in self._data_cache:
            self._data_cache[ts_code] = pd.DataFrame(columns=["close", "volume"])
        df = self._data_cache[ts_code]
        new_row = pd.DataFrame([{
            "close": bar.close,
            "volume": bar.volume,
        }])
        self._data_cache[ts_code] = pd.concat([df, new_row], ignore_index=True)

        # 限制缓存大小
        max_rows = max(self.momentum_windows) * 3
        if len(self._data_cache[ts_code]) > max_rows:
            self._data_cache[ts_code] = (
                self._data_cache[ts_code].tail(max_rows).reset_index(drop=True)
            )

    def _make_signal(
        self,
        ts_code: str,
        direction: SignalDirection,
        signal_type: SignalType,
        reason: str,
        confidence: float = 0.8,
    ) -> TradingSignal:
        """创建交易信号。"""
        import uuid

        # 获取最新价格
        df = self._data_cache.get(ts_code)
        price = float(df["close"].iloc[-1]) if df is not None and len(df) > 0 else 0.0

        # 估算数量（等权重分配）
        # 实际金额由 Broker/Sizer 计算，此处给出基础数量
        quantity = 100  # 最小单位

        return TradingSignal(
            id=str(uuid.uuid4()),
            strategy_id=self.name,
            strategy_name=self.name,
            ts_code=ts_code,
            signal_type=signal_type,
            direction=direction,
            price=price,
            quantity=quantity,
            amount=price * quantity if price > 0 else 0,
            confidence=confidence,
            reason=reason,
            timestamp=datetime.now(),
        )

    # ==================== 查询接口 ====================

    def get_parameters(self) -> dict:
        """获取当前策略参数（用于前端展示）。"""
        return {
            "universe": self._etf_universe,
            "momentum_windows": self.momentum_windows,
            "rank_weights": self.rank_weights,
            "top_n": self.top_n,
            "rebalance_frequency": self.rebalance_frequency,
            "min_history": self.min_history,
        }

    def get_current_scores(self) -> Dict[str, float]:
        """获取最新一期各 ETF 的综合得分（用于调试/监控）。"""
        return {
            ts_code: self._compute_composite_score(momentum)
            for ts_code, momentum in self._score_cache.items()
        }

    def get_holdings(self) -> List[str]:
        """获取当前持仓 ETF 列表。"""
        return sorted(self._current_holdings)
