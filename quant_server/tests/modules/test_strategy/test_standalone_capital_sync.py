# -*- coding: utf-8 -*-
"""B1 修复：非组合 live 策略的 sizing 基准每日按绑定账户权益同步。

背景：`update_strategy_capital` 此前只被组合 rebalance 调用，不在任何组合里的
实盘策略，其 `context.total_assets` 启动后**永不更新** → sizing 基准恒为启动资金，
净值涨了不加仓、跌了不减仓，与回测口径（每日同步真实权益）严重背离。

注：本环境未装 pytest-asyncio，async 用例统一用 `asyncio.run()` 包装，
与既有测试（@pytest.mark.asyncio 因缺插件而失败）不同，此处不引入新依赖。

锁定五条不变式：
  1. 非组合 running+live 策略 → total_assets/available_capital 写成账户权益
  2. **不覆写 `initial_capital`**（资金契约 §2.2 写字段边界）
  3. 账户权益为 0 → 跳过（不把策略资金清零）
  4. 一次批量查账户（N+1 防回归）
  5. SQL 带 composite_group_id IS NULL（与组合互斥，防双写）
"""
import asyncio
from types import SimpleNamespace

import pytest

from modules.strategy.engines.strategy_manager import StrategyManager


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeSession:
    """按 SQL 关键字返回预置行，并记录调用（用于断言查询次数）。"""

    def __init__(self, strategy_rows, balance_rows):
        self._strategy_rows = strategy_rows
        self._balance_rows = balance_rows
        self.calls = []

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        self.calls.append((sql, params))
        if "FROM strategies" in sql:
            return _FakeResult(self._strategy_rows)
        if "FROM accounts" in sql:
            return _FakeResult(self._balance_rows)
        return _FakeResult([])

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


STRAT = ("sid-1", "跨市场避险-实盘", "acct-1")


def _manager(strategy_rows, balance_rows, contexts):
    """构造只带同步所需属性的 StrategyManager（绕开依赖引擎的 __init__）。

    复用同一个 _FakeSession 实例，便于用 mgr._test_session.calls 断言查询次数。
    """
    mgr = StrategyManager.__new__(StrategyManager)
    mgr._contexts = contexts
    session = _FakeSession(strategy_rows, balance_rows)
    mgr._test_session = session
    mgr.session_factory = lambda: session
    return mgr


def _ctx(total=0.0, avail=0.0, initial=0.0):
    return SimpleNamespace(
        total_assets=total, available_capital=avail, initial_capital=initial
    )


def _sync(mgr):
    return asyncio.run(mgr.sync_standalone_strategy_capital())


def test_standalone_strategy_synced_to_account_equity():
    ctx = _ctx(total=100000.0, avail=90000.0, initial=100000.0)
    mgr = _manager([STRAT], [("acct-1", 20560.56, 19574.06)], {"sid-1": ctx})

    assert _sync(mgr) == 1
    assert ctx.total_assets == pytest.approx(20560.56)
    # available_capital 取账户的 available_balance，而非 total_balance
    assert ctx.available_capital == pytest.approx(19574.06)


def test_initial_capital_not_overwritten():
    """资金契约 §2.2：initial_capital 语义是「初始资金」，不得被同步覆写。"""
    ctx = _ctx(total=100000.0, avail=90000.0, initial=100000.0)
    mgr = _manager([STRAT], [("acct-1", 20560.56, 19574.06)], {"sid-1": ctx})

    _sync(mgr)

    assert ctx.initial_capital == 100000.0


def test_zero_balance_skipped():
    """账户权益为 0 → 保持现值，不把策略资金清零。"""
    ctx = _ctx(total=100000.0, avail=90000.0, initial=100000.0)
    mgr = _manager([STRAT], [("acct-1", 0.0, 0.0)], {"sid-1": ctx})

    assert _sync(mgr) == 0
    assert ctx.total_assets == 100000.0


def test_missing_account_row_skipped():
    """策略绑定的账户在 accounts 表查不到 → 视为 0，跳过。"""
    ctx = _ctx(total=100000.0)
    mgr = _manager([STRAT], [], {"sid-1": ctx})

    assert _sync(mgr) == 0
    assert ctx.total_assets == 100000.0


def test_context_missing_skipped():
    """策略未运行（context 不存在）→ 跳过，不报错。"""
    mgr = _manager([STRAT], [("acct-1", 20560.0, 19574.0)], {})

    assert _sync(mgr) == 0


def test_batch_account_query_no_n_plus_1():
    """多策略多账户：账户查询只发一次，且用 ANY(:ids)。"""
    strategies = [
        ("sid-1", "A", "acct-1"),
        ("sid-2", "B", "acct-2"),
        ("sid-3", "C", "acct-1"),
    ]
    balances = [("acct-1", 10000.0, 9000.0), ("acct-2", 20000.0, 18000.0)]
    contexts = {"sid-1": _ctx(), "sid-2": _ctx(), "sid-3": _ctx()}
    mgr = _manager(strategies, balances, contexts)

    assert _sync(mgr) == 3
    assert contexts["sid-1"].total_assets == pytest.approx(10000.0)
    assert contexts["sid-2"].total_assets == pytest.approx(20000.0)
    assert contexts["sid-3"].total_assets == pytest.approx(10000.0)

    session = mgr._test_session
    account_calls = [c for c in session.calls if "FROM accounts" in c[0]]
    assert len(account_calls) == 1, "账户查询必须批量一次，禁止 N+1"
    assert account_calls[0][1] and "ids" in account_calls[0][1]


def test_query_excludes_composite_members():
    """与组合互斥：SQL 必须带 composite_group_id IS NULL（否则与组合 rebalance 双写）。"""
    from modules.strategy.engines import strategy_manager as sm_mod

    src = open(sm_mod.__file__, encoding="utf-8").read()
    start = src.index("async def sync_standalone_strategy_capital")
    body = src[start:start + 2600]
    assert "composite_group_id IS NULL" in body
    assert "run_mode = 'live'" in body
    assert "status = 'running'" in body


def test_no_session_factory_returns_zero():
    mgr = StrategyManager.__new__(StrategyManager)
    mgr._contexts = {}
    mgr.session_factory = None

    assert _sync(mgr) == 0
