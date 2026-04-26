"""
数据同步任务

负责数据同步相关的异步任务，包括：
1. 定时同步任务
2. 手动触发同步
3. 增量同步
4. 全量同步

设计原则：
- 幂等性：多次执行相同任务结果一致
- 容错性：任务失败后可以恢复
- 可监控：支持进度跟踪和状态查询
- 可配置：支持不同的同步策略
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional

from celery import Celery, Task
from celery.schedules import crontab

from quant_server.api.dependencies import get_event_engine
from quant_server.modules.data.events.sync_events import (
	DataSyncStartedEvent,
	DataSyncCompletedEvent,
	DataSyncFailedEvent,
	DataSyncProgressEvent
)
from quant_server.modules.data.services.sync_service import DataSyncService, DataType
from quant_server.shared.database import get_session_manager
from quant_server.utils.core_utils.time_utils import TradingCalendar

logger = logging.getLogger(__name__)

# 创建Celery应用
celery_app = Celery('data_sync_tasks')
celery_app.config_from_object('shared.config.celery_config')


# ========== 公共辅助函数 ==========

async def _get_sync_service () -> DataSyncService:
	"""异步获取数据同步服务实例"""
	session_manager = get_session_manager()
	async with session_manager.get_session() as session:
		return DataSyncService(session=session)


def _publish_sync_started_event (task_id: str, sync_type: str, data_types: List[str]) -> None:
	"""发布同步开始事件"""
	event_engine = get_event_engine()
	if event_engine:
		asyncio.create_task(event_engine.put(
			DataSyncStartedEvent(
				task_id=task_id,
				sync_type=sync_type,
				data_types=data_types,
				start_time=datetime.now(),
				source="data_module"
			)
		))


def _publish_progress_event (task_id: str, progress: int, message: str, sync_type: str, **kwargs) -> None:
	"""发布进度事件"""
	event_engine = get_event_engine()
	if event_engine:
		asyncio.create_task(event_engine.put(
			DataSyncProgressEvent(
				task_id=task_id,
				progress=progress,
				message=message,
				sync_type=sync_type,
				source="data_module",
				**kwargs
			)
		))


def _publish_sync_completed_event (task_id: str, sync_type: str, result: Dict) -> None:
	"""发布同步完成事件"""
	event_engine = get_event_engine()
	if event_engine:
		asyncio.create_task(event_engine.put(
			DataSyncCompletedEvent(
				task_id=task_id,
				sync_type=sync_type,
				record_count=result.get('record_count', 0),
				duration_seconds=0,
				success=result.get('success', False),
				source="data_module"
			)
		))


def _update_task_progress (task_instance, progress: int, message: str, **kwargs) -> None:
	"""更新任务进度状态"""
	task_instance.update_state(
		state='PROGRESS',
		meta={
			'current': progress,
			'total': 100,
			'status': message,
			**kwargs
		}
	)


class SyncTaskBase(Task):
	"""同步任务基类"""

	def __init__ (self):
		super().__init__()
		self.sync_engine = None
		self.sync_service = None
		self.cache_manager = None
		self.executor = ThreadPoolExecutor(max_workers=4)

	def on_success (self, retval, task_id, args, kwargs):
		"""任务成功回调"""
		logger.info(f"同步任务成功: {task_id}")

		# 发布任务完成事件
		event_engine = get_event_engine()

		if event_engine:
			asyncio.create_task(event_engine.put(
				DataSyncCompletedEvent(
					task_id=task_id,
					sync_type=kwargs.get('sync_type', 'unknown'),
					record_count=retval.get('record_count', 0),
					duration_seconds=0,
					success=True,
					source="data_module"
				)
			))

	def on_failure (self, exc, task_id, args, kwargs, einfo=None):
		"""任务失败回调"""
		logger.error(f"同步任务失败: {task_id}, 错误: {exc}")

		# 发布任务失败事件
		event_engine = get_event_engine()

		if event_engine:
			# 同步处理事件发布
			try:
				event = DataSyncFailedEvent(
					task_id=task_id,
					sync_type=kwargs.get('sync_type', 'unknown'),
					error_message=str(exc)
				)
				# 检查 event_engine.put 是否是异步方法
				if hasattr(event_engine, 'put'):
					put_method = event_engine.put
					if asyncio.iscoroutinefunction(put_method):
						# 如果是异步方法，使用 asyncio.run
						asyncio.run(put_method(event))
					else:
						# 如果是同步方法，直接调用
						put_method(event)
			except Exception as put_error:
				logger.error(f"执行事件发布失败: {put_error}")


@celery_app.task(base=SyncTaskBase, bind=True, max_retries=3, default_retry_delay=60)
async def sync_stock_data_task (
		self,
		sync_type: str = "daily",
		start_date: Optional[str] = None,
		end_date: Optional[str] = None,
		stock_codes: Optional[List[str]] = None,
		force_update: bool = False,
		**kwargs
) -> Dict[str, Any]:
	"""
	同步股票数据任务

	Args:
		self: 任务实例
		sync_type: 同步类型 (daily, weekly, monthly, all)
		start_date: 开始日期 (YYYY-MM-DD)
		end_date: 结束日期 (YYYY-MM-DD)
		stock_codes: 股票代码列表
		force_update: 是否强制更新
		**kwargs: 额外参数

	Returns:
		同步结果
	"""
	task_id = self.request.id
	logger.info(f"开始股票数据同步任务: {task_id}, 类型: {sync_type}")

	try:
		# 发布任务开始事件
		_publish_sync_started_event(task_id, sync_type, ["stock_quote"])

		# 初始化服务
		sync_service = await  _get_sync_service()

		# 更新进度和发布事件
		_update_task_progress(self, 10, '初始化同步服务')
		_publish_progress_event(task_id, 10, "初始化同步服务", sync_type)

		# 设置日期范围
		if not start_date:
			if sync_type == "daily":
				start_date = (date.today() - timedelta(days=7)).strftime('%Y%m%d')
			else:
				start_date = "20100101"

		if not end_date:
			end_date = date.today().strftime('%Y%m%d')

		# 获取股票列表
		if not stock_codes:
			logger.info("获取所有股票代码")
			_update_task_progress(self, 20, '获取股票列表')
			_publish_progress_event(task_id, 20, "获取股票列表", sync_type)

			# 获取所有上市股票
			all_stocks = await sync_service.get_listed_stocks()
			stock_codes = [stock['ts_code'] for stock in all_stocks]

			logger.info(f"共获取 {len(stock_codes)} 只股票")

		# 分批同步
		batch_size = kwargs.get('batch_size', 100)
		total_batches = (len(stock_codes) + batch_size - 1) // batch_size

		logger.info(f"开始分批同步，共 {total_batches} 批")

		results = []
		failed_stocks = []

		for batch_num in range(total_batches):
			start_idx = batch_num * batch_size
			end_idx = min((batch_num + 1) * batch_size, len(stock_codes))
			batch_codes = stock_codes[start_idx:end_idx]

			# 更新进度
			progress = 30 + int((batch_num / total_batches) * 60)
			_update_task_progress(self, progress, f'同步第 {batch_num + 1}/{total_batches} 批')
			_publish_progress_event(
				task_id, progress, f"同步第 {batch_num + 1}/{total_batches} 批", sync_type,
				current_batch=batch_num + 1, total_batches=total_batches
			)

			logger.info(f"同步第 {batch_num + 1} 批，共 {len(batch_codes)} 只股票")

			try:
				# 执行同步
				batch_result = await sync_service.sync_market_data(
					data_type=DataType.DAILY_QUOTES,
					ts_codes=batch_codes,
					start_date=datetime.strptime(start_date, '%Y%m%d').date(),
					end_date=datetime.strptime(end_date, '%Y%m%d').date(),
					force_update=force_update
				)

				results.append(batch_result)
				logger.info(f"第 {batch_num + 1} 批同步完成: {batch_result}")

			except Exception as e:
				logger.error(f"第 {batch_num + 1} 批同步失败: {e}")
				failed_stocks.extend(batch_codes)

		# 汇总结果
		total_records = sum(result.get('record_count', 0) for result in results)
		success_count = len(results) - len(failed_stocks)

		result_summary = {
			'task_id': task_id,
			'sync_type': sync_type,
			'success': len(failed_stocks) == 0,
			'total_stocks': len(stock_codes),
			'successful_batches': success_count,
			'failed_batches': len(failed_stocks),
			'failed_stocks': failed_stocks,
			'record_count': total_records,
			'start_date': start_date,
			'end_date': end_date,
			'completed_at': datetime.now().isoformat()
		}

		logger.info(f"股票数据同步任务完成: {result_summary}")

		# 更新最终进度
		_update_task_progress(self, 100, '同步完成')
		_publish_progress_event(task_id, 100, "同步完成", sync_type, result=result_summary)

		return result_summary

	except Exception as e:
		logger.error(f"股票数据同步任务失败: {e}", exc_info=True)

		# 重试逻辑
		if self.request.retries < self.max_retries:
			logger.info(f"准备重试任务，已重试 {self.request.retries} 次")
			raise self.retry(exc=e)
		else:
			raise


@celery_app.task(base=SyncTaskBase, bind=True, max_retries=2, default_retry_delay=300)
async def sync_financial_data_task (
		self,
		report_type: str = "quarterly",
		year: Optional[int] = None,
		quarter: Optional[int] = None,
		stock_codes: Optional[List[str]] = None,
) -> Dict[str, Any]:
	"""
	同步财务数据任务

	Args:
		self: 任务实例
		report_type: 报告类型 (quarterly, annual)
		year: 年份
		quarter: 季度 (1-4)
		stock_codes: 股票代码列表

	Returns:
		同步结果
	"""
	task_id = self.request.id
	logger.info(f"开始财务数据同步任务: {task_id}, 类型: {report_type}")

	try:
		# 发布任务开始事件
		_publish_sync_started_event(task_id, "financial", [f"financial_{report_type}"])

		# 初始化服务
		sync_service = await _get_sync_service()

		# 更新进度
		_update_task_progress(self, 10, '初始化财务数据同步')
		_publish_progress_event(task_id, 10, "初始化财务数据同步", "financial")

		# 设置年份和季度
		if not year:
			year = date.today().year

		if report_type == "quarterly" and not quarter:
			current_month = date.today().month
			quarter = (current_month - 1) // 3 + 1

		# 获取股票列表
		if not stock_codes:
			logger.info("获取所有股票代码")
			_update_task_progress(self, 30, '获取股票列表')
			_publish_progress_event(task_id, 30, "获取股票列表", "financial")

			all_stocks = await sync_service.get_listed_stocks()
			stock_codes = [stock['ts_code'] for stock in all_stocks]

		# 执行同步
		logger.info(f"开始同步 {report_type} 财务数据，共 {len(stock_codes)} 只股票")

		_update_task_progress(self, 50, '同步财务数据')
		_publish_progress_event(task_id, 50, "同步财务数据", "financial")

		sync_result = await sync_service.sync_market_data(
			data_type=DataType.FINANCIAL_INCOME,
			start_date=date(year, 1, 1),
			end_date=date(year, 12, 31),
			ts_codes=stock_codes
		)

		# 汇总结果
		result_summary = {
			'task_id': task_id,
			'report_type': report_type,
			'year': year,
			'quarter': quarter if report_type == "quarterly" else None,
			'total_stocks': len(stock_codes),
			'record_count': sync_result.get('record_count', 0),
			'success': sync_result.get('success', False),
			'message': sync_result.get('message', ''),
			'completed_at': datetime.now().isoformat()
		}

		logger.info(f"财务数据同步任务完成: {result_summary}")

		# 更新最终进度
		_update_task_progress(self, 100, '同步完成')
		_publish_progress_event(task_id, 100, "财务数据同步完成", "financial", result=result_summary)

		return result_summary

	except Exception as e:
		logger.error(f"财务数据同步任务失败: {e}", exc_info=True)

		if self.request.retries < self.max_retries:
			logger.info(f"准备重试任务，已重试 {self.request.retries} 次")
			raise self.retry(exc=e)
		else:
			raise


@celery_app.task(base=SyncTaskBase, bind=True, max_retries=2)
async def sync_index_data_task (
		self,
		index_codes: Optional[List[str]] = None,
		start_date: Optional[str] = None,
		end_date: Optional[str] = None,
) -> Dict[str, Any]:
	"""
	同步指数数据任务

	Args:
		self: 任务实例
		index_codes: 指数代码列表
		start_date: 开始日期
		end_date: 结束日期

	Returns:
		同步结果
	"""
	task_id = self.request.id
	logger.info(f"开始指数数据同步任务: {task_id}")

	try:
		# 发布任务开始事件
		_publish_sync_started_event(task_id, "index", ["index_quote"])

		# 初始化服务
		sync_service = await _get_sync_service()

		# 更新进度
		_update_task_progress(self, 10, '初始化指数数据同步')
		_publish_progress_event(task_id, 10, "初始化指数数据同步", "index")

		# 设置默认指数
		if not index_codes:
			index_codes = [
				'000001.SH',  # 上证指数
				'399001.SZ',  # 深证成指
				'399006.SZ',  # 创业板指
				'000300.SH',  # 沪深300
				'000905.SH',  # 中证500
			]

		# 设置日期范围
		if not start_date:
			start_date = (date.today() - timedelta(days=365)).strftime('%Y%m%d')

		if not end_date:
			end_date = date.today().strftime('%Y%m%d')

		# 执行同步
		logger.info(f"开始同步指数数据，共 {len(index_codes)} 个指数")

		_update_task_progress(self, 30, '同步指数数据')
		_publish_progress_event(task_id, 30, "同步指数数据", "index")

		results = []
		for index_code in index_codes:
			try:
				result = await sync_service.sync_index_data(
					start_date=start_date,
					end_date=end_date,
					index_codes=[index_code]
				)
				results.append(result)
				logger.info(f"指数 {index_code} 同步完成")
			except Exception as e:
				logger.error(f"指数 {index_code} 同步失败: {e}")
				results.append({
					'index_code': index_code,
					'success': False,
					'error': str(e)
				})

		# 汇总结果
		total_records = sum(result.get('record_count', 0) for result in results)
		success_count = sum(1 for result in results if result.get('success', False))

		result_summary = {
			'task_id': task_id,
			'sync_type': 'index',
			'total_indices': len(index_codes),
			'successful_indices': success_count,
			'failed_indices': len(index_codes) - success_count,
			'record_count': total_records,
			'start_date': start_date,
			'end_date': end_date,
			'results': results,
			'completed_at': datetime.now().isoformat()
		}

		logger.info(f"指数数据同步任务完成: {result_summary}")

		# 更新最终进度
		_update_task_progress(self, 100, '同步完成')
		_publish_progress_event(task_id, 100, "指数数据同步完成", "index", result=result_summary)

		return result_summary

	except Exception as e:
		logger.error(f"指数数据同步任务失败: {e}", exc_info=True)

		if self.request.retries < self.max_retries:
			logger.info(f"准备重试任务，已重试 {self.request.retries} 次")
			raise self.retry(exc=e)
		else:
			raise


@celery_app.task(base=SyncTaskBase, bind=True, max_retries=2)
async def sync_macro_data_task (
		self,
		macro_types: Optional[List[str]] = None,
		start_date: Optional[str] = None,
		end_date: Optional[str] = None,
) -> Dict[str, Any]:
	"""
	同步宏观经济数据任务

	Args:
		self: 任务实例
		macro_types: 宏观数据类型列表
		start_date: 开始日期
		end_date: 结束日期

	Returns:
		同步结果
	"""
	task_id = self.request.id
	logger.info(f"开始宏观经济数据同步任务: {task_id}")

	try:
		# 发布任务开始事件
		_publish_sync_started_event(task_id, "macro", macro_types or ["macro_economic"])

		# 初始化服务
		sync_service = await _get_sync_service()

		# 更新进度
		_update_task_progress(self, 10, '初始化宏观经济数据同步')
		_publish_progress_event(task_id, 10, "初始化宏观经济数据同步", "macro")

		# 设置默认宏观数据类型
		if not macro_types:
			macro_types = [
				'GDP',  # 国内生产总值
				'CPI',  # 居民消费价格指数
				'PPI',  # 工业生产者出厂价格指数
				'PMI',  # 采购经理指数
				'M2',  # 货币供应量
				'RATE',  # 利率
			]

		# 设置日期范围
		if not start_date:
			start_date = "20100101"

		if not end_date:
			end_date = date.today().strftime('%Y%m%d')

		# 执行同步
		logger.info(f"开始同步宏观经济数据，共 {len(macro_types)} 种类型")

		results = []
		for i, macro_type in enumerate(macro_types):
			try:
				# 更新进度
				progress = 30 + int((i / len(macro_types)) * 60)
				_update_task_progress(self, progress, f'同步 {macro_type} 数据')
				_publish_progress_event(task_id, progress, f"同步 {macro_type} 数据", "macro", macro_type=macro_type)

				result = await sync_service.sync_macro_data(
					macro_type=macro_type,
					start_date=start_date,
					end_date=end_date
				)
				results.append(result)
				logger.info(f"宏观经济数据 {macro_type} 同步完成")

			except Exception as e:
				logger.error(f"宏观经济数据 {macro_type} 同步失败: {e}")
				results.append({
					'macro_type': macro_type,
					'success': False,
					'error': str(e)
				})

		# 汇总结果
		total_records = sum(result.get('record_count', 0) for result in results)
		success_count = sum(1 for result in results if result.get('success', False))

		result_summary = {
			'task_id': task_id,
			'sync_type': 'macro',
			'total_macro_types': len(macro_types),
			'successful_types': success_count,
			'failed_types': len(macro_types) - success_count,
			'record_count': total_records,
			'start_date': start_date,
			'end_date': end_date,
			'results': results,
			'completed_at': datetime.now().isoformat()
		}

		logger.info(f"宏观经济数据同步任务完成: {result_summary}")

		# 更新最终进度
		_update_task_progress(self, 100, '同步完成')
		_publish_progress_event(task_id, 100, "宏观经济数据同步完成", "macro", result=result_summary)

		return result_summary

	except Exception as e:
		logger.error(f"宏观经济数据同步任务失败: {e}", exc_info=True)

		if self.request.retries < self.max_retries:
			logger.info(f"准备重试任务，已重试 {self.request.retries} 次")
			raise self.retry(exc=e)
		else:
			raise


def schedule_daily_sync ():
	"""
	安排每日同步任务

	每天收盘后执行以下同步任务：
	1. 同步当日股票行情数据
	2. 同步指数数据
	3. 检查数据质量
	"""
	from celery import current_app
	from datetime import datetime, time

	logger.info("安排每日同步任务")

	# 获取交易日历
	calendar = TradingCalendar()
	today = date.today()

	# 检查今日是否为交易日
	if calendar.is_trading_day(today):
		# 安排在今日收盘后（下午3:30）
		schedule_time = datetime.combine(today, time(15, 30))

		# 如果当前时间已经过了15:30，安排在明天同一时间
		if schedule_time < datetime.now():
			tomorrow = today + timedelta(days=1)
			schedule_time = datetime.combine(tomorrow, time(15, 30))

		# 安排股票数据同步（同步今日数据）
		current_app.send_task(
			'modules.data.tasks.sync_tasks.sync_stock_data_task',
			kwargs={
				'sync_type': 'daily',
				'start_date': today.strftime('%Y%m%d'),
				'end_date': today.strftime('%Y%m%d')
			},
			eta=schedule_time
		)

		# 安排指数数据同步（比股票数据晚5分钟）
		current_app.send_task(
			'modules.data.tasks.sync_tasks.sync_index_data_task',
			kwargs={
				'start_date': today.strftime('%Y%m%d'),
				'end_date': today.strftime('%Y%m%d')
			},
			eta=schedule_time + timedelta(minutes=5)
		)

		logger.info(f"每日同步任务已安排: {schedule_time} (同步今日数据: {today})")
	else:
		logger.info(f"今日({today})非交易日，跳过同步任务安排")

	return True


# 配置Celery定时任务
celery_app.conf.beat_schedule = {
	'daily-stock-sync': {
		'task': 'modules.data.tasks.sync_tasks.sync_stock_data_task',
		'schedule': crontab(hour=16, minute=0, day_of_week='mon-fri'),  # 工作日每天下午4点
		'args': (),
		'kwargs': {
			'sync_type': 'daily',
			'force_update': False
		},
	},
	'quarterly-financial-sync': {
		'task': 'modules.data.tasks.sync_tasks.sync_financial_data_task',
		'schedule': crontab(hour=2, minute=0, day_of_month='1'),  # 每月1号凌晨2点
		'args': (),
		'kwargs': {
			'report_type': 'quarterly'
		},
	},
	'annual-financial-sync': {
		'task': 'modules.data.tasks.sync_tasks.sync_financial_data_task',
		'schedule': crontab(hour=2, minute=0, day_of_month='1', month_of_year='4'),  # 每年4月1号凌晨2点
		'args': (),
		'kwargs': {
			'report_type': 'annual'
		},
	},
}


# 异步任务函数（非Celery任务）
async def async_sync_stock_data (
		stock_codes: List[str],
		start_date: str,
		end_date: str,
		sync_type: str = "daily"
) -> Dict[str, Any]:
	"""
	异步同步股票数据

	Args:
		stock_codes: 股票代码列表
		start_date: 开始日期
		end_date: 结束日期
		sync_type: 同步类型

	Returns:
		同步结果
	"""
	try:
		logger.info(f"异步同步股票数据: {len(stock_codes)} 只股票")

		sync_service = await _get_sync_service()
		# 分批异步处理
		batch_size = 50
		tasks = []

		for i in range(0, len(stock_codes), batch_size):
			batch_codes = stock_codes[i:i + batch_size]

			task = asyncio.create_task(
				_async_sync_batch(
					sync_service,
					batch_codes,
					start_date,
					end_date,
					sync_type
				)
			)
			tasks.append(task)

		# 等待所有任务完成
		results = await asyncio.gather(*tasks, return_exceptions=True)

		# 汇总结果
		successful_batches = 0
		failed_batches = 0
		total_records = 0

		for result in results:
			if isinstance(result, Exception):
				failed_batches += 1
				logger.error(f"批次同步失败: {result}")
			else:
				successful_batches += 1
				total_records += result.get('record_count', 0)

		return {
			'success': failed_batches == 0,
			'total_batches': len(tasks),
			'successful_batches': successful_batches,
			'failed_batches': failed_batches,
			'record_count': total_records,
			'completed_at': datetime.now().isoformat()
		}

	except Exception as e:
		logger.error(f"异步同步股票数据失败: {e}")
		raise


async def _async_sync_batch (
		sync_service: DataSyncService,
		stock_codes: List[str],
		start_date: str,
		end_date: str,
		sync_type: str
) -> Dict[str, Any]:
	"""异步同步批次数据"""
	try:
		result = await sync_service.async_sync_stock_quotes(
			stock_codes=stock_codes,
			start_date=start_date,
			end_date=end_date,
			sync_type=sync_type
		)
		return result
	except Exception as e:
		logger.error(f"批次同步失败: {e}")
		raise