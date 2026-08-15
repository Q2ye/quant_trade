"""
时间处理工具模块

提供统一的时间处理、转换、调度和交易日历功能。
包含以下主要功能：
1. 交易日历 - TradingCalendar
2. 调度管理 - ScheduleManager

本模块被所有业务模块和核心引擎使用，确保系统时间处理的一致性。
"""

from .trading_calendar import TradingCalendar, TradingDayStatus, MarketSchedule
from .schedule_manager import ScheduleManager, ScheduleJob, ScheduleType

__version__ = "1.0.0"
__all__ = [
    "TradingCalendar",
    "TradingDayStatus",
    "MarketSchedule",
    "ScheduleManager",
    "ScheduleJob",
    "ScheduleType",
]
