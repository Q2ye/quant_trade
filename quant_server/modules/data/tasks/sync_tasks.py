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
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Union
import uuid
import json
from celery import Celery, Task
from celery.schedules import crontab
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

from modules.data.engines.sync_engine import DataSyncEngine
from modules.data.services.sync_service import DataSyncService
from shared.database.session import SessionManager
from shared.cache.cache_manager import CacheManager
from shared.sources.tushare_source import TushareSource
from modules.data.events.sync_events import (
	DataSyncStartedEvent,
	DataSyncCompletedEvent,
	DataSyncErrorEvent,
	DataSyncProgressEvent
)

logger = logging.getLogger(__name__)

# 创建Celery应用
celery_app = Celery('data_sync_tasks')
celery_app.config_from_object('shared.config.celery_config')


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
		from core.events.event_engine import get_event_engine
		event_engine = get_event_engine()

		if event_engine:
			asyncio.create_task(event_engine.put(
				DataSyncCompletedEvent(
					task_id=task_id,
					sync_type=kwargs.get('sync_type', 'unknown'),
					record_count=retval.get('record_count', 0),
					success=True
				)
			))

	def on_failure (self, exc, task_id, args, kwargs):
		"""任务失败回调"""
		logger.error(f"同步任务失败: {task_id}, 错误: {exc}")

		# 发布任务失败事件
		from core.events.event_engine import get_event_engine
		event_engine = get_event_engine()

		if event_engine:
			asyncio.create_task(event_engine.put(
				DataSyncErrorEvent(
					task_id=task_id,
					sync_type=kwargs.get('sync_type', 'unknown'),
					error_message=str(exc)
				)
			))


@celery_app.task(base=SyncTaskBase, bind=True, max_retries=3, default_retry_delay=60)
def sync_stock_data_task (
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
		from core.events.event_engine import get_event_engine
		event_engine = get_event_engine()

		if event_engine:
			asyncio.create_task(event_engine.put(
				DataSyncStartedEvent(
					task_id=task_id,
					sync_type=sync_type,
					data_types=["stock_quote"],
					start_time=datetime.now()
				)
			))

		# 初始化服务
		sync_service = DataSyncService()

		# 更新进度
		self.update_state(
			state='PROGRESS',
			meta={'current': 10, 'total': 100, 'status': '初始化同步服务'}
		)

		# 发布进度事件
		if event_engine:
			asyncio.create_task(event_engine.put(
				DataSyncProgressEvent(
					task_id=task_id,
					progress=10,
					message="初始化同步服务",
					sync_type=sync_type
				)
			))

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
			self.update_state(
				state='PROGRESS',
				meta={'current': 20, 'total': 100, 'status': '获取股票列表'}
			)

			if event_engine:
				asyncio.create_task(event_engine.put(
					DataSyncProgressEvent(
						task_id=task_id,
						progress=20,
						message="获取股票列表",
						sync_type=sync_type
					)
				))

			# 获取所有上市股票
			all_stocks = sync_service.get_listed_stocks()
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
			self.update_state(
				state='PROGRESS',
				meta={
					'current': progress,
					'total': 100,
					'status': f'同步第 {batch_num + 1}/{total_batches} 批'
				}
			)

			if event_engine:
				asyncio.create_task(event_engine.put(
					DataSyncProgressEvent(
						task_id=task_id,
						progress=progress,
						message=f"同步第 {batch_num + 1}/{total_batches} 批",
						sync_type=sync_type,
						current_batch=batch_num + 1,
						total_batches=total_batches
					)
				))

			logger.info(f"同步第 {batch_num + 1} 批，共 {len(batch_codes)} 只股票")

			try:
				# 执行同步
				batch_result = sync_service.sync_stock_quotes(
					stock_codes=batch_codes,
					start_date=start_date,
					end_date=end_date,
					sync_type=sync_type,
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
		self.update_state(
			state='PROGRESS',
			meta={'current': 100, 'total': 100, 'status': '同步完成'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				DataSyncProgressEvent(
					task_id=task_id,
					progress=100,
					message="同步完成",
					sync_type=sync_type,
					result=result_summary
				)
			))

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
def sync_financial_data_task (
		self,
		report_type: str = "quarterly",
		year: Optional[int] = None,
		quarter: Optional[int] = None,
		stock_codes: Optional[List[str]] = None,
		**kwargs
) -> Dict[str, Any]:
	"""
	同步财务数据任务

	Args:
		report_type: 报告类型 (quarterly, annual)
		year: 年份
		quarter: 季度 (1-4)
		stock_codes: 股票代码列表
		**kwargs: 额外参数

	Returns:
		同步结果
	"""
	task_id = self.request.id
	logger.info(f"开始财务数据同步任务: {task_id}, 类型: {report_type}")

	try:
		# 发布任务开始事件
		from core.events.event_engine import get_event_engine
		event_engine = get_event_engine()

		if event_engine:
			asyncio.create_task(event_engine.put(
				DataSyncStartedEvent(
					task_id=task_id,
					sync_type="financial",
					data_types=[f"financial_{report_type}"],
					start_time=datetime.now()
				)
			))

		# 初始化服务
		sync_service = DataSyncService()

		# 更新进度
		self.update_state(
			state='PROGRESS',
			meta={'current': 10, 'total': 100, 'status': '初始化财务数据同步'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				DataSyncProgressEvent(
					task_id=task_id,
					progress=10,
					message="初始化财务数据同步",
					sync_type="financial"
				)
			))

		# 设置年份和季度
		if not year:
			year = date.today().year

		if report_type == "quarterly" and not quarter:
			current_month = date.today().month
			quarter = (current_month - 1) // 3 + 1

		# 获取股票列表
		if not stock_codes:
			logger.info("获取所有股票代码")
			self.update_state(
				state='PROGRESS',
				meta={'current': 30, 'total': 100, 'status': '获取股票列表'}
			)

			if event_engine:
				asyncio.create_task(event_engine.put(
					DataSyncProgressEvent(
						task_id=task_id,
						progress=30,
						message="获取股票列表",
						sync_type="financial"
					)
				))

			all_stocks = sync_service.get_listed_stocks()
			stock_codes = [stock['ts_code'] for stock in all_stocks]

		# 执行同步
		logger.info(f"开始同步 {report_type} 财务数据，共 {len(stock_codes)} 只股票")

		self.update_state(
			state='PROGRESS',
			meta={'current': 50, 'total': 100, 'status': '同步财务数据'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				DataSyncProgressEvent(
					task_id=task_id,
					progress=50,
					message="同步财务数据",
					sync_type="financial"
				)
			))

		sync_result = sync_service.sync_financial_data(
			stock_codes=stock_codes,
			report_type=report_type,
			year=year,
			quarter=quarter,
			**kwargs
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
		self.update_state(
			state='PROGRESS',
			meta={'current': 100, 'total': 100, 'status': '同步完成'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				DataSyncProgressEvent(
					task_id=task_id,
					progress=100,
					message="财务数据同步完成",
					sync_type="financial",
					result=result_summary
				)
			))

		return result_summary

	except Exception as e:
		logger.error(f"财务数据同步任务失败: {e}", exc_info=True)

		if self.request.retries < self.max_retries:
			logger.info(f"准备重试任务，已重试 {self.request.retries} 次")
			raise self.retry(exc=e)
		else:
			raise


@celery_app.task(base=SyncTaskBase, bind=True, max_retries=2)
def sync_index_data_task (
		self,
		index_codes: Optional[List[str]] = None,
		start_date: Optional[str] = None,
		end_date: Optional[str] = None,
		**kwargs
) -> Dict[str, Any]:
	"""
	同步指数数据任务

	Args:
		index_codes: 指数代码列表
		start_date: 开始日期
		end_date: 结束日期
		**kwargs: 额外参数

	Returns:
		同步结果
	"""
	task_id = self.request.id
	logger.info(f"开始指数数据同步任务: {task_id}")

	try:
		# 发布任务开始事件
		from core.events.event_engine import get_event_engine
		event_engine = get_event_engine()

		if event_engine:
			asyncio.create_task(event_engine.put(
				DataSyncStartedEvent(
					task_id=task_id,
					sync_type="index",
					data_types=["index_quote"],
					start_time=datetime.now()
				)
			))

		# 初始化服务
		sync_service = DataSyncService()

		# 更新进度
		self.update_state(
			state='PROGRESS',
			meta={'current': 10, 'total': 100, 'status': '初始化指数数据同步'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				DataSyncProgressEvent(
					task_id=task_id,
					progress=10,
					message="初始化指数数据同步",
					sync_type="index"
				)
			))

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

		self.update_state(
			state='PROGRESS',
			meta={'current': 30, 'total': 100, 'status': '同步指数数据'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				DataSyncProgressEvent(
					task_id=task_id,
					progress=30,
					message="同步指数数据",
					sync_type="index"
				)
			))

		results = []
		for index_code in index_codes:
			try:
				result = sync_service.sync_index_data(
					index_code=index_code,
					start_date=start_date,
					end_date=end_date,
					**kwargs
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
		self.update_state(
			state='PROGRESS',
			meta={'current': 100, 'total': 100, 'status': '同步完成'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				DataSyncProgressEvent(
					task_id=task_id,
					progress=100,
					message="指数数据同步完成",
					sync_type="index",
					result=result_summary
				)
			))

		return result_summary

	except Exception as e:
		logger.error(f"指数数据同步任务失败: {e}", exc_info=True)

		if self.request.retries < self.max_retries:
			logger.info(f"准备重试任务，已重试 {self.request.retries} 次")
			raise self.retry(exc=e)
		else:
			raise


@celery_app.task(base=SyncTaskBase, bind=True, max_retries=2)
def sync_macro_data_task (
		self,
		macro_types: Optional[List[str]] = None,
		start_date: Optional[str] = None,
		end_date: Optional[str] = None,
		**kwargs
) -> Dict[str, Any]:
	"""
	同步宏观经济数据任务

	Args:
		macro_types: 宏观数据类型列表
		start_date: 开始日期
		end_date: 结束日期
		**kwargs: 额外参数

	Returns:
		同步结果
	"""
	task_id = self.request.id
	logger.info(f"开始宏观经济数据同步任务: {task_id}")

	try:
		# 发布任务开始事件
		from core.events.event_engine import get_event_engine
		event_engine = get_event_engine()

		if event_engine:
			asyncio.create_task(event_engine.put(
				DataSyncStartedEvent(
					task_id=task_id,
					sync_type="macro",
					data_types=macro_types or ["macro_economic"],
					start_time=datetime.now()
				)
			))

		# 初始化服务
		sync_service = DataSyncService()

		# 更新进度
		self.update_state(
			state='PROGRESS',
			meta={'current': 10, 'total': 100, 'status': '初始化宏观经济数据同步'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				DataSyncProgressEvent(
					task_id=task_id,
					progress=10,
					message="初始化宏观经济数据同步",
					sync_type="macro"
				)
			))

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
				self.update_state(
					state='PROGRESS',
					meta={
						'current': progress,
						'total': 100,
						'status': f'同步 {macro_type} 数据'
					}
				)

				if event_engine:
					asyncio.create_task(event_engine.put(
						DataSyncProgressEvent(
							task_id=task_id,
							progress=progress,
							message=f"同步 {macro_type} 数据",
							sync_type="macro"
						)
					))

				result = sync_service.sync_macro_data(
					macro_type=macro_type,
					start_date=start_date,
					end_date=end_date,
					**kwargs
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
		self.update_state(
			state='PROGRESS',
			meta={'current': 100, 'total': 100, 'status': '同步完成'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				DataSyncProgressEvent(
					task_id=task_id,
					progress=100,
					message="宏观经济数据同步完成",
					sync_type="macro",
					result=result_summary
				)
			))

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

	logger.info("安排每日同步任务")

	# 计算下一个交易日
	from core_utils.time_utils.trading_calendar import TradingCalendar
	calendar = TradingCalendar()
	next_trading_day = calendar.get_next_trading_day(date.today())

	if next_trading_day:
		# 安排每日收盘后的同步任务（下午4点）
		schedule_time = next_trading_day.replace(hour=16, minute=0, second=0)

		# 安排股票数据同步
		current_app.send_task(
			'modules.data.tasks.sync_tasks.sync_stock_data_task',
			kwargs={
				'sync_type': 'daily',
				'start_date': next_trading_day.strftime('%Y%m%d'),
				'end_date': next_trading_day.strftime('%Y%m%d')
			},
			eta=schedule_time
		)

		# 安排指数数据同步
		current_app.send_task(
			'modules.data.tasks.sync_tasks.sync_index_data_task',
			kwargs={
				'start_date': next_trading_day.strftime('%Y%m%d'),
				'end_date': next_trading_day.strftime('%Y%m%d')
			},
			eta=schedule_time + timedelta(minutes=5)
		)

		logger.info(f"每日同步任务已安排: {schedule_time}")

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

		sync_service = DataSyncService()

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