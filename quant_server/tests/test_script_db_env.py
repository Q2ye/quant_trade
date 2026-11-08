"""脚本统一 DSN 解析单测（REQ-20261108-script-dsn-unification 任务 1）。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import _db_env  # noqa: E402


def _set_prod(monkeypatch, user="quant_prod"):
    monkeypatch.setenv("PROD_DB_HOST", "prod-host")
    monkeypatch.setenv("PROD_DB_PORT", "5433")
    monkeypatch.setenv("PROD_DB_USER", user)
    monkeypatch.setenv("PROD_DB_PASSWORD", "prod-pw")
    monkeypatch.setenv("PROD_DB_NAME", "quant_signals")


def _set_dev(monkeypatch):
    monkeypatch.setenv("DB_DEV_HOST", "dev-host")
    monkeypatch.setenv("DB_DEV_PORT", "5434")
    monkeypatch.setenv("DB_DEV_USER", "quant_dev")
    monkeypatch.setenv("DB_DEV_PASSWORD", "dev-pw")
    monkeypatch.setenv("DB_DEV_NAME", "quant_signals")


def test_prod_kwargs(monkeypatch):
    _set_prod(monkeypatch)
    cfg = _db_env.db_kwargs("prod")
    assert cfg == {
        "host": "prod-host",
        "port": 5433,
        "user": "quant_prod",
        "password": "prod-pw",
        "database": "quant_signals",
    }


def test_dev_kwargs(monkeypatch):
    _set_dev(monkeypatch)
    cfg = _db_env.db_kwargs("dev")
    assert cfg["host"] == "dev-host"
    assert cfg["user"] == "quant_dev"
    assert cfg["database"] == "quant_signals"


def test_prod_url(monkeypatch):
    _set_prod(monkeypatch)
    url = _db_env.db_url("prod")
    assert url == (
        "postgresql+asyncpg://quant_prod:prod-pw@prod-host:5433/quant_signals"
    )


def test_reject_postgres(monkeypatch):
    _set_prod(monkeypatch, user="postgres")
    with pytest.raises(SystemExit):
        _db_env.db_kwargs("prod")


def test_invalid_env():
    with pytest.raises(SystemExit):
        _db_env.db_kwargs("staging")
