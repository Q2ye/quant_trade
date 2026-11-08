# -*- coding: utf-8 -*-
"""日频数据底座模型与契约的一致性测试（不连库）。"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import UniqueConstraint

from modules.data.data_contracts import DATA_CONTRACTS
from shared.database.models.data_models_ext_registry import EXT_MODELS

REPO_ROOT = Path(__file__).resolve().parents[4]
DDL_PATH = REPO_ROOT / "docs" / "sql" / "create_table.sql"
BEGIN_MARK = "-- ===== BEGIN DAILY_DATA_BASE ====="
END_MARK = "-- ===== END DAILY_DATA_BASE ====="


def _ddl_tables() -> set[str]:
    text = DDL_PATH.read_text(encoding="utf-8")
    section = text.split(BEGIN_MARK, 1)[1].split(END_MARK, 1)[0]
    return set(re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", section))


def _business_key(model) -> tuple:
    for arg in getattr(model, "__table_args__", ()):
        if isinstance(arg, UniqueConstraint):
            return tuple(c.name for c in arg.columns)
    return tuple(c.name for c in model.__table__.primary_key)


def test_registry_covers_all_ddl_tables():
    assert set(EXT_MODELS) == _ddl_tables()
    assert len(EXT_MODELS) == 57


def test_every_contract_has_model():
    for c in DATA_CONTRACTS.values():
        assert c.table in EXT_MODELS, c.table


def test_business_keys_match_contracts():
    for c in DATA_CONTRACTS.values():
        model = EXT_MODELS[c.table]
        assert _business_key(model) == c.primary_key, c.table


def test_models_expose_all_contract_pk_columns():
    for c in DATA_CONTRACTS.values():
        model = EXT_MODELS[c.table]
        cols = {col.name for col in model.__table__.columns}
        assert set(c.primary_key) <= cols, c.table


def test_progress_model_present():
    model = EXT_MODELS["data_backfill_progress"]
    assert _business_key(model) == ("data_type", "trade_date", "period_key")
