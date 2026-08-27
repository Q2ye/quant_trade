# -*- coding: utf-8 -*-
"""
高波动动量轮动策略 v7.1（第一性原理 · 右侧追强 · 熊市温和启动 · 宽止损）
====================================================================================
目标：年化 40-80%（不可下修）。MDD < 30%，赔率 > 2:1。

第一性原理（数学路径）：
  月均 +5%（年化80%） = 满仓集中 1-2 只 × 盈亏比 3:1 × 胜率 40%
    单笔期望 = 0.4×(+30%) - 0.6×(-10%) = +6% → 每月 1-2 笔 → 年化 ~100%
  因此三个必须：
    ① 必须集中（2×50%）—— 分散到 3×33% 单票贡献减半，够不着 80%
    ② 必须让利润奔跑（无固定止盈，ATR移动止损）—— 没有右尾就没有 80%
    ③ 必须控制亏损（2×ATR 自适应止损）—— 固定 -4% 对高波动票是自杀

版本迭代（v5 → v7.2 优化积累）：
  v5.0  第一性原理重写：右侧追强（创新高 + MA50>MA200 + 放量）+ 多因子打分
        （60日动量 + 20日加速 + 相对强度）+ ATR移动止损(2×ATR) + 年线门
        → 5年+297%、MDD 29.3%（首个达标版本）
  v6.0  尝试（扩池/回调入场方向），未达预期，被 v7 取代
  v7.0  熊市分支（温和放量启动）：年线下不放量突破→空仓；放量 + 动量<0.05
        + ATR<0.3 + 距MA20<0.10 → 1只25%仓位。依据：熊市假突破 avg=-0.97%，
        温和启动过滤 → +2.47%、胜率49%。结果 +208%（熊市分支未达预期）
  v7.1  熊市独立宽止损：v7.0 教训——温和启动股波动小，2×ATR 移动止损太紧，
        85% 交易 1-3 天被截断（avg_win 仅 +2.84%）。改 trailing 3.5×ATR +
        硬止损 2.5×ATR，让赢家奔跑。附修复：跨行情候选按当前 regime 封顶权重
        （P1-1）、趋势破坏退出跳过熊市持仓（P1-2，否则宽止损被架空）、
        ATR<=0 保护。→ +299.30%、MDD 33.94%、夏普 1.18
  v7.2  慢熊改进（A+B 组合，2026-08-11 已回测验证 → 放弃，代码回退 v7.1）：
        A 市场动量确认（年线门 + CSI500 MA20>MA60 + 近20日动量>0）
        B 追强信号质量门槛（mom60≥0.08 + rs>0 + mom20>0）
        ※ 回测结论：A 负优化（+177%/MDD31.8%，2025 大牛损失 213pp），
          B 完全无效（B-only = 7.1，过滤从不触发）→ 本版本不保留

通用机制（跨策略候选落库，v6.14 起统一）：
  - 候选信号落库 signals 表（pending_confirm + signal_id），前端信号列表可见
  - 确认转正 promoted + 买入信号 parent_id（候选→信号→订单 全链路追溯）
  - 重启从 DB 恢复候选（跨重启不丢）
  - 重放（silent replay）抑制候选落库，防脏候选
  - 回测不落库（_is_live_mode 仅实盘/模拟盘持久化）

设计要点：
  - 全市场主板扫描，无市值上限（翻倍股 86% 在 200 亿以下），只设流动性下限
  - 牛市：多因子打分（60日动量+20日加速+相对强度），右侧追强 Top2
  - 熊市：温和放量启动（量比≥2+创新高+动量<0.05+ATR<0.3+距MA20<0.10），1×25% 降仓
  - 持有：无止盈目标；2×ATR 自适应移动止损（从最高点回撤即走），趋势破坏兜底
  - Regime：CSI500 年线门（熊市降仓/空仓，不裸奔）
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
    """高波动动量轮动策略 v7.1（右侧追强 · 熊市温和启动 · 宽止损）"""

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
        "use_annual_gate": True,         # CSI500 收盘<MA250 熊市
        "annual_gate_band": 0.03,        # 年线门偏离阈值（±3%，统一 shared.market_regime）

        # —— v7.0 熊市分支（温和放量启动） ——
        # 熊市（年线下）不放量突破 → 空仓；放量突破+温和过滤 → 1只25%仓位
        "bear_max_positions": 1,          # 熊市最大持仓数（降仓）
        "bear_single_weight": 0.25,       # 熊市单票权重（25%）
        "bear_vol_ratio": 2.0,            # 熊市放量阈值：当日量 ≥ 近20日均量 × 此值
        "bear_mom60_max": 0.05,           # 熊市动量上限（排除已暴涨高位股）
        "bear_atr_max": 0.30,             # 熊市波动上限（排除游资暴炒）
        "bear_ma20_dev_max": 0.10,        # 熊市距MA20上限（刚启动未过热）

        # —— v7.1 熊市独立宽止损（让温和启动赢家奔跑） ——
        # v7.0 教训：熊市温和启动股波动小，2×ATR 移动止损太紧，
        # 85% 交易 1-3 天被截断（avg_win 仅 +2.84%，信号级 +2.47% 未兑现）。
        # v7.1 熊市持仓用更宽止损：trailing 3.5×ATR + 硬止损 2.5×ATR，让趋势走出来。
        "bear_atr_trailing_mult": 3.5,    # 熊市移动止损倍数（牛市 2.0 → 熊市 3.5）
        "bear_atr_stop_mult": 2.5,        # 熊市硬止损倍数（牛市 2.0 → 熊市 2.5）

        # —— 运行 ——
        "verbose_logging": True,
    }

    def __init__(
        self,
        name: str = "高波动动量轮动v7.1",
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
        self.annual_gate_band = float(merged.get("annual_gate_band", 0.03))
        # v7.0 熊市分支参数
        self.bear_max_positions = int(merged.get("bear_max_positions", 1))
        self.bear_single_weight = float(merged.get("bear_single_weight", 0.25))
        self.bear_vol_ratio = float(merged.get("bear_vol_ratio", 2.0))
        self.bear_mom60_max = float(merged.get("bear_mom60_max", 0.05))
        self.bear_atr_max = float(merged.get("bear_atr_max", 0.30))
        self.bear_ma20_dev_max = float(merged.get("bear_ma20_dev_max", 0.10))
        # v7.1 熊市独立宽止损
        self.bear_atr_trailing_mult = float(merged.get("bear_atr_trailing_mult", 3.5))
        self.bear_atr_stop_mult = float(merged.get("bear_atr_stop_mult", 2.5))
        # 运行
        self.verbose_logging = bool(merged.get("verbose_logging", True))

        # ---- 状态 ----
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._bar_dates: Dict[str, str] = {}
        self._st_stocks: Set[str] = set()
        self._listing_dates: Dict[str, str] = {}
        self._holdings: Dict[str, Dict] = {}    # {code: {entry_price, weight, shares, entry_date, peak_high}}
        self._exit_pending: Set[str] = set()
        self._confirmed_active: Set[str] = set()  # 已确认转正且未卖出 → 选股排除（防补仓）
        self._buy_pending: Dict[str, dict] = {}
        # 竞态修复：本批次确认失败（rejected）的候选 id ——
        # persist 幂等复用须跳过，避免 fire-and-forget reject 与新候选 persist 竞写同一行
        self._rejected_candidate_ids: Set[str] = set()
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
        logger.info(f"高波动动量轮动 v7.1 初始化: 牛市追强+熊市温和启动+宽止损, 持仓≤{self.max_positions}×{self.max_single_weight:.0%}, "
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
                logger.info(f"{self.name} 全市场股票池已加载: {len(self._universe)} 只主板股 "
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
                signals = self._run_rebalance()
                self._last_rebalance_date = td
                self._first_screen_done = True
        except Exception as e:
            logger.error(f"{self.name} on_bar_batch_end 异常: {trade_date}: {e}", exc_info=True)
        return signals

    # =========================================================================
    # 主调仓（牛市右侧追强 + 熊市温和启动 + ATR 风控）
    # =========================================================================
    def _run_rebalance(self) -> List[TradingSignal]:
        signals: List[TradingSignal] = []
        # 竞态修复：每批次重置候选拒绝记录（确认失败 → persist 跳过复用）
        self._rejected_candidate_ids.clear()
        if len(self._data_cache) < 10:
            return signals

        # 0. 结算待卖出
        self._finalize_exits()

        # 1. 行情判定（年线门 → 熊市/牛市）
        regime = self._current_regime() if self.use_annual_gate else 2
        bear = regime == 0
        # 持仓上限与单票权重：熊市降仓（1×25%），非熊市满仓（2×50%）
        eff_max_pos = self.bear_max_positions if bear else self.max_positions
        eff_weight = self.bear_single_weight if bear else self.max_single_weight
        if self.verbose_logging:
            _regime_label = {0: "熊市", 1: "震荡", 2: "牛市"}.get(regime, "?")
            logger.info(f"{self.name} 调仓: {_regime_label} 持仓={len(self._holdings)} "
                        f"上限={eff_max_pos} 权重={eff_weight:.0%}")

        # 2. 日频风控（对持仓）：2×ATR 硬止损 + 2×ATR 移动止损 + 趋势破坏
        signals.extend(self._check_stops_and_trailing())

        # 3. 确认昨日待买候选（收盘确认）
        signals.extend(self._confirm_pending_buys())

        # 4. 无空位则不再扫描
        if len(self._holdings) >= eff_max_pos:
            return signals

        # 5. 选股：牛市右侧追强 / 熊市温和放量启动
        if bear:
            candidates = self._screen_bear_market()
        else:
            self._compute_market_momentum()   # 更新相对强度基准
            candidates = self._screen_stocks()
        confirmed = self._recheck_buy_list(candidates)

        slots = eff_max_pos - len(self._holdings)
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
            if code in self._holdings or code in self._exit_pending or code in self._confirmed_active:
                continue
            if code in self._pending_signals or code in self._buy_pending:
                continue
            score = self._score_candidate(code)
            if score is not None:
                scored.append((code, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        if self.verbose_logging:
            logger.info(f"{self.name} 选股: {len(scored)} 只通过, Top3={[(c, f'{s:.2%}') for c, s in scored[:3]]}")
        return [c for c, _ in scored]

    def _screen_bear_market(self) -> List[str]:
        """
        v7.0 熊市选股：温和放量启动（只潜伏低位启动，不追高位暴炒）。

        实证（2022-2024）：熊市纯放量突破 20日 avg=-0.97%（假突破淹没）；
        叠加"温和启动"过滤 → +2.47%、胜率 49%。即：
        放量突破 + 60日动量<0.05（未暴涨）+ ATR<0.3（非暴炒）
                  + 距MA20<0.10（刚启动未过热）

        Returns:
            熊市候选列表（按温和度打分排序）
        """
        scored: List[Tuple[str, float]] = []
        for code in self._data_cache.keys():
            if code in self._holdings or code in self._exit_pending or code in self._confirmed_active:
                continue
            if code in self._pending_signals or code in self._buy_pending:
                continue
            score = self._score_bear_candidate(code)
            if score is not None:
                scored.append((code, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        if self.verbose_logging:
            logger.info(f"{self.name} 熊市选股: {len(scored)} 只温和启动, Top3={[(c, f'{s:.2%}') for c, s in scored[:3]]}")
        return [c for c, _ in scored]

    def _score_bear_candidate(self, code: str) -> Optional[float]:
        """熊市温和启动评分：放量突破 + 温和过滤"""
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
            lows = df["low"].values.astype(np.float64) if "low" in df.columns else closes
            vols = df["volume"].values.astype(np.float64)
            if len(closes) < 80:
                return None

            price = float(closes[-1])
            if price <= 0:
                return None

            # —— ① 放量突破：当日量 ≥ 近20日均量 × bear_vol_ratio ——
            avg_vol20 = float(np.mean(vols[-20:]))
            if avg_vol20 <= 0 or vols[-1] / avg_vol20 < self.bear_vol_ratio:
                return None

            # —— ② 创新高：收盘 ≥ 前 20 日新高（不含当日，防当日 high 恒>close 误判） ——
            if len(highs) < 21:
                return None
            hhv20 = float(np.max(highs[-21:-1]))
            if hhv20 <= 0 or price < hhv20:
                return None

            # —— ③ 动量温和：60日动量 < bear_mom60_max（排除已暴涨） ——
            base60 = closes[-60]
            if base60 <= 0:
                return None
            mom60 = float(np.log(price / base60))
            if mom60 > self.bear_mom60_max:
                return None

            # —— ④ 波动温和：ATR < bear_atr_max（排除游资暴炒） ——
            if len(closes) >= self.atr_window + 1:
                tr = np.maximum(
                    highs[1:] - lows[1:],
                    np.maximum(
                        np.abs(highs[1:] - closes[:-1]),
                        np.abs(lows[1:] - closes[:-1]),
                    ),
                )
                atr = float(np.mean(tr[-self.atr_window:]))
                if atr / price > self.bear_atr_max:
                    return None
            else:
                return None

            # —— ⑤ 未过热：距 MA20 < bear_ma20_dev_max（刚启动） ——
            ma20 = float(np.mean(closes[-20:]))
            if ma20 <= 0 or price / ma20 - 1.0 > self.bear_ma20_dev_max:
                return None

            # 打分：动量越低越"温和"（更接近启动点），加分
            return float(-mom60)
        except Exception:
            return None

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
    def _resolve_capital(self) -> float:
        """解析实际运行资本：context.initial_capital 优先，否则 allocated_capital 参数，兜底 100000。"""
        return float(
            getattr(self.context, "initial_capital", 0)
            or self.parameters.get("allocated_capital", 100000)
        )

    def _confirm_pending_buys(self) -> List[TradingSignal]:
        signals: List[TradingSignal] = []
        if not self._buy_pending:
            return signals
        today = str(self._last_trade_date)[:10]
        capital = self._resolve_capital()
        pending = dict(self._buy_pending)
        self._buy_pending.clear()
        # v7.1: 判断当前是否熊市（决定持仓上限与 is_bear 标志）
        is_bear = self._annual_line_gate() if self.use_annual_gate else False
        eff_max_pos = self.bear_max_positions if is_bear else self.max_positions

        # —— 阶段一：对所有候选做价格确认（先确认，再看仓位）——
        # 每个候选都有明确结果：确认失败(rejected) / 确认通过(passed) / 未到确认日(保留待次日)。
        # 修复 2026-08-25：原逻辑先判满仓即跳过确认，导致满仓候选永不确认（8-25 603565 实证）。
        passed: List[Tuple[str, dict, float]] = []
        for code, pinfo in pending.items():
            # [修复 2026-08-25] 同日入池/当日恢复候选未到确认日：
            # 当日收盘价(=信号价)确认恒成立 price<=signal_price 误拒（8-24 603519/603565）。
            # 跳过并放回，待次日收盘确认。
            _sig_date = str(pinfo.get("signal_date", ""))[:10]
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
            if len(self._holdings) >= eff_max_pos:
                self._buy_pending[code] = pinfo
                continue
            signal_price = float(pinfo["signal_price"])
            # P1-1 修复：按当前 regime 封顶权重（跨行情候选：牛市入池 weight=0.5，熊市确认时不得超 25%）
            _weight_cap = self.bear_single_weight if is_bear else self.max_single_weight
            weight = min(float(pinfo.get("weight", _weight_cap)), _weight_cap)
            amount = capital * weight
            shares = max(int(amount / price / self.min_lot_size) * self.min_lot_size, self.min_lot_size)
            # [阶段3 单行流转] 候选行直接流转到 pending_manual（待人工审核），
            # 不再单独 promoted 中间态 + 另起买入行；买入信号 parent_id 复用候选行。
            _cand_sid = pinfo.get("signal_id")
            if _cand_sid and not getattr(self, "_replaying", False):
                self._fire_db(self._mark_candidate_status(_cand_sid, "pending_manual", "收盘确认转正", signal_date=today))
            sig = self._make_entry_signal(code, weight, shares, price,
                                          f"{'熊市温和启动' if is_bear else '右侧追强'}买入(收盘确认): 收盘{price:.2f} > 信号价{signal_price:.2f}",
                                          parent_id=_cand_sid)
            signals.append(sig)
            self._holdings[code] = {
                "entry_price": price,
                "weight": weight,
                "shares": shares,
                "entry_date": today,
                "peak_high": price,
                "is_bear": is_bear,   # v7.1: 标记熊市持仓，止损用宽参数
            }
            if self.verbose_logging:
                logger.info(f"{self.name} 买入(收盘确认): {code}, 收盘{price:.2f}, 仓位={weight:.0%}, "
                            f"{'熊市' if is_bear else '牛市'}")
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

            # P2 修复：ATR 无效（<atr_window+1 根 bar 数据）时跳过止损判定，避免 hard_stop=entry / trail_stop=peak 收阴即误平仓
            if atr <= 0:
                continue

            # v7.1: 熊市持仓用宽止损（让温和启动赢家奔跑），牛市用原 2×ATR
            is_bear_pos = bool(self._holdings[code].get("is_bear", False))
            stop_mult = self.bear_atr_stop_mult if is_bear_pos else self.atr_stop_mult
            trail_mult = self.bear_atr_trailing_mult if is_bear_pos else self.atr_trailing_mult

            # —— 1. 硬止损：价格 < 入场价 - N×ATR ——
            hard_stop = entry - stop_mult * atr
            if current < hard_stop:
                self._exit_pending.add(code)
                signals.append(self._make_exit_signal(
                    code, reason=f"硬止损: 现价{current:.2f} < 入场{entry:.2f}-{stop_mult:.0f}×ATR({atr:.2f})",
                    signal_type=SignalType.STOP_LOSS
                ))
                continue

            # —— 2. 移动止损（让利润奔跑）：价格 < 最高点 - N×ATR ——
            trail_stop = peak - trail_mult * atr
            if current < trail_stop:
                self._exit_pending.add(code)
                signals.append(self._make_exit_signal(
                    code, reason=f"移动止盈: 最高{peak:.2f}回落{((peak-current)/peak):.1%} > {trail_mult:.0f}×ATR",
                    signal_type=SignalType.TAKE_PROFIT
                ))
                continue

            # —— 3. 趋势破坏兜底：MA50 < MA200（P1-2 修复：熊市持仓跳过此退出，只走 3.5×ATR 宽止损，让温和启动赢家奔跑）——
            if not is_bear_pos and len(closes) >= self.ma_long:
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
                self._confirmed_active.discard(code)  # 卖出后释放占用，可重新纳入选股
        self._exit_pending.clear()

    # =========================================================================
    # Regime（年线门）
    # =========================================================================
    def _current_regime(self) -> int:
        """返回统一 regime：0=熊 1=震 2=牛（shared.market_regime.compute_regime）。"""
        if not self.use_annual_gate or self._csi500_cache.empty or not self._last_trade_date:
            return 2  # 默认非熊（与旧 _annual_line_gate 返回 False 一致）
        from shared.market_regime import compute_regime
        closes_dict = dict(zip(
            self._csi500_cache["trade_date"].astype(str),
            self._csi500_cache["close"].astype(np.float64),
        ))
        return compute_regime(closes_dict, self._last_trade_date, self.annual_gate_band)

    def _annual_line_gate(self) -> bool:
        """CSI500 收盘 < MA250×(1-band) → 停买（熊市）。"""
        return self._current_regime() == 0

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

    async def _rebuild_confirmed_active(self, db=None) -> None:
        """从 signals 表重建「已确认转正且未卖出」的活跃占用集合。

        确认采纳(promoted/executed)即视为占用：选股时排除（防补仓/重复建仓），
        直到卖出(_finalize_exits)释放。跨重启经此恢复。
        """
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
                rows = (await db_session.execute(
                    select(Signal).where(Signal.strategy_id == sid)
                    .order_by(Signal.ts_code, Signal.signal_time.desc())
                )).scalars().all()
                # 每只股票取最新一条信号；最新为 buy 且 promoted/executed → 占用
                seen: Dict[str, Signal] = {}
                for r in rows:
                    if r.ts_code not in seen:
                        seen[r.ts_code] = r
                self._confirmed_active = {
                    code for code, r in seen.items()
                    if str(r.signal_type).lower() in ("buy", "entry", "long")
                    # pending_manual=确认转正后待成交的买入信号，同样视为占用（防补仓）
                    and getattr(r, "signal_status", "") in ("promoted", "executed", "pending_manual")
                }
                if self._confirmed_active:
                    logger.info(f"[{self.name}] 已确认占用恢复: {len(self._confirmed_active)} 只 {sorted(self._confirmed_active)}")
        except Exception as e:
            logger.warning(f"活跃确认集重建失败: {e}")

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
        try:
            await self._rebuild_confirmed_active()
        except Exception as e:
            logger.warning(f"[{self.name}] 已确认占用重建失败: {e}")

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
            order_mode="close",
        )
        sig.weight = weight
        if parent_id:
            sig.parent_id = parent_id  # 候选→买入信号 链路关联
        return sig

    def _make_exit_signal(
        self, code, reason, signal_type=SignalType.EXIT
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
            "strategy_version": "v7.1",
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
