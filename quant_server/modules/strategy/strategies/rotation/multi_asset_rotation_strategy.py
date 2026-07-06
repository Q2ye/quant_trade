# -*- coding: utf-8 -*-
"""
多资产 ETF 轮动策略 — 移植自聚宽参考策略

聚宽原文: https://www.joinquant.com/post/72442
聚宽 5 年回测: 年化 74.24%, 夏普 2.482, 最大回撤 26.45%

核心逻辑：
  1. ETF 池 = A 股宽基 + 跨境(纳指/日经/港股) + 商品(黄金/原油) + 债券
  2. 动量 = 加权对数线性回归斜率 × R²（参考聚宽方法）
  3. 过滤 = 量异常 + RSRS 阻速线
  4. 持有 1 只，全仓进出，每天决策
  5. 止损 = 固定 9% + 日内 3% + 量异常出场

与 IndustryRotationStrategy 的区别：
  - 不依赖 IndustryScoringService（不需要 PE/PB/行业数据）
  - ETF 池为多资产，不限于 A 股行业
  - 动量算法不同（对数线性回归 vs 窗口收益差）
  - 无三层入场过滤、无分批建仓、无市场状态
"""

import logging
import math
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from core.engines.types.entities import BarData
from modules.strategy.constants import StrategyType, SignalDirection, SignalType
from modules.strategy.models import TradingSignal
from modules.strategy.strategies.base.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class MultiAssetRotationStrategy(BaseStrategy):
    """
    多资产 ETF 轮动策略。

    策略类型：ROTATION
    继承 BaseStrategy，遵循 on_bar 驱动模式。

    核心原则：
      - 每天选动量最强的 ETF，全仓持有 1 只
      - 多资产配置（A股/跨境/商品/债券），降低相关性
      - 对数线性回归动量 × R²，更精准捕捉趋势
    """

    strategy_type: StrategyType = StrategyType.ROTATION

    DEFAULT_PARAMS: Dict[str, Any] = {
        # —— ETF 候选池 ——
        "etf_pool": [
            '518880.SH',  # 黄金ETF
            '513100.SH',  # 纳指100
            '513520.SH',  # 日经ETF
            '513020.SH',  # 港股科技
            '510180.SH',  # 上证180
            '588220.SH',  # 科创板
            '159915.SZ',  # 创业板
            '511090.SH',  # 30年国债ETF
            '501018.SH',  # 南方原油
        ],
        # —— 动量参数（参考聚宽：25天对数线性回归） ——
        "momentum_days": 25,        # 回归窗口（交易日）
        "rsrs_window": 18,          # RSRS 计算窗口
        "rsrs_lookback": 250,       # RSRS Beta 回溯天数
        "rsrs_beta_window": 20,     # RSRS Beta 滚动窗口

        # —— 量异常参数 ——
        "volume_check_days": 7,     # 量异常检测周期（日均量）
        "volume_threshold": 2.0,    # 量异常阈值（超过均值 2 倍视为异常）

        # —— 调仓 ——
        "rebalance_frequency": 1,   # 每天调仓
        "top_n": 1,                 # 持有数量

        # —— 止损 ——
        "stop_loss": -0.09,         # 固定止损 -9%
        "intraday_stop_loss": -0.03,  # 日内止损 -3%
        "cooling_period": 3,        # 止损后冷却天数

        # —— 调试 ——
        "verbose_logging": False,
    }

    def __init__(
        self,
        name: str = "多资产ETF轮动",
        strategy_type: StrategyType = StrategyType.ROTATION,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        merged = dict(self.DEFAULT_PARAMS)
        if parameters:
            merged.update(parameters)
        super().__init__(name=name, strategy_type=strategy_type, parameters=merged)

        self.etf_pool: List[str] = list(merged.get("etf_pool", []))
        self.momentum_days: int = int(merged.get("momentum_days", 25))
        self.rebalance_frequency: int = int(merged.get("rebalance_frequency", 1))
        self.top_n: int = int(merged.get("top_n", 1))
        self.verbose_logging: bool = bool(merged.get("verbose_logging", False))

        # —— 运行时状态 ——
        self._data_cache: Dict[str, pd.DataFrame] = {}   # {ETF代码: DataFrame}
        self._bar_count: int = 0
        self._last_rebalance_date: str = ""
        self._last_trade_date: str = ""

        # 持仓跟踪
        self._current_holding: Optional[str] = None       # 当前持仓 ETF 代码
        self._entry_price: float = 0.0
        self._highest_price: float = 0.0
        self._entry_date: str = ""
        self._cooling_until: str = ""                    # 止损后冷却到期日期

        # 缓存
        self._prev_scores: Dict[str, float] = {}          # 上期动量得分
        self._stop_triggered_today: bool = False            # 当日已触发止损，不再买入

    # =============================================================================
    # 生命周期
    # =============================================================================

    def on_init(self) -> None:
        """设置股票池"""
        self._universe = list(self.etf_pool)
        logger.info(
            f"多资产ETF轮动策略初始化: {self.name}, "
            f"ETF池={len(self.etf_pool)}只, "
            f"动量窗口={self.momentum_days}天"
        )

    async def on_start(self) -> None:
        """重置状态"""
        self._bar_count = 0
        self._last_rebalance_date = ""
        self._data_cache.clear()
        self._current_holding = None
        self._entry_price = 0.0
        self._highest_price = 0.0
        self._entry_date = ""
        self._cooling_until = ""
        self._prev_scores.clear()
        self._stop_triggered_today = False

        # 从 DB 预热
        loaded = await self._preload_history()
        if loaded > 0:
            logger.info(f"多资产ETF轮动策略已启动 — 预热 {loaded} 条数据")
        else:
            logger.info("多资产ETF轮动策略已启动（等待 bar 累积）")

    async def _preload_history(self) -> int:
        """从 DB 加载 ETF 历史数据预热缓存"""
        session_factory = getattr(self, "_db_session_factory", None)
        if session_factory is None:
            return 0

        from datetime import date as _dt, timedelta
        from modules.strategy.engines.data_feed_engine import DataFeedEngine as _DFE

        end_date = _dt.today()
        lookback = int(self.momentum_days * 2) + 60
        start_date = end_date - timedelta(days=lookback)

        try:
            async with session_factory() as db:
                engine = _DFE(db)
                df = await engine.load_historical_data(
                    symbols=self.etf_pool,
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
            logger.warning(f"历史预热失败（将等待 bar 累积）: {e}")
        return 0

    def on_stop(self) -> None:
        """清理状态"""
        self._data_cache.clear()
        self._prev_scores.clear()
        self._current_holding = None
        self._stop_triggered_today = False
        logger.info("多资产ETF轮动策略已停止")

    # =============================================================================
    # 核心入口：on_bar
    # =============================================================================

    def on_bar(self, bar: BarData) -> List[TradingSignal]:
        """
        接收一根 K 线。
        只处理 ETF 池中的标的。
        """
        signals: List[TradingSignal] = []
        ts_code = bar.ts_code

        try:
            if ts_code not in self.etf_pool:
                return signals

            # 缓存数据
            self._append_data(ts_code, bar)

            # 记录交易日
            trade_date = getattr(bar, "trade_date", "") or getattr(bar, "datetime", "")
            if isinstance(trade_date, str) and len(trade_date) >= 10:
                trade_date = trade_date[:10]
            self._last_trade_date = trade_date

            # 同一天不重复调仓
            if self._last_rebalance_date and trade_date == self._last_rebalance_date:
                return signals

            self._bar_count += 1

            # 每 rebalance_frequency 日调仓
            if self._bar_count % self.rebalance_frequency == 0:
                signals = self._run_rebalance()
                self._last_rebalance_date = trade_date

        except Exception as e:
            logger.error(f"多资产ETF轮动 on_bar 异常: {ts_code}: {e}", exc_info=True)

        return signals

    # =============================================================================
    # 主调仓
    # =============================================================================

    def _run_rebalance(self) -> List[TradingSignal]:
        """
        核心调仓逻辑，对应聚宽策略3的 strategy_3_calc → sell → buy。

        流程：
          1. 预热检查
          2. 计算所有 ETF 的动量得分（对数线性回归）
          3. 量异常过滤
          4. RSRS 趋势确认过滤
          5. 日内止损检查（当前持仓）
          6. 固定止损检查（当前持仓）
          7. 换仓决策
        """
        signals: List[TradingSignal] = []

        # ---- 重置当日止损标记 ----
        self._stop_triggered_today = False

        # ---- 预热检查 ----
        if len(self._data_cache) < 3:
            return signals

        max_days = max(
            (len(df) for df in self._data_cache.values()), default=0
        )
        if max_days < self.momentum_days + 1:
            return signals

        # ---- 1. 动量排名 ----
        rankings = self._calc_momentum_rankings()
        if not rankings:
            return signals

        # ---- 2. 量异常过滤 ----
        rankings = self._filter_volume(rankings)

        # ---- 3. RSRS 过滤 + 最优选取 ----
        target = self._filter_rsrs(rankings)
        if target is None and rankings:
            # RSRS 无通过者，取动量第一（宽松兜底）
            target = rankings[0][0]
            if self.verbose_logging:
                logger.info(f"RSRS 无通过者，取动量第一: {target} (动量={rankings[0][1]:.4f})")

        if target is None:
            return signals

        if self.verbose_logging:
            self._log_rankings(rankings, target)

        # ---- 4. 日内止损 ----
        if self._current_holding:
            exit_sig = self._check_intraday_stop(self._current_holding)
            if exit_sig:
                logger.info(f"日内止损触发: {self._current_holding}")
                signals.append(exit_sig)
                self._clear_position()
                self._stop_triggered_today = True

        # ---- 5. 固定止损 ----
        if self._current_holding:
            exit_sig = self._check_fixed_stop(self._current_holding)
            if exit_sig:
                logger.info(f"固定止损触发: {self._current_holding}")
                signals.append(exit_sig)
                self._clear_position()
                self._stop_triggered_today = True

        # ---- 6. 换仓决策（同日买卖） ----
        # BacktestEngine 按 signals 列表顺序处理：先卖释放资金 → 再买使用
        if self._current_holding and self._current_holding == target:
            if self.verbose_logging:
                logger.info(f"KEEP: {target}")
            return signals

        # 冷却期检查
        if self._cooling_until and self._last_trade_date < self._cooling_until:
            logger.info(f"冷却期: {self._cooling_until} 前不交易")
            return signals

        # 当日已止损 → 不再买入
        if self._stop_triggered_today:
            if self.verbose_logging:
                logger.debug("当日已触发止损，跳过买入")
            return signals

        # ---- 执行换仓（同日先卖后买） ----
        if self._current_holding:
            signals.append(self._make_exit_signal(
                self._current_holding,
                reason=f"换仓: 动量更优",
            ))
            logger.info(f"卖出: {self._current_holding} → 买入: {target}")

        entry_sig = self._make_entry_signal(target)
        if entry_sig:
            signals.append(entry_sig)
            self._current_holding = target
            self._entry_price = self._get_price(target)
            self._highest_price = self._entry_price
            self._entry_date = self._last_trade_date
            logger.info(f"买入: {target}")

        return signals

    # =============================================================================
    # 动量计算（对数线性回归斜率 × R²）
    # =============================================================================

    def _calc_momentum_rankings(self) -> List[Tuple[str, float]]:
        """
        加权对数线性回归动量。

        对应聚宽参考策略的 filter_moment_rank()。
        使用 momentum_days 天窗口（默认 25），加权拟合。
        """
        results: List[Tuple[str, float]] = []
        days = self.momentum_days

        for code, df in self._data_cache.items():
            closes = df["close"].values.astype(np.float64)
            if len(closes) < days + 1:
                continue

            # 原版 get_etf_rank 第一步：当日从开盘跌超 3% 的不参与排名
            # 对应：cal_cur_to_open_ratio <= stoploss_limit_by_cur_day（-0.03）
            if "open" in df.columns and len(df) >= 2:
                today_open = float(df["open"].iloc[-1])
                today_close = float(closes[-1])
                if today_open > 0 and (today_close - today_open) / today_open <= -0.03:
                    if self.verbose_logging:
                        logger.info(f"开盘暴跌排除 {code}: 开盘{today_open:.2f}→收盘{today_close:.2f} ({(today_close-today_open)/today_open:.1%})")
                    continue

            prices = closes[-(days + 1):]
            # 过滤无效价格
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

                # 尾端跳水检查（连续3日中有任意1日跌幅 > 5%）
                # 原版给 -8 分（不是永久排除，-8 以上还有机会通过 >0 过滤）
                if len(valid) >= 4:
                    changes = valid[-4:][1:] / valid[-4:][:-1] - 1
                    if np.min(changes) < -0.05:
                        score = -8.0

                results.append((code, score))

            except Exception:
                continue

        results.sort(key=lambda x: x[1], reverse=True)

        # 原版 filter_moment_rank 过滤：得分 > 上限的排除（避免极端动量）
        # 对应聚宽：df[(df['score'] > ll) & (df['score'] < hh)] 中 hh=5
        max_score = 5.0
        results = [(c, s) for c, s in results if s < max_score]

        return results

    # =============================================================================
    # 量异常过滤（对应 filter_volume）
    # =============================================================================

    def _filter_volume(self, rankings: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """
        过滤量异常 ETF（对应聚宽原版 filter_volume）。

        原版方式：当日成交量（至检查时刻的累计量）vs 过去 N 日均值。
        我们使用日线 bar：当日总成交量 vs 前 N 日均量。
        若今日量 > 前 N 日均量 × 阈值，视为异常放量，排除。
        """
        if not rankings:
            return []

        filtered = []
        days = int(self.parameters.get("volume_check_days", 7))
        threshold = float(self.parameters.get("volume_threshold", 2.0))

        for code, score in rankings:
            df = self._data_cache.get(code)
            if df is None or len(df) < days + 2:
                filtered.append((code, score))
                continue

            vol = df["volume"].values.astype(np.float64)
            today_vol = vol[-1]
            avg_vol = float(np.mean(vol[-(days + 1):-1]))  # 前 N 天（不含今天）
            if avg_vol > 0 and today_vol / avg_vol > threshold:
                if self.verbose_logging:
                    logger.info(f"量异常过滤 {code}: 今日量={today_vol:.0f}, {days}日均量={avg_vol:.0f}, 倍率={today_vol/avg_vol:.2f}x")
                continue

            filtered.append((code, score))

        return filtered

    # =============================================================================
    # RSRS 阻速线过滤（对应 filter_rsrs）
    # =============================================================================

    def _filter_rsrs(self, rankings: List[Tuple[str, float]]) -> Optional[str]:
        """
        RSRS 阻速线趋势确认。

        对应聚宽参考策略的 filter_rsrs()。
        通过当日斜率与历史 Beta 比较判断趋势强度。
        返回通过筛选且动量最强的 ETF 代码。
        """
        if not rankings:
            return None

        for code, _ in rankings:
            df = self._data_cache.get(code)
            if df is None or len(df) < 30:
                continue

            closes = df["close"].values.astype(np.float64)
            highs = df.get("high", df["close"]).values.astype(np.float64) if "high" in df.columns else closes
            lows = df.get("low", df["close"]).values.astype(np.float64) if "low" in df.columns else closes

            # 1. 计算 RSRS 斜率（当日）
            rsrs_window = int(self.parameters.get("rsrs_window", 18))
            if len(closes) < rsrs_window:
                continue
            slope = float(np.polyfit(lows[-rsrs_window:], highs[-rsrs_window:], 1)[0])

            # 2. 计算 Beta 阈值
            lookback = int(self.parameters.get("rsrs_lookback", 250))
            beta_window = int(self.parameters.get("rsrs_beta_window", 20))
            if len(closes) < min(lookback, beta_window + 1):
                continue

            lookback = min(lookback, len(closes))
            slope_list = []
            for i in range(lookback - beta_window):
                segment_low = lows[i:i + beta_window]
                segment_high = highs[i:i + beta_window]
                if len(segment_low) < beta_window or len(segment_high) < beta_window:
                    continue
                if np.std(segment_low) == 0 or np.std(segment_high) == 0:
                    continue
                s = float(np.polyfit(segment_low, segment_high, 1)[0])
                slope_list.append(s)

            if len(slope_list) < 2:
                continue

            mean_slope = float(np.mean(slope_list))
            std_slope = float(np.std(slope_list))
            beta = mean_slope - 2 * std_slope

            # 3. 计算强度
            strength = (slope - beta) / abs(beta) if abs(beta) > 0.001 else 0.0

            # 4. 检查价格是否在 20 日均线上方（对应原版 _check_above_ma(stock, 20)）
            above_ma20 = False
            if len(closes) >= 20:
                ma20 = float(np.mean(closes[-20:]))
                above_ma20 = closes[-1] >= ma20

            # 5. 决策：斜率 > Beta（RSRS 正信号）
            # 对应原版 filter_rsrs 的三层决策
            if slope > beta:
                if strength > 0.15:
                    return code
                elif strength > 0.03 and above_ma20:
                    return code
                elif above_ma20:
                    return code

        return None

    # =============================================================================
    # 止损检查
    # =============================================================================

    def _check_intraday_stop(self, code: str) -> Optional[TradingSignal]:
        """
        日内止损：当日价格从开盘价下跌超过阈值。
        对应聚宽原版的 etf_stop_loss_by_cur_day + stop_loss_by_cur_day。

        原版方式：检测 (当前价 - 当日开盘价) / 当日开盘价 < -3%
        与我们的方式（累计浮亏）不同。原版专门检测当日表现，
        如果当天从开盘暴跌到收盘/盘中，无论之前赚了多少都止损。
        """
        df = self._data_cache.get(code)
        if df is None or len(df) < 2:
            return None
        # 当日开盘价和收盘价
        today_open = float(df["open"].iloc[-1])
        today_close = float(df["close"].iloc[-1])
        if today_open <= 0:
            return None

        # 日内跌幅 = (收盘价 - 开盘价) / 开盘价
        # 原版使用盘中 realtime 价格，我们使用收盘价近似
        day_loss = (today_close - today_open) / today_open
        threshold = float(self.parameters.get("intraday_stop_loss", -0.03))
        if day_loss < threshold:
            return self._make_exit_signal(
                code,
                reason=f"日内止损: 当日从开盘{today_open:.2f}跌至{today_close:.2f} ({day_loss:.1%})",
                signal_type=SignalType.STOP_LOSS,
            )
        return None

    def _check_fixed_stop(self, code: str) -> Optional[TradingSignal]:
        """固定止损：浮亏超过 9%"""
        if not self._entry_price:
            return None
        current_price = self._get_price(code)
        if current_price <= 0:
            return None

        loss = (current_price - self._entry_price) / self._entry_price
        threshold = float(self.parameters.get("stop_loss", -0.09))
        if loss < threshold:
            return self._make_exit_signal(
                code,
                reason=f"固定止损: 浮亏{loss:.1%} < {threshold:.0%}",
                signal_type=SignalType.STOP_LOSS,
            )
        return None

    # =============================================================================
    # 辅助方法
    # =============================================================================

    def _get_price(self, code: str) -> float:
        """获取最新价格"""
        df = self._data_cache.get(code)
        if df is not None and len(df) > 0:
            return float(df["close"].iloc[-1])
        return 0.0

    def _clear_position(self) -> None:
        """清理持仓状态"""
        self._current_holding = None
        self._entry_price = 0.0
        self._highest_price = 0.0

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
        max_rows = (self.momentum_days * 2) + 300
        if len(self._data_cache[ts_code]) > max_rows:
            self._data_cache[ts_code] = (
                self._data_cache[ts_code].tail(max_rows).reset_index(drop=True)
            )

    def _log_rankings(self, rankings: List[Tuple[str, float]], target: str) -> None:
        """打印动量排名（调试用）"""
        lines = [f"\n{'='*60}", "多资产ETF动量排名"]
        for i, (code, score) in enumerate(rankings[:5]):
            marker = " <<<" if code == target else ""
            lines.append(f"  #{i+1}: {code} 动量={score:.4f}{marker}")
        lines.append(f"{'='*60}")
        logger.info("\n".join(lines))

    # =============================================================================
    # 信号生成
    # =============================================================================

    def _make_entry_signal(self, ts_code: str) -> Optional[TradingSignal]:
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
            reason=f"多资产ETF轮动买入: {ts_code}",
            timestamp=datetime.now(),
        )
        # 全仓：weight = 1.0
        sig.weight = 0.95
        return sig

    def _make_exit_signal(
        self,
        ts_code: str,
        reason: str = "",
        signal_type: SignalType = SignalType.EXIT,
    ) -> TradingSignal:
        """生成卖出信号"""
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
        import uuid
        return str(uuid.uuid4())

    # =============================================================================
    # 查询接口
    # =============================================================================

    def get_holdings(self) -> List[str]:
        if self._current_holding:
            return [self._current_holding]
        return []
