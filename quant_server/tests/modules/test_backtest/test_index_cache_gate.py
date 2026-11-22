# -*- coding: utf-8 -*-
"""回测路径的「降级门禁」单元测试（2026-09-19）。

## 为什么回测必须硬失败，而实盘允许降级运行

跨市场动量避险在 regime 指数不可用时置 `_index_cache_ok=False` → 走「姿态 A」
（目标强制降为防御标的）。对**实盘**这是有意的保守化（宁可少赚，不可裸奔）；
但对**回测**它会让整段净值变成"只持国债"——而三条冒烟门
（≥1 笔交易 / 无 NaN / 收益∈[−95%,+500%]）**对该形态完全免疫**，
于是被降级的净值会**静默进入 `backtest_tasks` 当权威口径**，且 `_index_cache_ok`
不落库，事后无法分辨哪一次结果是被降级的。

本文件守住 `BacktestService._assert_index_cache_ready` 这道门禁：
降级 → **抛错**（任务被标记 failed 并带原因），而不是静默产出一条假结果。
"""
from types import SimpleNamespace

import pytest


def _service(objs):
    """构造只带 `strategy_manager` 的鸭子类型 self（门禁方法只用到这一个属性）。"""
    class _SM:
        def get_strategy_object(self, sid):
            return objs.get(sid)

    return SimpleNamespace(strategy_manager=_SM())


def _strategy(ok: bool, name: str = "跨市场动量避险轮动-实盘-2.0"):
    return SimpleNamespace(_index_cache_ok=ok, name=name)


@pytest.fixture(scope="module")
def gate():
    """门禁方法（未绑定函数）—— 避免构造完整 BacktestService 的依赖。"""
    from modules.backtest.services.backtest_service import BacktestService

    return BacktestService._assert_index_cache_ready


def test_gate_raises_when_degraded(gate):
    svc = _service({"a": _strategy(ok=False)})
    with pytest.raises(RuntimeError) as ei:
        gate(svc, ["a"], "task-1")
    msg = str(ei.value)
    assert "不可作为口径" in msg, "报错必须说清后果，而不只是'失败了'"
    assert "只持防御标的" in msg and "task-1" in msg


def test_gate_passes_when_healthy(gate):
    svc = _service({"a": _strategy(ok=True)})
    gate(svc, ["a"], "task-1")          # 不抛错即通过


def test_gate_passes_for_strategy_without_the_flag(gate):
    """其它策略（无 `_index_cache_ok`）不得被本门禁误伤。"""
    svc = _service({"b": SimpleNamespace(name="高波动动量轮动")})
    gate(svc, ["b"], "task-1")


def test_gate_ignores_unknown_strategy_id(gate):
    svc = _service({})
    gate(svc, ["missing"], "task-1")


def test_gate_checks_every_strategy_in_composite(gate):
    """组合回测：任一成员降级 → 整单失败（不得只用第一个成员做判断）。"""
    svc = _service({"a": _strategy(ok=True), "b": _strategy(ok=False, name="跨市场-成员2")})
    with pytest.raises(RuntimeError) as ei:
        gate(svc, ["a", "b"], "task-2")
    assert "跨市场-成员2" in str(ei.value)
