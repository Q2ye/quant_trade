"""
数据质量检查任务

负责数据质量相关的异步任务，包括：
1. 定时质量检查
2. 数据清洗任务
3. 数据验证任务
4. 质量报告生成

设计原则：
- 自动化：定时自动执行质量检查
- 可配置：支持不同的检查规则和阈值
- 可追溯：保存检查结果和历史记录
- 可操作：提供具体地改进建议
"""

import asyncio
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Union

import pandas as pd
from celery import Celery, Task
from celery.schedules import crontab

from api.dependencies import get_event_engine
from modules.data.events.clean_events import DataCleanCompletedEvent, DataCleanResult
from modules.data.events.quality_events import (
	DataQualityCheckStartedEvent,
	DataQualityCheckCompletedEvent, DataQualityIssueFoundEvent,
)
from modules.data.services.quality_service import DataQualityService
from modules.data.utils.quality_checker import DataQualityChecker, QualityCheckType
from shared.database.repositories.market.basic.stock_repo import StockBasicRepository
from shared.database.repositories.market.quote.stock_daily_repo import StockDailyRepository

logger = logging.getLogger(__name__)

# 创建Celery应用
celery_app = Celery('data_quality_tasks')
celery_app.config_from_object('quant_server.shared.config.celery_config')


class QualityTaskBase(Task):
	"""质量任务基类"""

	def __init__ (self):
		super().__init__()
		self.quality_checker = None
		self.quality_service = None

	def on_success (self, retval, task_id, args, kwargs):
		"""任务成功回调"""
		logger.info(f"质量检查任务成功: {task_id}")

		# 发布任务完成事件
		try:
			event_engine = asyncio.run(get_event_engine())
		except RuntimeError:
			event_engine = None

		if event_engine:
			# 同步处理事件发布
			try:
				event = DataQualityCheckCompletedEvent(
					check_id=task_id,
					total_checks=1,
					passed_checks=1 if retval.get('passed', False) else 0,
					failed_checks=0 if retval.get('passed', False) else 1,
					issue_summary={'medium': retval.get('total_issues', 0)},
					duration_seconds=0
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


def on_failure (exc, task_id):
	"""任务失败回调"""
	logger.error(f"质量检查任务失败: {task_id}, 错误: {exc}")

	# 发布任务失败事件
	try:
		event_engine = asyncio.run(get_event_engine())
	except RuntimeError:
		event_engine = None

	if event_engine:
		# 同步处理事件发布
		try:
			event = DataQualityCheckCompletedEvent(
				check_id=task_id,
				total_checks=1,
				passed_checks=0,
				failed_checks=1,
				issue_summary={'critical': 1},
				duration_seconds=0
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


@celery_app.task(base=QualityTaskBase, bind=True, max_retries=2, default_retry_delay=60)
async def check_data_quality_task (
		self,
		data_type: str = "stock_quote",
		check_date: Optional[str] = None,
		check_types: Optional[List[str]] = None,
		threshold: float = 70.0,
		**kwargs
) -> Dict[str, Any]:
	"""
	检查数据质量任务

	Args:
		self: 任务实例
		data_type: 数据类型
		check_date: 检查日期
		check_types: 检查类型列表
		threshold: 质量阈值
		**kwargs: 额外参数

	Returns:
		质量检查结果
	"""
	task_id = self.request.id

	try:
		logger.info(f"开始数据质量检查任务: {task_id}, 数据类型: {data_type}")

		# 发布任务开始事件
		event_engine = await get_event_engine()

		if event_engine:
			asyncio.create_task(event_engine.put(
				DataQualityCheckStartedEvent(
					check_type="full" if check_types and "all" in check_types else "partial",
					target_tables=[data_type],
					check_rules=check_types or ["basic", "completeness", "consistency"]
				)
			))

		# 设置检查日期
		if not check_date:
			check_date = date.today().strftime('%Y-%m-%d')

		# 转换检查类型
		quality_check_types = []
		if check_types:
			for ct in check_types:
				try:
					quality_check_types.append(ct)
				except ValueError:
					logger.warning(f"无效的检查类型: {ct}")
		else:
			# 默认检查所有类型
			quality_check_types = ['completeness', 'consistency', 'accuracy']

		# 获取数据
		logger.info(f"获取 {data_type} 数据进行检查")

		self.update_state(
			state='PROGRESS',
			meta={'current': 10, 'total': 100, 'status': '获取数据'}
		)

		data = None
		from shared.database.session import get_session_manager

		session_manager = get_session_manager()
		event_engine = await get_event_engine()
		async with session_manager.get_session() as session:
			# 初始化服务
			quality_checker = DataQualityChecker()
			quality_service = DataQualityService(session, event_engine)

			if data_type == "stock_quote":
				# 获取股票行情数据
				quote_repo = StockDailyRepository(session)

				# 获取最近30天的数据进行检查
				start_date = (datetime.strptime(check_date, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')

				data = await quote_repo.get_quotes_by_date_range(
					start_date=start_date,
					end_date=check_date,
					limit=10000
				)

				if isinstance(data, list):
					data = pd.DataFrame(data)

			elif data_type == "stock_basic":
				# 获取股票基础信息
				stock_repo = StockBasicRepository(session)
				data = await stock_repo.get_all_stocks()

				if isinstance(data, list):
					data = pd.DataFrame(data)

		# 检查数据
		if data is not None and not data.empty:
			logger.info(f"开始执行质量检查，数据大小: {data.shape}")

			self.update_state(
				state='PROGRESS',
				meta={'current': 30, 'total': 100, 'status': '执行质量检查'}
			)

			# 执行质量检查
			check_result = quality_checker.check_quality(
				data=data,
				data_type=data_type,
				check_types=quality_check_types,
				**kwargs
			)

			# 保存检查结果
			self.update_state(
				state='PROGRESS',
				meta={'current': 70, 'total': 100, 'status': '保存检查结果'}
			)

			result_id = await quality_service.save_quality_result(
				data_type=data_type,
				check_date=check_date,
				check_result=check_result,
				task_id=task_id
			)

			# 检查质量分数
			quality_score = check_result.get('summary', {}).get('quality_score', 0)

			if quality_score < threshold:
				logger.warning(f"数据质量分数低于阈值: {quality_score} < {threshold}")

				# 发布质量问题事件
				if event_engine:
					asyncio.create_task(event_engine.put(
						DataQualityIssueFoundEvent(
							issue_type="quality_score_below_threshold",
							table_name=data_type,
							column_name="quality_score",
							severity="medium",
							affected_count=check_result.get('summary', {}).get('total_issues', 0)
						)
					))

			# 汇总结果
			result_summary = {
				'task_id': task_id,
				'data_type': data_type,
				'check_date': check_date,
				'quality_score': quality_score,
				'total_issues': check_result.get('summary', {}).get('total_issues', 0),
				'result_id': result_id,
				'check_types': [ct for ct in quality_check_types],
				'threshold': threshold,
				'passed': quality_score >= threshold,
				'completed_at': datetime.now().isoformat()
			}

			logger.info(f"数据质量检查任务完成: {result_summary}")

			self.update_state(
				state='PROGRESS',
				meta={'current': 100, 'total': 100, 'status': '检查完成'}
			)

			return result_summary
		else:
			error_msg = f"未找到 {data_type} 数据或数据为空"
			logger.warning(error_msg)

			result_summary = {
				'task_id': task_id,
				'data_type': data_type,
				'check_date': check_date,
				'quality_score': 0,
				'total_issues': 0,
				'error': error_msg,
				'completed_at': datetime.now().isoformat()
			}

			return result_summary

	except Exception as e:
		logger.error(f"数据质量检查任务失败: {e}", exc_info=True)

		if self.request.retries < self.max_retries:
			logger.info(f"准备重试任务，已重试 {self.request.retries} 次")
			raise self.retry(exc=e)
		else:
			raise


@celery_app.task(base=QualityTaskBase, bind=True, max_retries=2)
def run_daily_quality_check (
		self,
		data_types: Optional[List[str]] = None,
		**kwargs
) -> Dict[str, Any]:
	"""
	运行每日质量检查

	Args:
		self: 任务实例
		data_types: 数据类型列表
		**kwargs: 额外参数

	Returns:
		检查结果汇总
	"""
	task_id = self.request.id

	try:
		logger.info(f"开始每日质量检查任务: {task_id}")

		# 设置默认数据类型
		if not data_types:
			data_types = [
				"stock_quote",
				"stock_basic",
				"index_quote"
			]

		# 执行每个数据类型的检查
		results = []

		for i, data_type in enumerate(data_types):
			try:
				# 更新进度
				progress = int((i / len(data_types)) * 90)
				self.update_state(
					state='PROGRESS',
					meta={
						'current': progress,
						'total': 100,
						'status': f'检查 {data_type} 数据质量'
					}
				)

				# 执行质量检查
				check_task = check_data_quality_task.apply_async(
					kwargs={
						'data_type': data_type,
						'check_date': date.today().strftime('%Y-%m-%d'),
						'check_types': ['completeness', 'consistency', 'accuracy'],
						**kwargs
					}
				)

				# 等待任务完成（超时时间5分钟）
				check_result = check_task.get(timeout=300)
				results.append({
					'data_type': data_type,
					'success': True,
					'result': check_result
				})

				logger.info(f"{data_type} 数据质量检查完成")

			except Exception as e:
				logger.error(f"{data_type} 数据质量检查失败: {e}")
				results.append({
					'data_type': data_type,
					'success': False,
					'error': str(e)
				})

		# 汇总结果
		successful_checks = sum(1 for r in results if r['success'])
		total_quality_score = sum(
			r['result'].get('quality_score', 0) for r in results if r['success']
		)
		avg_quality_score = total_quality_score / successful_checks if successful_checks > 0 else 0

		result_summary = {
			'task_id': task_id,
			'check_date': date.today().strftime('%Y-%m-%d'),
			'total_data_types': len(data_types),
			'successful_checks': successful_checks,
			'failed_checks': len(data_types) - successful_checks,
			'average_quality_score': round(avg_quality_score, 2),
			'results': results,
			'completed_at': datetime.now().isoformat()
		}

		logger.info(f"每日质量检查任务完成: {result_summary}")

		self.update_state(
			state='PROGRESS',
			meta={'current': 100, 'total': 100, 'status': '所有检查完成'}
		)

		return result_summary

	except Exception as e:
		logger.error(f"每日质量检查任务失败: {e}", exc_info=True)

		if self.request.retries < self.max_retries:
			logger.info(f"准备重试任务，已重试 {self.request.retries} 次")
			raise self.retry(exc=e)
		else:
			raise


@celery_app.task(base=QualityTaskBase, bind=True, max_retries=3, default_retry_delay=120)
async def clean_invalid_data_task (
		self,
		data_type: str = "stock_quote",
		start_date: Optional[str] = None,
		end_date: Optional[str] = None,
		cleaning_rules: Optional[Dict] = None,
) -> Dict[str, Any]:
	"""
	清理无效数据任务

	Args:
		self: 任务实例
		data_type: 数据类型
		start_date: 开始日期
		end_date: 结束日期
		cleaning_rules: 清理规则

	Returns:
		清理结果
	"""
	task_id = self.request.id

	try:
		logger.info(f"开始清理无效数据任务: {task_id}, 数据类型: {data_type}")
		task_start_time = datetime.now()

		# 设置日期范围
		if not start_date:
			start_date = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')

		if not end_date:
			end_date = date.today().strftime('%Y-%m-%d')

		# 设置默认清理规则
		if not cleaning_rules:
			cleaning_rules = {
				'remove_duplicates': True,
				'fix_missing_values': True,
				'remove_outliers': False,
				'validate_ranges': True
			}

		# 获取需要清理的数据
		logger.info(f"获取 {data_type} 数据进行清理")

		self.update_state(
			state='PROGRESS',
			meta={'current': 10, 'total': 100, 'status': '获取数据'}
		)

		# 根据数据类型获取数据
		data_to_clean = None
		from shared.database.session import get_session_manager

		session_manager = get_session_manager()
		event_engine = await get_event_engine()
		async with session_manager.get_session() as session:
			# 初始化服务
			quality_service = DataQualityService(session, event_engine)

			if data_type == "stock_quote":
				# 获取股票行情数据
				quote_repo = StockDailyRepository(session)
				data_to_clean = await quote_repo.get_quotes_by_date_range(
					start_date=start_date,
					end_date=end_date,
					limit=50000
				)

		if data_to_clean is None or len(data_to_clean) == 0:
			return {
				'task_id': task_id,
				'data_type': data_type,
				'cleaned_count': 0,
				'message': '没有需要清理的数据',
				'completed_at': datetime.now().isoformat()
			}

		# 执行数据清理
		logger.info(f"开始清理数据，共 {len(data_to_clean)} 条记录")

		# 将 StockDaily 对象转换为字典
		data_to_clean_dict = []
		for item in data_to_clean:
			item_dict = {
				'ts_code': item.ts_code,
				'trade_date': item.trade_date,
				'open': float(item.open) if item.open else None,
				'high': float(item.high) if item.high else None,
				'low': float(item.low) if item.low else None,
				'close': float(item.close) if item.close else None,
				'pre_close': float(item.pre_close) if item.pre_close else None,
				'change': float(item.change) if item.change else None,
				'pct_chg': float(item.pct_chg) if item.pct_chg else None,
				'vol': item.vol,
				'amount': float(item.amount) if item.amount else None
			}
			data_to_clean_dict.append(item_dict)

		self.update_state(
			state='PROGRESS',
			meta={'current': 30, 'total': 100, 'status': '执行数据清理'}
		)

		cleaning_result = await quality_service.clean_invalid_data(
			data=data_to_clean_dict,
			data_type=data_type,
			cleaning_rules=cleaning_rules,
		)

		# 保存清理后的数据
		self.update_state(
			state='PROGRESS',
			meta={'current': 70, 'total': 100, 'status': '保存清理结果'}
		)

		# 发布数据清理事件
		event_engine = await get_event_engine()

		if event_engine:
			# 创建DataCleanResult对象
			clean_result = DataCleanResult(
				total_issues=cleaning_result.get('removed_count', 0) + cleaning_result.get('fixed_count', 0),
				cleaned_at=datetime.now()
			)

			asyncio.create_task(event_engine.put(
				DataCleanCompletedEvent(
					clean_id=task_id,
					data_type=data_type,
					result=clean_result,
					duration_seconds=(datetime.now() - task_start_time).total_seconds()
				)
			))

		# 汇总结果
		result_summary = {
			'task_id': task_id,
			'data_type': data_type,
			'start_date': start_date,
			'end_date': end_date,
			'original_count': cleaning_result.get('original_count', 0),
			'cleaned_count': cleaning_result.get('cleaned_count', 0),
			'removed_count': cleaning_result.get('removed_count', 0),
			'fixed_count': cleaning_result.get('fixed_count', 0),
			'cleaning_rules': cleaning_rules,
			'success': cleaning_result.get('success', False),
			'message': cleaning_result.get('message', ''),
			'completed_at': datetime.now().isoformat()
		}

		logger.info(f"无效数据清理任务完成: {result_summary}")

		self.update_state(
			state='PROGRESS',
			meta={'current': 100, 'total': 100, 'status': '清理完成'}
		)

		return result_summary

	except Exception as e:
		logger.error(f"无效数据清理任务失败: {e}", exc_info=True)

		if self.request.retries < self.max_retries:
			logger.info(f"准备重试任务，已重试 {self.request.retries} 次")
			raise self.retry(exc=e)
		else:
			raise


@celery_app.task(base=QualityTaskBase, bind=True, max_retries=2)
async def validate_data_consistency_task (
		self,
		validation_type: str = "cross_reference",
		reference_date: Optional[str] = None,
) -> Dict[str, Any]:
	"""
	验证数据一致性任务

	Args:
		self: 任务实例
		validation_type: 验证类型
		reference_date: 参考日期

	Returns:
		验证结果
	"""
	task_id = self.request.id

	try:
		logger.info(f"开始数据一致性验证任务: {task_id}, 类型: {validation_type}")

		# 设置参考日期
		if not reference_date:
			reference_date = date.today().strftime('%Y-%m-%d')

		# 执行验证
		logger.info(f"执行 {validation_type} 验证")

		self.update_state(
			state='PROGRESS',
			meta={'current': 20, 'total': 100, 'status': '执行数据验证'}
		)

		# 初始化服务
		from shared.database.session import get_session_manager
		session_manager = get_session_manager()
		event_engine = await get_event_engine()
		async with session_manager.get_session() as session:
			quality_service = DataQualityService(session, event_engine)

			validation_result = await quality_service.validate_data_consistency(
				validation_type=validation_type,
				reference_date=reference_date
			)

		# 处理验证结果
		self.update_state(
			state='PROGRESS',
			meta={'current': 70, 'total': 100, 'status': '处理验证结果'}
		)

		# 如果有不一致的数据，记录日志
		inconsistencies = validation_result.get('inconsistencies', [])

		if inconsistencies:
			logger.warning(f"发现 {len(inconsistencies)} 个数据不一致问题")

			for inconsistency in inconsistencies[:10]:  # 只记录前10个
				logger.warning(f"数据不一致: {inconsistency}")

		# 汇总结果
		result_summary = {
			'task_id': task_id,
			'validation_type': validation_type,
			'reference_date': reference_date,
			'total_checks': validation_result.get('total_checks', 0),
			'passed_checks': validation_result.get('passed_checks', 0),
			'failed_checks': validation_result.get('failed_checks', 0),
			'inconsistency_count': len(inconsistencies),
			'consistency_score': validation_result.get('consistency_score', 0),
			'success': validation_result.get('success', False),
			'completed_at': datetime.now().isoformat()
		}

		logger.info(f"数据一致性验证任务完成: {result_summary}")

		self.update_state(
			state='PROGRESS',
			meta={'current': 100, 'total': 100, 'status': '验证完成'}
		)

		return result_summary

	except Exception as e:
		logger.error(f"数据一致性验证任务失败: {e}", exc_info=True)

		if self.request.retries < self.max_retries:
			logger.info(f"准备重试任务，已重试 {self.request.retries} 次")
			raise self.retry(exc=e)
		else:
			raise


# 配置Celery定时任务
celery_app.conf.beat_schedule = {
	'daily-quality-check': {
		'task': 'modules.data.tasks.quality_tasks.run_daily_quality_check',
		'schedule': crontab(hour=1, minute=0),  # 每天凌晨1点
		'args': (),
		'kwargs': {
			'data_types': ['stock_quote', 'stock_basic']
		},
	},
	'weekly-data-cleaning': {
		'task': 'modules.data.tasks.quality_tasks.clean_invalid_data_task',
		'schedule': crontab(hour=2, minute=0, day_of_week='sunday'),  # 每周日凌晨2点
		'args': (),
		'kwargs': {
			'data_type': 'stock_quote',
			'start_date': (date.today() - timedelta(days=7)).strftime('%Y-%m-%d'),
			'cleaning_rules': {
				'remove_duplicates': True,
				'fix_missing_values': True,
				'validate_ranges': True
			}
		},
	},
	'monthly-consistency-validation': {
		'task': 'modules.data.tasks.quality_tasks.validate_data_consistency_task',
		'schedule': crontab(hour=3, minute=0, day_of_month='1'),  # 每月1号凌晨3点
		'args': (),
		'kwargs': {
			'validation_type': 'cross_reference'
		},
	},
}


# 异步任务函数
async def async_check_data_quality (
		data: pd.DataFrame,
		data_type: str,
		check_types: Optional[List[QualityCheckType]] = None
) -> Dict[str, Any]:
	"""
	异步检查数据质量

	Args:
		data: 待检查的数据
		data_type: 数据类型
		check_types: 检查类型列表

	Returns:
		质量检查结果
	"""
	try:
		logger.info(f"异步检查数据质量: {data_type}, 数据大小: {data.shape}")

		quality_checker = DataQualityChecker()

		# 执行检查
		check_result = await asyncio.to_thread(
			quality_checker.check_quality,
			data=data,
			data_type=data_type,
			check_types=check_types
		)

		return check_result

	except Exception as e:
		logger.error(f"异步检查数据质量失败: {e}")
		raise


async def async_clean_data (
		data: Union[pd.DataFrame, List[Dict]],
		data_type: str,
		cleaning_rules: Dict
) -> Dict[str, Any]:
	"""
	异步清理数据

	Args:
		data: 待清理的数据
		data_type: 数据类型
		cleaning_rules: 清理规则

	Returns:
		清理结果
	"""
	try:
		logger.info(f"异步清理数据: {data_type}")

		# 初始化服务
		from shared.database.session import get_session_manager
		session_manager = get_session_manager()
		event_engine = await get_event_engine()
		async with session_manager.get_session() as session:
			quality_service = DataQualityService(session, event_engine)

			# 执行清理
			if isinstance(data, pd.DataFrame):
				data_list = data.to_dict('records')
			else:
				data_list = data

			cleaning_result = await asyncio.to_thread(
				quality_service.clean_invalid_data,
				data=data_list,
				data_type=data_type,
				cleaning_rules=cleaning_rules
			)

		return cleaning_result

	except Exception as e:
		logger.error(f"异步清理数据失败: {e}")
		raise


async def generate_quality_report (
		start_date: str,
		end_date: str,
		data_types: Optional[List[str]] = None
) -> Dict[str, Any]:
	"""
	生成质量报告

	Args:
		start_date: 开始日期
		end_date: 结束日期
		data_types: 数据类型列表

	Returns:
		质量报告
	"""
	try:
		logger.info(f"生成质量报告: {start_date} 到 {end_date}")

		# 初始化服务
		from shared.database.session import get_session_manager
		session_manager = get_session_manager()
		event_engine = await get_event_engine()
		async with session_manager.get_session() as session:
			quality_service = DataQualityService(session, event_engine)

			# 生成报告
			report = await quality_service.generate_quality_report(
				start_date=start_date,
				end_date=end_date,
				data_types=data_types
			)

		return report

	except Exception as e:
		logger.error(f"生成质量报告失败: {e}")
		raise