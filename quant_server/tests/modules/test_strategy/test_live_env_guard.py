# -*- coding: utf-8 -*-
"""Live 策略环境门单测（纯函数，不连库）。"""

import pytest

from modules.strategy.constants import ErrorCode, RunMode
from modules.strategy.utils.env_guard import (
    can_run_live,
    is_production_env,
    normalize_run_mode,
    should_restore_strategy,
)


@pytest.mark.parametrize("env,expected", [
    ("production", True),
    (" development ", False),
    ("test", False),
    ("testing", False),
    ("staging", False),
])
def test_is_production_env(env, expected):
    assert is_production_env(env) is expected


@pytest.mark.parametrize("run_mode,env,expected", [
    ("live", "production", True),
    ("live", "development", False),
    ("live", "test", False),
    ("paper", "development", True),
    ("backtest", "development", True),
    (None, "production", True),
    (None, "development", False),
    (RunMode.LIVE, "development", False),
    (RunMode.PAPER, "development", True),
    (RunMode.BACKTEST, "development", True),
    ("LIVE", "production", True),
])
def test_can_run_live(run_mode, env, expected):
    assert can_run_live(run_mode, env) is expected


def test_should_restore_matches_can_run_live():
    assert should_restore_strategy("live", "development") is False
    assert should_restore_strategy("live", "production") is True
    assert should_restore_strategy("paper", "development") is True


def test_normalize_run_mode():
    assert normalize_run_mode(RunMode.LIVE) == "live"
    assert normalize_run_mode(" LIVE ") == "live"
    assert normalize_run_mode(None) == "live"


def test_live_production_only_error_code_exists():
    assert ErrorCode.LIVE_PRODUCTION_ONLY == 1012


def test_environment_enum_is_normalized():
    from shared.config.config_manager import Environment

    assert is_production_env(Environment.PRODUCTION) is True
    assert can_run_live("live", Environment.PRODUCTION) is True
    assert can_run_live("live", Environment.DEVELOPMENT) is False


@pytest.mark.parametrize("mode,env,expected", [
    ("simulation", "development", False),
    ("simulation", "production", True),
    ("weird", "development", False),
    ("weird", "production", True),
])
def test_unknown_mode_is_treated_as_live_like(mode, env, expected):
    assert can_run_live(mode, env) is expected


def test_execution_start_rejects_live_in_dev(monkeypatch):
    import asyncio
    from modules.strategy.constants import StrategyLifecycleStatus
    from modules.strategy.services.execution_service import ExecutionService

    monkeypatch.setenv("ENVIRONMENT", "development")

    class _S:
        id = "s1"
        user_id = "u1"
        status = StrategyLifecycleStatus.STOPPED.value
        allocated_capital = 10000
        run_mode = "live"
        name = "x"

    class _Repo:
        async def get_by_id(self, sid):
            return _S()

    class _RunRepo:
        called = False

        async def create(self, data):
            _RunRepo.called = True

    svc = object.__new__(ExecutionService)
    svc.strategy_repo = _Repo()
    svc.strategy_run_repo = _RunRepo()
    svc.session = None
    svc.event_engine = None

    result = asyncio.run(svc.start_strategy("s1", "u1", capital=10000, run_mode=RunMode.LIVE))
    assert result["success"] is False
    assert result["error_code"] == ErrorCode.LIVE_PRODUCTION_ONLY
    assert _RunRepo.called is False


def test_execution_resume_rejects_live_in_dev(monkeypatch):
    import asyncio
    from modules.strategy.constants import StrategyLifecycleStatus
    from modules.strategy.services.execution_service import ExecutionService

    monkeypatch.setenv("ENVIRONMENT", "development")

    class _S:
        id = "s1"
        user_id = "u1"
        status = StrategyLifecycleStatus.PAUSED.value
        run_mode = "live"

    class _Repo:
        async def get_by_id(self, sid):
            return _S()

    svc = object.__new__(ExecutionService)
    svc.strategy_repo = _Repo()
    svc.session = None
    svc.event_engine = None

    result = asyncio.run(svc.resume_strategy("s1", "u1"))
    assert result["success"] is False
    assert result["error_code"] == ErrorCode.LIVE_PRODUCTION_ONLY


def test_manager_recovery_skips_live_in_dev(monkeypatch):
    import asyncio
    from modules.strategy.engines.strategy_manager import StrategyManager

    monkeypatch.setenv("ENVIRONMENT", "development")

    class _Result:
        def fetchall(self):
            return [("s1", "n", "u", "rotation", "code", "running",
                     "live", "semi_auto", None, 0)]

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def execute(self, *args, **kwargs):
            return _Result()

    class _SF:
        def __call__(self):
            return _Session()

    manager = object.__new__(StrategyManager)
    manager.session_factory = _SF()
    manager.strategies = {}
    manager.running_states = {}

    asyncio.run(manager._recover_running_strategies())
    assert "s1" not in manager.strategies


def test_manager_start_event_rejects_live_in_dev(monkeypatch):
    import asyncio
    from modules.strategy.engines.strategy_manager import StrategyManager

    monkeypatch.setenv("ENVIRONMENT", "development")

    class _Event:
        data = {"strategy_id": "s1", "run_mode": "live"}

    manager = object.__new__(StrategyManager)
    manager.strategies = {}
    manager.running_states = {}
    manager.session_factory = None
    manager.event_engine = None

    asyncio.run(manager._on_strategy_start_requested(_Event()))
    assert "s1" not in manager.running_states


def test_manager_trigger_rejects_live_in_dev(monkeypatch):
    import asyncio
    from datetime import date
    from modules.strategy.engines.strategy_manager import StrategyManager

    monkeypatch.setenv("ENVIRONMENT", "development")

    class _Instance:
        run_mode = RunMode.LIVE
        name = "x"
        parameters = {}

    manager = object.__new__(StrategyManager)
    manager.strategies = {"s1": _Instance()}
    manager._strategy_objects = {}

    result = asyncio.run(manager.trigger_strategy("s1", date(2026, 11, 6)))
    assert result["success"] is False
