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
}


def _all_types() -> set:
    return set(DataType)


def test_daily_types_are_exactly_seven():
    assert len(DAILY_STRATEGY_TYPES) == 7
    assert set(DAILY_STRATEGY_TYPES) == _EXPECTED_DAILY


def test_excluded_types_are_exactly_four():
    assert len(EXCLUDED_FROM_NIGHT) == 4
    assert set(EXCLUDED_FROM_NIGHT) == _EXPECTED_EXCLUDED


def test_night_types_cover_everything_else():
    expected = _all_types() - _EXPECTED_DAILY - _EXPECTED_EXCLUDED
    assert len(NIGHT_SYNC_TYPES) == 102
    assert len(set(NIGHT_SYNC_TYPES)) == 102
    assert set(NIGHT_SYNC_TYPES) == expected


def test_layers_are_disjoint():
    assert set(DAILY_STRATEGY_TYPES).isdisjoint(set(NIGHT_SYNC_TYPES))


def test_night_covers_all_new_contracts():
    new_types = {DataType(key) for key in DATA_CONTRACTS}
    assert new_types <= set(NIGHT_SYNC_TYPES)


def test_factor_and_financial_types_are_in_night():
    for dt in (DataType.STK_FACTOR, DataType.STK_FACTOR_PRO,
               DataType.IDX_FACTOR_PRO, DataType.FINANCIAL_INCOME,
               DataType.FINANCIAL_BALANCE, DataType.FINANCIAL_CASHFLOW):
        assert dt in NIGHT_SYNC_TYPES


def test_minute_tick_and_merged_financial_are_not_in_night():
    for dt in _EXPECTED_EXCLUDED:
        assert dt not in NIGHT_SYNC_TYPES
