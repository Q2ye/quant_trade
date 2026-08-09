# -*- coding: utf-8 -*-
"""高波动动量轮动策略 v5.0 单元测试（右侧追强 · 2×ATR 风控）"""
import os

import numpy as np
import pandas as pd
import pytest

from core.engines.types.entities import BarData

_STRATEGY_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..",
    "modules", "strategy", "strategies", "rotation",
    "high_vol_momentum_strategy.py",
)


def _load_strategy_class():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "high_vol_momentum", os.path.abspath(_STRATEGY_PATH)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.HighVolMomentumStrategy


def _seed_history(strategy, code, closes, vols=None, highs=None,
                  start="2019-01-01", volume=1e6):
    """注入模拟历史 K 线（含 high/low 供 ATR）"""
    import datetime as _dt
    df = pd.DataFrame(columns=["trade_date", "open", "high", "low", "close", "volume", "amount"])
    base = _dt.date.fromisoformat(start)
    for i, c in enumerate(closes):
        d = base + _dt.timedelta(days=i)
        while d.weekday() >= 5:
            d += _dt.timedelta(days=1)
        h = highs[i] if highs else float(c) * 1.02
        v = vols[i] if vols else volume
        df.loc[len(df)] = {
            "trade_date": d.isoformat(),
            "open": float(c) * 0.99, "high": float(h),
            "low": float(c) * 0.98, "close": float(c),
            "volume": float(v), "amount": float(v) * float(c),
        }
    strategy._data_cache[code] = df.reset_index(drop=True)
    strategy._bar_dates[code] = str(df["trade_date"].iloc[-1])[:10]


class TestTradableFilter:
    """主板过滤"""

    def test_mainboard_allowed(self):
        cls = _load_strategy_class()
        assert cls._is_tradable("600030.SH") is True
        assert cls._is_tradable("002415.SZ") is True

    def test_non_mainboard_blocked(self):
        cls = _load_strategy_class()
        assert cls._is_tradable("300750.SZ") is False
        assert cls._is_tradable("688981.SH") is False
        assert cls._is_tradable("920001.BJ") is False


class TestScoreCandidate:
    """多因子选股（右侧追强）"""

    def _make_strategy(self):
        cls = _load_strategy_class()
        s = cls(name="test", parameters={"verbose_logging": False})
        return s

    def test_strong_uptrend_scores(self):
        s = self._make_strategy()
        # 持续上行 + 创新高 + 放量 → 应通过
        n = 260
        closes = [100 * (1 + 0.004 * i) for i in range(n)]
        vols = [1e6 * (1.5 if i >= n - 5 else 1.0) for i in range(n)]
        _seed_history(s, "600030.SH", closes, vols=vols)
        s._last_trade_date = s._bar_dates["600030.SH"]
        s._market_mom60 = 0.0
        score = s._score_candidate("600030.SH")
        assert score is not None and score > 0

    def test_downtrend_rejected(self):
        s = self._make_strategy()
        n = 260
        closes = [100 * (0.99 ** i) for i in range(n)]
        _seed_history(s, "600030.SH", closes)
        s._last_trade_date = s._bar_dates["600030.SH"]
        assert s._score_candidate("600030.SH") is None

    def test_not_breakout_rejected(self):
        s = self._make_strategy()
        # 高位横盘：未创新高 → 应拒绝（右侧确认要求）
        n = 260
        closes = [100.0] * n
        _seed_history(s, "600030.SH", closes)
        s._last_trade_date = s._bar_dates["600030.SH"]
        assert s._score_candidate("600030.SH") is None

    def test_st_rejected(self):
        s = self._make_strategy()
        s._st_stocks.add("600030.SH")
        n = 260
        closes = [100 * (1 + 0.004 * i) for i in range(n)]
        _seed_history(s, "600030.SH", closes)
        s._last_trade_date = s._bar_dates["600030.SH"]
        assert s._score_candidate("600030.SH") is None

    def test_stale_bar_rejected(self):
        s = self._make_strategy()
        n = 260
        closes = [100 * (1 + 0.004 * i) for i in range(n)]
        _seed_history(s, "600030.SH", closes)
        s._last_trade_date = "2099-01-01"  # 今日 bar 未推送
        assert s._score_candidate("600030.SH") is None


class TestATRStops:
    """2×ATR 自适应止损"""

    def test_hard_stop_trigger(self):
        cls = _load_strategy_class()
        s = cls(name="test", parameters={"atr_stop_mult": 2.0})
        # 高波动序列：ATR 较大
        closes = [100.0 + (5.0 * (i % 2)) for i in range(30)]
        _seed_history(s, "600030.SH", closes)
        s._last_trade_date = s._bar_dates["600030.SH"]
        atr = s._calc_atr("600030.SH")
        assert atr > 0
        # 入场 100，现价远低于 100-2×ATR → 触发
        result = s.check_stop_profit_stop_loss("600030.SH", 100.0, 80.0)
        assert result is not None and result[0].name == "STOP_LOSS"

    def test_hard_stop_not_trigger_within_atr(self):
        cls = _load_strategy_class()
        s = cls(name="test", parameters={"atr_stop_mult": 2.0})
        closes = [100.0 + (1.0 * (i % 2)) for i in range(30)]  # 低波动
        _seed_history(s, "600030.SH", closes)
        s._last_trade_date = s._bar_dates["600030.SH"]
        # 现价 99，入场 100，-1% 在 2×ATR 内
        result = s.check_stop_profit_stop_loss("600030.SH", 100.0, 99.0)
        assert result is None

    def test_atr_positive_for_volatile(self):
        cls = _load_strategy_class()
        s = cls(name="test")
        closes = [100.0 + (8.0 * (i % 2)) for i in range(30)]  # 高振幅
        _seed_history(s, "600030.SH", closes)
        atr = s._calc_atr("600030.SH")
        assert atr > 4.0  # 大振幅 → ATR 大


class TestAnnualLineGate:
    """年线门"""

    def _make_with_gate(self, closes):
        import datetime as _dt
        cls = _load_strategy_class()
        s = cls(name="test")
        base = _dt.date(2015, 1, 1)
        dates = [(base + _dt.timedelta(days=i)).isoformat() for i in range(len(closes))]
        s._csi500_cache = pd.DataFrame({"trade_date": dates, "close": closes})
        return s

    def test_gate_trigger_when_below_ma250(self):
        closes = [100 * (0.99 ** i) for i in range(300)]
        s = self._make_with_gate(closes)
        s._last_trade_date = s._csi500_cache["trade_date"].iloc[-1]
        assert s._annual_line_gate() is True

    def test_gate_off_when_above_ma250(self):
        closes = [100 * (1.005 ** i) for i in range(300)]
        s = self._make_with_gate(closes)
        s._last_trade_date = s._csi500_cache["trade_date"].iloc[-1]
        assert s._annual_line_gate() is False

    def test_gate_needs_250_days(self):
        closes = [100.0] * 100
        s = self._make_with_gate(closes)
        s._last_trade_date = s._csi500_cache["trade_date"].iloc[-1]
        assert s._annual_line_gate() is False


class TestConfirmBuy:
    """收盘确认买入"""

    def test_confirm_when_close_above_signal(self):
        cls = _load_strategy_class()
        s = cls(name="test")
        s._buy_pending["600030.SH"] = {"signal_price": 100.0, "weight": 0.5,
                                       "signal_date": "2021-01-01"}
        closes = [100.0] * 20 + [102.0]
        _seed_history(s, "600030.SH", closes)
        s._last_trade_date = s._bar_dates["600030.SH"]
        s.context = type("C", (), {"initial_capital": 100000})()
        sigs = s._confirm_pending_buys()
        assert any(sig.ts_code == "600030.SH" and sig.direction.name == "LONG" for sig in sigs)

    def test_reject_when_close_below_signal(self):
        cls = _load_strategy_class()
        s = cls(name="test")
        s._buy_pending["600030.SH"] = {"signal_price": 100.0, "weight": 0.5,
                                       "signal_date": "2021-01-01"}
        closes = [100.0] * 20 + [98.0]
        _seed_history(s, "600030.SH", closes)
        s._last_trade_date = s._bar_dates["600030.SH"]
        s.context = type("C", (), {"initial_capital": 100000})()
        sigs = s._confirm_pending_buys()
        assert not any(sig.ts_code == "600030.SH" for sig in sigs)


class TestPositionSize:
    """仓位管理"""

    def test_clamp(self):
        cls = _load_strategy_class()
        s = cls(name="test")
        assert s.calculate_position_size(1.5) == 1.0
        assert s.calculate_position_size(-0.5) == 0.0
        assert s.calculate_position_size(0.5) == pytest.approx(0.5)


class TestGetParameters:
    """查询接口"""

    def test_version_v5(self):
        cls = _load_strategy_class()
        s = cls(name="test")
        params = s.get_parameters()
        assert params["strategy_version"] == "v5.0"
        assert params["max_positions"] == 2
        assert params["max_single_weight"] == 0.5
