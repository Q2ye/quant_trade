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
