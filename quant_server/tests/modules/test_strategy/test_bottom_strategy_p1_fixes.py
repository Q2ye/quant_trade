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


class TestMarkCandidateStatusTimestamp:
    """阶段1: _mark_candidate_status 转正/拒绝时更新 signal_time（状态流转时间闭环）"""

    def test_status_update_includes_signal_time(self):
        """传入 signal_date 时，update 数据含 signal_time（= 确认日）"""
        strat = _make_strategy()
        strat._is_live_mode = lambda: True

        captured = {}

        class FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def commit(self):
                pass

        strat._db_session_factory = lambda: FakeSession()

        # 打桩 SignalRepository，捕获 update 参数
        import modules.strategy.strategies.etf.bottom_strategy as bs

        class _Repo:
            async def update(self, sig_id, data):
                captured["sig_id"] = sig_id
                captured["data"] = data

        _orig = bs.SignalRepository if hasattr(bs, "SignalRepository") else None
        # SignalRepository 在方法内 import，打桩模块级引用
        import importlib
        repo_mod = importlib.import_module(
            "shared.database.repositories.strategy.signal.signal_repo")
        repo_mod.SignalRepository = lambda db: _Repo()

        import asyncio

        asyncio.run(strat._mark_candidate_status(
            "sig-1", "promoted", "收盘确认转正", signal_date="2026-08-25"))

        assert captured["sig_id"] == "sig-1"
        assert captured["data"]["signal_status"] == "promoted"
        assert "signal_time" in captured["data"]
        assert str(captured["data"]["signal_time"].date()) == "2026-08-25"

        # 还原
        if _orig is not None:
            repo_mod.SignalRepository = _orig

    def test_status_update_without_signal_date(self):
        """不传 signal_date 时，update 数据不含 signal_time（兼容 expired 等场景）"""
        strat = _make_strategy()
        strat._is_live_mode = lambda: True

        captured = {}

        class FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def commit(self):
                pass

        strat._db_session_factory = lambda: FakeSession()

        class _Repo:
            async def update(self, sig_id, data):
                captured["data"] = data

        import importlib
        repo_mod = importlib.import_module(
            "shared.database.repositories.strategy.signal.signal_repo")
        _orig = repo_mod.SignalRepository
        repo_mod.SignalRepository = lambda db: _Repo()

        import asyncio

        asyncio.run(strat._mark_candidate_status("sig-2", "expired", "过期未确认"))
        assert "signal_time" not in captured["data"]
        repo_mod.SignalRepository = _orig


class TestConfirmedActiveExclusion:
    """2026-08-25: 已确认转正(promoted/executed)且未卖出的股票不再生成候选信号"""

    def test_on_bar_skips_confirmed_active(self):
        """确认占用标的在 on_bar 直接跳过（不进入候选确认/新预测）"""
        strat = _make_strategy()
        strat.parameters = {
            "etf_pool": ["510050.SH"],
            "min_warmup_bars": 2,
            "confirm_enabled": True,
            "vol_confirm_enabled": True,
            "threshold": 0.5,
            "regime_threshold_adj": {},
            "regime_max_positions": {0: 2, 1: 2, 2: 0},
            "cooling_days": 3,
        }
        strat._confirm_restored = True   # 跳过 P4 buffer 历史重建
        strat.model = object()           # 非 None，通过 model 检查
        strat._confirmed_active.add("510050.SH")
        strat._data_cache["510050.SH"] = [_make_bar(), _make_bar()]
        sigs = strat.on_bar(_make_bar(close=2.0))
        assert sigs == []
        assert strat._diag["confirmed_active"] == 1

    def test_make_exit_releases_confirmed_active(self):
        """卖出(_make_exit)后释放占用，股票可重新纳入选股"""
        strat = _make_strategy()
        strat.parameters = {"cooling_days": 3}
        strat._confirmed_active.add("510050.SH")
        strat._position_entry["510050.SH"] = (_dt.date(2026, 8, 1), 1.0)
        strat._track_high["510050.SH"] = 1.0
        bar = _make_bar(close=1.1)
        sig = strat._make_exit("510050.SH", bar, "止盈", "take_profit")
        assert sig is not None
        assert "510050.SH" not in strat._confirmed_active
