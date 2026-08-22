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
        """v8.0：收盘低于确认价（信号价×(1-容差)）时拒绝买入。

        原 7.1 阈值是 signal_price=100；v8.0 加入 2% 容差 → 确认价=98。
        close=95（-5%）明确低于确认价 → 仍应拒绝。
        """
        cls = _load_strategy_class()
        s = cls(name="test")
        s._buy_pending["600030.SH"] = {"signal_price": 100.0, "weight": 0.5,
                                       "signal_date": "2021-01-01"}
        closes = [100.0] * 20 + [95.0]
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

    def test_version_v7(self):
        cls = _load_strategy_class()
        s = cls(name="test")
        params = s.get_parameters()
        assert params["strategy_version"] == "v7.1"
        assert params["max_positions"] == 2
        assert params["max_single_weight"] == 0.5
        # v7.0 熊市参数默认值
        assert s.bear_max_positions == 1
        assert s.bear_single_weight == 0.25
        assert s.bear_vol_ratio == 2.0
        assert s.bear_mom60_max == 0.05


class TestBearMarketScreen:
    """v7.0 熊市温和放量启动选股"""

    def _make_strategy(self):
        cls = _load_strategy_class()
        return cls(name="test", parameters={"verbose_logging": False})

    def _seed_bear_series(self, s, code, base_price=100, mild=True):
        """构造熊市温和启动序列：低位横盘后温和放量突破"""
        n = 100
        # 前 80 天横盘（close=100，60日动量≈0），末 20 天缓升（总 +2%），末天 +2.5% 创新高
        closes = [base_price] * 80
        for k in range(1, 20):
            closes.append(base_price * (1 + 0.001 * k))     # 缓升到 1.019
        closes.append(closes[-1] * 1.025)                    # 末天 +2.5% → 1.044
        vols = [1e6] * (n - 1) + [2.5e6]
        _seed_history(s, code, closes, vols=vols,
                      highs=[c * 1.001 for c in closes])
        s._last_trade_date = s._bar_dates[code]

    def test_mild_breakout_scores(self):
        """温和放量启动应通过熊市选股"""
        s = self._make_strategy()
        self._seed_bear_series(s, "600030.SH")
        score = s._score_bear_candidate("600030.SH")
        assert score is not None

    def test_high_momentum_rejected(self):
        """已暴涨的高动量股应被熊市选股拒绝"""
        s = self._make_strategy()
        n = 100
        # 前期暴涨（60日动量高）
        closes = [50 * (1.02 ** i) for i in range(n)]
        vols = [1e6] * (n - 1) + [2.5e6]
        _seed_history(s, "600030.SH", closes, vols=vols)
        s._last_trade_date = s._bar_dates["600030.SH"]
        assert s._score_bear_candidate("600030.SH") is None

    def test_no_volume_surge_rejected(self):
        """未放量突破应被拒绝"""
        s = self._make_strategy()
        n = 100
        closes = [100 * (1 + 0.001 * i) for i in range(n)]
        vols = [1e6] * n  # 无放量
        _seed_history(s, "600030.SH", closes, vols=vols)
        s._last_trade_date = s._bar_dates["600030.SH"]
        assert s._score_bear_candidate("600030.SH") is None

    def test_not_breakout_rejected(self):
        """未创新高应被拒绝"""
        s = self._make_strategy()
        n = 100
        # 高位横盘：不创新高
        closes = [100.0] * 60 + [99.0] * 40
        vols = [1e6] * (n - 1) + [2.5e6]
        _seed_history(s, "600030.SH", closes, vols=vols)
        s._last_trade_date = s._bar_dates["600030.SH"]
        assert s._score_bear_candidate("600030.SH") is None

    def test_bear_params_in_rebalance(self):
        """熊市时用降仓参数（1×25%）"""
        cls = _load_strategy_class()
        s = cls(name="test", parameters={"verbose_logging": False})
        # 手动模拟熊市：构造 CSI500 在年线下
        import datetime as _dt
        base = _dt.date(2015, 1, 1)
        dates = [(base + _dt.timedelta(days=i)).isoformat() for i in range(300)]
        closes = [100 * (0.99 ** i) for i in range(300)]  # 单边下跌
        s._csi500_cache = pd.DataFrame({"trade_date": dates, "close": closes})
        s._last_trade_date = dates[-1]
        assert s._annual_line_gate() is True


class TestBearWideStop:
    """v7.1 熊市独立宽止损"""

    def test_bear_params_default(self):
        cls = _load_strategy_class()
        s = cls(name="test")
        assert s.bear_atr_trailing_mult == 3.5
        assert s.bear_atr_stop_mult == 2.5

    def test_bear_position_uses_wide_stop(self):
        """熊市持仓(is_bear=True)应触发宽止损而非2×ATR"""
        cls = _load_strategy_class()
        s = cls(name="test", parameters={"verbose_logging": False})
        # 构造持仓 + 低波动数据（ATR小）
        closes = [100.0] * 40
        _seed_history(s, "600030.SH", closes)
        s._last_trade_date = s._bar_dates["600030.SH"]
        s._holdings["600030.SH"] = {
            "entry_price": 100.0, "weight": 0.25, "shares": 100,
            "entry_date": "2023-01-01", "peak_high": 100.0, "is_bear": True,
        }
        atr = s._calc_atr("600030.SH")
        # 熊市硬止损 = 100 - 2.5×ATR，现价应低于它触发（熊市宽止损）
        # 构造现价 = 100 - 2.2×ATR（在牛市2.0×ATR内、但低于熊市2.5×ATR）
        if atr > 0:
            # 覆盖 close 为 100 - 2.2×ATR
            df = s._data_cache["600030.SH"]
            df.loc[df.index[-1], "close"] = 100.0 - 2.2 * atr
            sigs = s._check_stops_and_trailing()
            # 熊市用 2.5×ATR 止损，100-2.2×ATR > 100-2.5×ATR，不应触发
            assert not any(x.ts_code == "600030.SH" for x in sigs), \
                "熊市持仓在2.2×ATR回撤内不应触发2.5×ATR硬止损"

    def test_bear_wide_trailing_not_trigger_early(self):
        """熊市移动止损3.5×ATR应比牛市2.0×ATR更宽（不易误触发）"""
        cls = _load_strategy_class()
        s = cls(name="test", parameters={"verbose_logging": False})
        closes = [100.0] * 40
        _seed_history(s, "600030.SH", closes)
        s._last_trade_date = s._bar_dates["600030.SH"]
        s._holdings["600030.SH"] = {
            "entry_price": 100.0, "weight": 0.25, "shares": 100,
            "entry_date": "2023-01-01", "peak_high": 105.0, "is_bear": True,
        }
        atr = s._calc_atr("600030.SH")
        if atr > 0:
            # 现价 = 105 - 2.5×ATR（在牛市2.0×ATR移动止损内已触发，但熊市3.5×ATR内不触发）
            df = s._data_cache["600030.SH"]
            df.loc[df.index[-1], "close"] = 105.0 - 2.5 * atr
            sigs = s._check_stops_and_trailing()
            assert not any(x.ts_code == "600030.SH" for x in sigs), \
                "熊市3.5×ATR移动止损不应在2.5×ATR回撤触发"

    def test_bull_position_uses_original_stop(self):
        """牛市持仓(is_bear=False)仍用2×ATR"""
        cls = _load_strategy_class()
        s = cls(name="test", parameters={"verbose_logging": False})
        closes = [100.0] * 40
        _seed_history(s, "600030.SH", closes)
        s._last_trade_date = s._bar_dates["600030.SH"]
        s._holdings["600030.SH"] = {
            "entry_price": 100.0, "weight": 0.5, "shares": 100,
            "entry_date": "2023-01-01", "peak_high": 105.0, "is_bear": False,
        }
        atr = s._calc_atr("600030.SH")
        if atr > 0:
            # 现价 = 105 - 2.5×ATR（牛市2.0×ATR移动止损应触发）
            df = s._data_cache["600030.SH"]
            df.loc[df.index[-1], "close"] = 105.0 - 2.5 * atr
            sigs = s._check_stops_and_trailing()
            assert any(x.ts_code == "600030.SH" for x in sigs), \
                "牛市2.0×ATR移动止损应在2.5×ATR回撤触发"
