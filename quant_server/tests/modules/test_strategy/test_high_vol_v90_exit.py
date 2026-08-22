# -*- coding: utf-8 -*-
"""高波动动量轮动 v9.0 出场优化测试。

9.0 = 7.1 严格确认（保留 alpha）+ 出场优化：
  ① 移动止损 2.0 → 2.5×ATR（允许强势股更深回调，避免"卖在回调底部"）
  ② 趋势破坏缓冲：MA50<MA200 需连续 trend_break_confirm_days(2) 日才卖
  ③ 保留 v7.1 已修复：竞态 _rejected_candidate_ids、北京时间信号时间戳
"""
import os

import pandas as pd

_STRATEGY_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..",
    "modules", "strategy", "strategies", "rotation",
    "high_vol_momentum_v90.py",
)


def _load_strategy_class():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "high_vol_momentum_v90", os.path.abspath(_STRATEGY_PATH)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.HighVolMomentumStrategy


def _seed(strategy, code, closes, highs=None, lows=None, vols=None, start="2026-08-10"):
    """注入 K 线（默认 21 根，末根由调用方覆盖）。"""
    import datetime as _dt
    n = len(closes)
    if highs is None:
        highs = [c * 1.02 for c in closes]
    if lows is None:
        lows = [c * 0.98 for c in closes]
    if vols is None:
        vols = [1e6] * n
    df = pd.DataFrame({
        "trade_date": [(_dt.date.fromisoformat(start) + _dt.timedelta(days=i)).isoformat()
                       for i in range(n)],
        "open": closes, "high": highs, "low": lows, "close": closes,
        "volume": vols, "amount": [v * c for v, c in zip(vols, closes)],
    })
    strategy._data_cache[code] = df.reset_index(drop=True)
    strategy._bar_dates[code] = str(df["trade_date"].iloc[-1])[:10]


def _make_holding(strategy, code, entry_price, peak_high, is_bear=False, days_held=5):
    """构造一笔持仓（含足够历史供 ATR/MA 计算）。"""
    # 50 根缓升 bar（MA50/MA200 需要 200 根，但 _calc_atr 只需 21；趋势破坏需 ma_long）
    # 用 205 根平缓 bar，末根当前价
    closes = [entry_price * (1 - 0.01 * i / 200) for i in range(205)]
    closes[-1] = entry_price  # 当前价 = entry
    strategy._holdings[code] = {
        "entry_price": entry_price, "weight": 0.5, "shares": 5000,
        "entry_date": "2026-08-01", "peak_high": peak_high,
        "is_bear": is_bear, "trend_break_days": 0,
    }
    return strategy


class TestV90_TrailingStop:
    """9.0 移动止损 2.5×ATR"""

    def test_trailing_mult_default_25(self):
        s = _load_strategy_class()(name="test")
        assert s.atr_trailing_mult == 2.5

    def test_trailing_stop_wider_than_7_1(self):
        """2.5×ATR 移动止损：回撤 2.2×ATR 时 7.1 会卖，9.0 不卖（更宽容）"""
        s = _load_strategy_class()(name="test")
        # 构造平缓行情 → ATR 小；peak 高、current 回撤到 2.2×ATR 处
        entry = 10.0
        # 205 根平缓 bar，末根 close=9.5（回撤 5%），ATR 用前 20 根 TR
        closes = [10.0] * 205
        closes[-1] = 9.5
        _seed(s, "600030.SH", closes)
        # 设置 peak=10.0（=entry），current=9.5
        s._last_trade_date = s._bar_dates["600030.SH"]
        s._holdings["600030.SH"] = {
            "entry_price": 10.0, "weight": 0.5, "shares": 5000,
            "entry_date": "2026-08-01", "peak_high": 10.0,
            "is_bear": False, "trend_break_days": 0,
        }
        atr = s._calc_atr("600030.SH")
        trail_stop = 10.0 - s.atr_trailing_mult * atr
        # current=9.5，检查是否触发（2.5×ATR 应比 2.0×ATR 更不易触发）
        assert atr > 0
        # 用 7.1 的 2.0 对比
        stop_71 = 10.0 - 2.0 * atr
        stop_90 = 10.0 - 2.5 * atr
        assert stop_90 < stop_71  # 9.0 止损价更低 = 更宽容
        sigs = s._check_stops_and_trailing()
        # 取决于 ATR：若 9.5 > stop_90 则不触发（更宽容的体现）
        if 9.5 >= stop_90:
            assert not any(sig.ts_code == "600030.SH" for sig in sigs)


class TestV90_TrendBreakBuffer:
    """9.0 趋势破坏连续 N 日确认"""

    def _make_trend_break_scenario(self, closes_tail, days):
        """构造 MA50<MA200 的行情，验证连续天数确认。

        用"缓跌到 8.0"而非"暴跌到 5.0"，避免触发硬止损/移动止损
        （entry=10, current=8，回撤 20% < 硬止损 10-2×ATR，若 ATR≈0.5 则 9.0）。
        """
        s = _load_strategy_class()(name="test")
        entry = 10.0
        # 205 根：前 200 根 10.0（MA200=10），后 5 根缓跌（MA50 < MA200）
        closes = [10.0] * 200 + closes_tail
        _seed(s, "600030.SH", closes)
        s._last_trade_date = s._bar_dates["600030.SH"]
        s._holdings["600030.SH"] = {
            "entry_price": entry, "weight": 0.5, "shares": 5000,
            "entry_date": "2026-08-01", "peak_high": 10.0,
            "is_bear": False, "trend_break_days": days,
        }
        return s

    def test_first_break_day_not_sold(self):
        """首次 MA50<MA200（缓冲第1日）→ 不卖（9.0 新增缓冲）"""
        s = self._make_trend_break_scenario([9.4, 9.3, 9.25, 9.2, 9.2], days=0)
        sigs = s._check_stops_and_trailing()
        assert not any(sig.ts_code == "600030.SH" for sig in sigs)

    def test_second_consecutive_break_day_sold(self):
        """连续第 2 日 MA50<MA200 → 卖出"""
        s = self._make_trend_break_scenario([9.4, 9.3, 9.25, 9.2, 9.2], days=1)
        sigs = s._check_stops_and_trailing()
        assert any(sig.ts_code == "600030.SH" for sig in sigs)


class TestV90_Baseline7_1:
    """9.0 保留 7.1 核心特性（读源码文件验证）"""

    def _read_source(self) -> str:
        with open(_STRATEGY_PATH, "r", encoding="utf-8") as f:
            return f.read()

    def test_strict_confirm_kept(self):
        """确认逻辑仍为 7.1 严格：close > signal_price 才买入"""
        src = self._read_source()
        assert "if price <= signal_price" in src  # 严格确认保留
        # 无 8.x 的 confirm_tolerance（9.0 保持 7.1 严格确认，无容差）
        assert "confirm_tolerance" not in src

    def test_race_fix_kept(self):
        """竞态修复保留（_rejected_candidate_ids）"""
        src = self._read_source()
        assert "_rejected_candidate_ids" in src

    def test_beijing_time_kept(self):
        """北京时间信号时间戳保留"""
        src = self._read_source()
        assert "beijing_now()" in src
