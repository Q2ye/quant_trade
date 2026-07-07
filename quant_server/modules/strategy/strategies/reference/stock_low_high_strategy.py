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

        # —— 三档行情风控（方案C：中证500指数）——
        # 判定依据：中证500（000905.SH）收盘价与均线位置
        "csi500_ma_short": 20,          # 短期均线周期
        "csi500_ma_long": 60,           # 长期均线周期
        "csi500_sideways_pct": 0.03,    # 震荡市判定：近N日涨跌幅 ≤ 3%

        # —— 下跌市风控（收紧止损+降至1只，不停买） ——
        "bear_max_pos": 1,              # 下跌市最多 1 只
        "bear_stop_loss": -0.025,       # 下跌市止损收紧至 -2.5%

        # —— 震荡市风控 ——
        "sideways_max_pos": 2,          # 震荡市最多 2 只

        # —— 风控（上涨市默认） ——
        "stop_loss": -0.04,             # 个股止损 -4%

        # —— 动态再平衡 ——
        "rebalance_threshold": 1.0,     # 持仓浮盈超过 100% 时强制卖半仓

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
        self._exit_pending: Set[str] = set()        # {ts_code: 待确认卖出的股票}
        # 中证500指数日线数据缓存（方案C：用于行情判定，通过 IndexDailyRepository 加载）
        self._csi500_cache: pd.DataFrame = pd.DataFrame()
        # 已结算持仓的累积"现金价值"（权重空间），用于组合回撤计算防 phantom drawdown
        # 盈利股退出后其贡献不会消失 → 无 phantom drawdown
        self._exited_entry_value: float = 0.0   # 已结算持仓的总投入（权重）
        self._exited_cash_value: float = 0.0    # 已结算持仓的总退出价值（权重）
        self._peak_return: float = -999.0       # 组合收益峰值（回撤计算用）

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
        self._exit_pending.clear()
        self._exited_entry_value = 0.0
        self._exited_cash_value = 0.0
        self._peak_return = -999.0
        self._csi500_cache = pd.DataFrame()
        self._bar_count = 0
        self._last_rebalance_date = ""
        self._first_screen_done = False
        self._st_stocks = set()

        # 从 DB 加载中证500指数数据（通过 IndexDailyRepository，非原始 SQL）
        session_factory = getattr(self, "_db_session_factory", None)
        if session_factory:
            try:
                from shared.database.repositories.market.basic.index_repo import IndexDailyRepository
                from datetime import date, timedelta
                async with session_factory() as db:
                    idx_repo = IndexDailyRepository(db)
                    # 加载全部可用数据（策略起始需向前取足够天数计算 MA20/MA60）
                    # 查询范围为回测起始日往前推 90 天到结束日
                    today = date.today()
                    start = today - timedelta(days=800)  # 覆盖约 3 年
                    records = await idx_repo.get_by_date_range('000905.SH', start, today)
                    if records:
                        df = pd.DataFrame([{
                            "trade_date": r.trade_date,
                            "close": float(r.close or 0),
                            "open": float(r.open or 0),
                            "high": float(r.high or 0),
                            "low": float(r.low or 0),
                            "volume": float(r.vol or 0),
                        } for r in records])
                        self._csi500_cache = df.sort_values("trade_date").reset_index(drop=True)
                        logger.info(f"中证500指数数据已加载: {len(self._csi500_cache)} 条")
                    else:
                        logger.warning("中证500指数数据为空，将回退到 bullish_pct 判定")
            except Exception as e:
                logger.warning(f"中证500指数数据加载失败（非致命，回退到 bullish_pct）: {e}")
        else:
            logger.info("DB 会话不可用，行情判定将使用 bullish_pct 代理")

        logger.info(f"低吸轮动策略已启动: 数据缓存={len(self._data_cache)}")

    def on_stop(self) -> None:
        self._data_cache.clear()
        self._track_high.clear()
        self._holdings.clear()
        self._exit_pending.clear()
        self._exited_entry_value = 0.0
        self._exited_cash_value = 0.0
        self._peak_return = -999.0
        self._csi500_cache = pd.DataFrame()
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

        v6.0（源策略对齐版）：
          0. 【结算待卖出】
          1. 【大盘环境 + 组合回撤】→ 确定 effective_max_pos
          2. 【提前选股】→ 获得今日选股池（供池内池外止盈 + 半仓轮动使用）
          3. 【P0 池内池外止盈】池内股只止损，池外股止损+抛物线止盈
          4. 【差异三 两步复检】用今日 bar 重新验证候选股
          5. 【差异二 半仓轮动】有新标无空位时，清仓最差池内股腾位
          6. 【买入】用动态上限计算
        """
        signals: List[TradingSignal] = []
        if len(self._data_cache) < 10:
            return signals

        # ---- 0. 结算昨日的待确认卖出 ----
        self._finalize_exits()

        # ---- 1. 三档行情判定（方案C：中证500指数）----
        max_pos = int(self.parameters.get("max_positions", 3))
        regime, bullish_pct = self._calc_csi500_regime()

        if regime == "上涨市":
            regime_max_pos = max_pos
            regime_stop_loss = float(self.parameters.get("stop_loss", -0.04))
            regime_no_new_buy = False
        elif regime == "震荡市":
            regime_max_pos = int(self.parameters.get("sideways_max_pos", 2))
            regime_stop_loss = float(self.parameters.get("stop_loss", -0.04))
            regime_no_new_buy = False
        else:
            regime = "下跌市"
            regime_max_pos = int(self.parameters.get("bear_max_pos", 1))
            regime_stop_loss = float(self.parameters.get("bear_stop_loss", -0.025))
            regime_no_new_buy = False

        effective_max_pos = regime_max_pos

        if self.verbose_logging:
            logger.info(
                f"行情判定: {regime} (多头占比={bullish_pct:.1%}, "
                f"上限={regime_max_pos}, 止损={regime_stop_loss:.1%})"
            )

        # ---- 2. 获取当前持仓 ----
        current_holdings = set(self._holdings.keys())
        effective_count = len(current_holdings - self._exit_pending)

        # ---- 3. 提前选股（在止盈止损之前，获得今日选股池用于 P0）----
        if effective_max_pos > 0 and not regime_no_new_buy:
            buy_list = self._screen_stocks(current_holdings)
        else:
            buy_list = []

        # P0：today_pool 包含「新候选股」+「当前有效持仓（未标记卖出）」
        today_pool = (set(buy_list) if buy_list else set()) | (current_holdings - self._exit_pending)

        # ---- 4. P0 池内池外区分止盈（传入动态止损参数）----
        exit_signals = self._check_all_stop_profit(today_pool=today_pool, stop_loss=regime_stop_loss)
        signals.extend(exit_signals)

        # ---- 5. 差异三 两步合一步复检 ----
        confirmed = self._recheck_buy_list(buy_list) if buy_list else []

        if self.verbose_logging:
            logger.info(
                f"低吸轮动调仓: 持仓={len(current_holdings)}, "
                f"待卖出={len(self._exit_pending)}, 有效={effective_count}, "
                f"上限={effective_max_pos}, 行情={regime}, "
                f"多头占比={bullish_pct:.1%}, 初筛={len(buy_list)}, "
                f"复检={len(confirmed)}, {'暂停买入' if regime_no_new_buy else ''}"
            )

        # ---- 6. 震荡市成交量排名过滤（方案C）----
        if regime == "震荡市" and confirmed:
            confirmed = self._filter_sideways_volume(confirmed)

        # ---- 7. + 8. 半仓轮动 + 买入 ----
        if effective_max_pos <= 0 or regime_no_new_buy:
            return signals

        new_stocks = [s for s in confirmed if s not in current_holdings and s not in self._exit_pending]
        slots = effective_max_pos - effective_count

        # 差异二：无空位但有新标时，清仓最差池内股腾位
        if slots <= 0 and new_stocks:
            hold_in_pool = [
                s for s in current_holdings
                if s in today_pool and s not in self._exit_pending
            ]
            if hold_in_pool:
                def _pool_pnl(code):
                    entry = self._holdings.get(code, {}).get("entry_price", 0)
                    cur = self._get_price(code)
                    if entry <= 0 or cur <= 0:
                        return 999.0
                    return (cur - entry) / entry
                worst = min(hold_in_pool, key=_pool_pnl)
                self._exit_pending.add(worst)
                signals.append(self._make_exit_signal(
                    worst, reason=f"半仓轮动: 清仓弱势池内股为新标{new_stocks[0]}腾位(pnl={_pool_pnl(worst):.1%})",
                ))
                slots = 1
                if self.verbose_logging:
                    logger.info(f"半仓轮动: 清仓{worst}为新标{new_stocks[0]}腾位")

        # 买入
        if slots <= 0 or not new_stocks:
            return signals

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
                amount=1.0 / effective_max_pos,
                confidence=0.75,
                reason=f"低吸轮动买入: {target}",
                timestamp=datetime.now(),
            )
            sig.weight = 1.0 / effective_max_pos
            signals.append(sig)
            self._holdings[target] = {
                "entry_price": price, "quantity": 1.0 / effective_max_pos,
            }
            self._track_high[target] = price

            if self.verbose_logging:
                logger.info(f"低吸轮动买入: {target}, 仓位={sig.weight:.0%}")

        return signals

    # =============================================================================
    # 大盘环境过滤
    # =============================================================================

    def _calc_bullish_pct(self) -> float:
        """
        计算数据缓存中 MA5 > MA20（多头排列）的股票占比。

        用作市场环境代理指标：多头占比越低说明市场越弱势。
        低于 min_bullish_pct 阈值时策略应降低仓位。
        """
        total = 0
        bullish = 0
        for code, df in self._data_cache.items():
            closes = df["close"].values.astype(np.float64)
            if len(closes) < 20:
                continue
            total += 1
            ma5 = float(np.mean(closes[-5:]))
            ma20 = float(np.mean(closes[-20:]))
            if ma5 > ma20:
                bullish += 1
        return bullish / total if total > 0 else 0.0

    # =============================================================================
    # 三档行情判定（方案C：中证500指数，通过 IndexDailyRepository 加载）
    # =============================================================================

    def _calc_csi500_regime(self) -> Tuple[str, float]:
        """
        基于中证500（000905.SH）的行情判定。

        判定规则：
          上涨市：close > MA20 > MA60 且 MA20斜率正
          震荡市：近20日涨跌幅 ≤ 3% 且 MA20走平
          下跌市：close < MA20 < MA60 且 MA20斜率为负

        回退：中证500数据不足或未加载时，使用 bullish_pct 代理判定。

        Returns:
            (regime_name, bullish_pct) — regime_name 用于仓位决策，bullish_pct 用于日志
        """
        bullish_pct = self._calc_bullish_pct()

        # 数据不足时回退到 bullish_pct 代理
        if self._csi500_cache.empty or len(self._csi500_cache) < 65:
            up_th = float(self.parameters.get("csi500_upper_fallback", 0.25))
            dn_th = float(self.parameters.get("csi500_lower_fallback", 0.10))
            if bullish_pct > up_th:
                return "上涨市", bullish_pct
            elif bullish_pct > dn_th:
                return "震荡市", bullish_pct
            else:
                return "下跌市", bullish_pct

        closes = self._csi500_cache["close"].values.astype(np.float64)
        ma_short = int(self.parameters.get("csi500_ma_short", 20))
        ma_long = int(self.parameters.get("csi500_ma_long", 60))
        sideways_pct = float(self.parameters.get("csi500_sideways_pct", 0.03))

        close_now = closes[-1]
        n = len(closes)
        ma20 = float(np.mean(closes[-ma_short:])) if n >= ma_short else close_now
        ma60 = float(np.mean(closes[-ma_long:])) if n >= ma_long else close_now

        # MA20斜率（当前MA20 vs 3天前的MA20）
        if n >= ma_short + 3:
            ma20_3d_ago = float(np.mean(closes[-(ma_short + 3):-3]))
            ma20_slope = (ma20 - ma20_3d_ago) / ma20_3d_ago if ma20_3d_ago > 0 else 0
        else:
            ma20_slope = 0

        # 近20日涨跌幅
        recent_return = (close_now - closes[-21]) / closes[-21] if n >= 21 else 0

        # 上涨市：close > MA20 > MA60, MA20斜率正
        if close_now > ma20 > ma60 and ma20_slope > 0:
            return "上涨市", bullish_pct
        # 下跌市：close < MA20 < MA60, MA20斜率为负
        if close_now < ma20 < ma60 and ma20_slope < 0:
            return "下跌市", bullish_pct
        # 震荡市：涨跌幅小或MA20走平
        if abs(recent_return) <= sideways_pct or abs(ma20_slope) < 0.005:
            return "震荡市", bullish_pct
        # 兜底
        if close_now > ma20:
            return "上涨市", bullish_pct
        elif close_now < ma20:
            return "下跌市", bullish_pct
        return "震荡市", bullish_pct

    # =============================================================================
    # 组合回撤保护（累计退出价值法，无 phantom drawdown）
    # =============================================================================

    def _calc_portfolio_return(self) -> float:
        """
        计算组合近似 NAV 收益率。

        算法：维护一个"虚拟账本"— _exited_cash_value 代表已退出持仓的
        累积回收价值（类似现金），_exited_entry_value 代表对应的总投入。
        当前持仓按实时市价计算。

        NAV 代理 = (已退出持仓的退出价值 + 当前持仓市值) / (总投入) - 1

        关键：已兑现的利润不会消失 → 无 phantom drawdown。
        不受持仓数量变化影响（总投入是固定的，不会被稀释）。
        """
        total_entry = self._exited_entry_value
        total_current = self._exited_cash_value

        for code, holding in self._holdings.items():
            entry = holding.get("entry_price", 0)
            if entry <= 0:
                continue
            current = self._get_price(code)
            if current <= 0:
                continue
            qty = holding.get("quantity", 1.0)
            total_entry += entry * qty
            total_current += current * qty

        if total_entry <= 0:
            return 0.0
        return total_current / total_entry - 1.0

    def _check_portfolio_drawdown(self) -> float:
        """
        计算组合从收益峰值的回撤比例。

        回撤 = (peak_return - current_return) / (1 + peak_return)
        创新高时更新 _peak_return 并返回 0。
        """
        current_ret = self._calc_portfolio_return()
        if current_ret > self._peak_return:
            self._peak_return = current_ret
            return 0.0
        if self._peak_return <= -0.999:
            return 0.0
        dd = (self._peak_return - current_ret) / (1 + self._peak_return)
        return max(0.0, dd)

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
                # P1: 买入价下限——不买从 20 日新高跌超 8% 的（不接飞刀）
                if closes[-1] < hhv_20 * 0.92:
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
    # 两步合一步复检（差异三：用今日 bar 数据二次验证候选股）
    # =============================================================================

    def _recheck_buy_list(self, buy_list: List[str]) -> List[str]:
        """
        两步合一步复检：用今日已收到的 Bar 数据重新验证候选股。

        相当于源策略 9:51 二次筛选的核心功能，但不依赖时间片调度：
          1. 今日成交量 > 0（非停牌/无交易）
          2. 今日开盘未涨停
          3. 今日跳空 < 3%（避免追高）
          4. 用今日开盘价重新验证 20 日新高低吸条件

        Args:
            buy_list: _screen_stocks 输出的候选列表。

        Returns:
            通过复检的候选列表。
        """
        confirmed: List[str] = []
        below_rate = float(self.parameters.get("buy_below_high_rate", 0.0015))

        for code in buy_list:
            df = self._data_cache.get(code)
            if df is None or len(df) < 2:
                continue

            opens = df["open"].values.astype(np.float64)
            volumes = df["volume"].values.astype(np.float64)
            closes = df["close"].values.astype(np.float64)

            today_open = float(opens[-1])
            today_vol = float(volumes[-1])
            prev_close = float(closes[-2]) if len(closes) >= 2 else 0

            # 检查1: 今日有成交量（非停牌/无交易）
            if today_vol <= 0:
                continue

            # 检查2: 今日开盘未涨停（open < 前收 × 1.095）
            if prev_close > 0 and today_open >= prev_close * 1.095:
                continue

            # 检查3: 今日跳空未超过 3%
            if prev_close > 0 and (today_open - prev_close) / prev_close > 0.03:
                continue

            # 检查4: 用今日开盘价重新验证 20 日新高条件
            hhv_20 = float(np.max(closes[-20:])) if len(closes) >= 20 else 0
            if hhv_20 > 0:
                below = (hhv_20 - today_open) / hhv_20
                if below < below_rate:
                    continue

            confirmed.append(code)

        return confirmed

    # =============================================================================
    # 震荡市成交量排名过滤（方案C：只买流动性前50%的候选股）
    # =============================================================================

    def _filter_sideways_volume(self, candidates: List[str]) -> List[str]:
        """
        震荡市中，按近5日均量排序，只保留成交量前50%的候选股。

        逻辑：震荡市中大量"脉冲一日游"的伪信号，
        成交量大的股票至少说明有资金关注，失败概率更低。

        Args:
            candidates: 复检后的候选列表。

        Returns:
            成交量前50%的候选列表（最少保留1只）。
        """
        if len(candidates) <= 2:
            return candidates

        vol_list = []
        for code in candidates:
            df = self._data_cache.get(code)
            if df is None or len(df) < 5:
                continue
            volumes = df["volume"].values.astype(np.float64)
            avg_vol = float(np.mean(volumes[-5:]))
            vol_list.append((code, avg_vol))

        if len(vol_list) <= 2:
            return [c[0] for c in vol_list]

        vol_list.sort(key=lambda x: x[1], reverse=True)
        cutoff = max(1, len(vol_list) // 2)
        filtered = [c[0] for c in vol_list[:cutoff]]

        if self.verbose_logging:
            logger.info(
                f"震荡市成交量过滤: {len(candidates)} → {len(filtered)} 只 "
                f"(保留成交量前50%)"
            )
        return filtered

    # =============================================================================
    # MACD 检查（numpy 版）
    # =============================================================================

    @staticmethod
    def _check_macd_bullish(closes: np.ndarray) -> bool:
        """
        MACD 金叉检查：DIF > DEA（DIF 在信号线上方），确认上升趋势。
        比原版仅 DIF > 0 更严格，避免高位钝化时误入。
        计算量允许范围内使用多期 DIF 值计算 DEA（信号线）。
        """
        if len(closes) < 35:   # 需要 26 期 EMA + 9 期 DEA 缓存
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

        # DIF = EMA12 - EMA26
        recent26 = closes[-26:]
        ema12 = _ema(recent26, 12)
        ema26 = _ema(recent26, 26)
        dif = ema12 - ema26

        # 计算 DEA（DIF 的 9 期 EMA）
        # 从每个有效窗口计算 DIF 值构成序列
        dif_values = []
        for i in range(len(closes) - 26, len(closes)):
            segment = closes[i:i + 26]
            if len(segment) == 26:
                e12 = _ema(segment, 12)
                e26 = _ema(segment, 26)
                dif_values.append(e12 - e26)

        if len(dif_values) < 9:
            return dif > 0   # 数据不足时回退到原版检查

        dea = _ema(np.array(dif_values), 9)

        return dif > dea and dif > 0

    # =============================================================================
    # 止盈止损（v2.0 纯净版 — -4% 止损 + 抛物线止盈）
    # =============================================================================

    def _finalize_exits(self) -> None:
        """
        结算前一日标记为待卖出的股票。

        将已确认卖出的股票从 _holdings 中移除，并将退出时的
        投入价值和回收价值累加到 _exited_entry/cash_value 中。
        这使得组合回撤计算能感知已兑现利润 → 无 phantom drawdown。

        关键设计：退出利润以"现金"形式保留在 NAV 代理中，
        不会被后续新入场的持仓稀释。
        """
        for code in list(self._exit_pending):
            if code in self._holdings:
                entry = self._holdings[code].get("entry_price", 0)
                qty = self._holdings[code].get("quantity", 1.0)
                exit_price = self._get_price(code)
                if entry > 0 and exit_price > 0:
                    entry_val = entry * qty
                    exit_val = exit_price * qty
                    self._exited_entry_value += entry_val
                    self._exited_cash_value += exit_val
                del self._holdings[code]
            if code in self._track_high:
                del self._track_high[code]
        self._exit_pending.clear()

    def _check_all_stop_profit(self, today_pool: Set[str] = None, stop_loss: float = -0.04) -> List[TradingSignal]:
        """
        P0: 池内池外区分止盈（源策略核心逻辑）。

        池内股（仍在今日选股池）→ 只止损，不止盈（让强势股自由奔跑）
        池外股（已跌出选股池）→ 止损 + 抛物线止盈（原版逻辑）

        Args:
            today_pool: 今日选股池（包含候选股 + 当前有效持仓）
            stop_loss: 动态止损比例（由三档行情决定，上涨市 -4%，下跌市 -2.5%）
        """
        signals: List[TradingSignal] = []

        for code in list(self._holdings.keys()):
            if code in self._exit_pending:
                continue

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

            # 是否为今日选股池内股
            is_in_pool = today_pool is not None and code in today_pool

            # ---- 动态再平衡（在止损前执行，防集中度风险）----
            rebalance_th = float(self.parameters.get("rebalance_threshold", 1.0))
            if pnl >= rebalance_th:
                old_qty = self._holdings[code]["quantity"]
                half_qty = old_qty / 2
                self._holdings[code]["quantity"] = half_qty  # 保留半仓
                # 另外半仓生成卖出信号（带 half_exit 标记）
                sig = self._make_exit_signal(
                    code, reason=f"动态再平衡: 浮盈{pnl:.1%}>={rebalance_th:.0%}，减半仓",
                    signal_type=SignalType.TAKE_PROFIT,
                )
                sig.half_exit = True
                signals.append(sig)
                if self.verbose_logging:
                    logger.info(
                        f"动态再平衡: {code} 浮盈{pnl:.1%}>={rebalance_th:.0%}，"
                        f"减半仓({old_qty}→{half_qty})"
                    )
                # 重置最高价（减半仓后重新追踪）
                self._track_high[code] = current_price
                continue

            # ---- 止损（所有持仓统一执行）----
            if pnl < stop_loss:
                self._exit_pending.add(code)
                signals.append(self._make_exit_signal(
                    code, reason=f"止损: 亏损{pnl:.1%}",
                    signal_type=SignalType.STOP_LOSS,
                ))
                continue

            # ---- 池内股：只止损，不止盈，跳过所有止盈逻辑 ----
            # 集中度风险由「动态再平衡」（浮盈≥100%卖半仓）处理，更精准
            if is_in_pool:
                continue

            # ---- 池外股：抛物线止盈（原版）----
            tp_drawdown = 0.0
            if pnl >= 0.80:
                tp_drawdown = 0.02
            elif pnl >= 0.40:
                tp_drawdown = 0.04
            elif pnl >= 0.20:
                tp_drawdown = 0.06
            elif pnl >= 0.10:
                tp_drawdown = 0.08

            if tp_drawdown > 0 and dd >= tp_drawdown:
                self._exit_pending.add(code)
                signals.append(self._make_exit_signal(
                    code, reason=f"池外止盈: 浮盈{pnl:.1%} 高点回落{dd:.1%}>{tp_drawdown:.0%}",
                    signal_type=SignalType.TAKE_PROFIT,
                ))

        return signals

    # =============================================================================
    # 工具方法
    # =============================================================================

    @classmethod
    def _is_tradable(cls, code: str) -> bool:
        """判断是否可交易的主板股票"""
        if not code:
            return False
        stock_code = code.split(".")[0]
        if not stock_code:
            return False
        if stock_code.startswith(cls.FORBID_PREFIX):
            return False
        if not stock_code.startswith(cls.ALLOW_PREFIX):
            return False
        return True

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
