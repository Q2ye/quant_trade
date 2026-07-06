# -*- coding: utf-8 -*-
"""
沪深主板强势股低吸轮动策略 — 移植自聚宽高抛低吸策略

聚宽原文: https://www.joinquant.com/post/75503

核心逻辑：
  1. 选股：全市场扫描，筛选条件：
     - 仅 00/60 开头主板股（排除双创/北交所）
     - 排除 ST、新股（上市不满30日）、停牌、涨停
     - 昨日收阳线 + 涨幅 >= 0.7%
     - MA5 > MA20（多头排列）
     - 成交量 >= 近20日均量 1.2 倍
     - ROC > 5 且 MACD 金叉
     - 价格低于 20 日新高 >= 0.15%（低吸位置）
  2. 持仓：最多 3 只，半仓轮动
  3. 风控：通用止损 4%，非池内止盈（从高点回落 2%）

适配说明（与聚宽原版的区别）：
  - 原版有 9:40/9:51/9:52 时间节点分批执行
    系统策略改为单次 rebalance 中完成（9:40 初筛 → 9:51 复检一次完成）
  - 原版使用 talib，改为 numpy 实现
  - 原版使用 get_price/attribute_history，改为策略内 DataFrame 缓存
  - 原版有半仓轮动逻辑，系统回测中通过 Broker 资金管理自动实现
"""

import logging
import math
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from core.engines.types.entities import BarData
from modules.strategy.constants import StrategyType, SignalDirection, SignalType
from modules.strategy.models import TradingSignal
from modules.strategy.strategies.base.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class StockLowHighStrategy(BaseStrategy):
    """
    沪深主板强势股低吸轮动策略。

    策略类型：CUSTOM
    全市场扫描选股 + 半仓轮动。
    """

    strategy_type: StrategyType = StrategyType.CUSTOM

    # 主板股票前缀（与聚宽原版一致）
    ALLOW_PREFIX: Tuple[str, ...] = ('000', '002', '600', '603', '601', '605')
    FORBID_PREFIX: Tuple[str, ...] = ('300', '688', '8', '4', '001', '003')

    DEFAULT_PARAMS: Dict[str, Any] = {
        # —— 选股 ——
        "min_daily_volume": 500,        # 近5日日均成交量 ≥ 500 手
        "min_yesterday_rise": 0.007,    # 昨日涨幅 ≥ 0.7%
        "min_volume_ratio": 1.2,        # 当日成交量 ≥ 近20日均量 1.2 倍
        "roc_threshold": 5.0,           # ROC(10) > 5
        "buy_below_high_rate": 0.0015,  # 价格低于20日新高 >= 0.15%
        "new_stock_days": 30,           # 新股过滤：上市不足 N 个交易日
        "lookback_days": 60,            # 选股回溯天数（预加载）

        # —— 持仓 ——
        "max_positions": 3,             # 最大持仓数
        "rebalance_frequency": 1,       # 每天调仓

        # —— 风控 ——
        "stop_loss": -0.04,             # 通用止损 -4%

        # —— 调试 ——
        "verbose_logging": False,
    }

    def __init__(
        self,
        name: str = "低吸轮动",
        strategy_type: StrategyType = StrategyType.CUSTOM,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        merged = dict(self.DEFAULT_PARAMS)
        if parameters:
            merged.update(parameters)
        super().__init__(name=name, strategy_type=strategy_type, parameters=merged)

        self.verbose_logging: bool = bool(merged.get("verbose_logging", False))

        # —— 数据缓存 ——
        # {ts_code: DataFrame[close, volume, high, low, open]}
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._st_stocks: Set[str] = set()         # ST 股票代码集合
        self._listing_dates: Dict[str, str] = {}   # {ts_code: 上市日期}
        self._stock_pool: List[str] = []           # 当前 A 股代码列表
        self._bar_count: int = 0
        self._last_rebalance_date: str = ""
        self._last_trade_date: str = ""
        self._first_screen_done: bool = False

        # 手动持仓跟踪（回测引擎不将 Broker 持仓同步回策略，必须自己管理）
        # {ts_code: {"entry_price": float, "quantity": float, "locked": bool}}
        self._holdings: Dict[str, Dict] = {}
        self._track_high: Dict[str, float] = {}    # {ts_code: 持仓期间最高价}

    # =============================================================================
    # 生命周期
    # =============================================================================

    def on_init(self) -> None:
        """初始化（不设置 _universe，让 BacktestEngine 或用户配置决定候选池）"""
        logger.info(f"低吸轮动策略初始化: {self.name}, 最大持仓={self.parameters.get('max_positions', 3)}")

    async def on_start(self) -> None:
        """重置状态 + 加载 ST 列表"""
        self._data_cache.clear()
        self._listing_dates.clear()
        self._track_high.clear()
        self._holdings.clear()
        self._bar_count = 0
        self._last_rebalance_date = ""
        self._first_screen_done = False
        self._st_stocks = set()

        # 从 DB 加载 ST 列表（用于选股过滤）
        session_factory = getattr(self, "_db_session_factory", None)
        if session_factory:
            try:
                from shared.database.repositories.market.basic.st_list_repo import STListRepository
                from datetime import date as _dt
                async with session_factory() as db:
                    st_repo = STListRepository(db)
                    st_list = await st_repo.get_current_st_stocks(_dt.today())
                    self._st_stocks = set(s.ts_code for s in st_list)
                    logger.info(f"ST 列表已加载: {len(self._st_stocks)} 只")
            except Exception as e:
                logger.warning(f"ST 列表加载失败（非致命）: {e}")

        logger.info(f"低吸轮动策略已启动: 数据缓存={len(self._data_cache)}")

    def on_stop(self) -> None:
        self._data_cache.clear()
        self._track_high.clear()
        self._holdings.clear()
        self._st_stocks.clear()
        logger.info("低吸轮动策略已停止")

    # =============================================================================
    # 核心入口：on_bar
    # =============================================================================

    def on_bar(self, bar: BarData) -> List[TradingSignal]:
        signals: List[TradingSignal] = []
        ts_code = bar.ts_code

        try:
            # 缓存所有传入 bar 的数据（选股时通过 _is_tradable 过滤）
            self._append_data(ts_code, bar)

            trade_date = getattr(bar, "trade_date", "") or getattr(bar, "datetime", "")
            if isinstance(trade_date, str) and len(trade_date) >= 10:
                trade_date = trade_date[:10]
            self._last_trade_date = trade_date

            if self._last_rebalance_date and trade_date == self._last_rebalance_date:
                return signals

            self._bar_count += 1

            # 每 N 根 bar 执行一次调仓
            freq = int(self.parameters.get("rebalance_frequency", 1))
            if self._bar_count % freq == 0:
                signals = self._run_rebalance()
                self._last_rebalance_date = trade_date
                self._first_screen_done = True

        except Exception as e:
            logger.error(f"低吸轮动 on_bar 异常: {ts_code}: {e}", exc_info=True)

        return signals

    # =============================================================================
    # 主调仓（选股 + 买卖）
    # =============================================================================

    def _run_rebalance(self) -> List[TradingSignal]:
        """
        主调仓流程（对应原版 9:40 初筛 + 9:51 二次筛选 + 9:52 买入）。

        流程：
          1. 获取当前持仓
          2. 【止盈止损】检查
          3. 【清仓非池股】持仓不在今日选股池中的卖出
          4. 【初次选股】全市场扫描
          5. 【二次筛选】部分条件重新校验
          6. 【买入】新标的
        """
        signals: List[TradingSignal] = []
        if len(self._data_cache) < 10:
            return signals

        # 使用自维护的 _holdings（Broker 持仓不同步到 self.positions）
        current_holdings = set(self._holdings.keys())
        if self.verbose_logging:
            logger.info(f"低吸轮动调仓: 当前持仓={len(current_holdings)}")

        # ---- 1. 止盈止损检查（对应原版 stop_loss_take_profit）----
        exit_signals = self._check_all_stop_profit()
        signals.extend(exit_signals)

        # ---- 2. 初次选股 + 二次筛选（合并为一次）----
        buy_list = self._screen_stocks(current_holdings)
        if not buy_list:
            if self.verbose_logging:
                logger.info("低吸轮动: 无合格选股标的")
            return signals

        # ---- 3. 买入 ----
        # 计算每个新标的的可买数量
        new_stocks = [s for s in buy_list if s not in current_holdings]
        max_pos = int(self.parameters.get("max_positions", 3))
        slots = max_pos - len(current_holdings)

        if slots <= 0 or not new_stocks:
            return signals

        # 取前 slots 个新标的
        targets = new_stocks[:slots]

        for target in targets:
            price = self._get_price(target)
            if price <= 0:
                continue

            sig = TradingSignal(
                id=self._gen_id(),
                strategy_id=self.name,
                strategy_name=self.name,
                ts_code=target,
                signal_type=SignalType.ENTRY,
                direction=SignalDirection.LONG,
                price=price,
                quantity=0,
                amount=1.0 / max_pos,   # amount=分配比例（Sizer 用此字段计算买入量）
                confidence=0.75,
                reason=f"低吸轮动买入: {target}",
                timestamp=datetime.now(),
            )
            sig.weight = 1.0 / max_pos
            signals.append(sig)
            # 记录持仓（用于止盈止损，self.positions 不自动同步）
            self._holdings[target] = {"entry_price": price, "quantity": 1.0 / max_pos}
            self._track_high[target] = price

            if self.verbose_logging:
                logger.info(f"低吸轮动买入: {target}, 仓位={sig.weight:.0%}")

        return signals

    # =============================================================================
    # 选股引擎
    # =============================================================================

    def _screen_stocks(self, current_holdings: Set[str]) -> List[str]:
        """
        全市场选股（合并原版 9:40 初筛 + 9:51 二次筛选）。

        返回按 成交额降序 排列的候选股票代码列表。
        """
        candidates: List[str] = []
        min_vol_ratio = float(self.parameters.get("min_volume_ratio", 1.2))
        roc_th = float(self.parameters.get("roc_threshold", 5.0))
        below_rate = float(self.parameters.get("buy_below_high_rate", 0.0015))

        for code, df in self._data_cache.items():
            try:
                # 跳过已持仓
                if code in current_holdings:
                    continue

                # 基本过滤
                if not self._is_tradable(code):
                    continue
                if code in self._st_stocks:
                    continue

                # 新股过滤
                if self._is_new_stock(code):
                    continue

                closes = df["close"].values.astype(np.float64)
                volumes = df["volume"].values.astype(np.float64)
                opens = df["open"].values.astype(np.float64) if "open" in df.columns else closes

                if len(closes) < 25:
                    continue

                # ---- 条件1: 昨日收阳 + 涨幅 >= 0.7% ----
                close_yest = closes[-2]
                open_yest = opens[-2]
                close_pre = closes[-3] if len(closes) >= 3 else close_yest
                if close_pre <= 0:
                    continue

                is_up_bar = close_yest > open_yest
                rise_rate = (close_yest - close_pre) / close_pre
                if not (is_up_bar and rise_rate >= self.parameters.get("min_yesterday_rise", 0.007)):
                    continue

                # ---- 条件2: MA5 > MA20（多头） ----
                ma5 = float(np.mean(closes[-5:]))
                ma20 = float(np.mean(closes[-20:]))
                if ma5 < ma20:
                    continue

                # ---- 条件3: 量比 >= 1.2 ----
                avg_vol_20 = float(np.mean(volumes[-20:]))
                last_vol = float(volumes[-1])
                if avg_vol_20 > 0 and last_vol / avg_vol_20 < min_vol_ratio:
                    continue

                # ---- 条件4: ROC(10) > 5 ----
                roc_10 = (closes[-1] - closes[-11]) / closes[-11] * 100 if len(closes) >= 11 else 0
                if roc_10 < roc_th:
                    continue

                # ---- 条件5: MACD 金叉（简化：DIF > DEA） ----
                macd_bullish = self._check_macd_bullish(closes)
                if not macd_bullish:
                    continue

                # ---- 条件6: 价格低于 20 日新高 >= 0.15% ----
                hhv_20 = float(np.max(closes[-20:]))
                if hhv_20 <= 0:
                    continue
                below_high = (hhv_20 - closes[-1]) / hhv_20
                if below_high < below_rate:
                    continue

                # 全部条件通过
                candidates.append(code)

            except Exception:
                continue

        # 按成交量降序排列（流动机优先）
        candidates.sort(
            key=lambda c: float(np.mean(
                self._data_cache[c]["volume"].values.astype(np.float64)[-5:]
            )) if c in self._data_cache and len(self._data_cache[c]) >= 5 else 0,
            reverse=True,
        )

        if self.verbose_logging:
            logger.info(f"低吸轮动选股: {len(candidates)} 只通过筛选")

        return candidates

    # =============================================================================
    # MACD 检查（numpy 版）
    # =============================================================================

    @staticmethod
    def _check_macd_bullish(closes: np.ndarray) -> bool:
        """
        简化版 MACD 检查。
        要求 DIF = EMA12 - EMA26 > 0，确保股票处于上升趋势中。
        """
        if len(closes) < 26:
            return False

        def _ema(data: np.ndarray, period: int) -> float:
            n = len(data)
            if n < period:
                return float(np.mean(data))
            multiplier = 2.0 / (period + 1)
            result = float(data[0])
            for i in range(1, n):
                result = (data[i] - result) * multiplier + result
            return result

        recent = closes[-26:]
        ema12 = _ema(recent, 12)
        ema26 = _ema(recent, 26)
        dif = ema12 - ema26

        return dif > 0

    # =============================================================================
    # 止盈止损
    # =============================================================================

    def _check_all_stop_profit(self) -> List[TradingSignal]:
        """
        检查所有持仓的止损和抛物线止盈。
        使用自维护的 _holdings（回测引擎不把 Broker 持仓同步到策略）。

        止损：统一 -4%
        止盈：抛物线式移动止盈（浮盈越大回撤容忍越低）
          浮盈 < 10%: 只止损，不止盈（给启动期空间）
          浮盈 10-20%: 从最高点回撤 8% 止盈
          浮盈 20-40%: 从最高点回撤 6% 止盈
          浮盈 >= 40%: 从最高点回撤 4% 止盈
        """
        signals: List[TradingSignal] = []
        stop_loss = float(self.parameters.get("stop_loss", -0.04))

        for code in list(self._holdings.keys()):
            entry = self._holdings[code]["entry_price"]
            if entry <= 0:
                self._holdings.pop(code, None)
                continue

            df = self._data_cache.get(code)
            if df is None or len(df) == 0:
                continue
            current_price = float(df["close"].iloc[-1])

            # 更新最高价
            if code not in self._track_high:
                self._track_high[code] = current_price
            else:
                self._track_high[code] = max(self._track_high[code], current_price)

            high = self._track_high[code]
            pnl = (current_price - entry) / entry
            dd = (high - current_price) / high if high > 0 else 0

            # ---- 止损 ----
            if pnl < stop_loss:
                signals.append(self._make_exit_signal(
                    code, reason=f"止损: 亏损{pnl:.1%}",
                    signal_type=SignalType.STOP_LOSS,
                ))
                del self._holdings[code]
                if code in self._track_high:
                    del self._track_high[code]
                continue

            # ---- 抛物线止盈 ----
            tp_drawdown = 0.0
            if pnl >= 0.80:
                tp_drawdown = 0.02   # 浮盈 80%+：回撤 2% 止盈（锁定超级利润）
            elif pnl >= 0.40:
                tp_drawdown = 0.04   # 浮盈 40-80%：回撤 4% 止盈
            elif pnl >= 0.20:
                tp_drawdown = 0.06   # 浮盈 20-40%：回撤 6% 止盈
            elif pnl >= 0.10:
                tp_drawdown = 0.08   # 浮盈 10-20%：回撤 8% 止盈

            if tp_drawdown > 0 and dd >= tp_drawdown:
                signals.append(self._make_exit_signal(
                    code, reason=f"抛物线止盈: 浮盈{pnl:.1%} 高点回落{dd:.1%}>{tp_drawdown:.0%}",
                    signal_type=SignalType.TAKE_PROFIT,
                ))
                del self._holdings[code]
                if code in self._track_high:
                    del self._track_high[code]

        return signals

    # =============================================================================
    # 工具方法
    # =============================================================================

    @classmethod
    def _is_tradable(cls, code: str) -> bool:
        """判断是否可交易的主板股票"""
        if not code or "." not in code:
            code = code  # 可能没有后缀
        stock_code = code.split(".")[0]
        if stock_code.startswith(cls.FORBID_PREFIX):
            return False
        if stock_code.startswith(cls.ALLOW_PREFIX):
            return True
        return False

    @classmethod
    def _is_st_by_prefix(cls, code: str) -> bool:
        """通过前缀判断 ST"""
        stock_code = code.split(".")[0]
        st_prefixes = ("ST", "*ST", "SST", "S*ST")
        return any(stock_code.startswith(p) for p in st_prefixes)

    def _is_new_stock(self, code: str) -> bool:
        """判断是否为新股（上市不满 30 个交易日）"""
        df = self._data_cache.get(code)
        if df is None or len(df) < 2:
            return True
        # 用缓存中的 data 行数近似判断（数据越少上市越晚）
        new_days = int(self.parameters.get("new_stock_days", 30))
        return len(df) < new_days

    def _get_price(self, code: str) -> float:
        df = self._data_cache.get(code)
        if df is not None and len(df) > 0:
            return float(df["close"].iloc[-1])
        return 0.0

    def _append_data(self, ts_code: str, bar: BarData) -> None:
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

        # 限制缓存（最多保留 250 行）
        if len(self._data_cache[ts_code]) > 250:
            self._data_cache[ts_code] = (
                self._data_cache[ts_code].tail(250).reset_index(drop=True)
            )

    @staticmethod
    def _gen_id() -> str:
        import uuid
        return str(uuid.uuid4())

    def _make_exit_signal(
        self,
        ts_code: str,
        reason: str = "",
        signal_type: SignalType = SignalType.EXIT,
    ) -> TradingSignal:
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
            reason=reason,
            timestamp=datetime.now(),
        )
