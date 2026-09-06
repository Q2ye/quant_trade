# -*- coding: utf-8 -*-
"""
高波动动量轮动策略 v9.0（右侧追强 · 熊市空仓 · 宽止损）
====================================================================================
目标：年化 40-80%（不可下修）。MDD < 30%，赔率 > 2:1。

第一性原理（数学路径）：
  月均 +5%（年化80%） = 满仓集中 1-2 只 × 盈亏比 3:1 × 胜率 40%
    单笔期望 = 0.4×(+30%) - 0.6×(-10%) = +6% → 每月 1-2 笔 → 年化 ~100%
  因此三个必须：
    ① 必须集中（2×50%）—— 分散到 3×33% 单票贡献减半，够不着 80%
    ② 必须让利润奔跑（无固定止盈，ATR移动止损）—— 没有右尾就没有 80%
    ③ 必须控制亏损（2×ATR 自适应止损）—— 固定 -4% 对高波动票是自杀

设计要点：
  - 全市场主板扫描，无市值上限（翻倍股 86% 在 200 亿以下），只设流动性下限
  - 牛市：多因子打分（60日动量+20日加速+相对强度），右侧追强 Top2
  - 熊市：年线门触发 → 清仓空仓（不搞温和启动抄底，v7.x 已证伪）
  - 持有：无止盈目标；2×ATR 自适应移动止损（从最高点回撤即走），趋势破坏兜底
  - Regime：CSI500 年线门（熊市降仓/空仓，不裸奔）

版本迭代历史（v5→v9.0 版本记录 / 实盘修复 / 评审结论 / 已验证失败方案）见
  docs/00-核心策略体系/高波动动量轮动策略迭代记录.md
"""
import logging
import numpy as np
import pandas as pd
from datetime import date, datetime
from shared.utils.time_utils import BEIJING_TZ, beijing_now
from shared.config.constants import SignalRejectReason
from typing import Any, Dict, List, Optional, Set, Tuple

from core.engines.types.entities import BarData
from modules.strategy.constants import StrategyType, SignalDirection, SignalType
from modules.strategy.models import TradingSignal
from modules.strategy.strategies.base.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class HighVolMomentumStrategy(BaseStrategy):
    """高波动动量轮动策略 v9.0（右侧追强 · 熊市空仓 · 宽止损）"""

    strategy_type: StrategyType = StrategyType.ROTATION

    # 主板股票前缀
    ALLOW_PREFIX: Tuple[str, ...] = ('000', '002', '600', '603', '601', '605')
    FORBID_PREFIX: Tuple[str, ...] = ('300', '688', '8', '4', '001', '003')

    DEFAULT_PARAMS: Dict[str, Any] = {
        # —— 标的池（全市场扫描，无市值上限） ——
        "universe": "all_market",
        "min_daily_volume": 500,         # 近5日日均成交量 ≥ 500 手（流动性下限）
        "min_circ_mv": 50000,            # 流通市值下限 5 亿（万元，只剔壳股，放行微盘翻倍股）
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
        "atr_trailing_mult": 3.5,        # 移动止损 = 最高点 - 3.5×ATR（放宽，让翻倍股奔跑，恢复 v7.1 宽 trailing）
        "hard_stop_pct": 0.04,           # 人工盯盘 -4% 日内硬止损：盘中 low < 入场价×(1-此值) → trigger 卖出
        "max_drawdown_pct": 0.20,        # 回撤熔断：已实现净值峰值回撤 > 此值 → 强制空仓（不依赖 regime）

        # —— Regime（中证1000 小盘指数年线门） ——
        "use_annual_gate": True,         # 指数年线门判 regime
        "regime_index_code": "000852.SH",  # regime 基准指数：中证1000（小盘，对齐策略交易标的）
        "regime_band": 0.05,             # 指数 vs MA250 偏离阈值（>1+band 牛市，<1-band 熊市；0.05 收紧牛市判定）
        "breadth_bear_threshold": 30.0,  # 已废弃：原市场宽度阈值（指数版不用，保留防 DB 孤儿覆盖）
        "breadth_bull_threshold": 60.0,  # 已废弃
        "annual_gate_band": 0.0,         # 已废弃：原 CSI500 年线门 band

        # —— 运行 ——
        "verbose_logging": True,
    }

    def __init__(
        self,
        name: str = "高波动动量轮动v9.0",
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
        self.min_circ_mv = float(merged.get("min_circ_mv", 50000))
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
        self.hard_stop_pct = float(merged.get("hard_stop_pct", 0.04))
        self.max_drawdown_pct = float(merged.get("max_drawdown_pct", 0.20))
        # Regime
        self.use_annual_gate = bool(merged.get("use_annual_gate", True))
        self.regime_index_code = str(merged.get("regime_index_code", "000852.SH"))
        self.regime_band = float(merged.get("regime_band", 0.05))
        self.annual_gate_band = float(merged.get("annual_gate_band", 0.0))
        self.breadth_bear_threshold = float(merged.get("breadth_bear_threshold", 30.0))
        self.breadth_bull_threshold = float(merged.get("breadth_bull_threshold", 60.0))
        # 运行
        self.verbose_logging = bool(merged.get("verbose_logging", True))

        # ---- 状态 ----
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._bar_dates: Dict[str, str] = {}
        self._st_stocks: Set[str] = set()
        self._listing_dates: Dict[str, str] = {}
        self._holdings: Dict[str, Dict] = {}    # {code: {entry_price, weight, shares, entry_date, peak_high}}
        self._pending_buys: Dict[str, dict] = {}  # 待成交（T 收盘确认、T+1 开盘成交前暂存，成交日搬到 _holdings）
        self._exit_pending: Set[str] = set()
        self._buy_pending: Dict[str, dict] = {}
        # 竞态修复：本批次确认失败（rejected）的候选 id ——
        # persist 幂等复用须跳过，避免 fire-and-forget reject 与新候选 persist 竞写同一行
        self._rejected_candidate_ids: Set[str] = set()
        # F 修复：本批次确认失败（rejected）的 code，选股阶段当天排除，次日重算（防反复入池循环）
        self._rejected_codes: Set[str] = set()
        self._index_cache: Dict[str, float] = {}  # {trade_date: close}，中证1000 收盘（指数年线门）
        self._injected_regime: Optional[int] = None  # 组合层注入的 regime（None=自算兜底）
        self._market_mom60: float = 0.0         # 全市场 60 日动量中位数（相对强度基准）
        self._nav_realized: float = 1.0
        self._peak_nav: float = 1.0  # 已实现净值峰值（回撤熔断基准）
        self._bar_count: int = 0
        self._last_rebalance_date: str = ""
        self._last_trade_date: str = ""
        self._first_screen_done: bool = False
        self._pending_rows: Dict[str, list] = {}  # on_bar 累积的待 flush 行（性能：避免逐行 df.loc 追加）

    # =========================================================================
    # 生命周期
    # =========================================================================
    def on_init(self) -> None:
        logger.info(f"高波动动量轮动 v9.0 初始化: 牛市追强+熊市空仓+宽止损, 持仓≤{self.max_positions}×{self.max_single_weight:.0%}, "
                    f"止损=2×ATR, 年线门={'开' if self.use_annual_gate else '关'}")

    async def on_start(self) -> None:
        self._data_cache.clear()
        self._bar_dates.clear()
        self._listing_dates.clear()
        self._holdings.clear()
        self._exit_pending.clear()
        self._buy_pending.clear()
        self._nav_realized = 1.0
        self._peak_nav = 1.0
        self._bar_count = 0
        self._last_rebalance_date = ""
        self._first_screen_done = False
        self._st_stocks = set()

        session_factory = getattr(self, "_db_session_factory", None)
        if session_factory:
            # 指数年线门基准：中证1000 收盘（替代市场宽度/CSI500，对齐策略交易的小盘高波动标的）
            try:
                from sqlalchemy import text
                async with session_factory() as db:
                    rows = (await db.execute(text(
                        "SELECT trade_date, close FROM index_daily "
                        "WHERE ts_code = :code ORDER BY trade_date"
                    )), {"code": self.regime_index_code}).fetchall()
                    self._index_cache = {str(r[0])[:10]: float(r[1]) for r in rows}
            except Exception as e:
                logger.warning(f"指数 regime 基准加载失败（年线门降级）: {e}")

            # 全市场股票池
            try:
                from shared.database.repositories.market.basic.stock_repo import (
                    StockBasicRepository,
                )
                from sqlalchemy import text
                async with session_factory() as db:
                    all_stocks = await StockBasicRepository(db).get_active_stocks()
                    # 市值下限：剔除流通市值 < min_circ_mv 的微盘壳股（防独立崩盘 + 流动性）
                    # 注：实盘用最新市值；回测需历史快照（未来函数待后续优化）
                    _mv_rows = (await db.execute(text(
                        "SELECT ts_code, circ_mv FROM stock_daily_basic "
                        "WHERE trade_date = (SELECT MAX(trade_date) FROM stock_daily_basic)"
                    ))).fetchall()
                    _circ_mv_map = {str(r[0]): float(r[1] or 0) for r in _mv_rows}
                universe: List[str] = []
                for s in all_stocks:
                    code = s.ts_code
                    if not self._is_tradable(code):
                        continue
                    if _circ_mv_map.get(code, 0) < self.min_circ_mv:
                        continue  # 市值下限：剔微盘壳股
                    name = str(getattr(s, "name", "") or "")
                    if "ST" in name.upper():
                        self._st_stocks.add(code)
                        continue
                    list_dt = getattr(s, "list_date", None)
                    if list_dt:
                        self._listing_dates[code] = str(list_dt)[:10]
                    universe.append(code)
                self._universe = universe
                logger.info(f"{self.name} 全市场股票池已加载: {len(self._universe)} 只主板股 "
                            f"(剔除 ST {len(self._st_stocks)} 只, 剔市值<{self.min_circ_mv/10000:.0f}亿)")
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
        self._index_cache.clear()
        self._injected_regime = None
        self._pending_rows.clear()

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
            logger.error(f"{self.name} on_bar 异常: {bar.ts_code}: {e}", exc_info=True)
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
                if self.verbose_logging:
                    logger.info(f"{self.name} 诊断: td={td} bar_count={self._bar_count} "
                                f"last_reb={self._last_rebalance_date} cache={len(self._data_cache)} "
                                f"hold={len(self._holdings)}")
                signals = self._run_rebalance()
                self._last_rebalance_date = td
                self._first_screen_done = True
        except Exception as e:
            logger.error(f"{self.name} on_bar_batch_end 异常: {trade_date}: {e}", exc_info=True)
        return signals

    # =========================================================================
    # 主调仓（牛市右侧追强 + 熊市空仓 + ATR 风控）
    # =========================================================================
    def _run_rebalance(self) -> List[TradingSignal]:
        signals: List[TradingSignal] = []
        # 竞态修复：每批次重置候选拒绝记录（确认失败 → persist 跳过复用）
        self._rejected_candidate_ids.clear()
        self._rejected_codes.clear()  # F 修复：本批次确认失败的 code 重置
        if len(self._data_cache) < 10:
            return signals

        # 性能：把 on_bar 累积的 bar 行 flush 到 _data_cache（替代逐行 df.loc 追加）
        self._flush_pending_rows()

        # -1. [契约] 对账 broker 实际持仓（卖出确认 / 删幽灵 / 回补，反馈闭环）
        self._reconcile_holdings()

        # -0.5 回撤熔断：近似权益（已实现净值 + 持仓浮盈亏）峰值回撤 > max_drawdown_pct → 强制空仓
        # 注：已实现净值只在卖出结算时更新、不含浮亏，熔断会滞后；
        # 此处用「已实现净值 × (1 + 持仓浮盈亏×权重)」近似权益，让熔断及时捕捉浮亏。
        _equity = self._nav_realized
        for _c, _h in self._holdings.items():
            _p = self._get_price(_c)
            _e = _h.get("entry_price", 0)
            _w = _h.get("weight", 0)
            if _p > 0 and _e > 0 and _w > 0:
                _equity *= 1.0 + (_p / _e - 1.0) * _w
        if _equity > self._peak_nav:
            self._peak_nav = _equity
        if self._peak_nav > 0:
            _dd = _equity / self._peak_nav - 1.0
            if _dd < -self.max_drawdown_pct:
                if self.verbose_logging:
                    logger.info(f"{self.name} [回撤熔断] 权益回撤{_dd:.1%} > {self.max_drawdown_pct:.0%} "
                                f"equity={_equity:.4f} peak={self._peak_nav:.4f} 持仓={len(self._holdings)}")
                for code in list(self._holdings.keys()):
                    if code not in self._exit_pending:
                        self._exit_pending.add(code)
                        _sig = self._make_exit_signal(
                            code, reason=f"回撤熔断: 权益回撤{_dd:.1%} > {self.max_drawdown_pct:.0%}"
                        )
                        if _sig:
                            signals.append(_sig)
                # 重置峰值，打破「熔断→空仓→回撤仍超限→再熔断」死锁
                self._peak_nav = _equity
                return signals

        # 0.5 待成交 → 已成交：昨天确认的买入已 T+1 开盘成交，搬到 _holdings（策略持仓与 broker 对齐，消除一日错位）
        # 记录成交日 fill_date，供风控/调仓跳过「买入成交当天」（A 股 T+1：当日买入不可当日卖出，可卖 0）
        _fill_date = str(self._last_trade_date)[:10]
        for _code, _pinfo in self._pending_buys.items():
            _pinfo["fill_date"] = _fill_date
            # 修复 entry 基准：实际成交价是当日开盘价（order_mode=open），
            # 止损须锚定真实成本而非确认日收盘价（否则止损线偏松、止损失效、回撤累积）
            _df = self._data_cache.get(_code)
            if _df is not None and len(_df) > 0 and "open" in _df.columns:
                _open = float(_df["open"].iloc[-1])
                if _open > 0:
                    _pinfo["entry_price"] = _open
            self._holdings[_code] = _pinfo
        self._pending_buys.clear()

        # 1. 行情判定（年线门 → 熊市空仓 / 牛市满仓追强）
        regime = self._current_regime() if self.use_annual_gate else 2
        bear = regime == 0
        # 持仓上限与单票权重：牛市满仓（2×50%）
        eff_max_pos, eff_weight = self._position_sizing(regime)
        if self.verbose_logging:
            _regime_label = {0: "熊市", 1: "震荡", 2: "牛市"}.get(regime, "?")
            logger.info(f"{self.name} 调仓: {_regime_label} 持仓={len(self._holdings)} "
                        f"上限={eff_max_pos} 权重={eff_weight:.0%}")

        # 2. 日频风控（对持仓）：2×ATR 硬止损 + 2×ATR 移动止损 + 趋势破坏
        #    （-4% 日内硬止损已删：2026-09-05 回测证实其致收益 -65%，磨损严重）
        # 止损前移：熊市也先逐笔止损（2×ATR 次日 open），
        # 对齐实盘人工盯盘+次日执行，避免熊市浮亏全靠次日清仓硬扛
        signals.extend(self._check_stops_and_trailing())

        # 1.5 熊市：清仓空仓（不搞温和放量启动，直接空仓躲慢熊）
        if bear:
            _today = str(self._last_trade_date)[:10]
            for code in list(self._holdings.keys()):
                if code in self._exit_pending:
                    continue
                if self._holdings[code].get("fill_date") == _today:
                    continue  # T+1 未解锁，跳过买入成交当天
                self._exit_pending.add(code)
                _sig = self._make_exit_signal(code, reason="熊市空仓")
                if _sig:
                    signals.append(_sig)
            return signals

        # 3. 确认昨日待买候选（收盘确认）
        signals.extend(self._confirm_pending_buys())

        # 4. 无空位则不再扫描（含待成交：已确认待成交也占空位，防超买）
        if len(self._holdings) + len(self._pending_buys) >= eff_max_pos:
            return signals

        # 5. 选股：牛市右侧追强（熊市已在上面空仓返回）
        self._compute_market_momentum()   # 更新相对强度基准
        candidates = self._screen_stocks()
        confirmed = self._recheck_buy_list(candidates)

        slots = eff_max_pos - len(self._holdings) - len(self._pending_buys)
        for target in confirmed[:slots]:
            price = self._get_price(target)
            if price <= 0:
                continue
            _cand_sid = self._gen_id()
            self._buy_pending[target] = {
                "signal_price": price,
                "weight": eff_weight,
                "signal_date": str(self._last_trade_date)[:10],
                "signal_id": _cand_sid,
            }
            # 候选落库（与低吸/ETF 一致，跨重启保留 + 信号追溯）
            if not getattr(self, "_replaying", False):
                self._fire_db(self._persist_candidate(target, self._buy_pending[target]))
            if self.verbose_logging:
                logger.info(f"{self.name} 候选入池: {target}, 信号价={price:.2f}, 仓位={eff_weight:.0%}")

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
            if code in self._rejected_codes:  # F 修复：本批次确认失败当天排除，次日重算
                continue
            score = self._score_candidate(code)
            if score is not None:
                scored.append((code, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        if self.verbose_logging:
            logger.info(f"{self.name} 选股: {len(scored)} 只通过, Top3={[(c, f'{s:.2%}') for c, s in scored[:3]]}")
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
        except Exception as e:
            logger.warning(f"{self.name} 选股评分异常 {code}: {e}")
            return None

    def _recheck_buy_list(self, candidates: List[str]) -> List[str]:
        """复检：今日量>0 / 跳空<5%（5% 阈值已覆盖涨停开盘，无需单独判断）"""
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
            if prev_close > 0 and (today_open - prev_close) / prev_close > 0.05:
                continue
            # 当日涨幅 >9.5%（涨停价）不买（放宽：只防涨停接盘，放行 7~9.5% 强势股追妖）
            today_close = float(closes[-1])
            if prev_close > 0 and (today_close - prev_close) / prev_close > 0.095:
                continue
            confirmed.append(code)
        return confirmed

    # =========================================================================
    # 收盘确认买入
    # =========================================================================
    def _resolve_capital(self) -> float:
        """[契约] sizing 资本统一读 context.total_assets（本策略被授权资本），见策略资金与仓位契约。"""
        return self.resolve_sizing_capital()

    def _confirm_pending_buys(self) -> List[TradingSignal]:
        signals: List[TradingSignal] = []
        if not self._buy_pending:
            return signals
        today = str(self._last_trade_date)[:10]
        capital = self._resolve_capital()
        pending = dict(self._buy_pending)
        self._buy_pending.clear()
        # 判断当前 regime（决定持仓上限/权重上限）
        _regime = self._current_regime() if self.use_annual_gate else 2
        eff_max_pos, _weight_cap = self._position_sizing(_regime)

        # —— 阶段一：对所有候选做价格确认（先确认，再看仓位）——
        # 每个候选都有明确结果：确认失败(rejected) / 确认通过(passed) / 未到确认日(保留待次日)。
        # 修复 2026-08-25：原逻辑先判满仓即跳过确认，导致满仓候选永不确认（8-25 603565 实证）。
        passed: List[Tuple[str, dict, float]] = []
        for code, pinfo in pending.items():
            # [修复 2026-08-25] 同日入池/当日恢复候选未到确认日：
            # 当日收盘价(=信号价)确认恒成立 price<=signal_price 误拒（8-24 603519/603565）。
            # 跳过并放回，待次日收盘确认。
            _sig_date = str(pinfo.get("signal_date", ""))[:10]
            # 严格 T+1：仅确认 signal_date < today 的候选（同日候选留到次日收盘确认，
            # 避免「当日收盘=信号价」恒等误拒）。缺 signal_date 的旧候选按已到确认日处理。
            if _sig_date and _sig_date >= today:
                self._buy_pending[code] = pinfo
                continue
            price = self._get_price(code)
            if price <= 0:
                continue
            signal_price = float(pinfo["signal_price"])
            if price <= signal_price:
                if self.verbose_logging:
                    logger.info(f"买入确认失败: {code} 收盘{price:.2f} ≤ 信号价{signal_price:.2f}")
                # F 修复：确认失败的 code 当天选股阶段排除，次日重新计算（防反复入池循环）
                self._rejected_codes.add(code)
                # v7.2 修复：确认失败须回写信号状态，否则前端信号列表一直停留在"待确认"
                _cand_sid = pinfo.get("signal_id")
                if _cand_sid:
                    # 竞态修复：记录本批次 reject 的候选 id，
                    # _persist_candidate 幂等复用扫描跳过（防 reject 与新候选 persist 竞写覆盖）
                    self._rejected_candidate_ids.add(_cand_sid)
                    self._fire_db(self._mark_candidate_status(
                        _cand_sid, "rejected",
                        f"{SignalRejectReason.CONFIRM_FAILED.value}: 收盘{price:.2f} ≤ 信号价{signal_price:.2f}，确认失败",
                        signal_date=today,
                    ))
                continue
            # 确认通过（收盘 > 信号价）
            passed.append((code, pinfo, price))

        if not passed:
            return signals

        # —— 阶段二：处理确认通过者（先看仓位）——
        # 满仓时在通过候选中选择：按确认相对强度（收盘/信号价）降序，最强优先；
        # 无空位则保留待空位（已明确确认结果，不误判不丢弃）。
        passed.sort(key=lambda x: x[2] / float(x[1]["signal_price"]), reverse=True)
        for code, pinfo, price in passed:
            if len(self._holdings) + len(self._pending_buys) >= eff_max_pos:
                self._buy_pending[code] = pinfo  # 满仓保留待空位（修复#2：候选已确认不丢弃，待空位次日重确认）
                continue
            signal_price = float(pinfo["signal_price"])
            # 封顶权重：单票权重不得超过 max_single_weight（跨行情候选入池防超买）
            weight = min(float(pinfo.get("weight", _weight_cap)), _weight_cap)
            # [契约] amount = min(基准×权重, 可用现金) 封顶，防回撤/跳空超买（见策略资金与仓位契约）
            amount = min(capital * weight, self.resolve_available_cash())
            if amount < price * self.min_lot_size:
                # 现金不足一手 → 保留候选待现金，不强行买 1 手（防超买）
                self._buy_pending[code] = pinfo
                continue
            shares = max(int(amount / price / self.min_lot_size) * self.min_lot_size, self.min_lot_size)
            # [阶段3 单行流转] 候选行直接流转到 pending_manual（待人工审核），
            # 不再单独 promoted 中间态 + 另起买入行；买入信号 parent_id 复用候选行。
            _cand_sid = pinfo.get("signal_id")
            if _cand_sid and not getattr(self, "_replaying", False):
                self._fire_db(self._mark_candidate_status(_cand_sid, "pending_manual", "收盘确认转正", signal_date=today))
            sig = self._make_entry_signal(code, weight, shares, price,
                                          f"右侧追强买入(收盘确认): 收盘{price:.2f} > 信号价{signal_price:.2f}",
                                          parent_id=_cand_sid)
            signals.append(sig)
            # T+1 执行：买入信号 order_mode=open，T+1 开盘才成交。此处只写「待成交」，
            # 次日 _run_rebalance 开头搬到 _holdings（已成交），避免 _holdings 提前一天领先 broker positions。
            self._pending_buys[code] = {
                "entry_price": price,
                "weight": weight,
                "shares": shares,
                "entry_date": today,
                "peak_high": price,
            }
            if self.verbose_logging:
                logger.info(f"{self.name} 买入(收盘确认): {code}, 收盘{price:.2f}, 仓位={weight:.0%}")
        return signals

    # =========================================================================
    # 风控：2×ATR 硬止损 + 2×ATR 移动止损 + 趋势破坏
    # =========================================================================
    def _check_stops_and_trailing(self) -> List[TradingSignal]:
        signals: List[TradingSignal] = []
        _today = str(self._last_trade_date)[:10]
        for code in list(self._holdings.keys()):
            if code in self._exit_pending:
                continue
            # 跳过「买入成交当天」的持仓（T+1 未解锁，可卖 0，当日不砍/不换仓）
            if self._holdings[code].get("fill_date") == _today:
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
            lows = df["low"].values.astype(np.float64) if "low" in df.columns else closes
            current = float(closes[-1])
            day_high = float(highs[-1])
            day_low = float(lows[-1])

            # —— 已去掉 -4% 日内硬止损（对高波动票太紧，盘中 -4% 极常见，误杀强势股、止损后反弹踏空）——
            # 仅保留 2×ATR 自适应止损 + 移动止盈 + 趋势破坏（v5.0 第一性原理：固定 -4% 对高波动票是自杀）

            atr = self._calc_atr(code)

            # 更新阶段高点（移动止损基准）
            peak = max(self._holdings[code].get("peak_high", entry), day_high)
            self._holdings[code]["peak_high"] = peak

            # P2 修复：ATR 无效（<atr_window+1 根 bar 数据）时跳过止损判定，避免 hard_stop=entry / trail_stop=peak 收阴即误平仓
            if atr <= 0:
                continue

            stop_mult = self.atr_stop_mult
            trail_mult = self.atr_trailing_mult

            # —— 1. 硬止损：价格 < 入场价 - N×ATR ——
            hard_stop = entry - stop_mult * atr
            if current < hard_stop:
                if self.verbose_logging:
                    logger.info(f"{self.name} [止损2ATR] {code} 现价{current:.2f} < 入场{entry:.2f}-{stop_mult:.0f}×ATR({atr:.2f})")
                self._exit_pending.add(code)
                signals.append(self._make_exit_signal(
                    code, reason=f"硬止损: 现价{current:.2f} < 入场{entry:.2f}-{stop_mult:.0f}×ATR({atr:.2f})",
                    signal_type=SignalType.STOP_LOSS
                ))
                continue

            # —— 2. 移动止损（让利润奔跑）：价格 < 最高点 - N×ATR ——
            trail_stop = peak - trail_mult * atr
            if current < trail_stop:
                if self.verbose_logging:
                    logger.info(f"{self.name} [移动止盈] {code} 现价{current:.2f} < 最高{peak:.2f}-{trail_mult:.0f}×ATR")
                self._exit_pending.add(code)
                signals.append(self._make_exit_signal(
                    code, reason=f"移动止盈: 最高{peak:.2f}回落{((peak-current)/peak):.1%} > {trail_mult:.0f}×ATR",
                    signal_type=SignalType.TAKE_PROFIT
                ))
                continue

            # —— 3. 趋势破坏兜底：MA50 < MA200 ——
            if len(closes) >= self.ma_long:
                ma_s = float(np.mean(closes[-self.ma_short:]))
                ma_l = float(np.mean(closes[-self.ma_long:]))
                if ma_s < ma_l:
                    if self.verbose_logging:
                        logger.info(f"{self.name} [趋势破坏] {code} MA{self.ma_short}<MA{self.ma_long}")
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
        except Exception as e:
            logger.warning(f"{self.name} ATR 计算异常 {code}: {e}")
            return 0.0

    def _reconcile_holdings(self) -> None:
        """[契约] 反馈闭环：对账 _holdings 与 context.positions（broker 实际持仓），双向。

        1. 卖出确认：_exit_pending 中的票 broker 已无 → 卖出成交，结算 PnL 并移除；
           broker 仍有 → 跌停/停牌挂单中，保留 _exit_pending 与 _holdings 待成交。
        2. 幽灵删除：_holdings 有、broker 无（非 pending）→ 买入被拒，删除。
        3. broker 幽灵回补：broker 有、_holdings 无 → 策略丢失跟踪（历史残留），回补。
        见 docs/01-业务设计/策略资金与仓位契约.md §3.4。
        """
        if self._is_live_mode():
            return  # 实盘/模拟盘由 _active_positions 管理，context.positions 不同步，不对账
        broker_positions = getattr(self.context, "positions", None) if self.context else None
        if broker_positions is None:
            return  # 无同步数据（context 未注入）才跳过；空 dict（broker 清仓）仍要结算卖出/删幽灵

        # 1. 卖出确认 / 未成交（跌停挂单中）
        for code in list(self._exit_pending):
            bp = broker_positions.get(code)
            if bp is None or int(getattr(bp, "quantity", 0) or 0) <= 0:
                # broker 已无此持仓 → 卖出成交 → 结算 PnL + 移除
                if code in self._holdings:
                    entry = float(self._holdings[code].get("entry_price", 0) or 0)
                    w = float(self._holdings[code].get("weight", 1.0) or 1.0)
                    exit_price = self._get_price(code)
                    if entry > 0 and exit_price > 0:
                        pnl = (exit_price - entry) / entry
                        self._nav_realized *= 1.0 + pnl * w
                    del self._holdings[code]
                self._exit_pending.discard(code)
            # else: broker 仍有 → 跌停/停牌未成交，保留 _exit_pending 待下日成交

        # 2. 幽灵删除：_holdings 有、broker 无（不在 _exit_pending，已由 1 处理）
        for code in list(self._holdings.keys()):
            bp = broker_positions.get(code)
            if bp is None or int(getattr(bp, "quantity", 0) or 0) <= 0:
                if self.verbose_logging:
                    logger.info(f"{self.name} 对账删幽灵持仓: {code}")
                del self._holdings[code]
                continue
            actual_qty = int(getattr(bp, "quantity", 0) or 0)
            recorded_qty = int(self._holdings[code].get("shares", 0) or 0)
            if recorded_qty != actual_qty:
                # 跳空部分成交/补仓 → 用 broker 实际股数校正
                self._holdings[code]["shares"] = actual_qty

        # 3. broker 幽灵回补：broker 有、_holdings 无（且不在 pending）
        for code, bp in broker_positions.items():
            qty = int(getattr(bp, "quantity", 0) or 0)
            if qty <= 0:
                continue
            if code in self._holdings or code in self._pending_buys or code in self._exit_pending:
                continue
            # 策略丢失跟踪（如历史跌停卖不出的残留）→ 回补
            avg_cost = float(getattr(bp, "avg_cost", 0) or 0)
            cur_price = self._get_price(code)
            entry_price = avg_cost if avg_cost > 0 else cur_price
            _weight = self.max_single_weight
            if self.verbose_logging:
                logger.info(f"{self.name} 对账回补丢失持仓: {code} 数量={qty} 成本={entry_price:.2f}")
            self._holdings[code] = {
                "entry_price": entry_price,
                "weight": _weight,
                "shares": qty,
                "entry_date": str(self._last_trade_date)[:10],
                "peak_high": cur_price if cur_price > 0 else entry_price,
            }

    # =========================================================================
    # Regime（年线门）
    # =========================================================================
    def _current_regime(self) -> int:
        """返回 regime：0熊/1震/2牛，用中证1000 指数 vs MA250 ±band 判。

        - 外部注入 regime（组合层 CapitalAllocator）优先，无注入时自算兜底（单策略回测）。
        - 自算：读 index_daily 中证1000 收盘 → compute_regime（指数均线偏离）。
        """
        # regime 注入：组合场景下组合层统一判，策略跟随（与资金分配不打架）
        if self._injected_regime is not None:
            return self._injected_regime
        if not self.use_annual_gate or not self._last_trade_date:
            return 2
        td = str(self._last_trade_date)[:10]
        from shared.market_regime import compute_regime
        return compute_regime(self._index_cache, td, self.regime_band)

    def set_injected_regime(self, regime: Optional[int]) -> None:
        """组合层注入 regime（多策略回测/实盘）；传 None 清除注入，走自算兜底。"""
        self._injected_regime = regime

    def _annual_line_gate(self) -> bool:
        """指数 < MA250×(1-band) → 熊市停买。"""
        return self._current_regime() == 0

    def _position_sizing(self, regime: int) -> Tuple[int, float]:
        """按 regime 返回 (最大持仓数, 单票权重)。

        熊市(0) 空仓 0×0；震荡(1) 半仓 1×50%；牛市(2) 满仓 2×50%。
        """
        if regime == 0:
            return 0, 0.0  # 熊市：空仓
        if regime == 1:
            return 1, 0.5  # 震荡：半仓（1只×50%）
        return self.max_positions, self.max_single_weight  # 牛市满仓（2×50%）

    # =========================================================================
    # 信号构造（四大模块）
    # =========================================================================
    # ==================== 候选落库（与低吸/ETF 一致） ====================
    def _is_live_mode(self) -> bool:
        """判断是否实盘/模拟盘模式（仅实盘持久化候选，回测不写 signals 表）。"""
        rm = getattr(getattr(self, "context", None), "run_mode", None)
        if rm is None:
            return False
        v = rm.value if hasattr(rm, "value") else rm
        return v in ("live", "paper")

    def _fire_db(self, coro) -> None:
        """在同步策略方法中调度异步 DB 写任务（fire-and-forget）。"""
        try:
            import asyncio
            asyncio.get_running_loop().create_task(coro)
        except RuntimeError:
            logger.debug("事件循环未运行，跳过候选 DB 写入")

    async def _mark_candidate_status(self, sig_id, status: str, reason: str = "", signal_date=None) -> None:
        """更新候选信号行的状态（promoted 转正 / rejected / expired）。

        signal_date: 状态变更日，传入时同步更新 signal_time（状态流转时间闭环，
        消除「候选创建日」与「转正日」混淆导致的"当天转正"假象）。
        """
        if not self._is_live_mode():
            return
        sf = getattr(self, "_db_session_factory", None)
        if not sf or not sig_id:
            return
        try:
            from shared.database.repositories.strategy.signal.signal_repo import SignalRepository
            _data = {"signal_status": status, "reason": reason}
            if signal_date:
                _d = signal_date
                if isinstance(_d, str):
                    _d = date.fromisoformat(_d[:10])
                _data["signal_time"] = datetime.combine(_d, beijing_now().time(), tzinfo=BEIJING_TZ)
            async with sf() as db:
                await SignalRepository(db).update(sig_id, _data)
                await db.commit()
        except Exception as e:
            logger.warning(f"候选状态更新失败({status}): {e}")

    async def _persist_candidate(self, code: str, pinfo: dict) -> None:
        """候选落库：signals 表 pending_confirm（与低吸/ETF 一致，跨重启保留）。"""
        sf = getattr(self, "_db_session_factory", None)
        if not sf or not self._is_live_mode():
            return
        sid = getattr(getattr(self, "context", None), "strategy_id", "") or self.name
        sig_id = pinfo.get("signal_id")
        if not sid or not sig_id:
            return
        try:
            from shared.database.repositories.strategy.signal.signal_repo import SignalRepository
            async with sf() as db:
                # [阶段2] 落库前校验：已持仓 / 未了结买入意图 → 拒绝落库（防补仓/重复入池）
                from sqlalchemy import select, text
                from shared.database.models.business_models import Signal
                _pos = (await db.execute(text(
                    "SELECT 1 FROM positions WHERE strategy_id = :sid AND ts_code = :code AND volume > 0"
                ), {"sid": sid, "code": code})).fetchall()
                if _pos:
                    if self.verbose_logging:
                        logger.info(f"{self.name} {code} 已持仓，跳过候选落库")
                    return
                _intent = (await db.execute(select(Signal.id).where(
                    Signal.strategy_id == sid,
                    Signal.ts_code == code,
                    Signal.signal_type == "buy",
                    Signal.signal_status.in_(("promoted", "pending_manual", "approved")),
                ))).scalars().all()
                if _intent:
                    if self.verbose_logging:
                        logger.info(f"{self.name} {code} 已有未了结买入意图，跳过候选落库")
                    return
                repo = SignalRepository(db)
                _td = getattr(self, "_last_trade_date", None)
                if isinstance(_td, str):
                    try:
                        _td = date.fromisoformat(_td[:10])
                    except ValueError:
                        _td = None
                elif hasattr(_td, "date"):
                    _td = _td.date()
                # 时间戳修复：日期保留交易日 _td（跨日确认依赖），
                # 时刻用 beijing_now().time()（北京时间具体时分秒，此前 00:00 固定）
                _sig_time = datetime.combine(_td, beijing_now().time(), tzinfo=BEIJING_TZ) if _td else beijing_now()
                data = {
                    "strategy_id": sid,
                    "ts_code": code,
                    "direction": "long",
                    "signal_type": "buy",
                    "signal_time": _sig_time,
                    "price": float(pinfo.get("signal_price", 0) or 0),
                    "strength": float(pinfo.get("weight", 0.5) or 0.5),
                    "signal_status": "pending_confirm",
                    "reason": "高波动候选，待次日收盘确认",
                }
                existing = await repo.get(sig_id)
                if not existing:
                    # 幂等：同代码已存在 pending_confirm 候选 → 复用其行
                    # 竞态修复：跳过本批次确认失败的候选（reject 可能未提交，
                    # 复用会覆盖 rejected → 必须跳过并新建行）
                    _dups = await repo.get_by_stock(ts_code=code, strategy_id=sid, limit=20)
                    for _d in _dups:
                        if _d.id in self._rejected_candidate_ids:
                            continue
                        if getattr(_d, "signal_status", None) == "pending_confirm":
                            sig_id = _d.id
                            pinfo["signal_id"] = sig_id
                            existing = _d
                            break
                if existing:
                    await repo.update(sig_id, data)
                else:
                    data["id"] = sig_id
                    await repo.create(data)
                await db.commit()
        except Exception as e:
            logger.warning(f"候选持久化失败: {code}: {e}")

    async def _restore_candidates_from_db(self, db=None) -> None:
        """从 signals 表读回 pending_confirm 候选，重建 _buy_pending（重启恢复）。"""
        sf = getattr(self, "_db_session_factory", None)
        if not sf:
            return
        sid = getattr(getattr(self, "context", None), "strategy_id", "") or self.name
        if not sid:
            return
        try:
            from sqlalchemy import select
            from shared.database.models.business_models import Signal
            async with sf() as db_session:
                rows = (await db_session.execute(select(Signal).where(
                    Signal.strategy_id == sid,
                    Signal.signal_status == "pending_confirm",
                ))).scalars().all()
                restored = 0
                for r in rows:
                    _sd = r.signal_time.strftime("%Y-%m-%d") if r.signal_time else ""
                    if _sd:
                        try:
                            if (date.today() - date.fromisoformat(_sd)).days > 5:
                                await self._mark_candidate_status(r.id, "expired", f"{SignalRejectReason.EXPIRED_UNCONFIRMED.value}: 过期未确认")
                                continue
                        except (ValueError, TypeError):
                            pass
                    self._buy_pending[r.ts_code] = {
                        "signal_price": float(r.price or 0),
                        "weight": float(r.strength or 0.5) if getattr(r, "strength", None) else 0.5,
                        "signal_date": _sd,
                        "signal_id": r.id,
                    }
                    restored += 1
                if restored:
                    logger.info(f"[{self.name}] 重启恢复候选 {restored} 只 (pending_confirm)")
        except Exception as e:
            logger.warning(f"候选恢复失败: {e}")

    async def load_live_state(self, db, strategy_id=None, **kwargs):
        """覆写：注入实盘状态后，从 DB 恢复 pending_confirm 候选（重启不丢候选）。"""
        await super().load_live_state(db, strategy_id=strategy_id, **kwargs)
        try:
            await self._restore_candidates_from_db()
        except Exception as e:
            logger.warning(f"[{self.name}] 候选恢复失败: {e}")

    def _make_entry_signal(self, code, weight, shares, price, reason, parent_id=None) -> Optional[TradingSignal]:
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
            order_mode="open",  # T+1 开盘成交：贴近实盘人工「当天信号→次日成交」，避免当日收盘买卖偏乐观
        )
        sig.weight = weight
        if parent_id:
            sig.parent_id = parent_id  # 候选→买入信号 链路关联
        return sig

    def _make_exit_signal(
        self, code, reason, signal_type=SignalType.EXIT,
        order_mode="open", trigger_price=None,
    ) -> Optional[TradingSignal]:
        price = self._get_price(code)
        if price <= 0:
            return None
        # 修复：出场数量 = 实际持仓股数（全平）。此前硬编码 0 导致「建议数量 0 股」，
        # 且全自动模式下会下 0 股单卖不掉。_holdings 在买入(本文件 653 行)与
        # 重启恢复(strategy_manager 2006 行)两条路径均写入 "shares"。
        shares = int(self._holdings.get(code, {}).get("shares", 0) or 0)
        return TradingSignal(
            id=self._gen_id(),
            strategy_id=self.name,
            strategy_name=self.name,
            ts_code=code,
            signal_type=signal_type,
            direction=SignalDirection.CLOSE_LONG,
            price=price,
            quantity=shares,
            amount=shares * price,
            confidence=0.80,
            reason=reason,
            timestamp=datetime.now(),
            order_mode=order_mode,  # 默认 T+1 开盘成交；人工盯盘硬止损走 trigger 模式（当日触发价成交）
            trigger_price=trigger_price,
        )

    def generate_entry_signals(
        self, target: Dict[str, float], reason: str = ""
    ) -> List[TradingSignal]:
        signals = []
        for code, weight in target.items():
            price = self._get_price(code)
            if price <= 0:
                continue
            capital = self._resolve_capital()
            shares = max(int(capital * weight / price / self.min_lot_size) * self.min_lot_size,
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
        # 性能：df.loc 逐行追加 ~140μs/次（347 万次 ≈ 8 分钟），
        # 改为 append 到 list（~0.1μs），调仓前 _flush_pending_rows 一次性批量转 DataFrame
        self._pending_rows.setdefault(ts_code, []).append([
            bar_date,
            getattr(bar, "open", bar.close),
            getattr(bar, "high", bar.close),
            getattr(bar, "low", bar.close),
            bar.close,
            bar.volume,
            getattr(bar, "amount", 0.0),
        ])

    def _flush_pending_rows(self) -> None:
        """把 on_bar 累积的 pending 行批量合并到 _data_cache（替代逐行 df.loc 追加）。"""
        if not self._pending_rows:
            return
        cols = ["trade_date", "open", "high", "low", "close", "volume", "amount"]
        for code, rows in self._pending_rows.items():
            if not rows:
                continue
            new_df = pd.DataFrame(rows, columns=cols)
            df = self._data_cache.get(code)
            if df is None or len(df) == 0:
                self._data_cache[code] = new_df
            else:
                self._data_cache[code] = pd.concat([df, new_df], ignore_index=True)
            if len(self._data_cache[code]) > self.lookback_days + 60:
                self._data_cache[code] = self._data_cache[code].tail(self.lookback_days + 60).reset_index(drop=True)
        self._pending_rows.clear()

    @staticmethod
    def _gen_id() -> str:
        import uuid
        return str(uuid.uuid4())

    # =========================================================================
    # 查询接口
    # =========================================================================
    def get_parameters(self) -> Dict[str, Any]:
        return {
            "strategy_version": "v9.0",
            "universe": "all_market",
            "max_positions": self.max_positions,
            "max_single_weight": self.max_single_weight,
            "atr_stop_mult": self.atr_stop_mult,
            "atr_trailing_mult": self.atr_trailing_mult,
            "use_annual_gate": self.use_annual_gate,
            "current_holding_count": len(self._holdings),
            "universe_size": len(getattr(self, "_universe", [])),
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
