# -*- coding: utf-8 -*-
"""数据完整性校验门：**关键表陈旧必须阻断策略驱动**（2026-09-21 缺口 20）。

## 被修的漏洞

原判据**只查 `stock_daily`**。2026-09-21 实测反例：`stock_daily` 完好（09-21 有 5553 条），
而 `index_daily` 因同步 100% 失败**冻结在 09-18** —— 旧判据完全无感 → 策略照常驱动、
regime 用陈旧指数判走弱期（`docs/08_实盘策略报告/…` §四 缺口 18/20）。
关键点：**本策略的输入是 `index_daily` + `etf_daily`，`stock_daily` 反而与它无关** ——
这就是"判据覆盖不到实际依赖"的漏洞。

## 本文件守住的四件事

1. 三张关键表都新鲜 → 放行
2. **任一关键表最新日 ≠ 最近交易日 → 阻断**（含 `index_daily` / `etf_daily`）
3. 当日行数低于下限 → 阻断（拦「整体未同步 / 严重残缺」）
4. `stock_daily` 的既有判据不回归（含交易日历缺失时的回退路径）
"""
from types import SimpleNamespace

import pytest

from core.engines.system.main_engine import MainEngine

TD = "2026-09-21"


class _Res:
    def __init__(self, v):
        self._v = v

    def scalar(self):
        return self._v


class _FakeSession:
    """按 SQL 片段返回预设值的替身（未预设的按 `defaults` 兜底）。"""

    def __init__(self, values):
        self._values = values
        self.sqls = []

    async def execute(self, clause, params=None):
        sql = str(clause)
        self.sqls.append(sql)
        for key, val in self._values.items():
            if key in sql:
                return _Res(val)
        raise AssertionError(f"未预设的查询: {sql}")


class _Ctx:
    def __init__(self, session):
        self._s = session

    async def __aenter__(self):
        return self._s

    async def __aexit__(self, *exc):
        return False


class _SM:
    def __init__(self, session):
        self._s = session

    def get_session(self):
        return _Ctx(self._s)


def _install(monkeypatch, session) -> _FakeSession:
    import shared.database.session as _sess_mod
    monkeypatch.setattr(_sess_mod, "get_session_manager", lambda: _SM(session))
    return session


def _gate(self=None):
    """以哑对象当 self（该方法只用到 `_gate_checks`）。"""
    return MainEngine._data_integrity_gate(self or SimpleNamespace(_gate_checks=[]), TD)


def _values(stock_max=TD, stock_n=5500, index_max=TD, index_n=536,
            etf_max=TD, etf_n=1667, last_td=TD):
    return {
        "FROM trade_calendar": last_td,
        "MAX(trade_date) FROM stock_daily": stock_max,
        "COUNT(*) FROM stock_daily": stock_n,
        "MAX(trade_date) FROM index_daily": index_max,
        "COUNT(*) FROM index_daily": index_n,
        "MAX(trade_date) FROM etf_daily": etf_max,
        "COUNT(*) FROM etf_daily": etf_n,
    }


async def test_all_fresh_passes(monkeypatch, caplog):
    """三张关键表都到最近交易日且行数达标 → 放行，且每张表都留一条「通过」日志。"""
    _install(monkeypatch, _FakeSession(_values()))
    with caplog.at_level("INFO"):
        ok = await _gate()
    assert ok is True
    passed = [r.getMessage() for r in caplog.records if "数据完整性校验通过" in r.getMessage()]
    assert len(passed) == 3, passed
    assert any("index_daily" in m for m in passed) and any("etf_daily" in m for m in passed)


@pytest.mark.parametrize("tbl", ["index_daily", "etf_daily"])
async def test_stale_key_table_blocks(monkeypatch, caplog, tbl):
    """⚠️ 核心：`index_daily`/`etf_daily` 陈旧 → **阻断**（这正是 2026-09-21 漏掉的那一关）。"""
    _install(monkeypatch, _FakeSession(_values(**{f"{tbl.split('_')[0]}_max": "2026-09-18"})))
    with caplog.at_level("WARNING"):
        ok = await _gate()
    assert ok is False, f"{tbl} 陈旧必须阻断"
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert tbl in msgs and "跳过实盘策略驱动" in msgs


@pytest.mark.parametrize("tbl,min_rows", [("index_daily", 300), ("etf_daily", 1000)])
async def test_insufficient_rows_blocks(monkeypatch, caplog, tbl, min_rows):
    """当日行数低于下限 → 阻断（拦整体未同步/严重残缺）。"""
    _install(monkeypatch, _FakeSession(_values(**{f"{tbl.split('_')[0]}_n": min_rows - 1})))
    with caplog.at_level("WARNING"):
        ok = await _gate()
    assert ok is False
    assert f"{tbl} 最近交易日 {TD} 仅 {min_rows - 1} 条" in " ".join(
        r.getMessage() for r in caplog.records)


async def test_stock_daily_regression_unchanged(monkeypatch, caplog):
    """既有判据不回归：stock_daily 陈旧仍阻断（本轮改动不得削弱它）。"""
    _install(monkeypatch, _FakeSession(_values(stock_max="2026-09-18")))
    with caplog.at_level("WARNING"):
        ok = await _gate()
    assert ok is False
    assert "stock_daily 最新交易日=2026-09-18" in " ".join(
        r.getMessage() for r in caplog.records)


async def test_calendar_missing_falls_back_to_today(monkeypatch, caplog):
    """交易日历缺失 → 回退为与 today 比对（既有行为），且告警可见。"""
    vals = _values(stock_max=TD, index_max=TD, etf_max=TD, last_td=None)
    with caplog.at_level("WARNING"):
        _install(monkeypatch, _FakeSession({**vals, "FROM trade_calendar": None}))
        ok = await _gate()
    assert "交易日历无数据" in " ".join(r.getMessage() for r in caplog.records)
    # last_td 回退为 today(=TD) → 三表都等于 TD → 放行
    assert ok is True
