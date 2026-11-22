# -*- coding: utf-8 -*-
"""共享策略配置 · 写守卫单测（REQ-20261122-share-strategy-config W1/W2）。

覆盖：
  1. dev 环境：runner/live 策略被守卫拦下（返回 DEV_PROD_READONLY）
  2. dev 环境：draft/backtest 策略放行
  3. 生产环境：守卫完全不介入（行为不变）
"""

from types import SimpleNamespace

import pytest

from modules.strategy.constants import ErrorCode
from modules.strategy.services import strategy_service as svc


def _strat(status: str = "draft", run_mode: str = "backtest"):
    return SimpleNamespace(id="s-1", status=status, run_mode=run_mode)


@pytest.fixture
def as_dev(monkeypatch):
    monkeypatch.setattr(svc, "_is_dev_env", lambda: True)


@pytest.fixture
def as_prod(monkeypatch):
    monkeypatch.setattr(svc, "_is_dev_env", lambda: False)


def test_dev_blocks_running(as_dev):
    r = svc._dev_readonly_guard(_strat(status="running"))
    assert r is not None
    assert r["error_code"] == ErrorCode.DEV_PROD_READONLY


def test_dev_blocks_live_even_when_stopped(as_dev):
    r = svc._dev_readonly_guard(_strat(status="stopped", run_mode="live"))
    assert r is not None
    assert r["error_code"] == ErrorCode.DEV_PROD_READONLY


def test_dev_allows_draft_backtest(as_dev):
    assert svc._dev_readonly_guard(_strat(status="draft", run_mode="backtest")) is None


def test_prod_guard_noop(as_prod):
    assert svc._dev_readonly_guard(_strat(status="running")) is None
    assert svc._dev_readonly_guard(_strat(status="stopped", run_mode="live")) is None


def test_dev_error_code_is_1013():
    # ErrorCode 是「int 常量类」而非 Enum，直接比较数值
    assert ErrorCode.DEV_PROD_READONLY == 1013


# ============ F7（S5 评审）：补 delete 409 / 生命周期守卫 / 模板强制 ============

def test_delete_handler_maps_409(monkeypatch):
    """F1 回归：service 返回 DEV_PROD_READONLY 时，handler 必须抛 409 而非 400。"""
    import asyncio
    from types import SimpleNamespace
    from fastapi import HTTPException
    from modules.strategy.handlers import StrategyHandler

    class _FakeSvc:
        async def delete_strategy(self, strategy_id, user_id):
            return {"success": False, "error": "生产在跑策略在开发环境为只读",
                    "error_code": ErrorCode.DEV_PROD_READONLY}

    h = StrategyHandler.__new__(StrategyHandler)
    h.strategy_service = _FakeSvc()

    with pytest.raises(HTTPException) as ei:
        asyncio.run(h.delete_strategy("s-1", "u-1"))
    assert ei.value.status_code == 409


def test_lifecycle_guard_blocks_running(as_dev):
    """F2 回归：生命周期守卫对 running 策略抛 409。"""
    import asyncio
    from types import SimpleNamespace
    from fastapi import HTTPException
    from modules.strategy.handlers import StrategyHandler

    class _Repo:
        async def get_by_id(self, sid):
            return _strat(status="running")

    h = StrategyHandler.__new__(StrategyHandler)
    h.strategy_service = SimpleNamespace(strategy_repo=_Repo())

    with pytest.raises(HTTPException) as ei:
        asyncio.run(h._dev_lifecycle_guard("s-1"))
    assert ei.value.status_code == 409


def test_lifecycle_guard_allows_draft(as_dev):
    """F2 回归：draft 策略不被生命周期守卫拦截。"""
    import asyncio
    from types import SimpleNamespace
    from modules.strategy.handlers import StrategyHandler

    class _Repo:
        async def get_by_id(self, sid):
            return _strat(status="draft", run_mode="backtest")

    h = StrategyHandler.__new__(StrategyHandler)
    h.strategy_service = SimpleNamespace(strategy_repo=_Repo())
    asyncio.run(h._dev_lifecycle_guard("s-1"))  # 不抛即通过


def test_force_backtest_in_dev(as_dev):
    """F4 回归：dev 下任何 run_mode 都被强制为 backtest。"""
    assert svc._dev_force_backtest("live") == "backtest"
    assert svc._dev_force_backtest("backtest") == "backtest"


def test_force_backtest_in_prod(as_prod):
    """F4 回归：生产环境不干预。"""
    assert svc._dev_force_backtest("live") == "live"
