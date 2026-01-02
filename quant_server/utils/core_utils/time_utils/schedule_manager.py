"""
调度管理器

负责系统的任务调度管理，支持多种调度类型：
1. 定时调度（固定时间间隔）
2. 交易日调度（仅在交易日执行）
3. 交易时段调度（仅在交易时段执行）
4. Cron表达式调度（灵活时间安排）

设计原则：
- 支持异步调度
- 线程安全
- 可监控和动态调整
- 错误处理和重试机制
"""

import asyncio
import logging
from datetime import datetime, timedelta, time
from enum import Enum
from typing import Callable, Optional, Dict, List, Any, Awaitable
from dataclasses import dataclass, field
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .trading_calendar import TradingCalendar

# 配置日志
logger = logging.getLogger(__name__)


class ScheduleType(Enum):
	"""调度类型枚举"""

	# 固定时间间隔（秒）
	INTERVAL = "interval"

	# Cron表达式
	CRON = "cron"

	# 交易日调度（只在交易日执行）
	TRADING_DAY = "trading_day"

	# 交易时段调度（只在交易时段执行）
	TRADING_HOUR = "trading_hour"

	# 盘前调度（09:00-09:30）
	PRE_MARKET = "pre_market"

	# 盘中调度（09:30-11:30, 13:00-15:00）
	IN_TRADING = "in_trading"

	# 盘后调度（15:00-17:00）
	POST_MARKET = "post_market"


@dataclass
class ScheduleJob:
	"""调度任务配置"""

	# 任务标识
	job_id: str

	# 调度类型
	schedule_type: ScheduleType

	# 执行函数
	func: Callable[[], Awaitable[Any]]

	# 时间配置
	# interval类型：秒数
	# cron类型：cron表达式
	# 交易日类型：执行时间（HH:MM）
	schedule_config: Dict[str, Any]

	# 任务参数
	args: List[Any] = field(default_factory=list)
	kwargs: Dict[str, Any] = field(default_factory=dict)

	# 任务元数据
	name: str = ""
	description: str = ""
	enabled: bool = True

	# 重试配置
	max_retries: int = 3
	retry_delay: float = 5.0  # 秒

	# 执行历史
	last_executed: Optional[datetime] = None
	next_execution: Optional[datetime] = None
	execution_count: int = 0
	error_count: int = 0

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"job_id": self.job_id,
			"name": self.name,
			"schedule_type": self.schedule_type.value,
			"enabled": self.enabled,
			"last_executed": self.last_executed.isoformat() if self.last_executed else None,
			"next_execution": self.next_execution.isoformat() if self.next_execution else None,
			"execution_count": self.execution_count,
			"error_count": self.error_count,
		}


class ScheduleManager:
	"""
	调度管理器

	基于APScheduler实现，支持异步调度和交易日历调度
	"""

	def __init__ (self, trading_calendar: Optional[TradingCalendar] = None):
		"""
		初始化调度管理器

		Args:
			trading_calendar: 交易日历实例，如果为None则创建默认实例
		"""
		self.trading_calendar = trading_calendar or TradingCalendar()
		self.scheduler = AsyncIOScheduler()

		# 任务存储
		self.jobs: Dict[str, ScheduleJob] = {}
		self.scheduler_jobs: Dict[str, Any] = {}  # APScheduler Job对象

		# 状态
		self.is_running = False

		# 配置
		self.timezone = "Asia/Shanghai"

		logger.info("ScheduleManager初始化完成")

	async def start (self):
		"""启动调度器"""
		if self.is_running:
			logger.warning("调度器已经在运行")
			return

		self.scheduler.start()
		self.is_running = True

		logger.info("调度器已启动")

	async def stop (self, wait: bool = True):
		"""停止调度器

		Args:
			wait: 是否等待正在执行的任务完成
		"""
		if not self.is_running:
			logger.warning("调度器未运行")
			return

		self.scheduler.shutdown(wait=wait)
		self.is_running = False

		logger.info("调度器已停止")

	async def add_job (self, job: ScheduleJob) -> bool:
		"""
		添加调度任务

		Args:
			job: 调度任务配置

		Returns:
			bool: 是否添加成功
		"""
		if job.job_id in self.jobs:
			logger.error(f"任务已存在: {job.job_id}")
			return False

		try:
			# 根据调度类型创建触发器
			trigger = self._create_trigger(job)
			if not trigger:
				logger.error(f"创建触发器失败: {job.job_id}")
				return False

			# 创建APScheduler任务
			scheduler_job = self.scheduler.add_job(
				func=self._wrap_job_function(job),
				trigger=trigger,
				id=job.job_id,
				name=job.name,
				args=job.args,
				kwargs=job.kwargs,
				max_instances=3,
				misfire_grace_time=60,  # 任务错过执行时间时的宽限期（秒）
				coalesce=True,  # 合并多次错过的执行
			)

			# 保存任务
			self.jobs[job.job_id] = job
			self.scheduler_jobs[job.job_id] = scheduler_job

			# 更新下次执行时间
			job.next_execution = scheduler_job.next_run_time

			logger.info(f"任务添加成功: {job.job_id} - {job.name}")
			return True

		except Exception as e:
			logger.error(f"添加任务失败: {job.job_id}, 错误: {e}")
			return False

	def _create_trigger (self, job: ScheduleJob):
		"""
		根据调度类型创建触发器

		Args:
			job: 调度任务配置

		Returns:
			APScheduler Trigger对象
		"""
		try:
			if job.schedule_type == ScheduleType.INTERVAL:
				# 间隔调度
				seconds = job.schedule_config.get("seconds", 60)
				return IntervalTrigger(seconds=seconds, timezone=self.timezone)

			elif job.schedule_type == ScheduleType.CRON:
				# Cron表达式调度
				cron_expr = job.schedule_config.get("cron", "0 * * * *")
				return CronTrigger.from_crontab(cron_expr, timezone=self.timezone)

			elif job.schedule_type == ScheduleType.TRADING_DAY:
				# 交易日调度
				time_str = job.schedule_config.get("time", "09:00")
				hour, minute = map(int, time_str.split(":"))

				# 创建Cron触发器，但会在执行时检查是否为交易日
				return CronTrigger(
					day_of_week="mon-fri",  # 周一到周五
					hour=hour,
					minute=minute,
					timezone=self.timezone
				)

			elif job.schedule_type in [ScheduleType.TRADING_HOUR,
			                           ScheduleType.PRE_MARKET,
			                           ScheduleType.IN_TRADING,
			                           ScheduleType.POST_MARKET]:
				# 交易时段调度 - 使用Cron触发，在任务执行时检查时段
				hour = job.schedule_config.get("hour", 9)
				minute = job.schedule_config.get("minute", 0)

				return CronTrigger(
					day_of_week="mon-fri",  # 周一到周五
					hour=hour,
					minute=minute,
					timezone=self.timezone
				)

			else:
				logger.error(f"不支持的调度类型: {job.schedule_type}")
				return None

		except Exception as e:
			logger.error(f"创建触发器失败: {e}")
			return None

	def _wrap_job_function (self, job: ScheduleJob) -> Callable:
		"""
		包装任务函数，添加重试和日志功能

		Args:
			job: 调度任务配置

		Returns:
			包装后的函数
		"""

		async def wrapped_func (*args, **kwargs):
			"""包装函数，包含重试逻辑"""
			for attempt in range(job.max_retries + 1):
				try:
					# 检查调度条件
					if not self._check_schedule_condition(job):
						logger.debug(f"跳过执行 {job.job_id} - 不满足调度条件")
						return

					# 执行任务
					logger.info(f"开始执行任务: {job.job_id} - 尝试 {attempt + 1}")
					result = await job.func(*args, **kwargs)

					# 更新执行状态
					job.last_executed = datetime.now()
					job.execution_count += 1
					job.error_count = 0

					logger.info(f"任务执行成功: {job.job_id}")
					return result

				except Exception as e:
					job.error_count += 1
					logger.error(f"任务执行失败: {job.job_id}, 尝试 {attempt + 1}, 错误: {e}")

					if attempt < job.max_retries:
						# 等待重试
						await asyncio.sleep(job.retry_delay)
					else:
						# 重试次数用尽
						logger.error(f"任务重试次数用尽: {job.job_id}")
						raise

		return wrapped_func

	def _check_schedule_condition (self, job: ScheduleJob) -> bool:
		"""
		检查调度条件是否满足

		Args:
			job: 调度任务配置

		Returns:
			bool: 是否满足条件
		"""
		now = datetime.now()

		if job.schedule_type == ScheduleType.TRADING_DAY:
			# 检查是否为交易日
			if not self.trading_calendar.is_trading_day(now):
				return False

		elif job.schedule_type == ScheduleType.TRADING_HOUR:
			# 检查是否为交易时段
			if not self.trading_calendar.is_trading_hour(now):
				return False

		elif job.schedule_type == ScheduleType.PRE_MARKET:
			# 检查是否为盘前时段
			market_schedule = self.trading_calendar.get_market_schedule(now.date())
			current_time = now.time()

			if not market_schedule or not market_schedule.pre_market_start:
				return False

			if not (market_schedule.pre_market_start <= current_time <= market_schedule.pre_market_end):
				return False

		elif job.schedule_type == ScheduleType.IN_TRADING:
			# 检查是否为盘中时段
			market_schedule = self.trading_calendar.get_market_schedule(now.date())
			current_time = now.time()

			if not market_schedule:
				return False

			# 检查上午交易时段
			morning_trading = (market_schedule.market_start <= current_time <= market_schedule.market_morning_end)
			# 检查下午交易时段
			afternoon_trading = (market_schedule.market_afternoon_start <= current_time <= market_schedule.market_end)

			if not (morning_trading or afternoon_trading):
				return False

		elif job.schedule_type == ScheduleType.POST_MARKET:
			# 检查是否为盘后时段
			market_schedule = self.trading_calendar.get_market_schedule(now.date())
			current_time = now.time()

			if not market_schedule or not market_schedule.post_market_end:
				return False

			if not (market_schedule.post_market_start <= current_time <= market_schedule.post_market_end):
				return False

		return True

	async def remove_job (self, job_id: str) -> bool:
		"""
		移除调度任务

		Args:
			job_id: 任务ID

		Returns:
			bool: 是否移除成功
		"""
		if job_id not in self.jobs:
			logger.error(f"任务不存在: {job_id}")
			return False

		try:
			# 从APScheduler移除
			if job_id in self.scheduler_jobs:
				self.scheduler_jobs[job_id].remove()
				del self.scheduler_jobs[job_id]

			# 从本地存储移除
			del self.jobs[job_id]

			logger.info(f"任务移除成功: {job_id}")
			return True

		except Exception as e:
			logger.error(f"移除任务失败: {job_id}, 错误: {e}")
			return False

	async def pause_job (self, job_id: str) -> bool:
		"""暂停任务"""
		if job_id not in self.scheduler_jobs:
			return False

		try:
			self.scheduler_jobs[job_id].pause()
			if job_id in self.jobs:
				self.jobs[job_id].enabled = False
			return True
		except Exception as e:
			logger.error(f"暂停任务失败: {job_id}, 错误: {e}")
			return False

	async def resume_job (self, job_id: str) -> bool:
		"""恢复任务"""
		if job_id not in self.scheduler_jobs:
			return False

		try:
			self.scheduler_jobs[job_id].resume()
			if job_id in self.jobs:
				self.jobs[job_id].enabled = True
				self.jobs[job_id].next_execution = self.scheduler_jobs[job_id].next_run_time
			return True
		except Exception as e:
			logger.error(f"恢复任务失败: {job_id}, 错误: {e}")
			return False

	def get_job (self, job_id: str) -> Optional[ScheduleJob]:
		"""获取任务信息"""
		return self.jobs.get(job_id)

	def get_all_jobs (self) -> List[ScheduleJob]:
		"""获取所有任务"""
		return list(self.jobs.values())

	def get_job_status (self, job_id: str) -> Dict[str, Any]:
		"""获取任务状态"""
		job = self.get_job(job_id)
		if not job:
			return {"error": "任务不存在"}

		# 获取APScheduler任务状态
		scheduler_job = self.scheduler_jobs.get(job_id)

		status = job.to_dict()
		status.update({
			"next_run_time": scheduler_job.next_run_time.isoformat() if scheduler_job and scheduler_job.next_run_time else None,
			"pending": scheduler_job.pending if scheduler_job else False,
		})

		return status

	async def run_job_now (self, job_id: str) -> bool:
		"""
		立即运行任务

		Args:
			job_id: 任务ID

		Returns:
			bool: 是否运行成功
		"""
		job = self.get_job(job_id)
		if not job:
			return False

		try:
			# 直接执行任务函数
			await job.func(*job.args, **job.kwargs)

			# 更新执行时间
			job.last_executed = datetime.now()
			job.execution_count += 1

			return True

		except Exception as e:
			logger.error(f"立即运行任务失败: {job_id}, 错误: {e}")
			job.error_count += 1
			return False

	def get_stats (self) -> Dict[str, Any]:
		"""获取调度器统计信息"""
		return {
			"is_running": self.is_running,
			"total_jobs": len(self.jobs),
			"enabled_jobs": len([j for j in self.jobs.values() if j.enabled]),
			"disabled_jobs": len([j for j in self.jobs.values() if not j.enabled]),
			"next_execution": min(
				[j.next_execution for j in self.jobs.values() if j.next_execution]) if self.jobs else None,
		}