# -*- coding: utf-8 -*-
"""日频底座同步 provider 测试（FakeSession / FakeRepo / FakeSource，不连库不联网）。"""

from __future__ import annotations

import asyncio
from datetime import date

import pandas as pd
import pytest

from modules.data.constants import DataType
from modules.data.data_contracts import DATA_CONTRACTS
from modules.data.services.sync_service import DataSyncService
from shared.database.models.data_models_ext_registry import EXT_MODELS
from shared.database.repositories.market.ext import REPO_BY_TABLE


class FakeResult:
    def all(self):
        return []


class FakeSession:
    async def commit(self):
        pass

    async def execute(self, *args, **kwargs):
        return FakeResult()


class FakeRepo:
    def __init__(self, model):
        self.model = model
        self.records: list[dict] = []

    async def bulk_upsert(self, records):
        self.records.extend(records)
        return len(records)


class FakeCal:
    async def get_trade_dates(self, exchange, start, end):
        return [start] if start <= end else []


class FakeFactory:
    def __init__(self, source):
        self.source = source

    def get_source(self, data_source):
        return self.source


class FakeSource:
    def get_fx_daily(self, trade_date=""):
        return pd.DataFrame([
            {"ts_code": "USDCNH.FXCM", "trade_date": pd.Timestamp("2026-11-06"),
             "bid_close": 7.1}
        ])

    def get_namechange(self, start_date="", end_date=""):
        return pd.DataFrame([
            {"ts_code": "000001.SZ", "name": "ST平安",
             "start_date": pd.Timestamp("2020-01-01"),
             "end_date": None, "ann_date": None, "change_reason": None}
        ])

    def get_fx_obasic(self):
        return pd.DataFrame([
            {"ts_code": "USDCNH.FXCM", "name": "USDCNH", "traget_spread": 0.0001}
        ])

    def get_shibor(self, start_date="", end_date=""):
        return pd.DataFrame([
            {"date": pd.Timestamp("2026-11-06"), "on": 1.2, "1w": 1.3}
        ])

    def get_libor(self, start_date="", end_date=""):
        return pd.DataFrame()

    def get_hibor(self, start_date="", end_date=""):
        return pd.DataFrame()

    def get_us_tbr(self, start_date="", end_date=""):
        return pd.DataFrame()

    def get_us_tycr(self, start_date="", end_date=""):
        return pd.DataFrame()

    def get_moneyflow_dc(self, trade_date=""):
        return pd.DataFrame([{"trade_date": pd.Timestamp("2026-11-06"),
                              "ts_code": "000001.SZ", "net_amount": 1.0}])

    def get_moneyflow_ths(self, trade_date=""):
        return pd.DataFrame([{"trade_date": pd.Timestamp("2026-11-06"),
                              "ts_code": "000001.SZ", "net_amount": 2.0}])

    def get_ths_index(self):
        return pd.DataFrame([{"ts_code": "885001.TI"}, {"ts_code": "885002.TI"}])

    def get_ths_member(self, ts_code=""):
        return pd.DataFrame([{"ts_code": ts_code, "con_code": "000001.SZ",
                              "con_name": "平安银行"}])

    def get_fut_holding(self, trade_date="", symbol="", exchange=""):
        return pd.DataFrame([{"trade_date": pd.Timestamp("2026-11-06"),
                              "symbol": symbol, "broker": "测试", "vol": 1}])

    def get_fut_wsr(self, trade_date="", symbol="", exchange=""):
        return pd.DataFrame([{"trade_date": pd.Timestamp("2026-11-06"),
                              "symbol": symbol, "fut_name": "测试",
                              "warehouse": "库", "unit": "吨", "vol": 1}])

    def get_us_daily(self, trade_date=""):
        return pd.DataFrame([{"ts_code": "AAPL.US",
                              "trade_date": pd.Timestamp("2026-11-06"),
                              "close": 100.0}])


@pytest.fixture
def make_svc():
    created = []

    def _make(source=None):
        svc = DataSyncService(session=FakeSession())
        svc.source_factory = FakeFactory(source or FakeSource())
        svc.trade_calendar_repo = FakeCal()
        svc._ext_repos = {t: FakeRepo(EXT_MODELS[t]) for t in REPO_BY_TABLE}
        created.append(svc)
        return svc

    yield _make
    for svc in created:
        svc._executor.shutdown(wait=False)


def test_by_date_engine_and_fx_date_shift(make_svc):
    svc = make_svc()
    asyncio.run(svc._sync_ext(
        "fx_daily", start_date=date(2026, 11, 6), end_date=date(2026, 11, 6)
    ))
    rec = svc._ext_repos["fx_daily"].records[0]
    assert rec["source_date"] == date(2026, 11, 6)
    assert rec["trade_date"] == date(2026, 11, 7)


def test_by_range_engine_and_namechange_transform(make_svc):
    svc = make_svc()
    asyncio.run(svc._sync_ext(
        "stock_namechange", start_date=date(2026, 11, 1), end_date=date(2026, 11, 6)
    ))
    rec = svc._ext_repos["stock_namechange"].records[0]
    assert rec["is_st"] is True
    assert rec["start_date"] == date(2020, 1, 1)


def test_full_snapshot_and_fx_obasic_rename(make_svc):
    svc = make_svc()
    asyncio.run(svc._sync_ext("fx_basic"))
    rec = svc._ext_repos["fx_basic"].records[0]
    assert float(rec["target_spread"]) == 0.0001
    assert "traget_spread" not in rec


def test_macro_rate_unpivot(make_svc):
    svc = make_svc()
    asyncio.run(svc._sync_macro_rate(
        start_date=date(2026, 11, 6), end_date=date(2026, 11, 6)
    ))
    recs = svc._ext_repos["macro_rate"].records
    assert {(r["source"], r["tenor"]) for r in recs} == {
        ("shibor", "ON"), ("shibor", "1W")
    }
    assert all(r["currency"] == "CNY" for r in recs)


def test_moneyflow_ext_dual_source(make_svc):
    svc = make_svc()
    asyncio.run(svc._sync_stock_moneyflow_ext(
        start_date=date(2026, 11, 6), end_date=date(2026, 11, 6)
    ))
    recs = svc._ext_repos["stock_moneyflow_ext"].records
    assert {r["source"] for r in recs} == {"dc", "ths"}


def test_index_ths_member_snapshot(make_svc):
    svc = make_svc()
    asyncio.run(svc._sync_index_ths_member(
        start_date=date(2026, 11, 9), end_date=date(2026, 11, 9)
    ))
    recs = svc._ext_repos["index_ths_member"].records
    assert len(recs) == 2
    assert {r["index_code"] for r in recs} == {"885001.TI", "885002.TI"}
    assert all(r["snapshot_date"] == date(2026, 11, 9) for r in recs)


def test_fut_holding_and_wsr_paths(make_svc):
    svc = make_svc()
    asyncio.run(svc._sync_fut_holding(
        start_date=date(2026, 11, 6), end_date=date(2026, 11, 6)
    ))
    asyncio.run(svc._sync_fut_wsr(
        start_date=date(2026, 11, 6), end_date=date(2026, 11, 6)
    ))
    # FakeSession 查不到 fut_basic → 回退 5 个主力品种
    assert len(svc._ext_repos["fut_holding"].records) == 5
    assert len(svc._ext_repos["fut_wsr"].records) == 5
    assert all(r.get("exchange") for r in svc._ext_repos["fut_holding"].records)


def test_us_daily_generic_path(make_svc):
    svc = make_svc()
    asyncio.run(svc._sync_ext(
        "us_daily", start_date=date(2026, 11, 6), end_date=date(2026, 11, 6)
    ))
    recs = svc._ext_repos["us_daily"].records
    assert recs and recs[0]["ts_code"] == "AAPL.US"


def test_all_contracts_registered(make_svc):
    svc = make_svc()
    registered = {d.value for d in svc._sync_method_map}
    assert set(DATA_CONTRACTS) <= registered
    for key in DATA_CONTRACTS:
        assert DataType(key) in svc._sync_method_map
