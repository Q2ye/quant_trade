# -*- coding: utf-8 -*-
"""输出层抑制：昨日 pending 买入 → 今日同向入场信号不得重复登记。

## 被修复的问题（2026-10-23 实盘）

`_run_live_strategies` 在 per-strategy 循环里调用 `handle_bar_batch`，而后者
**默认驱动全部运行中策略** → N 个运行策略时 N² 驱动 + 信号重复发布（N=1 不可见）。

同时，防重复登记的输出层抑制原先放在 `_run_live_strategies` 返回之后 ——
但 `_publish_signals` 在 `handle_bar_batch` 内部就已把事件入队（SignalEngine
随即落库 + 微信告警），抑制因此只是马后炮。实测：日志说「不重复登记」，
DB 却新增了 `511010.SH` 买单行并推送了告警。

## 本文件守住五件事

1. 指定 `strategy_id` 时只驱动该策略（N² 回归门）。
2. 同向 pending 买入的入场信号在**发布前**被抑制（不落库、不告警）。
3. 卖单一律不动（策略的卖出重发由 `exit_retry_days` 负责）。
4. `pending_map` 未配 `strategy_id` 时被忽略（防止跨策略串扰）。
5. 纯函数判据本身可单测。
"""
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.strategy.constants import SignalType
from modules.strategy.engines.strategy_manager import StrategyManager

TODAY = date(2026, 10, 23)


class _FakeStrategy:
    """最小策略桩：on_bar 只吃 bar，所有信号由 on_bar_batch_end 产出。"""

    def __init__(self, signals):
        self._signals = list(signals)
        self.signals = []
        self.batch_calls = 0

    def on_bar(self, bar):
        return []

    def on_bar_batch_end(self, trade_date):
        self.batch_calls += 1
        return list(self._signals)

    def validate_signal(self, sig):
        return True

    def clear_signals(self):
        self.signals = []


def _entry(ts_code: str):
    return SimpleNamespace(
        ts_code=ts_code, signal_type=SignalType.ENTRY, direction="long"
    )


def _sell(ts_code: str):
    return SimpleNamespace(
        ts_code=ts_code, signal_type=SignalType.EXIT, direction="sell"
    )


def _manager(instances):
    mgr = StrategyManager(event_engine=MagicMock())
    for sid, strat in instances.items():
        mgr.running_states[sid] = SimpleNamespace(is_running=True, pending_signals=[])
        mgr._strategy_objects[sid] = strat
    mgr._publish_signals = AsyncMock()
    return mgr


# ---------------------------------------------------------------- N² 回归门


@pytest.mark.asyncio
async def test_drives_only_requested_strategy():
    """传 strategy_id 时，其他运行中策略不得被驱动（N² 回归门）。"""
    a = _FakeStrategy([_entry("511010.SH")])
    b = _FakeStrategy([_entry("512100.SH")])
    mgr = _manager({"A": a, "B": b})

    out = await mgr.handle_bar_batch(TODAY, [object()], strategy_id="A")

    assert a.batch_calls == 1
    assert b.batch_calls == 0, "未指定的策略被驱动了 → N² 缺陷回归"
    assert [s.ts_code for s in out] == ["511010.SH"]
    mgr._publish_signals.assert_awaited_once()
    args = mgr._publish_signals.await_args
    assert args.args[0] == "A"
    assert [s.ts_code for s in args.args[1]] == ["511010.SH"]


@pytest.mark.asyncio
async def test_all_strategies_driven_without_strategy_id():
    """不传 strategy_id → 保持原行为：驱动全部运行中策略。"""
    a = _FakeStrategy([_entry("511010.SH")])
    b = _FakeStrategy([_entry("512100.SH")])
    mgr = _manager({"A": a, "B": b})

    out = await mgr.handle_bar_batch(TODAY, [object()])

    assert a.batch_calls == 1 and b.batch_calls == 1
    assert sorted(s.ts_code for s in out) == ["511010.SH", "512100.SH"]


# ---------------------------------------------------------------- 发布前抑制


@pytest.mark.asyncio
async def test_pending_entry_suppressed_before_publish():
    """同向 pending 买单 → 今日入场信号不发布、不返回（发布前即被拦截）。"""
    a = _FakeStrategy([_entry("511010.SH")])
    mgr = _manager({"A": a})

    out = await mgr.handle_bar_batch(
        TODAY, [object()], strategy_id="A",
        pending_map={"511010.SH": {"id": "x", "direction": "long"}},
    )

    assert out == []
    mgr._publish_signals.assert_not_awaited()


@pytest.mark.asyncio
async def test_pending_does_not_suppress_sell():
    """卖单不受 pending 买单影响（V3 依赖卖单持续 pending）。"""
    a = _FakeStrategy([_sell("511010.SH")])
    mgr = _manager({"A": a})

    out = await mgr.handle_bar_batch(
        TODAY, [object()], strategy_id="A",
        pending_map={"511010.SH": {"id": "x", "direction": "long"}},
    )

    assert [s.ts_code for s in out] == ["511010.SH"]
    mgr._publish_signals.assert_awaited_once()


@pytest.mark.asyncio
async def test_pending_map_without_strategy_id_is_ignored():
    """pending_map 是单策略快照；未指定 strategy_id 时忽略，防止跨策略串扰。"""
    a = _FakeStrategy([_entry("511010.SH")])
    mgr = _manager({"A": a})

    out = await mgr.handle_bar_batch(
        TODAY, [object()],
        pending_map={"511010.SH": {"id": "x", "direction": "long"}},
    )

    assert [s.ts_code for s in out] == ["511010.SH"]


# ---------------------------------------------------------------- 纯函数


def test_filter_helper_only_entries_with_pending_buy():
    kept, suppressed = StrategyManager._filter_pending_entry_signals(
        [_entry("A"), _sell("A"), _entry("B")],
        {"A": {"direction": "long"}},
    )

    assert [s.ts_code for s in kept] == ["A", "B"]  # A 的卖单保留；B 无 pending 保留
    assert [s.signal_type for s in kept] == [SignalType.EXIT, SignalType.ENTRY]
    assert suppressed == ["A"]


def test_filter_helper_accepts_buy_direction_alias():
    """DB 里 direction 可能存 long / buy 两种写法，都应识别为买单。"""
    kept, suppressed = StrategyManager._filter_pending_entry_signals(
        [_entry("A")], {"A": {"direction": "buy"}}
    )

    assert kept == []
    assert suppressed == ["A"]
