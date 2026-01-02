"""
时间转换器

提供统一的时间转换和格式化功能，支持：
1. 字符串与datetime互转
2. 时间戳与datetime互转
3. 时区转换
4. 时间计算和比较
5. 时间格式化

设计原则：
- 统一的时区处理（默认使用上海时区）
- 线程安全
- 支持批量转换
"""

import re
import time as time_module
from datetime import datetime, date, time, timedelta
from typing import Union, Optional, List, Dict, Any
import pytz
import pandas as pd

# 配置常量
DEFAULT_TIMEZONE = "Asia/Shanghai"
DATE_FORMATS = [
	"%Y-%m-%d",  # 2023-12-28
	"%Y/%m/%d",  # 2023/12/28
	"%Y%m%d",  # 20231228
	"%Y-%m-%d %H:%M:%S",  # 2023-12-28 09:30:00
	"%Y/%m/%d %H:%M:%S",  # 2023/12/28 09:30:00
	"%Y%m%d%H%M%S",  # 20231228093000
	"%Y-%m-%dT%H:%M:%S",  # ISO格式
	"%Y-%m-%dT%H:%M:%S%z",  # ISO带时区
]


class TimeConverter:
	"""
	时间转换器

	提供统一的时间转换、格式化和计算功能
	"""

	def __init__ (self, default_timezone: str = DEFAULT_TIMEZONE):
		"""
		初始化时间转换器

		Args:
			default_timezone: 默认时区，默认为"Asia/Shanghai"
		"""
		self.default_timezone = pytz.timezone(default_timezone)
		self.local_timezone = pytz.timezone(default_timezone)

		# 常用时间格式正则
		self.date_patterns = [
			(re.compile(r'^\d{4}-\d{2}-\d{2}$'), "%Y-%m-%d"),
			(re.compile(r'^\d{4}/\d{2}/\d{2}$'), "%Y/%m/%d"),
			(re.compile(r'^\d{8}$'), "%Y%m%d"),
			(re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$'), "%Y-%m-%d %H:%M:%S"),
			(re.compile(r'^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}$'), "%Y/%m/%d %H:%M:%S"),
			(re.compile(r'^\d{14}$'), "%Y%m%d%H%M%S"),
			(re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'), "%Y-%m-%dT%H:%M:%S"),
		]

	# ============ 基础转换方法 ============

	def str_to_datetime (
			self,
			time_str: str,
			timezone: Optional[str] = None
	) -> Optional[datetime]:
		"""
		字符串转换为datetime

		Args:
			time_str: 时间字符串
			timezone: 时区，如果为None则使用默认时区

		Returns:
			datetime对象，转换失败返回None
		"""
		if not time_str:
			return None

		# 尝试多种格式
		for pattern, fmt in self.date_patterns:
			if pattern.match(time_str):
				try:
					dt = datetime.strptime(time_str, fmt)
					return self.localize_datetime(dt, timezone)
				except ValueError:
					continue

		# 如果上面的格式都不匹配，尝试pandas的灵活解析
		try:
			dt = pd.to_datetime(time_str)
			if isinstance(dt, pd.Timestamp):
				dt = dt.to_pydatetime()
			return self.localize_datetime(dt, timezone)
		except Exception:
			return None

	def datetime_to_str (
			self,
			dt: datetime,
			fmt: str = "%Y-%m-%d %H:%M:%S",
			timezone: Optional[str] = None
	) -> str:
		"""
		datetime转换为字符串

		Args:
			dt: datetime对象
			fmt: 格式化字符串
			timezone: 时区，如果指定则先转换时区

		Returns:
			格式化后的时间字符串
		"""
		if not dt:
			return ""

		# 时区转换
		if timezone:
			dt = self.convert_timezone(dt, timezone)

		# 格式化为字符串
		return dt.strftime(fmt)

	def timestamp_to_datetime (
			self,
			timestamp: Union[int, float],
			timezone: Optional[str] = None
	) -> datetime:
		"""
		时间戳转换为datetime

		Args:
			timestamp: Unix时间戳（秒）
			timezone: 目标时区

		Returns:
			datetime对象
		"""
		dt = datetime.fromtimestamp(timestamp, tz=self.default_timezone)
		if timezone:
			return self.convert_timezone(dt, timezone)
		return dt

	def datetime_to_timestamp (self, dt: datetime) -> float:
		"""
		datetime转换为时间戳

		Args:
			dt: datetime对象

		Returns:
			Unix时间戳（秒）
		"""
		if dt.tzinfo is None:
			dt = self.local_timezone.localize(dt)

		return dt.timestamp()

	# ============ 时区相关方法 ============

	def localize_datetime (
			self,
			dt: datetime,
			timezone: Optional[str] = None
	) -> datetime:
		"""
		本地化datetime（添加时区信息）

		Args:
			dt: datetime对象
			timezone: 时区，如果为None则使用默认时区

		Returns:
			带时区信息的datetime对象
		"""
		if dt.tzinfo is not None:
			return dt

		tz = self.default_timezone if timezone is None else pytz.timezone(timezone)
		return tz.localize(dt)

	def convert_timezone (
			self,
			dt: datetime,
			target_timezone: str,
			source_timezone: Optional[str] = None
	) -> datetime:
		"""
		转换时区

		Args:
			dt: datetime对象
			target_timezone: 目标时区
			source_timezone: 源时区，如果为None则从dt中获取

		Returns:
			转换时区后的datetime对象
		"""
		# 如果没有时区信息，先本地化
		if dt.tzinfo is None:
			if source_timezone:
				dt = pytz.timezone(source_timezone).localize(dt)
			else:
				dt = self.default_timezone.localize(dt)

		# 转换时区
		target_tz = pytz.timezone(target_timezone)
		return dt.astimezone(target_tz)

	def get_current_datetime (self, timezone: Optional[str] = None) -> datetime:
		"""
		获取当前时间

		Args:
			timezone: 时区，如果为None则使用默认时区

		Returns:
			当前时间的datetime对象
		"""
		dt = datetime.now(tz=self.default_timezone)
		if timezone and timezone != self.default_timezone.zone:
			return self.convert_timezone(dt, timezone)
		return dt

	def get_current_timestamp (self) -> float:
		"""获取当前时间戳"""
		return time_module.time()

	# ============ 日期计算方法 ============

	def add_days (
			self,
			dt: datetime,
			days: int,
			timezone: Optional[str] = None
	) -> datetime:
		"""
		添加天数

		Args:
			dt: 基础时间
			days: 要添加的天数（可以为负）
			timezone: 时区

		Returns:
			计算后的datetime
		"""
		result = dt + timedelta(days=days)
		if timezone:
			result = self.convert_timezone(result, timezone)
		return result

	def add_hours (
			self,
			dt: datetime,
			hours: int,
			timezone: Optional[str] = None
	) -> datetime:
		"""
		添加小时

		Args:
			dt: 基础时间
			hours: 要添加的小时数（可以为负）
			timezone: 时区

		Returns:
			计算后的datetime
		"""
		result = dt + timedelta(hours=hours)
		if timezone:
			result = self.convert_timezone(result, timezone)
		return result

	def add_minutes (
			self,
			dt: datetime,
			minutes: int,
			timezone: Optional[str] = None
	) -> datetime:
		"""
		添加分钟

		Args:
			dt: 基础时间
			minutes: 要添加的分钟数（可以为负）
			timezone: 时区

		Returns:
			计算后的datetime
		"""
		result = dt + timedelta(minutes=minutes)
		if timezone:
			result = self.convert_timezone(result, timezone)
		return result

	def get_start_of_day (
			self,
			dt: datetime,
			timezone: Optional[str] = None
	) -> datetime:
		"""
		获取当天的开始时间（00:00:00）

		Args:
			dt: datetime对象
			timezone: 时区

		Returns:
			当天开始的datetime
		"""
		start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
		if timezone:
			start = self.convert_timezone(start, timezone)
		return start

	def get_end_of_day (
			self,
			dt: datetime,
			timezone: Optional[str] = None
	) -> datetime:
		"""
		获取当天的结束时间（23:59:59.999999）

		Args:
			dt: datetime对象
			timezone: 时区

		Returns:
			当天结束的datetime
		"""
		end = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
		if timezone:
			end = self.convert_timezone(end, timezone)
		return end

	def get_week_start (
			self,
			dt: datetime,
			timezone: Optional[str] = None
	) -> datetime:
		"""
		获取当周的开始时间（周一00:00:00）

		Args:
			dt: datetime对象
			timezone: 时区

		Returns:
			当周开始的datetime
		"""
		# 获取周几（0=周一，6=周日）
		weekday = dt.weekday()
		start = self.get_start_of_day(dt - timedelta(days=weekday))
		if timezone:
			start = self.convert_timezone(start, timezone)
		return start

	def get_month_start (
			self,
			dt: datetime,
			timezone: Optional[str] = None
	) -> datetime:
		"""
		获取当月的开始时间（1号00:00:00）

		Args:
			dt: datetime对象
			timezone: 时区

		Returns:
			当月开始的datetime
		"""
		start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
		if timezone:
			start = self.convert_timezone(start, timezone)
		return start

	def get_year_start (
			self,
			dt: datetime,
			timezone: Optional[str] = None
	) -> datetime:
		"""
		获取当年的开始时间（1月1日00:00:00）

		Args:
			dt: datetime对象
			timezone: 时区

		Returns:
			当年开始的datetime
		"""
		start = dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
		if timezone:
			start = self.convert_timezone(start, timezone)
		return start

	# ============ 时间比较方法 ============

	def is_same_day (
			self,
			dt1: datetime,
			dt2: datetime
	) -> bool:
		"""
		判断是否为同一天

		Args:
			dt1: 第一个时间
			dt2: 第二个时间

		Returns:
			bool: 是否为同一天
		"""
		# 转换为相同时区比较
		dt1_local = self.convert_timezone(dt1, self.default_timezone.zone)
		dt2_local = self.convert_timezone(dt2, self.default_timezone.zone)

		return (dt1_local.year == dt2_local.year and
		        dt1_local.month == dt2_local.month and
		        dt1_local.day == dt2_local.day)

	def is_same_week (
			self,
			dt1: datetime,
			dt2: datetime
	) -> bool:
		"""
		判断是否为同一周

		Args:
			dt1: 第一个时间
			dt2: 第二个时间

		Returns:
			bool: 是否为同一周
		"""
		week_start1 = self.get_week_start(dt1)
		week_start2 = self.get_week_start(dt2)

		return self.is_same_day(week_start1, week_start2)

	def is_same_month (
			self,
			dt1: datetime,
			dt2: datetime
	) -> bool:
		"""
		判断是否为同一月

		Args:
			dt1: 第一个时间
			dt2: 第二个时间

		Returns:
			bool: 是否为同一月
		"""
		month_start1 = self.get_month_start(dt1)
		month_start2 = self.get_month_start(dt2)

		return self.is_same_day(month_start1, month_start2)

	def is_between (
			self,
			dt: datetime,
			start: datetime,
			end: datetime,
			inclusive: bool = True
	) -> bool:
		"""
		判断时间是否在区间内

		Args:
			dt: 要判断的时间
			start: 开始时间
			end: 结束时间
			inclusive: 是否包含边界

		Returns:
			bool: 是否在区间内
		"""
		if inclusive:
			return start <= dt <= end
		else:
			return start < dt < end

	# ============ 批量转换方法 ============

	def batch_str_to_datetime (
			self,
			time_strings: List[str],
			timezone: Optional[str] = None
	) -> List[Optional[datetime]]:
		"""
		批量字符串转datetime

		Args:
			time_strings: 时间字符串列表
			timezone: 时区

		Returns:
			datetime对象列表
		"""
		return [self.str_to_datetime(ts, timezone) for ts in time_strings]

	def batch_datetime_to_str (
			self,
			datetimes: List[datetime],
			fmt: str = "%Y-%m-%d %H:%M:%S",
			timezone: Optional[str] = None
	) -> List[str]:
		"""
		批量datetime转字符串

		Args:
			datetimes: datetime对象列表
			fmt: 格式字符串
			timezone: 时区

		Returns:
			时间字符串列表
		"""
		return [self.datetime_to_str(dt, fmt, timezone) for dt in datetimes]

	# ============ 实用方法 ============

	def get_date_range (
			self,
			start_date: Union[str, datetime, date],
			end_date: Union[str, datetime, date],
			timezone: Optional[str] = None
	) -> List[datetime]:
		"""
		获取日期范围

		Args:
			start_date: 开始日期
			end_date: 结束日期
			timezone: 时区

		Returns:
			日期列表
		"""
		# 转换为datetime
		if isinstance(start_date, str):
			start_dt = self.str_to_datetime(start_date, timezone)
		elif isinstance(start_date, date):
			start_dt = datetime.combine(start_date, time())
			start_dt = self.localize_datetime(start_dt, timezone)
		else:
			start_dt = start_date

		if isinstance(end_date, str):
			end_dt = self.str_to_datetime(end_date, timezone)
		elif isinstance(end_date, date):
			end_dt = datetime.combine(end_date, time())
			end_dt = self.localize_datetime(end_dt, timezone)
		else:
			end_dt = end_date

		if not start_dt or not end_dt:
			return []

		# 生成日期列表
		date_list = []
		current = self.get_start_of_day(start_dt)
		end = self.get_start_of_day(end_dt)

		while current <= end:
			date_list.append(current)
			current = self.add_days(current, 1)

		return date_list

	def format_duration (self, seconds: float) -> str:
		"""
		格式化持续时间

		Args:
			seconds: 秒数

		Returns:
			格式化的时间字符串
		"""
		if seconds < 60:
			return f"{seconds:.1f}秒"
		elif seconds < 3600:
			minutes = seconds / 60
			return f"{minutes:.1f}分钟"
		elif seconds < 86400:
			hours = seconds / 3600
			return f"{hours:.1f}小时"
		else:
			days = seconds / 86400
			return f"{days:.1f}天"

	def get_human_readable_time (self, dt: datetime) -> str:
		"""
		获取人性化时间显示

		Args:
			dt: datetime对象

		Returns:
			人性化时间字符串
		"""
		now = self.get_current_datetime()
		diff = now - dt

		if diff.total_seconds() < 60:
			return "刚刚"
		elif diff.total_seconds() < 3600:
			minutes = int(diff.total_seconds() / 60)
			return f"{minutes}分钟前"
		elif diff.total_seconds() < 86400:
			hours = int(diff.total_seconds() / 3600)
			return f"{hours}小时前"
		elif diff.total_seconds() < 604800:  # 7天
			days = int(diff.total_seconds() / 86400)
			return f"{days}天前"
		elif now.year == dt.year:
			return dt.strftime("%m-%d %H:%M")
		else:
			return dt.strftime("%Y-%m-%d")

	# ============ 静态方法 ============

	@staticmethod
	def get_available_timezones () -> List[str]:
		"""获取所有可用时区"""
		return pytz.all_timezones

	@staticmethod
	def validate_date_format (date_str: str, fmt: str = "%Y-%m-%d") -> bool:
		"""
		验证日期格式

		Args:
			date_str: 日期字符串
			fmt: 期望的格式

		Returns:
			bool: 格式是否有效
		"""
		try:
			datetime.strptime(date_str, fmt)
			return True
		except ValueError:
			return False

	@staticmethod
	def get_days_between (start: datetime, end: datetime) -> int:
		"""
		计算两个日期之间的天数

		Args:
			start: 开始日期
			end: 结束日期

		Returns:
			天数
		"""
		return (end.date() - start.date()).days

	@staticmethod
	def get_hours_between (start: datetime, end: datetime) -> float:
		"""
		计算两个时间之间的小时数

		Args:
			start: 开始时间
			end: 结束时间

		Returns:
			小时数
		"""
		return (end - start).total_seconds() / 3600