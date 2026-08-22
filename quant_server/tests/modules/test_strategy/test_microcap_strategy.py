# -*- coding: utf-8 -*-
"""微盘策略单元测试（阶段 4c）

覆盖（audit-strategy 门禁）：
  - 选池：circ_mv 过滤 / 流动性下限 / 市值最小 N
  - 门控1（regime BULL）/ 门控2（微盘指数 > MA20）
  - 门控关闭 → 整体空仓
  - 止损 -10% / 浮盈 30% 减半
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from modules.strategy.constants import SignalType
from modules.strategy.strategies.microcap.microcap_strategy import MicrocapStrategy


def make_strategy(**overrides):
    params = dict(MicrocapStrategy.DEFAULT_PARAMS)
    params.update(overrides)
    return MicrocapStrategy(name="微盘-测试", parameters=params)


def seed_regime(s, dates, regimes):
    for d, r in zip(dates, regimes):
        s._regime_by_date[d] = r


def seed_circ_mv(s, snap_date, codes_mv):
    """注入 circ_mv 月末快照。"""
    s._circ_mv_snapshots[snap_date] = {c: float(mv) for c, mv in codes_mv.items()}


def seed_stock(s, code, closes, amount=5e5, n_extra=25):
    """注入个股 K 线（amount 千元 → 万元 /10）。"""
    from datetime import date, timedelta
    d0 = date(2024, 1, 1) - timedelta(days=n_extra)
    df = pd.DataFrame({
        "trade_date": [(d0 + timedelta(days=i)).isoformat() for i in range(n_extra + len(closes))],
        "open": [10.0] * n_extra + closes,
        "high": [10.0 * 1.01] * n_extra + [c * 1.01 for c in closes],
        "low": [10.0 * 0.99] * n_extra + [c * 0.99 for c in closes],
        "close": [10.0] * n_extra + closes,
        "volume": [1e6] * (n_extra + len(closes)),
        "amount": [amount] * (n_extra + len(closes)),
    })
    s._data_cache[code] = df.reset_index(drop=True)


class TestPool:
    """选池：circ_mv / 流动性 / 市值最小"""

    def test_pool_filters_circ_mv_and_liquidity(self):
        s = make_strategy()
        # 4 只候选：A 超50亿剔除；B 流动性不足剔除；C/D 入选
        seed_circ_mv(s, "2024-01-31", {
            "600001.SH": 600000,  # 60 亿 → 剔除
            "600002.SH": 200000,  # 20 亿但流动性不足
            "600003.SH": 300000,  # 30 亿 ✓
            "600004.SH": 100000,  # 10 亿 ✓
        })
        seed_stock(s, "600002.SH", [10.0] * 5, amount=1000)   # 100 千元 = 10 万元 < 3000 万
        seed_stock(s, "600003.SH", [10.0] * 5, amount=5e5)    # 5e5 千元 = 5 万元？不对
        # amount=5e5 千元 = 50 万元 < 3000 万 → 也应剔除！修正用 3.5e7
        s._data_cache["600003.SH"]["amount"] = 3.5e7  # 3500 万元
        seed_stock(s, "600004.SH", [10.0] * 5, amount=1e8)    # 1 亿元

        s._rebuild_pool("2024-02-05")
        assert "600001.SH" not in s._pool
        assert "600002.SH" not in s._pool
        assert "600003.SH" in s._pool
        assert "600004.SH" in s._pool


class TestGates:
    """门控1（regime）/ 门控2（微盘指数 MA20）"""

    def test_market_gate_bull_only(self):
        s = make_strategy()
        dates = [f"2024-01-{i:02d}" for i in range(1, 6)]
        seed_regime(s, dates, ["BEAR", "NEUTRAL", "BULL", "BULL", "NEUTRAL"])
        assert s._check_market_gate("2024-01-01") is False
        assert s._check_market_gate("2024-01-03") is True

    def test_micro_gate_ma20(self):
        s = make_strategy()
        # 指数先涨后跌，MA20 上方 → 开；跌破 → 关
        s._micro_nav = 1.10
        s._micro_nav_history = [1.0] * 19 + [1.05]  # MA20 ≈ 1.0025 < 1.10 → 开
        assert s._check_micro_gate() is True
        s._micro_nav = 0.95
        s._micro_nav_history = [1.0] * 19 + [1.05]  # MA20 ≈ 1.0025 > 0.95 → 关
        assert s._check_micro_gate() is False

    def test_gate_close_closes_all(self):
        s = make_strategy()
        s._holdings["600003.SH"] = {"entry_price": 10.0, "entry_date": "2024-01-10",
                                    "peak": 10.0, "entry_weight": 0.05}
        s._holdings["600004.SH"] = {"entry_price": 9.0, "entry_date": "2024-01-10",
                                    "peak": 9.0, "entry_weight": 0.05}
        seed_stock(s, "600003.SH", [10.0] * 5)
        seed_stock(s, "600004.SH", [9.0] * 5)
        sigs = s._close_all("2024-02-01", reason="门控关闭空仓")
        assert len(sigs) == 2
        assert s._holdings == {}
        assert all(sig.signal_type == SignalType.EXIT for sig in sigs)


class TestRisk:
    """止损 / 减半"""

    def test_stop_loss(self):
        s = make_strategy()
        s._holdings["600003.SH"] = {"entry_price": 10.0, "entry_date": "2024-01-10",
                                    "peak": 10.0, "entry_weight": 0.05}

        class FakeBar:
            ts_code = "600003.SH"
            close = 8.9  # -11% → 止损

        sigs = s.check_stop_profit_stop_loss(FakeBar())
        assert len(sigs) == 1
        assert "600003.SH" not in s._holdings

    def test_profit_reduce_half(self):
        s = make_strategy()
        s._holdings["600003.SH"] = {"entry_price": 10.0, "entry_date": "2024-01-10",
                                    "peak": 10.0, "entry_weight": 0.05}

        class FakeBar:
            ts_code = "600003.SH"
            close = 13.2  # +32% → 减半

        sigs = s.check_stop_profit_stop_loss(FakeBar())
        assert len(sigs) == 1
        assert sigs[0].signal_type == SignalType.TAKE_PROFIT
        assert abs(sigs[0].weight - 0.5) < 1e-6
        assert s._holdings["600003.SH"].get("reduced") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header"])
