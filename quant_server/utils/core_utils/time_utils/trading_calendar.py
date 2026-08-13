"""
交易日历

提供A股交易日历功能，包括：
1. 判断是否为交易日
2. 判断是否为交易时段
3. 获取下一个交易日
4. 获取前一个交易日
5. 获取交易日列表

设计原则：
- 支持缓存，减少数据库查询
- 支持动态更新交易日历
- 支持节假日调整
- 线程安全
"""

import json
import logging
from datetime import datetime, date, time, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple, Union
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import pandas as pd

# 配置日志
logger = logging.getLogger(__name__)


class TradingDayStatus(Enum):
	"""交易日状态枚举"""

	TRADING_DAY = "trading_day"  # 交易日
	HOLIDAY = "holiday"  # 节假日
	WEEKEND = "weekend"  # 周末
	SUSPENDED = "suspended"  # 临时休市


@dataclass
class MarketSchedule:
	"""交易时段配置"""

	# 交易日日期
	date: date

	# 盘前时段（可选）
	pre_market_start: Optional[time] = time(9, 0)  # 09:00
	pre_market_end: Optional[time] = time(9, 30)  # 09:30

	# 上午交易时段
	market_start: time = time(9, 30)  # 09:30
	market_morning_end: time = time(11, 30)  # 11:30

	# 中午休市
	break_start: time = time(11, 30)  # 11:30
	break_end: time = time(13, 0)  # 13:00

	# 下午交易时段
	market_afternoon_start: time = time(13, 0)  # 13:00
	market_end: time = time(15, 0)  # 15:00

	# 盘后时段（可选）
	post_market_start: Optional[time] = time(15, 0)  # 15:00
	post_market_end: Optional[time] = time(17, 0)  # 17:00

	# 夜盘时段（可选，期货使用）
	night_market_start: Optional[time] = None
	night_market_end: Optional[time] = None

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"date": self.date.isoformat(),
			"pre_market_start": self.pre_market_start.isoformat() if self.pre_market_start else None,
			"pre_market_end": self.pre_market_end.isoformat() if self.pre_market_end else None,
			"market_start": self.market_start.isoformat(),
			"market_morning_end": self.market_morning_end.isoformat(),
			"break_start": self.break_start.isoformat(),
			"break_end": self.break_end.isoformat(),
			"market_afternoon_start": self.market_afternoon_start.isoformat(),
			"market_end": self.market_end.isoformat(),
			"post_market_start": self.post_market_start.isoformat() if self.post_market_start else None,
			"post_market_end": self.post_market_end.isoformat() if self.post_market_end else None,
		}

	def is_trading_hour (self, current_time: time) -> bool:
		"""
		判断是否为交易时段

		Args:
			current_time: 当前时间

		Returns:
			bool: 是否为交易时段
		"""
		# 上午交易时段
		morning_trading = (self.market_start <= current_time <= self.market_morning_end)
		# 下午交易时段
		afternoon_trading = (self.market_afternoon_start <= current_time <= self.market_end)

		return morning_trading or afternoon_trading

	def is_pre_market (self, current_time: time) -> bool:
		"""判断是否为盘前时段"""
		if not self.pre_market_start or not self.pre_market_end:
			return False
		return self.pre_market_start <= current_time <= self.pre_market_end

	def is_post_market (self, current_time: time) -> bool:
		"""判断是否为盘后时段"""
		if not self.post_market_start or not self.post_market_end:
			return False
		return self.post_market_start <= current_time <= self.post_market_end

	def get_current_session (self, current_time: time) -> str:
		"""获取当前交易时段"""
		if self.is_pre_market(current_time):
			return "pre_market"
		elif self.is_trading_hour(current_time):
			if current_time <= self.market_morning_end:
				return "morning_trading"
			else:
				return "afternoon_trading"
		elif self.is_post_market(current_time):
			return "post_market"
		elif self.break_start <= current_time <= self.break_end:
			return "break"
		else:
			return "closed"


class TradingCalendar:
	"""
	A股交易日历

	支持日期判断、交易时段判断、日期计算等功能
	"""

	# A股默认交易时段
	DEFAULT_MARKET_SCHEDULE = MarketSchedule(date=date.today())

	# 节假日缓存（可从数据库或文件加载）
	_holidays: List[date] = []

	def __init__ (
			self,
			db_path: Optional[str] = None,
			cache_days: int = 365
	):
		"""
		初始化交易日历

		Args:
			db_path: SQLite数据库路径，如果为None则使用内存数据库
			cache_days: 缓存天数，默认365天
		"""
		self.db_path = db_path
		self.cache_days = cache_days

		# 缓存
		self._trading_days_cache: Dict[date, bool] = {}
		self._schedule_cache: Dict[date, MarketSchedule] = {}

		# 初始化数据库
		self._init_database()

		# 加载节假日数据
		self._load_holidays()

		logger.info(f"交易日历初始化完成，缓存天数: {cache_days}")

	def _init_database (self):
		"""初始化数据库"""
		try:
			if self.db_path:
				self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
			else:
				# 使用内存数据库
				self.conn = sqlite3.connect(":memory:", check_same_thread=False)

			# 创建交易日历表
			cursor = self.conn.cursor()
			cursor.execute("""
                           CREATE TABLE IF NOT EXISTS trading_calendar
                           (
                               date           TEXT PRIMARY KEY,
                               is_trading_day INTEGER,
                               description    TEXT,
                               created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                           )
			               """)

			# 创建节假日表
			cursor.execute("""
                           CREATE TABLE IF NOT EXISTS holidays
                           (
                               date        TEXT PRIMARY KEY,
                               name        TEXT,
                               is_workday  INTEGER,
                               description TEXT
                           )
			               """)

			self.conn.commit()
			logger.info("交易日历数据库初始化完成")

		except Exception as e:
			logger.error(f"初始化交易日历数据库失败: {e}")
			raise

	def _load_holidays (self):
		"""加载节假日数据"""
		try:
			cursor = self.conn.cursor()
			cursor.execute("SELECT date, name FROM holidays")
			rows = cursor.fetchall()

			self._holidays = []
			for row in rows:
				try:
					holiday_date = date.fromisoformat(row[0])
					self._holidays.append(holiday_date)
				except ValueError:
					continue

			if not self._holidays:
				# P1 修复：节假日表为空 → 主动回退到默认节假日。
				# 此前空表查询不抛异常、默认数据永不加载，节假日防护对实盘完全失效。
				self._load_default_holidays()

			logger.info(f"加载节假日数据完成，共{len(self._holidays)}个节假日")

		except Exception as e:
			logger.error(f"加载节假日数据失败: {e}")
			# 使用默认节假日数据
			self._load_default_holidays()

	def _load_default_holidays (self):
		"""加载默认节假日数据（2023-2026 年兜底；实盘应以 PostgreSQL trade_calendar 表为准）"""
		# 兜底节假日数据（实际应从外部数据源加载）
		default_holidays = [
			# 2023年节假日
			date(2023, 1, 1),  # 元旦
			date(2023, 1, 2),
			date(2023, 1, 21),  # 春节
			date(2023, 1, 22),
			date(2023, 1, 23),
			date(2023, 1, 24),
			date(2023, 1, 25),
			date(2023, 1, 26),
			date(2023, 1, 27),
			date(2023, 4, 5),  # 清明节
			date(2023, 4, 29),  # 劳动节
			date(2023, 4, 30),
			date(2023, 5, 1),
			date(2023, 5, 2),
			date(2023, 5, 3),
			date(2023, 6, 22),  # 端午节
			date(2023, 6, 23),
			date(2023, 6, 24),
			date(2023, 9, 29),  # 中秋节、国庆节
			date(2023, 9, 30),
			date(2023, 10, 1),
			date(2023, 10, 2),
			date(2023, 10, 3),
			date(2023, 10, 4),
			date(2023, 10, 5),
			date(2023, 10, 6),

			# 2024年节假日
			date(2024, 1, 1),  # 元旦
			date(2024, 2, 10),  # 春节
			date(2024, 2, 11),
			date(2024, 2, 12),
			date(2024, 2, 13),
			date(2024, 2, 14),
			date(2024, 2, 15),
			date(2024, 2, 16),
			date(2024, 4, 4),  # 清明节
			date(2024, 4, 5),
			date(2024, 4, 6),
			date(2024, 5, 1),  # 劳动节
			date(2024, 5, 2),
			date(2024, 5, 3),
			date(2024, 5, 4),
			date(2024, 5, 5),
			date(2024, 6, 10),  # 端午节
			date(2024, 9, 15),  # 中秋节
			date(2024, 9, 16),
			date(2024, 9, 17),
			date(2024, 10, 1),  # 国庆节
			date(2024, 10, 2),
			date(2024, 10, 3),
			date(2024, 10, 4),
			date(2024, 10, 5),
			date(2024, 10, 6),
			date(2024, 10, 7),

			# 2025年节假日（国务院办公厅 2024年11月通知）
			date(2025, 1, 1),  # 元旦
			date(2025, 1, 28),  # 春节
			date(2025, 1, 29),
			date(2025, 1, 30),
			date(2025, 1, 31),
			date(2025, 2, 1),
			date(2025, 2, 2),
			date(2025, 2, 3),
			date(2025, 2, 4),
			date(2025, 4, 4),  # 清明节
			date(2025, 4, 5),
			date(2025, 4, 6),
			date(2025, 5, 1),  # 劳动节
			date(2025, 5, 2),
			date(2025, 5, 3),
			date(2025, 5, 4),
			date(2025, 5, 5),
			date(2025, 5, 31),  # 端午节
			date(2025, 6, 1),
			date(2025, 6, 2),
			date(2025, 10, 1),  # 国庆节+中秋节
			date(2025, 10, 2),
			date(2025, 10, 3),
			date(2025, 10, 4),
			date(2025, 10, 5),
			date(2025, 10, 6),
			date(2025, 10, 7),
			date(2025, 10, 8),

			# 2026年节假日（国务院办公厅 2025年11月通知 国办发明电〔2025〕7号）
			date(2026, 1, 1),  # 元旦
			date(2026, 1, 2),
			date(2026, 1, 3),
			date(2026, 2, 15),  # 春节
			date(2026, 2, 16),
			date(2026, 2, 17),
			date(2026, 2, 18),
			date(2026, 2, 19),
			date(2026, 2, 20),
			date(2026, 2, 21),
			date(2026, 2, 22),
			date(2026, 2, 23),
			date(2026, 4, 4),  # 清明节
			date(2026, 4, 5),
			date(2026, 4, 6),
			date(2026, 5, 1),  # 劳动节
			date(2026, 5, 2),
			date(2026, 5, 3),
			date(2026, 5, 4),
			date(2026, 5, 5),
			date(2026, 6, 19),  # 端午节
			date(2026, 6, 20),
			date(2026, 6, 21),
			date(2026, 9, 25),  # 中秋节
			date(2026, 9, 26),
			date(2026, 9, 27),
			date(2026, 10, 1),  # 国庆节
			date(2026, 10, 2),
			date(2026, 10, 3),
			date(2026, 10, 4),
			date(2026, 10, 5),
			date(2026, 10, 6),
			date(2026, 10, 7),
		]

		self._holidays = default_holidays
		logger.info(f"加载默认节假日数据完成，共{len(self._holidays)}个节假日")

	# ============ 核心功能方法 ============

	def is_trading_day (self, dt: Union[datetime, date, str]) -> bool:
		"""
		判断是否为交易日

		Args:
			dt: 日期或时间

		Returns:
			bool: 是否为交易日
		"""
		# 转换为date对象
		check_date = self._to_date(dt)
		if not check_date:
			return False

		# 检查缓存
		if check_date in self._trading_days_cache:
			return self._trading_days_cache[check_date]

		# 判断逻辑
		is_trading = self._check_trading_day(check_date)

		# 更新缓存
		self._trading_days_cache[check_date] = is_trading

		return is_trading

	def _check_trading_day (self, check_date: date) -> bool:
		"""
		检查是否为交易日（核心逻辑）

		Args:
			check_date: 检查日期

		Returns:
			bool: 是否为交易日
		"""
		# 1. 检查是否为节假日
		if check_date in self._holidays:
			return False

		# 2. 检查是否为周末
		if check_date.weekday() >= 5:  # 5=周六，6=周日
			return False

		# 3. 检查数据库中是否有特殊记录
		try:
			cursor = self.conn.cursor()
			cursor.execute(
				"SELECT is_trading_day FROM trading_calendar WHERE date = ?",
				(check_date.isoformat(),)
			)
			row = cursor.fetchone()

			if row:
				return bool(row[0])

		except Exception as e:
			logger.error(f"查询交易日历数据库失败: {e}")

		# 4. 默认情况：工作日且不是节假日就是交易日
		return True

	def get_trading_day_status (self, dt: Union[datetime, date, str]) -> TradingDayStatus:
		"""
		获取交易日状态

		Args:
			dt: 日期或时间

		Returns:
			TradingDayStatus: 交易日状态
		"""
		check_date = self._to_date(dt)
		if not check_date:
			return TradingDayStatus.SUSPENDED

		# 检查节假日
		if check_date in self._holidays:
			return TradingDayStatus.HOLIDAY

		# 检查周末
		if check_date.weekday() >= 5:
			return TradingDayStatus.WEEKEND

		# 检查特殊休市日（数据库记录）
		try:
			cursor = self.conn.cursor()
			cursor.execute(
				"SELECT is_trading_day FROM trading_calendar WHERE date = ?",
				(check_date.isoformat(),)
			)
			row = cursor.fetchone()

			if row:
				if bool(row[0]):
					return TradingDayStatus.TRADING_DAY
				else:
					return TradingDayStatus.SUSPENDED

		except Exception as e:
			logger.error(f"查询交易日历数据库失败: {e}")

		# 默认工作日为交易日
		return TradingDayStatus.TRADING_DAY

	def is_trading_hour (self, dt: Union[datetime, time, str]) -> bool:
		"""
		判断是否为交易时段

		Args:
			dt: 时间或日期时间

		Returns:
			bool: 是否为交易时段
		"""
		# 转换为datetime
		if isinstance(dt, time):
			# 只有时间，使用今天日期
			current_dt = datetime.combine(date.today(), dt)
		elif isinstance(dt, str):
			try:
				# 尝试解析为时间
				if ":" in dt and len(dt) <= 8:
					# 只有时间
					t = time.fromisoformat(dt)
					current_dt = datetime.combine(date.today(), t)
				else:
					# 完整日期时间
					current_dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
			except ValueError:
				return False
		else:
			current_dt = dt

		# 首先检查是否为交易日
		if not self.is_trading_day(current_dt):
			return False

		# 获取交易时段配置
		schedule = self.get_market_schedule(current_dt.date())
		if not schedule:
			return False

		# 检查是否为交易时段
		return schedule.is_trading_hour(current_dt.time())

	def get_market_schedule (self, dt: Union[datetime, date, str]) -> Optional[MarketSchedule]:
		"""
		获取交易时段配置

		Args:
			dt: 日期或时间

		Returns:
			MarketSchedule: 交易时段配置，如果为None表示没有配置
		"""
		check_date = self._to_date(dt)
		if not check_date:
			return None

		# 检查缓存
		if check_date in self._schedule_cache:
			return self._schedule_cache[check_date]

		# 创建默认交易时段配置
		schedule = MarketSchedule(
			date=check_date,
			# 可以根据日期进行特殊调整，比如节假日前后的特殊交易时间
		)

		# 更新缓存
		self._schedule_cache[check_date] = schedule

		return schedule

	# ============ 日期计算方法 ============

	def get_next_trading_day (
			self,
			dt: Union[datetime, date, str],
			n: int = 1
	) -> Optional[date]:
		"""
		获取下一个交易日

		Args:
			dt: 起始日期
			n: 向前推n个交易日，默认1

		Returns:
			date: 下一个交易日，如果没有找到返回None
		"""
		start_date = self._to_date(dt)
		if not start_date:
			return None

		current_date = start_date
		found_count = 0

		while found_count < n:
			# 向前推进一天
			current_date += timedelta(days=1)

			# 检查是否为交易日
			if self.is_trading_day(current_date):
				found_count += 1

		return current_date

	def get_previous_trading_day (
			self,
			dt: Union[datetime, date, str],
			n: int = 1
	) -> Optional[date]:
		"""
		获取前一个交易日

		Args:
			dt: 起始日期
			n: 向后推n个交易日，默认1

		Returns:
			date: 前一个交易日，如果没有找到返回None
		"""
		start_date = self._to_date(dt)
		if not start_date:
			return None

		current_date = start_date
		found_count = 0

		while found_count < n:
			# 向后倒退一天
			current_date -= timedelta(days=1)

			# 检查是否为交易日
			if self.is_trading_day(current_date):
				found_count += 1

		return current_date

	def get_trading_days_between (
			self,
			start_dt: Union[datetime, date, str],
			end_dt: Union[datetime, date, str]
	) -> List[date]:
		"""
		获取两个日期之间的所有交易日

		Args:
			start_dt: 开始日期
			end_dt: 结束日期

		Returns:
			List[date]: 交易日列表
		"""
		start_date = self._to_date(start_dt)
		end_date = self._to_date(end_dt)

		if not start_date or not end_date or start_date > end_date:
			return []

		trading_days = []
		current_date = start_date

		while current_date <= end_date:
			if self.is_trading_day(current_date):
				trading_days.append(current_date)
			current_date += timedelta(days=1)

		return trading_days

	def get_trading_days_count (
			self,
			start_dt: Union[datetime, date, str],
			end_dt: Union[datetime, date, str]
	) -> int:
		"""
		计算两个日期之间的交易日数量

		Args:
			start_dt: 开始日期
			end_dt: 结束日期

		Returns:
			int: 交易日数量
		"""
		return len(self.get_trading_days_between(start_dt, end_dt))

	# ============ 节假日管理方法 ============

	def add_holiday (
			self,
			holiday_date: Union[date, str],
			name: str = "",
			description: str = ""
	) -> bool:
		"""
		添加节假日

		Args:
			holiday_date: 节假日日期
			name: 节假日名称
			description: 描述

		Returns:
			bool: 是否添加成功
		"""
		try:
			if isinstance(holiday_date, str):
				holiday_date = date.fromisoformat(holiday_date)

			# 添加到内存缓存
			if holiday_date not in self._holidays:
				self._holidays.append(holiday_date)

			# 保存到数据库
			cursor = self.conn.cursor()
			cursor.execute("""
                INSERT OR REPLACE INTO holidays (date, name, is_workday, description)
                VALUES (?, ?, ?, ?)
            """, (
				holiday_date.isoformat(),
				name,
				0,  # 不是工作日
				description
			))

			self.conn.commit()

			# 清除缓存
			self._trading_days_cache.pop(holiday_date, None)

			logger.info(f"添加节假日成功: {holiday_date} - {name}")
			return True

		except Exception as e:
			logger.error(f"添加节假日失败: {e}")
			return False

	def remove_holiday (self, holiday_date: Union[date, str]) -> bool:
		"""移除节假日"""
		try:
			if isinstance(holiday_date, str):
				holiday_date = date.fromisoformat(holiday_date)

			# 从内存缓存移除
			if holiday_date in self._holidays:
				self._holidays.remove(holiday_date)

			# 从数据库删除
			cursor = self.conn.cursor()
			cursor.execute(
				"DELETE FROM holidays WHERE date = ?",
				(holiday_date.isoformat(),)
			)

			self.conn.commit()

			# 清除缓存
			self._trading_days_cache.pop(holiday_date, None)

			logger.info(f"移除节假日成功: {holiday_date}")
			return True

		except Exception as e:
			logger.error(f"移除节假日失败: {e}")
			return False

	def add_trading_day (
			self,
			trading_date: Union[date, str],
			description: str = ""
	) -> bool:
		"""
		添加特殊交易日（如补班日）

		Args:
			trading_date: 交易日日期
			description: 描述

		Returns:
			bool: 是否添加成功
		"""
		try:
			if isinstance(trading_date, str):
				trading_date = date.fromisoformat(trading_date)

			# 从节假日中移除（如果是节假日的话）
			if trading_date in self._holidays:
				self._holidays.remove(trading_date)

			# 保存到数据库
			cursor = self.conn.cursor()
			cursor.execute("""
                INSERT OR REPLACE INTO trading_calendar (date, is_trading_day, description)
                VALUES (?, ?, ?)
            """, (
				trading_date.isoformat(),
				1,  # 是交易日
				description
			))

			self.conn.commit()

			# 清除缓存
			self._trading_days_cache.pop(trading_date, None)

			logger.info(f"添加特殊交易日成功: {trading_date}")
			return True

		except Exception as e:
			logger.error(f"添加特殊交易日失败: {e}")
			return False

	def remove_trading_day (self, trading_date: Union[date, str]) -> bool:
		"""移除特殊交易日记录"""
		try:
			if isinstance(trading_date, str):
				trading_date = date.fromisoformat(trading_date)

			# 从数据库删除
			cursor = self.conn.cursor()
			cursor.execute(
				"DELETE FROM trading_calendar WHERE date = ?",
				(trading_date.isoformat(),)
			)

			self.conn.commit()

			# 清除缓存
			self._trading_days_cache.pop(trading_date, None)

			logger.info(f"移除特殊交易日成功: {trading_date}")
			return True

		except Exception as e:
			logger.error(f"移除特殊交易日失败: {e}")
			return False

	# ============ 批量操作方法 ============

	def batch_is_trading_day (
			self,
			dates: List[Union[datetime, date, str]]
	) -> List[bool]:
		"""
		批量判断是否为交易日

		Args:
			dates: 日期列表

		Returns:
			List[bool]: 是否为交易日列表
		"""
		return [self.is_trading_day(dt) for dt in dates]

	def get_trading_days_in_month (
			self,
			year: int,
			month: int
	) -> List[date]:
		"""
		获取某个月的所有交易日

		Args:
			year: 年份
			month: 月份

		Returns:
			List[date]: 交易日列表
		"""
		import calendar

		# 获取该月的第一天和最后一天
		_, last_day = calendar.monthrange(year, month)
		start_date = date(year, month, 1)
		end_date = date(year, month, last_day)

		return self.get_trading_days_between(start_date, end_date)

	def get_trading_days_in_year (self, year: int) -> List[date]:
		"""
		获取某年的所有交易日

		Args:
			year: 年份

		Returns:
			List[date]: 交易日列表
		"""
		start_date = date(year, 1, 1)
		end_date = date(year, 12, 31)

		return self.get_trading_days_between(start_date, end_date)

	# ============ 工具方法 ============

	def _to_date (self, dt: Union[datetime, date, str]) -> Optional[date]:
		"""
		统一转换为date对象

		Args:
			dt: 日期时间对象

		Returns:
			date: 日期对象，转换失败返回None
		"""
		if isinstance(dt, datetime):
			return dt.date()
		elif isinstance(dt, date):
			return dt
		elif isinstance(dt, str):
			try:
				# 尝试解析日期
				if "T" in dt or " " in dt:
					# 包含时间部分
					return datetime.fromisoformat(dt.replace("Z", "+00:00")).date()
				else:
					# 纯日期
					return date.fromisoformat(dt)
			except ValueError:
				try:
					# 尝试其他格式
					return datetime.strptime(dt, "%Y%m%d").date()
				except ValueError:
					return None
		else:
			return None

	def get_holidays (self, year: Optional[int] = None) -> List[date]:
		"""
		获取节假日列表

		Args:
			year: 年份，如果为None则返回所有节假日

		Returns:
			List[date]: 节假日列表
		"""
		if year:
			return [d for d in self._holidays if d.year == year]
		else:
			return self._holidays.copy()

	def clear_cache (self):
		"""清除缓存"""
		self._trading_days_cache.clear()
		self._schedule_cache.clear()
		logger.info("交易日历缓存已清除")

	def get_stats (self) -> Dict[str, Any]:
		"""获取统计信息"""
		today = date.today()
		current_year = today.year

		# 计算本年交易日数量
		year_trading_days = len(self.get_trading_days_in_year(current_year))

		# 计算本月交易日数量
		month_trading_days = len(self.get_trading_days_in_month(current_year, today.month))

		return {
			"total_holidays": len(self._holidays),
			"cache_size": len(self._trading_days_cache),
			"current_year": current_year,
			"year_trading_days": year_trading_days,
			"month_trading_days": month_trading_days,
			"today_is_trading_day": self.is_trading_day(today),
			"next_trading_day": self.get_next_trading_day(today).isoformat() if self.get_next_trading_day(
				today) else None,
		}

	def save_to_file (self, filepath: str):
		"""保存到文件"""
		try:
			data = {
				"holidays": [d.isoformat() for d in self._holidays],
				"cache_size": len(self._trading_days_cache),
				"generated_at": datetime.now().isoformat()
			}

			with open(filepath, 'w', encoding='utf-8') as f:
				json.dump(data, f, ensure_ascii=False, indent=2)

			logger.info(f"交易日历已保存到文件: {filepath}")

		except Exception as e:
			logger.error(f"保存交易日历到文件失败: {e}")

	def load_from_file (self, filepath: str):
		"""从文件加载"""
		try:
			with open(filepath, 'r', encoding='utf-8') as f:
				data = json.load(f)

			self._holidays = [date.fromisoformat(d) for d in data.get("holidays", [])]
			self.clear_cache()

			logger.info(f"从文件加载交易日历成功: {filepath}")

		except Exception as e:
			logger.error(f"从文件加载交易日历失败: {e}")

	def __del__ (self):
		"""析构函数，关闭数据库连接"""
		try:
			if hasattr(self, 'conn'):
				self.conn.close()
				logger.info("交易日历数据库连接已关闭")
		except:
			pass