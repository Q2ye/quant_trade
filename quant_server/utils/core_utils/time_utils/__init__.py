"""
时间处理工具模块

提供统一的时间处理、转换、调度和交易日历功能。
包含以下主要功能：
1. 时间转换 - TimeConverter
2. 交易日历 - TradingCalendar
3. 调度管理 - ScheduleManager

本模块被所有业务模块和核心引擎使用，确保系统时间处理的一致性。
"""

from .time_converter import TimeConverter
from .trading_calendar import TradingCalendar, TradingDayStatus, MarketSchedule
from .schedule_manager import ScheduleManager, ScheduleJob, ScheduleType

__version__ = "1.0.0"
__all__ = [
    "TimeConverter",
    "TradingCalendar", 
    "TradingDayStatus",
    "MarketSchedule",
    "ScheduleManager",
    "ScheduleJob",
    "ScheduleType",
]


'''
# 初始化
from core.utils.time_utils import TimeConverter, TradingCalendar, ScheduleManager

# 时间转换
converter = TimeConverter()
dt = converter.str_to_datetime("2024-01-15 09:30:00")

# 交易日历
calendar = TradingCalendar()
if calendar.is_trading_day("2024-01-15"):
    print("是交易日")

# 调度管理
scheduler = ScheduleManager(calendar)

# 创建交易日调度任务
job = ScheduleJob(
    job_id="daily_report",
    schedule_type=ScheduleType.TRADING_DAY,
    schedule_config={"time": "17:00"},
    func=generate_daily_report,
    name="每日报告生成"
)

# 添加并启动
await scheduler.add_job(job)
await scheduler.start()
'''