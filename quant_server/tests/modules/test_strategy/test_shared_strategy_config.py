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
