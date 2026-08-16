# -*- coding: utf-8 -*-
"""ETF 底部策略 P1 修复定向验证（2026-08 盘查）

覆盖两个 P1 阻断项的修复行为：
- P1-1: 重启后 _position_entry 从 _active_positions（DB 真相源）重建，幽灵持仓被清理
- P1-2: _make_entry 对无效信号（weight<=0）返回 None 且不写幽灵持仓状态
"""
import datetime as _dt
import importlib.util
import os
from types import SimpleNamespace

import pytest

_STRATEGY_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..",
    "modules", "strategy", "strategies", "etf", "bottom_strategy.py",
)


def _load_strategy_class():
    """按既有测试模式从文件加载策略类（避免包级副作用）"""
    spec = importlib.util.spec_from_file_location(
        "etf_bottom_strategy", os.path.abspath(_STRATEGY_PATH)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.LightGBMBottomStrategy


def _make_strategy():
    cls = _load_strategy_class()
    strat = cls(name="P1测试-底部", parameters={})
    strat.context = SimpleNamespace(available_capital=1_000_000.0)
    return strat


def _make_bar(close=1.0, trade_date=None):
    return SimpleNamespace(
        ts_code="510050.SH",
        close=close,
        trade_date=trade_date or _dt.date(2026, 8, 14),
        trade_time=None,
    )


class TestP1_1RebuildPositionState:
    """P1-1: 重启后持仓状态重建"""

    def test_rebuild_from_active_positions(self):
        strat = _make_strategy()
        from modules.strategy.strategies.base.base_strategy import LivePosition
        strat._active_positions["510050.SH"] = LivePosition(
            ts_code="510050.SH", quantity=1000, cost_price=1.5)
        # 预置一个未成交的幽灵持仓，应被清理
        strat._position_entry["512880.SH"] = (_dt.date(2026, 8, 10), 1.2)

        strat._rebuild_position_state()

        assert "510050.SH" in strat._position_entry
        entry_date, entry_price = strat._position_entry["510050.SH"]
        assert entry_price == 1.5
        assert isinstance(entry_date, _dt.date)  # 从今天起算持有期（保守）
        # 不在 DB 持仓中的条目被清除
        assert "512880.SH" not in strat._position_entry

    def test_empty_active_positions_clears_all(self):
        strat = _make_strategy()
        strat._position_entry["510050.SH"] = (_dt.date(2026, 8, 10), 1.2)
        strat._rebuild_position_state()
        assert strat._position_entry == {}

    def test_zero_quantity_ignored(self):
        strat = _make_strategy()
        from modules.strategy.strategies.base.base_strategy import LivePosition
        # 数量为 0 的持仓（不应存在）跳过
        strat._active_positions["510050.SH"] = LivePosition(
            ts_code="510050.SH", quantity=0, cost_price=1.5)
        strat._rebuild_position_state()
        assert "510050.SH" not in strat._position_entry


class TestP1_2MakeEntryGhostGuard:
    """P1-2: 无效信号不写幽灵持仓"""

    def test_weight_zero_returns_none_and_no_ghost(self):
        strat = _make_strategy()
        bar = _make_bar(close=2.0)
        sig = strat._make_entry("510050.SH", bar, proba=0.6, weight=0.0, regime=1)
        assert sig is None
        assert "510050.SH" not in strat._position_entry
        assert "510050.SH" not in strat._track_high

    def test_valid_entry_writes_state_and_signal(self):
        strat = _make_strategy()
        bar = _make_bar(close=2.0)
        sig = strat._make_entry("510050.SH", bar, proba=0.6, weight=0.11, regime=0)
        assert sig is not None
        assert "510050.SH" in strat._position_entry
        assert "510050.SH" in strat._track_high
        assert sig.quantity > 0
        assert sig.weight == pytest.approx(0.11)

    def test_zero_capital_returns_none(self):
        strat = _make_strategy()
        strat.context = SimpleNamespace(available_capital=0.0)
        bar = _make_bar(close=2.0)
        sig = strat._make_entry("510050.SH", bar, proba=0.6, weight=0.11, regime=0)
        assert sig is None
        assert "510050.SH" not in strat._position_entry
