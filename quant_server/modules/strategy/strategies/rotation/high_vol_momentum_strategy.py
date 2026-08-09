# -*- coding: utf-8 -*-
"""
高波动动量轮动策略 v5.0（第一性原理 · 右侧追强 · 让利润奔跑）
================================================================
目标：年化 40-80%（不可下修）。MDD < 30%，赔率 > 2:1。

第一性原理（数学路径）：
  月均 +5%（年化80%） = 满仓集中 1-2 只 × 盈亏比 3:1 × 胜率 40%
    单笔期望 = 0.4×(+30%) - 0.6×(-10%) = +6% → 每月 1-2 笔 → 年化 ~100%
  因此三个必须：
    ① 必须集中（2×50%）—— 分散到 3×33% 单票贡献减半，够不着 80%
    ② 必须让利润奔跑（无固定止盈，ATR移动止损）—— 没有右尾就没有 80%
    ③ 必须控制亏损（2×ATR 自适应止损）—— 固定 -4% 对高波动票是自杀

与 v1-v4 的本质区别：
  v1/v2/v3：固定小池 + 动量追高 → 买在顶部（胜率 20-33% 但盈亏比 1.3）
  v4.0：照搬低吸轮动选股 → 高频磨损型，76% 交易 1-5 天，无右尾（-33%）
  v5.0：右侧追强（创新高+多头+放量）+ 多因子打分 + ATR移动止损 → 让右尾跑

设计要点：
- 全市场主板扫描，无市值上限（翻倍股 86% 在 200 亿以下），只设流动性下限
- 多因子打分：60日动量 + 20日加速 + 相对强度，取 Top2
- 入场：右侧确认（close 创新高 + MA50>MA200 + 放量），收盘确认买入
- 持有：无止盈目标；2×ATR 自适应移动止损（从最高点回撤即走），趋势破坏兜底
- Regime：CSI500 年线门（熊市停买）
"""
import logging
import numpy as np
import pandas as pd
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from core.engines.types.entities import BarData
from modules.strategy.constants import StrategyType, SignalDirection, SignalType
from modules.strategy.models import TradingSignal
from modules.strategy.strategies.base.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class HighVolMomentumStrategy(BaseStrategy):
    """高波动动量轮动策略 v5.0（右侧追强 · 让利润奔跑）"""

    strategy_type: StrategyType = StrategyType.ROTATION

    # 主板股票前缀
    ALLOW_PREFIX: Tuple[str, ...] = ('000', '002', '600', '603', '601', '605')
    FORBID_PREFIX: Tuple[str, ...] = ('300', '688', '8', '4', '001', '003')

    DEFAULT_PARAMS: Dict[str, Any] = {
        # —— 标的池（全市场扫描，无市值上限） ——
        "universe": "all_market",
        "min_daily_volume": 500,         # 近5日日均成交量 ≥ 500 手（流动性下限）
        "new_stock_days": 30,            # 新股过滤
        "lookback_days": 250,            # 选股回溯（需 MA200 + 动量）

        # —— 选股（多因子打分） ——
        "momentum_window": 60,           # 中期动量（主因子）
        "momentum_accel_window": 20,     # 短期加速（次因子）
        "ma_short": 50,                  # 趋势过滤短均线
        "ma_long": 200,                  # 趋势过滤长均线
        "breakout_window": 20,           # 创新高窗口
        "breakout_near_pct": 0.02,       # 距 20 日新高 ≤2% 视为右侧确认
        "volume_surge_ratio": 1.2,       # 近5日均量 ≥ 近20日均量 × 此值

        # —— 持仓（集中 2×50%） ——
        "max_positions": 2,              # 最大持仓数
        "max_single_weight": 0.5,        # 单票权重上限
        "rebalance_frequency": 1,        # 每日扫描
        "min_lot_size": 100,

        # —— 止损（2×ATR 自适应） ——
        "atr_window": 20,                # ATR 窗口
        "atr_stop_mult": 2.0,            # 硬止损 = 入场价 - 2×ATR
        "atr_trailing_mult": 2.0,        # 移动止损 = 最高点 - 2×ATR

        # —— Regime（年线门） ——
        "use_annual_gate": True,         # CSI500 收盘<MA250 停买

        # —— 运行 ——
        "verbose_logging": True,
    }

    def __init__(
        self,
        name: str = "高波动动量轮动v5.0",
        strategy_type: StrategyType = StrategyType.ROTATION,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(name=name, strategy_type=strategy_type, parameters=parameters)
        merged = dict(self.DEFAULT_PARAMS)
        merged.update(parameters or {})
        # v5.0: 让 self.parameters 含完整合并参数（DEFAULT_PARAMS + 覆盖），
        # 供 StrategyManager 预热读取 universe/lookback_days 等。
        # 否则 self.parameters 仅为传入参数（可能为空），预热无法识别 all_market → 走慢路径。
        self.parameters = dict(merged)

        # 标的池
        self.min_daily_volume = float(merged["min_daily_volume"])
        self.new_stock_days = int(merged["new_stock_days"])
        self.lookback_days = int(merged["lookback_days"])
        # 选股
        self.momentum_window = int(merged["momentum_window"])
        self.momentum_accel_window = int(merged["momentum_accel_window"])
        self.ma_short = int(merged["ma_short"])
        self.ma_long = int(merged["ma_long"])
        self.breakout_window = int(merged["breakout_window"])
        self.breakout_near_pct = float(merged["breakout_near_pct"])
        self.volume_surge_ratio = float(merged["volume_surge_ratio"])
        # 持仓
        self.max_positions = int(merged["max_positions"])
        self.max_single_weight = float(merged["max_single_weight"])
        self.rebalance_frequency = int(merged["rebalance_frequency"])
        self.min_lot_size = int(merged["min_lot_size"])
        # 止损
        self.atr_window = int(merged["atr_window"])
        self.atr_stop_mult = float(merged["atr_stop_mult"])
        self.atr_trailing_mult = float(merged["atr_trailing_mult"])
        # Regime
        self.use_annual_gate = bool(merged.get("use_annual_gate", True))
        # 运行
        self.verbose_logging = bool(merged.get("verbose_logging", True))

        # ---- 状态 ----
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._bar_dates: Dict[str, str] = {}
        self._st_stocks: Set[str] = set()
        self._listing_dates: Dict[str, str] = {}
        self._holdings: Dict[str, Dict] = {}    # {code: {entry_price, weight, shares, entry_date, peak_high}}
        self._exit_pending: Set[str] = set()
        self._buy_pending: Dict[str, dict] = {}
        self._csi500_cache: pd.DataFrame = pd.DataFrame()
        self._market_mom60: float = 0.0         # 全市场 60 日动量中位数（相对强度基准）
        self._nav_realized: float = 1.0
        self._peak_return: float = -999.0
        self._bar_count: int = 0
        self._last_rebalance_date: str = ""
        self._last_trade_date: str = ""
        self._first_screen_done: bool = False

    # =========================================================================
    # 生命周期
    # =========================================================================
    def on_init(self) -> None:
        logger.info(f"高波动动量轮动 v5.0 初始化: 右侧追强, 持仓≤{self.max_positions}×{self.max_single_weight:.0%}, "
                    f"止损=2×ATR, 年线门={'开' if self.use_annual_gate else '关'}")

    async def on_start(self) -> None:
        self._data_cache.clear()
        self._bar_dates.clear()
        self._listing_dates.clear()
        self._holdings.clear()
        self._exit_pending.clear()
        self._buy_pending.clear()
        self._nav_realized = 1.0
        self._peak_return = -999.0
        self._bar_count = 0
        self._last_rebalance_date = ""
        self._first_screen_done = False
        self._st_stocks = set()

        session_factory = getattr(self, "_db_session_factory", None)
        if session_factory:
            # 中证500（年线门）
            try:
                from shared.database.repositories.market.basic.index_repo import IndexDailyRepository
                async with session_factory() as db:
                    idx_repo = IndexDailyRepository(db)
                    records = await idx_repo.get_by_date_range(
                        '000905.SH', date(2018, 1, 1), date.today()
                    )
                    if records:
                        self._csi500_cache = pd.DataFrame([{
                            "trade_date": str(r.trade_date)[:10],
                            "close": float(r.close or 0),
                        } for r in records]).sort_values("trade_date").reset_index(drop=True)
            except Exception as e:
                logger.warning(f"中证500加载失败（年线门降级）: {e}")

            # 全市场股票池
            try:
                from shared.database.repositories.market.basic.stock_repo import (
                    StockBasicRepository,
                )
                async with session_factory() as db:
                    all_stocks = await StockBasicRepository(db).get_active_stocks()
                universe: List[str] = []
                for s in all_stocks:
                    code = s.ts_code
                    if not self._is_tradable(code):
                        continue
                    name = str(getattr(s, "name", "") or "")
                    if "ST" in name.upper():
                        self._st_stocks.add(code)
                        continue
                    list_dt = getattr(s, "list_date", None)
                    if list_dt:
                        self._listing_dates[code] = str(list_dt)[:10]
                    universe.append(code)
                self._universe = universe
                logger.info(f"v5.0 全市场股票池已加载: {len(self._universe)} 只主板股 "
                            f"(剔除 ST {len(self._st_stocks)} 只)")
            except Exception as e:
                logger.warning(f"股票池加载失败: {e}")
        # 注：历史数据预热由 StrategyManager._warmup_all_market 负责（回测/实盘统一），
        # 策略不自载，避免与引擎双重加载 2879 只全市场数据。
        # _data_cache 在 start_strategy 预热后被填充，首个交易日即可选股。

    def on_stop(self) -> None:
        self._data_cache.clear()
        self._bar_dates.clear()
        self._holdings.clear()
        self._exit_pending.clear()
        self._buy_pending.clear()
        self._st_stocks.clear()
        self._csi500_cache = pd.DataFrame()

    # =========================================================================
    # 数据流
    # =========================================================================
    def on_bar(self, bar: BarData) -> List[TradingSignal]:
        try:
            self._append_data(bar.ts_code, bar)
            td = str(getattr(bar, "trade_date", "") or getattr(bar, "datetime", ""))[:10]
            if td:
                self._last_trade_date = td
        except Exception as e:
            logger.error(f"v5.0 on_bar 异常: {bar.ts_code}: {e}", exc_info=True)
        return []

    def on_bar_batch_end(self, trade_date: Any = None) -> List[TradingSignal]:
        signals: List[TradingSignal] = []
        try:
            td = str(trade_date)[:10] if trade_date else self._last_trade_date
            if td:
                self._last_trade_date = td
            if self._last_rebalance_date and td == self._last_rebalance_date:
                return signals

            self._bar_count += 1
            if self._bar_count % int(self.rebalance_frequency) == 0 and len(self._data_cache) >= 10:
                signals = self._run_rebalance()
                self._last_rebalance_date = td
                self._first_screen_done = True
        except Exception as e:
            logger.error(f"v5.0 on_bar_batch_end 异常: {trade_date}: {e}", exc_info=True)
        return signals

    # =========================================================================
    # 主调仓（右侧追强 + ATR 风控）
    # =========================================================================
    def _run_rebalance(self) -> List[TradingSignal]:
        signals: List[TradingSignal] = []
        if len(self._data_cache) < 10:
            return signals

        # 0. 结算待卖出
        self._finalize_exits()

        # 1. 行情判定（年线门 → 停买）
        bear = self._annual_line_gate() if self.use_annual_gate else False
        if self.verbose_logging:
            logger.info(f"v5.0 调仓: {'年线门停买' if bear else '正常'} 持仓={len(self._holdings)}")

        # 2. 日频风控（对持仓）：2×ATR 硬止损 + 2×ATR 移动止损 + 趋势破坏
        signals.extend(self._check_stops_and_trailing())

        # 3. 确认昨日待买候选（收盘确认）
        if not bear:
            signals.extend(self._confirm_pending_buys())
        else:
            self._buy_pending.clear()

        # 4. 若年线门停买，不再扫描新标的
        if bear:
            return signals

        # 5. 全市场选股（多因子打分，仅当有空位时）
        if len(self._holdings) >= self.max_positions:
            return signals

        self._compute_market_momentum()   # 更新相对强度基准
        candidates = self._screen_stocks()
        confirmed = self._recheck_buy_list(candidates)

        slots = self.max_positions - len(self._holdings)
        for target in confirmed[:slots]:
            price = self._get_price(target)
            if price <= 0:
                continue
            self._buy_pending[target] = {
                "signal_price": price,
                "weight": self.max_single_weight,
                "signal_date": str(self._last_trade_date)[:10],
            }
            if self.verbose_logging:
                logger.info(f"v5.0 候选入池: {target}, 信号价={price:.2f}, 仓位={self.max_single_weight:.0%}")

        return signals

    # =========================================================================
    # 选股（多因子打分 + 右侧确认）
    # =========================================================================
    def _compute_market_momentum(self) -> None:
        """全市场 60 日动量中位数（相对强度基准）"""
        m = []
        for code, df in self._data_cache.items():
            closes = df["close"].values.astype(np.float64)
            if len(closes) < self.momentum_window + 2:
                continue
            if closes[-1] <= 0 or closes[-self.momentum_window - 1] <= 0:
                continue
            m.append(np.log(closes[-1] / closes[-self.momentum_window - 1]))
        if m:
            self._market_mom60 = float(np.median(m))

    def _screen_stocks(self) -> List[str]:
        """全市场扫描：趋势过滤 + 右侧确认 + 多因子打分，返回 Top 候选"""
        scored: List[Tuple[str, float]] = []
        for code in self._data_cache.keys():
            if code in self._holdings or code in self._exit_pending:
                continue
            if code in self._pending_signals or code in self._buy_pending:
                continue
            score = self._score_candidate(code)
            if score is not None:
                scored.append((code, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        if self.verbose_logging:
            logger.info(f"v5.0 选股: {len(scored)} 只通过, Top3={[(c, f'{s:.2%}') for c, s in scored[:3]]}")
        return [c for c, _ in scored]

    def _score_candidate(self, code: str) -> Optional[float]:
        """多因子评分：趋势过滤硬门槛 + 右侧确认 + 动量/加速/相对强度"""
        df = self._data_cache.get(code)
        if df is None or df.empty:
            return None
        try:
            if code in self._st_stocks:
                return None
            if self._bar_dates.get(code) != self._last_trade_date:
                return None
            if self._is_new_stock(code):
                return None

            closes = df["close"].values.astype(np.float64)
            highs = df["high"].values.astype(np.float64) if "high" in df.columns else closes
            vols = df["volume"].values.astype(np.float64)
            if len(closes) < self.lookback_days:
                return None

            price = float(closes[-1])
            if price <= 0:
                return None

            # —— 趋势过滤硬门槛：价格 > MA200 且 MA50 > MA200 ——
            ma_s = float(np.mean(closes[-self.ma_short:]))
            ma_l = float(np.mean(closes[-self.ma_long:]))
            if price <= ma_l or ma_s <= ma_l:
                return None

            # —— 流动性下限 ——
            avg_vol5 = float(np.mean(vols[-5:]))
            if avg_vol5 < self.min_daily_volume:
                return None

            # —— 量能确认：近5日均量 ≥ 近20日均量 × ratio ——
            avg_vol20 = float(np.mean(vols[-20:]))
            if avg_vol20 <= 0 or avg_vol5 / avg_vol20 < self.volume_surge_ratio:
                return None

            # —— 右侧确认：价格创新高 或 距 20 日新高 ≤ 2% ——
            hhv20 = float(np.max(highs[-self.breakout_window:]))
            if hhv20 <= 0:
                return None
            if price < hhv20 * (1 - self.breakout_near_pct):
                return None

            # —— 多因子打分 ——
            # 60 日动量（主因子）
            base = closes[-self.momentum_window - 1]
            if base <= 0:
                return None
            mom60 = float(np.log(price / base))
            # 20 日加速（次因子）
            base_acc = closes[-self.momentum_accel_window - 1]
            if base_acc <= 0:
                return None
            mom20 = float(np.log(price / base_acc))
            # 相对强度 = 个股动量 - 全市场中位数
            rs = mom60 - self._market_mom60
            # 综合分：动量为主 + 加速 + 相对强度
            score = mom60 + 0.5 * mom20 + 0.5 * rs
            return float(score)
        except Exception:
            return None

    def _recheck_buy_list(self, candidates: List[str]) -> List[str]:
        """复检：今日量>0 / 未涨停 / 跳空<5%"""
        confirmed: List[str] = []
        for code in candidates:
            df = self._data_cache.get(code)
            if df is None or len(df) < 2:
                continue
            opens = df["open"].values.astype(np.float64)
            vols = df["volume"].values.astype(np.float64)
            closes = df["close"].values.astype(np.float64)
            today_open, today_vol = float(opens[-1]), float(vols[-1])
            prev_close = float(closes[-2]) if len(closes) >= 2 else 0
            if today_vol <= 0:
                continue
            if prev_close > 0 and today_open >= prev_close * 1.095:
                continue
            if prev_close > 0 and (today_open - prev_close) / prev_close > 0.05:
                continue
            confirmed.append(code)
        return confirmed

    # =========================================================================
    # 收盘确认买入
    # =========================================================================
    def _confirm_pending_buys(self) -> List[TradingSignal]:
        signals: List[TradingSignal] = []
        if not self._buy_pending:
            return signals
        today = str(self._last_trade_date)[:10]
        capital = float(
            getattr(self.context, "initial_capital", 0)
            or self.parameters.get("allocated_capital", 100000)
        )
        pending = dict(self._buy_pending)
        self._buy_pending.clear()

        for code, pinfo in pending.items():
            if len(self._holdings) >= self.max_positions:
                break
            price = self._get_price(code)
            if price <= 0:
                continue
            signal_price = float(pinfo["signal_price"])
            if price <= signal_price:
                if self.verbose_logging:
                    logger.info(f"买入确认失败: {code} 收盘{price:.2f} ≤ 信号价{signal_price:.2f}")
                continue
            weight = min(float(pinfo.get("weight", self.max_single_weight)), self.max_single_weight)
            amount = capital * weight
            shares = max(int(amount / price / self.min_lot_size) * self.min_lot_size, self.min_lot_size)
            sig = self._make_entry_signal(code, weight, shares, price,
                                          f"右侧追强买入(收盘确认): 收盘{price:.2f} > 信号价{signal_price:.2f}")
            signals.append(sig)
            self._holdings[code] = {
                "entry_price": price,
                "weight": weight,
                "shares": shares,
                "entry_date": today,
                "peak_high": price,
            }
            if self.verbose_logging:
                logger.info(f"v5.0 买入(收盘确认): {code}, 收盘{price:.2f}, 仓位={weight:.0%}")
        return signals

    # =========================================================================
    # 风控：2×ATR 硬止损 + 2×ATR 移动止损 + 趋势破坏
    # =========================================================================
    def _check_stops_and_trailing(self) -> List[TradingSignal]:
        signals: List[TradingSignal] = []
        for code in list(self._holdings.keys()):
            if code in self._exit_pending:
                continue
            entry = self._holdings[code].get("entry_price", 0)
            if entry <= 0:
                self._holdings.pop(code, None)
                continue
            df = self._data_cache.get(code)
            if df is None or len(df) == 0:
                continue
            closes = df["close"].values.astype(np.float64)
            highs = df["high"].values.astype(np.float64) if "high" in df.columns else closes
            current = float(closes[-1])
            day_high = float(highs[-1])
            atr = self._calc_atr(code)

            # 更新阶段高点（移动止损基准）
            peak = max(self._holdings[code].get("peak_high", entry), day_high)
            self._holdings[code]["peak_high"] = peak

            # —— 1. 硬止损：价格 < 入场价 - 2×ATR ——
            hard_stop = entry - self.atr_stop_mult * atr
            if current < hard_stop:
                self._exit_pending.add(code)
                signals.append(self._make_exit_signal(
                    code, reason=f"硬止损: 现价{current:.2f} < 入场{entry:.2f}-{self.atr_stop_mult:.0f}×ATR({atr:.2f})",
                    signal_type=SignalType.STOP_LOSS
                ))
                continue

            # —— 2. 移动止损（让利润奔跑）：价格 < 最高点 - 2×ATR ——
            trail_stop = peak - self.atr_trailing_mult * atr
            if current < trail_stop:
                self._exit_pending.add(code)
                signals.append(self._make_exit_signal(
                    code, reason=f"移动止盈: 最高{peak:.2f}回落{((peak-current)/peak):.1%} > {self.atr_trailing_mult:.0f}×ATR",
                    signal_type=SignalType.TAKE_PROFIT
                ))
                continue

            # —— 3. 趋势破坏兜底：MA50 < MA200 ——
            if len(closes) >= self.ma_long:
                ma_s = float(np.mean(closes[-self.ma_short:]))
                ma_l = float(np.mean(closes[-self.ma_long:]))
                if ma_s < ma_l:
                    self._exit_pending.add(code)
                    signals.append(self._make_exit_signal(
                        code, reason=f"趋势破坏: MA{self.ma_short}<MA{self.ma_long}"
                    ))
                    continue
        return signals

    def _calc_atr(self, code: str) -> float:
        """ATR(20)：平均真实波幅（当前 bar 数据）"""
        df = self._data_cache.get(code)
        if df is None or len(df) < self.atr_window + 1:
            return 0.0
        try:
            highs = df["high"].values.astype(np.float64)
            lows = df["low"].values.astype(np.float64)
            closes = df["close"].values.astype(np.float64)
            tr = np.maximum(
                highs[1:] - lows[1:],
                np.maximum(
                    np.abs(highs[1:] - closes[:-1]),
                    np.abs(lows[1:] - closes[:-1]),
                ),
            )
            return float(np.mean(tr[-self.atr_window:]))
        except Exception:
            return 0.0

    def _finalize_exits(self) -> None:
        for code in list(self._exit_pending):
            if code in self._holdings:
                entry = self._holdings[code].get("entry_price", 0)
                w = self._holdings[code].get("weight", 1.0)
                exit_price = self._get_price(code)
                if entry > 0 and exit_price > 0:
                    pnl = (exit_price - entry) / entry
                    self._nav_realized *= 1.0 + pnl * w
                del self._holdings[code]
        self._exit_pending.clear()

    # =========================================================================
    # Regime（年线门）
    # =========================================================================
    def _annual_line_gate(self) -> bool:
        """CSI500 收盘 < MA250 → 停买"""
        if not self.use_annual_gate or self._csi500_cache.empty or not self._last_trade_date:
            return False
        sliced = self._csi500_cache[
            self._csi500_cache["trade_date"].astype(str) <= self._last_trade_date
        ]
        closes = sliced["close"].values.astype(np.float64)
        if len(closes) < 250:
            return False
        return bool(closes[-1] < float(np.mean(closes[-250:])))

    # =========================================================================
    # 信号构造（四大模块）
    # =========================================================================
    def _make_entry_signal(self, code, weight, shares, price, reason) -> Optional[TradingSignal]:
        if price <= 0:
            return None
        sig = TradingSignal(
            id=self._gen_id(),
            strategy_id=self.name,
            strategy_name=self.name,
            ts_code=code,
            signal_type=SignalType.ENTRY,
            direction=SignalDirection.LONG,
            price=price,
            quantity=shares,
            amount=shares * price,
            confidence=0.75,
            reason=f"高波动动量轮动: {reason}",
            timestamp=datetime.now(),
            order_mode="close",
        )
        sig.weight = weight
        return sig

    def _make_exit_signal(
        self, code, reason, signal_type=SignalType.EXIT
    ) -> Optional[TradingSignal]:
        price = self._get_price(code)
        if price <= 0:
            return None
        return TradingSignal(
            id=self._gen_id(),
            strategy_id=self.name,
            strategy_name=self.name,
            ts_code=code,
            signal_type=signal_type,
            direction=SignalDirection.CLOSE_LONG,
            price=price,
            quantity=0,
            amount=0.0,
            confidence=0.80,
            reason=reason,
            timestamp=datetime.now(),
            order_mode="close",
        )

    def generate_entry_signals(
        self, target: Dict[str, float], reason: str = ""
    ) -> List[TradingSignal]:
        signals = []
        for code, weight in target.items():
            price = self._get_price(code)
            if price <= 0:
                continue
            shares = max(int(100000 * weight / price / self.min_lot_size) * self.min_lot_size,
                         self.min_lot_size)
            sig = self._make_entry_signal(code, weight, shares, price, reason)
            if sig:
                signals.append(sig)
        return signals

    def generate_exit_signals(
        self, codes: List[str], reason: str = "",
        signal_type: SignalType = SignalType.EXIT
    ) -> List[TradingSignal]:
        signals = []
        for code in codes:
            sig = self._make_exit_signal(code, reason, signal_type)
            if sig:
                signals.append(sig)
        return signals

    def calculate_position_size(self, weight: float) -> float:
        return max(0.0, min(1.0, float(weight)))

    def check_stop_profit_stop_loss(
        self, code: str, entry_price: float, current_price: float
    ) -> Optional[Tuple[str, str]]:
        """止盈止损判断（独立纯函数，供审计）"""
        if entry_price <= 0 or current_price <= 0:
            return None
        atr = self._calc_atr(code)
        if atr <= 0:
            return None
        pnl = current_price / entry_price - 1.0
        hard_stop = entry_price - self.atr_stop_mult * atr
        if current_price < hard_stop:
            return (SignalType.STOP_LOSS, f"硬止损: 现价{current_price:.2f} < {hard_stop:.2f}")
        return None

    # =========================================================================
    # 工具
    # =========================================================================
    @classmethod
    def _is_tradable(cls, code: str) -> bool:
        if not code:
            return False
        sc = code.split(".")[0]
        if sc.startswith(cls.FORBID_PREFIX):
            return False
        if not sc.startswith(cls.ALLOW_PREFIX):
            return False
        return True

    def _is_new_stock(self, code: str) -> bool:
        list_date = self._listing_dates.get(code)
        if list_date and self._last_trade_date:
            try:
                d0 = date.fromisoformat(str(list_date)[:10])
                d1 = date.fromisoformat(str(self._last_trade_date)[:10])
                return (d1 - d0).days < int(self.new_stock_days * 1.5)
            except ValueError:
                pass
        df = self._data_cache.get(code)
        if df is None or len(df) < 2:
            return True
        return len(df) < self.new_stock_days

    def _get_price(self, code: str) -> float:
        df = self._data_cache.get(code)
        if df is not None and len(df) > 0:
            return float(df["close"].iloc[-1])
        return 0.0

    def _append_data(self, ts_code: str, bar: BarData) -> None:
        bar_date = str(getattr(bar, "trade_date", "") or getattr(bar, "datetime", ""))[:10]
        if bar_date:
            self._bar_dates[ts_code] = bar_date
        if ts_code not in self._data_cache:
            self._data_cache[ts_code] = pd.DataFrame(
                columns=["trade_date", "open", "high", "low", "close", "volume", "amount"]
            )
        new_row = pd.DataFrame([{
            "trade_date": bar_date,
            "close": bar.close,
            "volume": bar.volume,
            "amount": getattr(bar, "amount", 0.0),
            "open": getattr(bar, "open", bar.close),
            "high": getattr(bar, "high", bar.close),
            "low": getattr(bar, "low", bar.close),
        }])
        self._data_cache[ts_code] = pd.concat(
            [self._data_cache[ts_code], new_row], ignore_index=True
        )
        if len(self._data_cache[ts_code]) > self.lookback_days + 60:
            self._data_cache[ts_code] = self._data_cache[ts_code].tail(
                self.lookback_days + 60
            ).reset_index(drop=True)

    @staticmethod
    def _gen_id() -> str:
        import uuid
        return str(uuid.uuid4())

    # =========================================================================
    # 查询接口
    # =========================================================================
    def get_parameters(self) -> Dict[str, Any]:
        return {
            "strategy_version": "v5.0",
            "universe": "all_market",
            "max_positions": self.max_positions,
            "max_single_weight": self.max_single_weight,
            "atr_stop_mult": self.atr_stop_mult,
            "atr_trailing_mult": self.atr_trailing_mult,
            "use_annual_gate": self.use_annual_gate,
            "current_holding_count": len(self._holdings),
            "universe_size": len(self._universe),
        }

    def get_daily_diagnostic(self) -> Optional[Dict[str, Any]]:
        try:
            return {
                "holdings": list(self._holdings.keys()),
                "buy_pending": list(self._buy_pending.keys()),
                "exit_pending": list(self._exit_pending),
            }
        except Exception:
            return None
