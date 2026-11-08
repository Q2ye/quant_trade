"""环境 → 数据库 DSN 解析单元测试（REQ-20261108-db-env-isolation 任务 1）。

覆盖：
- development 读 DB_DEV_*
- production 读 PROD_DB_*
- production 缺项回退 base + missing 列表
- 可选 DB_RO_* 只读配置

不连接真实数据库。
"""
from shared.config.config_manager import ReadOnlyDatabaseSettings, resolve_database_env

BASE = {
    "HOST": "base-host",
    "PORT": 5432,
    "USER": "base-user",
    "PASSWORD": "base-pw",
    "NAME": "base-db",
    "POOL_SIZE": 10,
    "MAX_OVERFLOW": 5,
}


def _fake_getenv(mapping):
    def _get(key, default=None):
        return mapping.get(key, default)

    return _get


def test_development_reads_db_dev():
    env = {
        "DB_DEV_HOST": "dev-host",
        "DB_DEV_PORT": "5433",
        "DB_DEV_USER": "quant_dev",
        "DB_DEV_PASSWORD": "dev-pw",
        "DB_DEV_NAME": "quant_signals",
        "DB_DEV_POOL_SIZE": "20",
        "DB_DEV_MAX_OVERFLOW": "7",
    }
    values, missing = resolve_database_env("development", BASE, _fake_getenv(env))

    assert values == {
        "HOST": "dev-host",
        "PORT": 5433,
        "USER": "quant_dev",
        "PASSWORD": "dev-pw",
        "NAME": "quant_signals",
        "POOL_SIZE": 20,
        "MAX_OVERFLOW": 7,
    }
    assert missing == []


def test_development_defaults_name_when_unset():
    values, missing = resolve_database_env("development", BASE, _fake_getenv({}))

    assert values["HOST"] == "base-host"
    assert values["USER"] == "base-user"
    assert values["NAME"] == "quant_signals"
    assert missing == []


def test_production_reads_prod_db():
    env = {
        "PROD_DB_HOST": "prod-host",
        "PROD_DB_PORT": "5434",
        "PROD_DB_USER": "quant_prod",
        "PROD_DB_PASSWORD": "prod-pw",
        "PROD_DB_NAME": "quant_signals",
        "PROD_DB_POOL_SIZE": "30",
    }
    values, missing = resolve_database_env("production", BASE, _fake_getenv(env))

    assert values["HOST"] == "prod-host"
    assert values["PORT"] == 5434
    assert values["USER"] == "quant_prod"
    assert values["PASSWORD"] == "prod-pw"
    assert values["NAME"] == "quant_signals"
    assert values["POOL_SIZE"] == 30
    assert missing == []


def test_production_missing_falls_back_and_reports():
    env = {"PROD_DB_HOST": "prod-host"}
    values, missing = resolve_database_env("production", BASE, _fake_getenv(env))

    assert values["HOST"] == "prod-host"
    assert values["USER"] == "base-user"
    assert values["PASSWORD"] == "base-pw"
    assert values["NAME"] == "quant_signals"
    assert set(missing) == {
        "PROD_DB_PORT",
        "PROD_DB_USER",
        "PROD_DB_PASSWORD",
        "PROD_DB_NAME",
    }


def test_readonly_settings_reads_db_ro(monkeypatch):
    monkeypatch.setenv("DB_RO_HOST", "ro-host")
    monkeypatch.setenv("DB_RO_PORT", "5433")
    monkeypatch.setenv("DB_RO_USER", "quant_ro")
    monkeypatch.setenv("DB_RO_PASSWORD", "ro-pw")
    monkeypatch.setenv("DB_RO_NAME", "quant_signals")

    settings = ReadOnlyDatabaseSettings()

    assert settings.HOST == "ro-host"
    assert settings.PORT == 5433
    assert settings.USER == "quant_ro"
    assert settings.NAME == "quant_signals"
    assert "quant_ro:ro-pw@ro-host:5433/quant_signals" in settings.async_url
