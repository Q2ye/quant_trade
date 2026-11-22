# -*- coding: utf-8 -*-
"""`_sync_moneyflow` 空表 / 异常 计数的回归测试（源自 2026-10-12 缺口事件）。

背景
----
`_process_one` 取到空响应时曾静默 `return {"added": 0, "updated": 0}`，而
`_parallel_for_each` 只累加 `added/updated/skipped/failed` —— 于是汇总行
「5565 只处理、新增=2556、跳过=0、失败=0」在计数上**完全自洽**，
掩盖了约 3000 只零写入（DB 实落 2378 行），且无任何告警。

同时 `TushareSource.get_moneyflow` 把接口异常吞成空表，使「接口报错」与
「本就没有数据」同形，调用方无法区分。

本文件锁定三条不变式：
  ① 空响应 → 计入 `records_empty`，且**必须有告警**（不许静默）；
  ② 接口异常 → 计入 `records_failed`，**不许伪装成空表**；
  ③ 守恒：`added + skipped + empty + failed` 覆盖全部处理过的标的。

约定：本项目无 pytest-asyncio，异步主体统一用 `asyncio.run` 包裹（见 conftest 说明）。
"""
import asyncio
import logging
from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest

LATEST = {"000001.SZ": date(2026, 10, 9), "000002.SZ": date(2026, 10, 9)}
END = date(2026, 10, 12)


class _StubRepo:
    """桩仓库：只记录 upsert 行数，绝不连库。"""

    def __init__(self, *_a, **_kw):
        pass

    async def bulk_upsert(self, records):
        return len(records)

    async def get_latest_trade_dates_batch(self, ts_codes):
        return {c: LATEST.get(c) for c in ts_codes}


class _StubStocks:
    class _S:
        def __init__(self, code):
            self.ts_code = code
            self.list_date = date(2010, 1, 1)

    async def get_active_stocks(self):
        return [self._S(c) for c in LATEST]


class _FakeSession:
    async def commit(self):
        return None

    async def rollback(self):
        return None


class _AsyncCtx:
    async def __aenter__(self):
        return _FakeSession()

    async def __aexit__(self, *a):
        return False


def _build_service(monkeypatch, fetch_impl):
    """装配真实 DataSyncService，桩化「落库 / 会话 / Tushare 取数」三处。"""
    import shared.database.session as _sds
    from modules.data.services import sync_service as ss
    from shared.sources.tushare_source import TushareSource

    monkeypatch.setattr(ss, "StockMoneyflowRepository", _StubRepo)
    monkeypatch.setattr(
        _sds, "get_session_manager", lambda: MagicMock(get_session=lambda: _AsyncCtx())
    )
    monkeypatch.setattr(TushareSource, "get_moneyflow", fetch_impl)

    # `_sync_by_date_batch` 返回前会 commit 批量写入（2026-10-19 死锁修复），
    # 故 session 必须是可 await 的桩，不能用 MagicMock（其 commit() 不可 await）。
    svc = ss.DataSyncService(session=_FakeSession())
    svc.stock_basic_repo = _StubStocks()
    svc.stock_moneyflow_repo = _StubRepo()

    async def _false():
        return False

    svc._is_cancelled = _false
    return svc, ss


def _run(svc, start_date=None, end_date=None):
    """start_date=None → 按日批量（默认路径）；显式日期 → 逐股 overlap（兜底路径）。"""
    return asyncio.run(
        svc._sync_moneyflow(
            start_date=start_date, end_date=end_date or END,
            ts_codes=list(LATEST), task_id="test-mf", user_id=None,
        )
    )


def _patch_calendar(monkeypatch):
    """隔离真实交易日历（否则批量路径会依赖 DB 中的 trade_calendar）。

    `_sync_by_date_batch` 在函数内 `from … import TradingCalendar`，
    因此 patch 模块属性即可生效。
    """
    class _Cal:
        def is_trading_day(self, d):
            return d.weekday() < 5

    monkeypatch.setattr(
        "utils.core_utils.time_utils.trading_calendar.TradingCalendar",
        lambda: _Cal(),
    )


# ---------------------------------------------------------------- ① 空表
def test_empty_response_is_counted_as_empty_not_silent(monkeypatch, caplog):
    """空响应必须计入 records_empty，并留下 WARNING（核心回归）。"""

    def _empty(self, symbol="", trade_date="", start_date="", end_date=""):
        return pd.DataFrame()

    svc, _ = _build_service(monkeypatch, _empty)
    with caplog.at_level(logging.WARNING):
        # 显式 start_date → 逐股兜底路径（本用例锁定的是该路径的记账不变式）
        res = _run(svc, start_date=END)

    assert res["records_empty"] == 2, "空响应没有计入 empty —— 缺口会再次静默"
    assert res["records_added"] == 0
    assert res["records_failed"] == 0
    assert res["records_skipped"] == 0
    assert any("返回空表" in r.message for r in caplog.records), "空表未打任何告警"


# ---------------------------------------------------------------- ② 接口异常
def test_api_error_is_counted_as_failed_not_empty(monkeypatch):
    """接口异常必须计入 failed，不得伪装成空表。"""

    def _boom(self, symbol="", trade_date="", start_date="", end_date=""):
        raise RuntimeError("抱歉，您访问接口(moneyflow)频率超限(500次/分钟)")

    svc, _ = _build_service(monkeypatch, _boom)
    res = _run(svc, start_date=END)

    assert res["records_failed"] == 2, "接口异常被吞成空表 —— 会重演静默丢数"
    assert res["records_empty"] == 0
    assert res["records_added"] == 0


# ---------------------------------------------------------------- ③ 守恒
def test_counts_cover_every_processed_symbol(monkeypatch):
    """added + skipped + empty + failed 必须覆盖全部标的（无「黑洞」）。"""
    calls = {"n": 0}

    def _mixed(self, symbol="", trade_date="", start_date="", end_date=""):
        calls["n"] += 1
        if symbol == "000001.SZ":
            return pd.DataFrame([{
                "ts_code": symbol, "trade_date": "20261012",
                "buy_sm_vol": 1, "buy_sm_amount": 1.0,
            }])
        if symbol == "000002.SZ":
            return pd.DataFrame()
        raise RuntimeError("boom")

    LATEST["000003.SZ"] = date(2026, 10, 9)
    try:
        svc, _ = _build_service(monkeypatch, _mixed)
        res = _run(svc, start_date=END)
    finally:
        LATEST.pop("000003.SZ", None)

    covered = (
        res["records_added"] + res["records_skipped"]
        + res["records_empty"] + res["records_failed"]
    )
    assert covered == 3, f"有标的未落入任何计数桶（记账黑洞）: {res}"
    assert res["records_added"] == 1
    assert res["records_empty"] == 1
    assert res["records_failed"] == 1


# ------------------------------------------------- ④ 按日批量路径（2026-10-17）
def test_batch_path_uses_one_call_for_all_symbols(monkeypatch):
    """日常增量（start_date=None）应走按日批量：1 次调用覆盖全市场。

    2026-10-17 前的逐股实现每天 5,565 次 HTTP，撞上 Tushare 500 次/分 限频，
    10-13 / 10-16 各丢约 3,000 只。本用例锁定「不能退回逐股」。
    """
    calls = {"n": 0}

    def _batch(self, symbol="", trade_date="", start_date="", end_date=""):
        calls["n"] += 1
        assert symbol == "", "批量模式必须不传 ts_code（空串会被当成过滤条件）"
        assert trade_date == "20261012"
        return pd.DataFrame([
            {"ts_code": "000001.SZ", "trade_date": "20261012",
             "buy_sm_vol": 1, "buy_sm_amount": 1.0},
            {"ts_code": "000002.SZ", "trade_date": "20261012",
             "buy_sm_vol": 1, "buy_sm_amount": 1.0},
        ])

    _patch_calendar(monkeypatch)
    svc, _ = _build_service(monkeypatch, _batch)
    res = _run(svc)  # start_date=None → 批量

    assert calls["n"] == 1, f"应只调用 1 次（按日批量），实际 {calls['n']} 次"
    assert res["records_added"] == 2
    assert res["records_failed"] == 0
    assert res["cancelled"] is False


def test_laggard_gap_is_backfilled_by_date_not_per_stock(monkeypatch):
    """落后标的的缺口按交易日批量补齐，不再逐股（2026-10-19 限频事故回归）。

    构造：3 只标的中 2 只最新为 10-09，1 只到 10-12 → ref_date=10-12，
    缺口日期只有 10-12 → 应发 2 次请求（主窗口 10-13 + 落后补齐 10-12），
    而不是逐股 2 次；且 10-12 只写入落后标的（过滤掉已最新的 000003.SZ）。
    """
    calls = []
    latest = {
        "000001.SZ": date(2026, 10, 9),
        "000002.SZ": date(2026, 10, 9),
        "000003.SZ": date(2026, 10, 12),
    }

    def _batch(self, symbol="", trade_date="", start_date="", end_date=""):
        calls.append(trade_date)
        assert symbol == "", "批量模式必须不传 ts_code"
        return pd.DataFrame([
            {"ts_code": c, "trade_date": trade_date,
             "buy_sm_vol": 1, "buy_sm_amount": 1.0}
            for c in latest
        ])

    _patch_calendar(monkeypatch)
    saved = dict(LATEST)
    LATEST.clear()
    LATEST.update(latest)
    try:
        svc, _ = _build_service(monkeypatch, _batch)
        res = _run(svc, end_date=date(2026, 10, 13))
    finally:
        LATEST.clear()
        LATEST.update(saved)

    # 主窗口 10-13 + 落后补齐 10-12，各 1 次；没有任何逐股请求
    assert calls == ["20261013", "20261012"], calls
    # 10-13 写 3 只；10-12 只写 2 只落后标的（000003 已最新，被过滤）
    assert res["records_added"] == 5, res
    assert res["records_failed"] == 0


def test_batch_empty_trading_day_is_counted(monkeypatch, caplog):
    """批量路径中「真实交易日返回空表」必须计入失败并告警。

    背景：`needed` 已按交易日历过滤，空响应不属于「非交易日」，静默 continue
    会让「部分日期成功 + 部分日期空」的缺口不可见。
    """
    def _batch(self, symbol="", trade_date="", start_date="", end_date=""):
        if trade_date == "20261012":
            return pd.DataFrame()          # 空日
        return pd.DataFrame([{
            "ts_code": "000001.SZ", "trade_date": "20261013",
            "buy_sm_vol": 1, "buy_sm_amount": 1.0,
        }])

    _patch_calendar(monkeypatch)
    svc, _ = _build_service(monkeypatch, _batch)
    with caplog.at_level(logging.WARNING):
        res = _run(svc, end_date=date(2026, 10, 13))

    assert res["records_added"] == 1
    assert res["records_failed"] == 1, "空日未计入失败 —— 缺口会再次不可见"
    assert any("返回空表" in r.message for r in caplog.records), "空日未打告警"


def test_explicit_start_date_bypasses_batch(monkeypatch):
    """显式 start_date（手动回填）不得被批量路径截断为用户区间之外。"""
    calls = {"batch": 0, "stock": 0}

    def _fetch(self, symbol="", trade_date="", start_date="", end_date=""):
        if trade_date:
            calls["batch"] += 1
            return pd.DataFrame()
        calls["stock"] += 1
        return pd.DataFrame([{
            "ts_code": symbol, "trade_date": "20261012",
            "buy_sm_vol": 1, "buy_sm_amount": 1.0,
        }])

    svc, _ = _build_service(monkeypatch, _fetch)
    res = _run(svc, start_date=END)

    assert calls["batch"] == 0, "显式回填不应走批量路径"
    assert calls["stock"] == 2
    assert res["records_added"] == 2


def test_laggard_symbol_is_caught_up_via_per_stock(monkeypatch):
    """落后标的（latest=None 或 < ref_date）在批量后必须继续走逐股补齐。"""
    LATEST["000003.SZ"] = None          # 新纳入跟踪：库内无任何历史
    calls = {"batch": 0, "stock": []}

    def _fetch(self, symbol="", trade_date="", start_date="", end_date=""):
        if trade_date:
            calls["batch"] += 1
            return pd.DataFrame([
                {"ts_code": "000001.SZ", "trade_date": "20261012",
                 "buy_sm_vol": 1, "buy_sm_amount": 1.0},
                {"ts_code": "000002.SZ", "trade_date": "20261012",
                 "buy_sm_vol": 1, "buy_sm_amount": 1.0},
            ])
        calls["stock"].append(symbol)
        return pd.DataFrame([{
            "ts_code": symbol, "trade_date": "20261012",
            "buy_sm_vol": 1, "buy_sm_amount": 1.0,
        }])

    try:
        _patch_calendar(monkeypatch)
        svc, _ = _build_service(monkeypatch, _fetch)
        res = _run(svc)
    finally:
        LATEST.pop("000003.SZ", None)

    assert calls["batch"] == 1
    assert calls["stock"] == ["000003.SZ"], "落后标的未走逐股补齐"
    assert res["records_added"] == 3, "批量(2) 与逐股(1) 的计数未合并"


def test_parallel_for_each_counts_silent_zero_as_empty(monkeypatch):
    """逐股 process_one 返回「零写入/零跳过/未失败」时应计为 empty。

    2026-10-17：此前这类结果不落入任何计数桶，汇总行「处理 N 只、写入 0 行」
    在计数上完全自洽（20 处非日频同步即为此形态）。
    """
    svc, _ = _build_service(monkeypatch, lambda *a, **k: pd.DataFrame())

    async def _process_one(session, code):
        return {"added": 0, "updated": 0}      # 旧式「静默空表」

    res = asyncio.run(
        svc._parallel_for_each(["000001.SZ", "000002.SZ"], "测试", "t", None, _process_one)
    )
    assert res["records_empty"] == 2
    assert res["records_failed"] == 0


# ------------------------------------------------- ⑤ 数据源契约（不再吞异常）
def test_tushare_get_moneyflow_reraises_on_error():
    """接口报错必须向上抛，不得返回空表。"""
    from shared.sources.tushare_source import TushareSource

    class _Pro:
        def moneyflow(self, **kw):
            raise RuntimeError("频率超限")

    src = object.__new__(TushareSource)
    src.pro = _Pro()
    with pytest.raises(RuntimeError):
        src.get_moneyflow(symbol="000001.SZ", start_date="20261012", end_date="20261012")


def test_tushare_get_moneyflow_none_becomes_empty_frame():
    """接口合法返回 None → 空表（「真的没有数据」，与报错区分开）。"""
    from shared.sources.tushare_source import TushareSource

    class _Pro:
        def moneyflow(self, **kw):
            return None

    src = object.__new__(TushareSource)
    src.pro = _Pro()
    df = src.get_moneyflow(symbol="000001.SZ", start_date="20261012", end_date="20261012")
    assert isinstance(df, pd.DataFrame) and df.empty
