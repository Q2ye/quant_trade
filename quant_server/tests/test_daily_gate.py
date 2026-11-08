"""日终任务注册守卫单元测试（REQ-20261108-db-env-isolation 任务 3）。"""
from modules.data import should_register_daily_tasks


def test_production_registers_daily_tasks():
    assert should_register_daily_tasks("production") is True


def test_development_skips_daily_tasks():
    assert should_register_daily_tasks("development") is False


def test_testing_skips_daily_tasks():
    assert should_register_daily_tasks("testing") is False


def test_staging_skips_daily_tasks():
    assert should_register_daily_tasks("staging") is False


def test_empty_environment_skips_daily_tasks():
    assert should_register_daily_tasks("") is False
