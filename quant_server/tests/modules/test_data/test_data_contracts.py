# -*- coding: utf-8 -*-
"""日频数据底座契约的结构测试。

不连数据库，只校验配置自身的完整性与 DDL 的一致性。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from modules.data.data_contracts import (
    BACKFILL_MODES,
    CONTRACTS_BY_TABLE,
    DATA_CONTRACTS,
    FREQUENCIES,
    GATE_MODES,
    TIERS,
    all_tables,
    contracts_by_tier,
    get_contract,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
DDL_PATH = REPO_ROOT / "docs" / "sql" / "create_table.sql"
BEGIN_MARK = "-- ===== BEGIN DAILY_DATA_BASE ====="
END_MARK = "-- ===== END DAILY_DATA_BASE ====="


def _ddl_tables() -> set[str]:
    text = DDL_PATH.read_text(encoding="utf-8")
    section = text.split(BEGIN_MARK, 1)[1].split(END_MARK, 1)[0]
    tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", section))
    # 回填进度表不是数据契约，但必须与 56 张数据表同段创建
    assert "data_backfill_progress" in tables
    return tables - {"data_backfill_progress"}


def test_contract_count_is_56():
    assert len(DATA_CONTRACTS) == 56
    assert len(CONTRACTS_BY_TABLE) == 56
    assert len(all_tables()) == 56


def test_data_type_and_table_are_unique():
    assert len({c.data_type for c in DATA_CONTRACTS.values()}) == 56
    assert len({c.table for c in DATA_CONTRACTS.values()}) == 56


def test_tier_distribution_matches_plan():
    assert len(contracts_by_tier("P0b")) == 12
    assert len(contracts_by_tier("P0c")) == 9
    assert len(contracts_by_tier("P1")) == 18
    assert len(contracts_by_tier("P2")) == 17


def test_modes_and_frequency_are_known_values():
    for c in DATA_CONTRACTS.values():
        assert c.backfill_mode in BACKFILL_MODES, c.table
        assert c.gate_mode in GATE_MODES, c.table
        assert c.frequency in FREQUENCIES, c.table
        assert c.tier in TIERS, c.table


def test_primary_key_not_empty_and_api_not_empty():
    for c in DATA_CONTRACTS.values():
        assert c.primary_key, c.table
        assert c.api, c.table
        assert all(isinstance(x, str) and x for x in c.api), c.table


def test_partition_tables_have_trade_date_in_pk():
    partitioned = [c for c in DATA_CONTRACTS.values() if c.partition]
    assert {c.table for c in partitioned} == {
        "fx_daily", "fut_daily", "opt_daily", "cb_daily",
        "stock_cyq_perf", "stock_moneyflow_ext", "index_ths_daily",
    }
    for c in partitioned:
        assert "trade_date" in c.primary_key, c.table


def test_earliest_format():
    for c in DATA_CONTRACTS.values():
        if c.earliest in ("", "implementation"):
            continue
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", c.earliest), (c.table, c.earliest)


def test_get_contract_and_by_table_are_consistent():
    for key, c in DATA_CONTRACTS.items():
        assert get_contract(key) is c
        assert CONTRACTS_BY_TABLE[c.table] is c
    with pytest.raises(KeyError):
        get_contract("__not_exists__")


def test_ddl_tables_match_contracts():
    assert _ddl_tables() == set(all_tables())
