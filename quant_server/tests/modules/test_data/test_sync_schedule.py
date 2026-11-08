# -*- coding: utf-8 -*-
"""日终/夜间同步清单的契约测试（不连库）。"""

from modules.data.constants import DataType
from modules.data.data_contracts import DATA_CONTRACTS
from modules.data.sync_schedule import (
    DAILY_STRATEGY_TYPES,
    EXCLUDED_FROM_NIGHT,
    NIGHT_SYNC_TYPES,
)

_EXPECTED_DAILY = {
    DataType.DAILY_QUOTES,
    DataType.ADJ_FACTOR,
    DataType.DAILY_BASIC,
    DataType.DAILY_LIMIT,
    DataType.ETF_DAILY,
    DataType.FUND_ADJ_FACTOR,
    DataType.INDEX_DAILY,
}

_EXPECTED_EXCLUDED = {
    DataType.MINUTE_QUOTES,
    DataType.TICK_QUOTES,
    DataType.ETF_MINUTE,
    DataType.FINANCIAL_DATA,
    DataType.STK_FACTOR,
    DataType.STK_FACTOR_PRO,
}


def _all_types() -> set:
    return set(DataType)


def test_daily_types_are_exactly_seven():
    assert len(DAILY_STRATEGY_TYPES) == 7
    assert set(DAILY_STRATEGY_TYPES) == _EXPECTED_DAILY


def test_excluded_types_are_exactly_six():
    assert len(EXCLUDED_FROM_NIGHT) == 6
    assert set(EXCLUDED_FROM_NIGHT) == _EXPECTED_EXCLUDED


def test_night_types_cover_everything_else():
    expected = _all_types() - _EXPECTED_DAILY - _EXPECTED_EXCLUDED
    assert len(NIGHT_SYNC_TYPES) == 100
    assert len(set(NIGHT_SYNC_TYPES)) == 100
    assert set(NIGHT_SYNC_TYPES) == expected


def test_layers_are_disjoint():
    assert set(DAILY_STRATEGY_TYPES).isdisjoint(set(NIGHT_SYNC_TYPES))


def test_night_covers_all_new_contracts():
    new_types = {DataType(key) for key in DATA_CONTRACTS}
    assert new_types <= set(NIGHT_SYNC_TYPES)


def test_index_factor_and_financial_types_are_in_night():
    for dt in (DataType.IDX_FACTOR_PRO, DataType.FINANCIAL_INCOME,
               DataType.FINANCIAL_BALANCE, DataType.FINANCIAL_CASHFLOW):
        assert dt in NIGHT_SYNC_TYPES


def test_stock_factor_types_are_excluded():
    assert DataType.STK_FACTOR not in NIGHT_SYNC_TYPES
    assert DataType.STK_FACTOR_PRO not in NIGHT_SYNC_TYPES


def test_excluded_types_are_not_in_night():
    for dt in _EXPECTED_EXCLUDED:
        assert dt not in NIGHT_SYNC_TYPES


def test_night_start_windows():
    from datetime import date, timedelta
    from modules.data.sync_schedule import night_start_for

    d = date(2026, 11, 9)
    assert night_start_for(d, DataType.MACRO_SF) == d - timedelta(days=62)
    assert night_start_for(d, DataType.CB_SHARE) == d - timedelta(days=200)
    assert night_start_for(d, DataType.FUND_MANAGER) == d - timedelta(days=7)
    assert night_start_for(d, DataType.FX_DAILY) is None
    assert night_start_for(d, DataType.CPI) == d - timedelta(days=62)


def test_night_types_have_sync_methods():
    """夜班 100 类都必须在 _sync_method_map 或 DATA_CONTRACTS 中有实现。"""
    import re
    from pathlib import Path

    src = (Path(__file__).resolve().parents[3]
           / "modules/data/services/sync_service.py").read_text(encoding="utf-8")
    explicit = set(re.findall(r"DataType\.([A-Z0-9_]+):", src))
    for dt in NIGHT_SYNC_TYPES:
        assert dt.name in explicit or dt.value in DATA_CONTRACTS, dt.name
