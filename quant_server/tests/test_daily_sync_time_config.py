"""日终流水线触发时间配置单测（REQ-20261108-daily-sync-time-config）。"""
from core.engines.system.main_engine import resolve_daily_sync_time


def test_valid_time():
    assert resolve_daily_sync_time("16:30") == "16:30"


def test_default_time():
    assert resolve_daily_sync_time("19:20") == "19:20"


def test_invalid_hour_falls_back():
    assert resolve_daily_sync_time("25:00") == "19:20"


def test_invalid_minute_falls_back():
    assert resolve_daily_sync_time("19:60") == "19:20"


def test_empty_and_none_fall_back():
    assert resolve_daily_sync_time(None) == "19:20"
    assert resolve_daily_sync_time("") == "19:20"


def test_non_zero_padded_falls_back():
    assert resolve_daily_sync_time("9:20") == "19:20"


def test_night_time_default():
    assert resolve_daily_sync_time(None, default="00:00") == "00:00"


def test_hhmm_to_cron_zero():
    from core.engines.system.main_engine import hhmm_to_cron

    assert hhmm_to_cron("00:00") == "0 0 * * *"


def test_hhmm_to_cron_non_zero():
    from core.engines.system.main_engine import hhmm_to_cron

    assert hhmm_to_cron("23:45") == "45 23 * * *"


def test_hhmm_to_cron_invalid_falls_back_to_night():
    from core.engines.system.main_engine import hhmm_to_cron

    assert hhmm_to_cron("25:00") == "0 0 * * *"


def test_system_config_has_night_defaults():
    from shared.config.config_manager import SystemSettings

    cfg = SystemSettings()
    assert cfg.night_sync_time == "00:00"
    assert cfg.night_sync_enabled is True


def test_should_run_night():
    from datetime import date
    from core.engines.system.main_engine import should_run_night

    assert should_run_night(date(2026, 11, 6), True) is True    # 周五交易日
    assert should_run_night(date(2026, 11, 7), False) is False  # 周六
    assert should_run_night(date(2026, 10, 2), False) is True   # 周五 A 股休市
    assert should_run_night(date(2026, 11, 9), True) is True    # 周一交易日
