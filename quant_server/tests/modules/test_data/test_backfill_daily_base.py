# -*- coding: utf-8 -*-
"""日频底座回填脚本的纯函数测试（不连库不联网）。"""

from __future__ import annotations

from datetime import date

import pytest

from modules.data.data_contracts import DATA_CONTRACTS
from scripts.data.backfill_daily_base import (
    _DATE_COL,
    _DATE_SHIFT_DAYS,
    _resolve_types,
    _start_for,
    months,
    parse_day,
)


def test_parse_day_accepts_both_formats():
    assert parse_day("20261106") == date(2026, 11, 6)
    assert parse_day("2026-11-06") == date(2026, 11, 6)


def test_parse_day_rejects_bad_format():
    with pytest.raises(Exception):
        parse_day("2026/11/06")


def test_months_are_inclusive():
    assert months(date(2026, 8, 1), date(2026, 11, 1)) == [
        "202608", "202609", "202610", "202611"
    ]


def test_resolve_types_valid_and_all():
    assert _resolve_types("fx_daily,stock_margin_detail") == [
        "fx_daily", "stock_margin_detail"
    ]
    assert len(_resolve_types("all")) == 56


def test_resolve_types_rejects_unknown():
    with pytest.raises(SystemExit):
        _resolve_types("fx_daily,not_a_type")


def test_start_for_uses_contract_earliest():
    assert _start_for(DATA_CONTRACTS["fx_daily"], None) == date(2005, 1, 1)
    assert _start_for(DATA_CONTRACTS["index_ths_member"], None) is None
    assert _start_for(DATA_CONTRACTS["fx_daily"], date(2020, 1, 1)) == date(2020, 1, 1)


def test_date_maps_cover_special_tables():
    assert _DATE_COL["fund_nav"] == "nav_date"
    assert _DATE_COL["macro_pmi"] == "month"
    assert _DATE_SHIFT_DAYS["fx_daily"] == 1
