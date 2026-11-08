"""环境隔离启动断言单元测试（REQ-20261108-db-env-isolation 任务 2）。

纯函数 + 装配级测试，不连接真实数据库。
"""
import asyncio

from shared.database.session import session_manager as sm_module
from shared.database.session.session_manager import evaluate_environment_safety


def test_development_ok():
    problems = evaluate_environment_safety(
        "development", "quant_dev", "dev, public", can_write_accounts=False
    )
    assert problems == []


def test_development_rejects_postgres_superuser():
    problems = evaluate_environment_safety(
        "development", "postgres", "dev, public", can_write_accounts=False
    )
    assert any("postgres" in p for p in problems)


def test_development_rejects_wrong_search_path():
    problems = evaluate_environment_safety(
        "development", "quant_dev", "public", can_write_accounts=False
    )
    assert any("search_path" in p for p in problems)


def test_development_rejects_account_write():
    problems = evaluate_environment_safety(
        "development", "quant_dev", "dev, public", can_write_accounts=True
    )
    assert any("public.accounts" in p for p in problems)


def test_production_ok():
    problems = evaluate_environment_safety(
        "production", "quant_prod", "public", can_write_accounts=True
    )
    assert problems == []


def test_production_rejects_dev_search_path():
    problems = evaluate_environment_safety(
        "production", "quant_prod", "dev, public", can_write_accounts=True
    )
    assert any("search_path" in p for p in problems)


def test_production_rejects_no_account_write():
    problems = evaluate_environment_safety(
        "production", "quant_prod", "public", can_write_accounts=False
    )
    assert any("public.accounts" in p for p in problems)


def test_testing_skips_assertion():
    problems = evaluate_environment_safety(
        "testing", "postgres", "", can_write_accounts=False
    )
    assert problems == []


def test_development_rejects_wrong_database():
    problems = evaluate_environment_safety(
        "development", "quant_dev", "dev, public", False,
        current_database="quant_signals_dev",
        expected_database="quant_signals",
    )
    assert any("current_database" in p for p in problems)


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def one(self):
        return self._row


class _FakeSession:
    def __init__(self, row):
        self._row = row

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, *args, **kwargs):
        return _FakeResult(self._row)


class _FakeSessionFactory:
    def __init__(self, row):
        self._row = row

    def __call__(self):
        return _FakeSession(self._row)


class _FakePool:
    def __init__(self, row):
        self._row = row

    async def initialize(self):
        return True

    def get_session_factory(self):
        return _FakeSessionFactory(self._row)


def test_initialize_returns_false_when_assertion_fails(monkeypatch):
    """装配级：断言失败 → initialize() 返回 False（main.py 会据此拒绝启动）。"""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setattr(
        sm_module, "get_connection_pool",
        lambda: _FakePool(("postgres", "public", "quant_signals", True)),
    )
    manager = sm_module.SessionManager()
    assert asyncio.run(manager.initialize()) is False


def test_initialize_returns_false_when_database_mismatch(monkeypatch):
    """dev 连到旧库 quant_signals_dev → 库名判据必须拦住。"""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DB_DEV_NAME", "quant_signals")
    monkeypatch.setattr(
        sm_module, "get_connection_pool",
        lambda: _FakePool(("quant_dev", "dev, public", "quant_signals_dev", False)),
    )
    manager = sm_module.SessionManager()
    assert asyncio.run(manager.initialize()) is False


def test_assertion_uses_environ_not_stale_config(monkeypatch):
    """旧 config=development，但 --mode=production 已写入 os.environ → 按 production 判定。"""
    class _StaleConfig:
        class settings:
            class ENVIRONMENT:
                value = "development"

    monkeypatch.setattr(sm_module, "config", _StaleConfig())
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(
        sm_module, "get_connection_pool",
        lambda: _FakePool(("quant_dev", "dev, public", "quant_signals", False)),
    )
    manager = sm_module.SessionManager()
    assert asyncio.run(manager.initialize()) is False
