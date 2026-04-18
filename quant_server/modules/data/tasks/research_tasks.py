"""
因子研究任务

负责因子研究相关的异步任务，包括：
1. 因子计算任务
2. 因子分析任务
3. 因子优化任务
4. 研究报告生成任务

设计原则：
- 计算密集型：因子计算可能需要大量计算资源
- 可中断：支持长时间运行的任务中断和恢复
- 可监控：支持进度跟踪和结果可视化
- 可配置：支持不同的研究参数和算法
"""

import asyncio
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Union, Tuple
import pandas as pd
import numpy as np
from celery import Celery, Task
from celery.schedules import crontab
import json
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from quant_server.modules.data.utils.factor_calculator import FactorCalculator, FactorCategory
from quant_server.modules.data.services.research_service import DataResearchService
from quant_server.modules.data.engines.research_engine import FactorResearchEngine, ResearchTaskType
from quant_server.shared.database.session import SessionManager
from quant_server.shared.database.repositories.market.quote import StockDailyRepository
from quant_server.shared.database.repositories.market.basic import StockBasicRepository
from quant_server.modules.data.events.research_events import (
	FactorResearchStartedEvent,
	FactorResearchCompletedEvent,
	FactorResearchProgressEvent,
	FactorAnalysisCompletedEvent
)

logger = logging.getLogger(__name__)

# 创建Celery应用
celery_app = Celery('data_research_tasks')
celery_app.config_from_object('shared.config.celery_config')


class ResearchTaskBase(Task):
	"""研究任务基类"""

	def __init__ (self):
		super().__init__()
		self.factor_calculator = None
		self.research_service = None
		self.research_engine = None
		self.process_pool = ProcessPoolExecutor(max_workers=4)
		self.thread_pool = ThreadPoolExecutor(max_workers=8)

	def on_success (self, retval, task_id, args, kwargs):
		"""任务成功回调"""
		logger.info(f"研究任务成功: {task_id}")

		# 发布任务完成事件
		from core.events.event_engine import get_event_engine
		event_engine = get_event_engine()

		if event_engine:
			asyncio.create_task(event_engine.put(
				FactorResearchCompletedEvent(
					task_id=task_id,
					task_type=kwargs.get('task_type', 'unknown'),
					results=retval,
					duration=retval.get('duration_seconds', 0),
					success=True
				)
			))

	def on_failure (self, exc, task_id, args, kwargs):
		"""任务失败回调"""
		logger.error(f"研究任务失败: {task_id}, 错误: {exc}")

		# 发布任务失败事件
		from core.events.event_engine import get_event_engine
		event_engine = get_event_engine()

		if event_engine:
			asyncio.create_task(event_engine.put(
				FactorResearchCompletedEvent(
					task_id=task_id,
					task_type=kwargs.get('task_type', 'unknown'),
					results={},
					duration=0,
					success=False,
					error_message=str(exc)
				)
			))


@celery_app.task(base=ResearchTaskBase, bind=True, max_retries=2, default_retry_delay=120)
def calculate_factor_task (
		self,
		factor_name: str,
		stock_codes: Optional[List[str]] = None,
		start_date: Optional[str] = None,
		end_date: Optional[str] = None,
		factor_params: Optional[Dict] = None,
		**kwargs
) -> Dict[str, Any]:
	"""
	计算因子任务

	Args:
		factor_name: 因子名称
		stock_codes: 股票代码列表
		start_date: 开始日期
		end_date: 结束日期
		factor_params: 因子参数
		**kwargs: 额外参数

	Returns:
		因子计算结果
	"""
	task_id = self.request.id
	start_time = datetime.now()

	try:
		logger.info(f"开始计算因子任务: {task_id}, 因子: {factor_name}")

		# 发布任务开始事件
		from core.events.event_engine import get_event_engine
		event_engine = get_event_engine()

		if event_engine:
			asyncio.create_task(event_engine.put(
				FactorResearchStartedEvent(
					task_id=task_id,
					task_type=ResearchTaskType.FACTOR_CALCULATION.value,
					factor_name=factor_name,
					start_time=start_time
				)
			))

		# 初始化服务
		factor_calculator = FactorCalculator()
		research_service = DataResearchService()

		# 设置日期范围
		if not start_date:
			start_date = (date.today() - timedelta(days=365)).strftime('%Y-%m-%d')

		if not end_date:
			end_date = date.today().strftime('%Y-%m-%d')

		# 设置股票代码
		if not stock_codes:
			logger.info("获取所有股票代码")

			self.update_state(
				state='PROGRESS',
				meta={'current': 10, 'total': 100, 'status': '获取股票列表'}
			)

			if event_engine:
				asyncio.create_task(event_engine.put(
					FactorResearchProgressEvent(
						task_id=task_id,
						progress=10,
						message="获取股票列表",
						task_type=ResearchTaskType.FACTOR_CALCULATION.value
					)
				))

			stock_repo = StockBasicRepository()
			all_stocks = stock_repo.get_listed_stocks()
			stock_codes = [stock['ts_code'] for stock in all_stocks]

			logger.info(f"共获取 {len(stock_codes)} 只股票")

		# 设置因子参数
		if not factor_params:
			factor_params = {}

		# 分批计算因子
		batch_size = kwargs.get('batch_size', 50)
		total_batches = (len(stock_codes) + batch_size - 1) // batch_size

		logger.info(f"开始分批计算因子，共 {total_batches} 批")

		all_factor_data = []
		failed_stocks = []

		for batch_num in range(total_batches):
			try:
				start_idx = batch_num * batch_size
				end_idx = min((batch_num + 1) * batch_size, len(stock_codes))
				batch_codes = stock_codes[start_idx:end_idx]

				# 更新进度
				progress = 20 + int((batch_num / total_batches) * 70)
				self.update_state(
					state='PROGRESS',
					meta={
						'current': progress,
						'total': 100,
						'status': f'计算第 {batch_num + 1}/{total_batches} 批'
					}
				)

				if event_engine:
					asyncio.create_task(event_engine.put(
						FactorResearchProgressEvent(
							task_id=task_id,
							progress=progress,
							message=f"计算第 {batch_num + 1}/{total_batches} 批",
							task_type=ResearchTaskType.FACTOR_CALCULATION.value,
							current_batch=batch_num + 1,
							total_batches=total_batches
						)
					))

				logger.info(f"计算第 {batch_num + 1} 批，共 {len(batch_codes)} 只股票")

				# 获取数据
				session = SessionManager.get_async_session()
				quote_repo = StockDailyRepository(session)

				# 为每只股票计算因子
				for i, stock_code in enumerate(batch_codes):
					try:
						# 获取股票数据
						stock_data = quote_repo.get_stock_quotes(
							stock_code=stock_code,
							start_date=start_date,
							end_date=end_date
						)

						if stock_data and len(stock_data) > 0:
							# 转换为DataFrame
							df = pd.DataFrame(stock_data)

							# 计算因子
							factor_values = factor_calculator.calculate_factor(
								data=df,
								factor_name=factor_name,
								**factor_params
							)

							# 保存因子数据
							if isinstance(factor_values, pd.DataFrame):
								for col in factor_values.columns:
									factor_data = {
										'symbol': stock_code,
										'date': df['trade_date'].iloc[-1] if 'trade_date' in df.columns else end_date,
										'factor_name': factor_name,
										'factor_value': factor_values[col].iloc[
											-1] if not factor_values.empty else None,
										'parameters': json.dumps(factor_params),
										'calculated_at': datetime.now()
									}
									all_factor_data.append(factor_data)

							logger.debug(f"股票 {stock_code} 因子计算完成")

					except Exception as e:
						logger.error(f"股票 {stock_code} 因子计算失败: {e}")
						failed_stocks.append(stock_code)

				logger.info(f"第 {batch_num + 1} 批因子计算完成")

			except Exception as e:
				logger.error(f"第 {batch_num + 1} 批因子计算失败: {e}")
				failed_stocks.extend(batch_codes)

		# 保存因子数据
		self.update_state(
			state='PROGRESS',
			meta={'current': 95, 'total': 100, 'status': '保存因子数据'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				FactorResearchProgressEvent(
					task_id=task_id,
					progress=95,
					message="保存因子数据",
					task_type=ResearchTaskType.FACTOR_CALCULATION.value
				)
			))

		if all_factor_data:
			# 保存到数据库
			saved_count = research_service.save_factor_data(
				factor_data=all_factor_data,
				factor_name=factor_name,
				factor_params=factor_params
			)

			logger.info(f"保存 {saved_count} 条因子数据")

		# 计算任务耗时
		end_time = datetime.now()
		duration = (end_time - start_time).total_seconds()

		# 汇总结果
		result_summary = {
			'task_id': task_id,
			'factor_name': factor_name,
			'start_date': start_date,
			'end_date': end_date,
			'total_stocks': len(stock_codes),
			'successful_stocks': len(stock_codes) - len(failed_stocks),
			'failed_stocks': failed_stocks,
			'factor_data_count': len(all_factor_data),
			'factor_params': factor_params,
			'duration_seconds': round(duration, 2),
			'completed_at': end_time.isoformat()
		}

		logger.info(f"因子计算任务完成: {result_summary}")

		# 更新最终进度
		self.update_state(
			state='PROGRESS',
			meta={'current': 100, 'total': 100, 'status': '计算完成'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				FactorResearchProgressEvent(
					task_id=task_id,
					progress=100,
					message="因子计算完成",
					task_type=ResearchTaskType.FACTOR_CALCULATION.value,
					result=result_summary
				)
			))

		return result_summary

	except Exception as e:
		logger.error(f"因子计算任务失败: {e}", exc_info=True)

		if self.request.retries < self.max_retries:
			logger.info(f"准备重试任务，已重试 {self.request.retries} 次")
			raise self.retry(exc=e)
		else:
			raise


@celery_app.task(base=ResearchTaskBase, bind=True, max_retries=2, default_retry_delay=180)
def analyze_factor_performance_task (
		self,
		factor_names: List[str],
		analysis_type: str = "performance",
		start_date: Optional[str] = None,
		end_date: Optional[str] = None,
		analysis_params: Optional[Dict] = None,
		**kwargs
) -> Dict[str, Any]:
	"""
	分析因子表现任务

	Args:
		factor_names: 因子名称列表
		analysis_type: 分析类型
		start_date: 开始日期
		end_date: 结束日期
		analysis_params: 分析参数
		**kwargs: 额外参数

	Returns:
		因子分析结果
	"""
	task_id = self.request.id
	start_time = datetime.now()

	try:
		logger.info(f"开始因子表现分析任务: {task_id}, 因子: {factor_names}")

		# 发布任务开始事件
		from core.events.event_engine import get_event_engine
		event_engine = get_event_engine()

		if event_engine:
			asyncio.create_task(event_engine.put(
				FactorResearchStartedEvent(
					task_id=task_id,
					task_type=ResearchTaskType.FACTOR_ANALYSIS.value,
					factor_names=factor_names,
					start_time=start_time
				)
			))

		# 初始化服务
		research_service = DataResearchService()

		# 设置日期范围
		if not start_date:
			start_date = (date.today() - timedelta(days=365 * 3)).strftime('%Y-%m-%d')  # 3年数据

		if not end_date:
			end_date = date.today().strftime('%Y-%m-%d')

		# 设置分析参数
		if not analysis_params:
			analysis_params = {
				'group_count': 10,  # 分组数量
				'holding_period': 20,  # 持有期
				'weight_method': 'equal',  # 权重方法
				'transaction_cost': 0.001  # 交易成本
			}

		# 获取因子数据
		logger.info(f"获取因子数据进行表现分析")

		self.update_state(
			state='PROGRESS',
			meta={'current': 20, 'total': 100, 'status': '获取因子数据'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				FactorResearchProgressEvent(
					task_id=task_id,
					progress=20,
					message="获取因子数据",
					task_type=ResearchTaskType.FACTOR_ANALYSIS.value
				)
			))

		factor_data = research_service.get_factor_data(
			factor_names=factor_names,
			start_date=start_date,
			end_date=end_date
		)

		if not factor_data or len(factor_data) == 0:
			error_msg = f"未找到因子数据: {factor_names}"
			logger.warning(error_msg)

			return {
				'task_id': task_id,
				'factor_names': factor_names,
				'analysis_type': analysis_type,
				'error': error_msg,
				'completed_at': datetime.now().isoformat()
			}

		# 执行因子分析
		logger.info(f"开始执行因子表现分析")

		self.update_state(
			state='PROGRESS',
			meta={'current': 50, 'total': 100, 'status': '执行因子分析'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				FactorResearchProgressEvent(
					task_id=task_id,
					progress=50,
					message="执行因子分析",
					task_type=ResearchTaskType.FACTOR_ANALYSIS.value
				)
			))

		analysis_result = research_service.analyze_factor_performance(
			factor_data=factor_data,
			analysis_type=analysis_type,
			**analysis_params
		)

		# 生成分析报告
		self.update_state(
			state='PROGRESS',
			meta={'current': 80, 'total': 100, 'status': '生成分析报告'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				FactorResearchProgressEvent(
					task_id=task_id,
					progress=80,
					message="生成分析报告",
					task_type=ResearchTaskType.FACTOR_ANALYSIS.value
				)
			))

		report = research_service.generate_factor_analysis_report(
			analysis_result=analysis_result,
			factor_names=factor_names,
			start_date=start_date,
			end_date=end_date,
			analysis_params=analysis_params
		)

		# 保存分析结果
		result_id = research_service.save_factor_analysis_result(
			factor_names=factor_names,
			analysis_type=analysis_type,
			analysis_result=analysis_result,
			report=report,
			task_id=task_id
		)

		# 计算任务耗时
		end_time = datetime.now()
		duration = (end_time - start_time).total_seconds()

		# 汇总结果
		result_summary = {
			'task_id': task_id,
			'factor_names': factor_names,
			'analysis_type': analysis_type,
			'start_date': start_date,
			'end_date': end_date,
			'factor_count': len(factor_names),
			'data_points': len(factor_data),
			'analysis_result_id': result_id,
			'analysis_params': analysis_params,
			'duration_seconds': round(duration, 2),
			'completed_at': end_time.isoformat()
		}

		logger.info(f"因子表现分析任务完成: {result_summary}")

		# 发布分析完成事件
		if event_engine:
			asyncio.create_task(event_engine.put(
				FactorAnalysisCompletedEvent(
					task_id=task_id,
					factor_names=factor_names,
					analysis_type=analysis_type,
					analysis_result=analysis_result,
					report_summary=report.get('summary', {}),
					duration_seconds=duration
				)
			))

		# 更新最终进度
		self.update_state(
			state='PROGRESS',
			meta={'current': 100, 'total': 100, 'status': '分析完成'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				FactorResearchProgressEvent(
					task_id=task_id,
					progress=100,
					message="因子分析完成",
					task_type=ResearchTaskType.FACTOR_ANALYSIS.value,
					result=result_summary
				)
			))

		return result_summary

	except Exception as e:
		logger.error(f"因子表现分析任务失败: {e}", exc_info=True)

		if self.request.retries < self.max_retries:
			logger.info(f"准备重试任务，已重试 {self.request.retries} 次")
			raise self.retry(exc=e)
		else:
			raise


@celery_app.task(base=ResearchTaskBase, bind=True, max_retries=2, default_retry_delay=300)
def optimize_factor_parameters_task (
		self,
		factor_name: str,
		optimization_method: str = "genetic",
		parameter_ranges: Optional[Dict] = None,
		objective_function: str = "sharpe_ratio",
		optimization_params: Optional[Dict] = None,
		**kwargs
) -> Dict[str, Any]:
	"""
	优化因子参数任务

	Args:
		factor_name: 因子名称
		optimization_method: 优化方法
		parameter_ranges: 参数范围
		objective_function: 目标函数
		optimization_params: 优化参数
		**kwargs: 额外参数

	Returns:
		参数优化结果
	"""
	task_id = self.request.id
	start_time = datetime.now()

	try:
		logger.info(f"开始因子参数优化任务: {task_id}, 因子: {factor_name}")

		# 发布任务开始事件
		from core.events.event_engine import get_event_engine
		event_engine = get_event_engine()

		if event_engine:
			asyncio.create_task(event_engine.put(
				FactorResearchStartedEvent(
					task_id=task_id,
					task_type=ResearchTaskType.FACTOR_OPTIMIZATION.value,
					factor_name=factor_name,
					start_time=start_time
				)
			))

		# 初始化服务
		research_service = DataResearchService()

		# 设置参数范围
		if not parameter_ranges:
			# 默认参数范围
			if factor_name == "rsi":
				parameter_ranges = {
					'period': {'min': 5, 'max': 30, 'step': 1}
				}
			elif factor_name == "ma":
				parameter_ranges = {
					'period': {'min': 5, 'max': 60, 'step': 5}
				}
			elif factor_name == "macd":
				parameter_ranges = {
					'fast_period': {'min': 8, 'max': 20, 'step': 1},
					'slow_period': {'min': 20, 'max': 40, 'step': 1},
					'signal_period': {'min': 5, 'max': 15, 'step': 1}
				}
			else:
				parameter_ranges = {}

		# 设置优化参数
		if not optimization_params:
			optimization_params = {
				'population_size': 50,
				'generations': 100,
				'crossover_rate': 0.8,
				'mutation_rate': 0.1,
				'random_state': 42
			}

		# 获取测试数据
		logger.info(f"获取测试数据进行参数优化")

		self.update_state(
			state='PROGRESS',
			meta={'current': 20, 'total': 100, 'status': '获取测试数据'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				FactorResearchProgressEvent(
					task_id=task_id,
					progress=20,
					message="获取测试数据",
					task_type=ResearchTaskType.FACTOR_OPTIMIZATION.value
				)
			))

		# 获取股票数据用于优化
		stock_repo = StockBasicRepository()
		session = SessionManager.get_async_session()
		quote_repo = StockDailyRepository(session)

		# 使用部分股票进行优化
		all_stocks = stock_repo.get_listed_stocks()
		sample_stocks = all_stocks[:50]  # 使用前50只股票进行优化

		test_data = []
		for stock in sample_stocks:
			stock_code = stock['ts_code']
			quotes = quote_repo.get_stock_quotes(
				stock_code=stock_code,
				start_date='20200101',
				end_date='20221231'
			)

			if quotes and len(quotes) > 100:  # 至少100个交易日
				test_data.append({
					'symbol': stock_code,
					'data': quotes
				})

		if not test_data:
			error_msg = "未找到足够的测试数据"
			logger.warning(error_msg)

			return {
				'task_id': task_id,
				'factor_name': factor_name,
				'error': error_msg,
				'completed_at': datetime.now().isoformat()
			}

		# 执行参数优化
		logger.info(f"开始执行参数优化")

		self.update_state(
			state='PROGRESS',
			meta={'current': 40, 'total': 100, 'status': '执行参数优化'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				FactorResearchProgressEvent(
					task_id=task_id,
					progress=40,
					message="执行参数优化",
					task_type=ResearchTaskType.FACTOR_OPTIMIZATION.value
				)
			))

		optimization_result = research_service.optimize_factor_parameters(
			factor_name=factor_name,
			test_data=test_data,
			optimization_method=optimization_method,
			parameter_ranges=parameter_ranges,
			objective_function=objective_function,
			optimization_params=optimization_params,
			progress_callback=lambda p, m: self._update_optimization_progress(p, m, task_id, event_engine)
		)

		# 验证优化结果
		self.update_state(
			state='PROGRESS',
			meta={'current': 90, 'total': 100, 'status': '验证优化结果'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				FactorResearchProgressEvent(
					task_id=task_id,
					progress=90,
					message="验证优化结果",
					task_type=ResearchTaskType.FACTOR_OPTIMIZATION.value
				)
			))

		validation_result = research_service.validate_optimization_result(
			optimization_result=optimization_result,
			factor_name=factor_name,
			test_data=test_data
		)

		# 保存优化结果
		result_id = research_service.save_optimization_result(
			factor_name=factor_name,
			optimization_method=optimization_method,
			parameter_ranges=parameter_ranges,
			optimization_result=optimization_result,
			validation_result=validation_result,
			task_id=task_id
		)

		# 计算任务耗时
		end_time = datetime.now()
		duration = (end_time - start_time).total_seconds()

		# 汇总结果
		result_summary = {
			'task_id': task_id,
			'factor_name': factor_name,
			'optimization_method': optimization_method,
			'objective_function': objective_function,
			'optimal_parameters': optimization_result.get('optimal_parameters', {}),
			'objective_value': optimization_result.get('objective_value'),
			'iterations': optimization_result.get('iterations', 0),
			'validation_score': validation_result.get('validation_score', 0),
			'optimization_result_id': result_id,
			'parameter_ranges': parameter_ranges,
			'optimization_params': optimization_params,
			'duration_seconds': round(duration, 2),
			'completed_at': end_time.isoformat()
		}

		logger.info(f"因子参数优化任务完成: {result_summary}")

		# 更新最终进度
		self.update_state(
			state='PROGRESS',
			meta={'current': 100, 'total': 100, 'status': '优化完成'}
		)

		if event_engine:
			asyncio.create_task(event_engine.put(
				FactorResearchProgressEvent(
					task_id=task_id,
					progress=100,
					message="参数优化完成",
					task_type=ResearchTaskType.FACTOR_OPTIMIZATION.value,
					result=result_summary
				)
			))

		return result_summary

	except Exception as e:
		logger.error(f"因子参数优化任务失败: {e}", exc_info=True)

		if self.request.retries < self.max_retries:
			logger.info(f"准备重试任务，已重试 {self.request.retries} 次")
			raise self.retry(exc=e)
		else:
			raise

	def _update_optimization_progress (self, progress: int, message: str, task_id: str, event_engine):
		"""更新优化进度"""
		try:
			# 计算总体进度（40% + 进度百分比 * 50%）
			overall_progress = 40 + int(progress * 0.5)

			self.update_state(
				state='PROGRESS',
				meta={
					'current': overall_progress,
					'total': 100,
					'status': message
				}
			)

			if event_engine:
				asyncio.create_task(event_engine.put(
					FactorResearchProgressEvent(
						task_id=task_id,
						progress=overall_progress,
						message=message,
						task_type=ResearchTaskType.FACTOR_OPTIMIZATION.value
					)
				))

		except Exception as e:
			logger.error(f"更新优化进度失败: {e}")


def schedule_weekly_research ():
	"""
	安排每周研究任务

	每周执行以下研究任务：
	1. 计算常用因子
	2. 分析因子表现
	3. 生成研究报告
	"""
	from celery import current_app

	logger.info("安排每周研究任务")

	# 计算下一个周一
	today = date.today()
	days_ahead = 0 - today.weekday()  # 0 = Monday
	if days_ahead <= 0:  # 如果今天是周一或之后
		days_ahead += 7

	next_monday = today + timedelta(days=days_ahead)

	# 安排周一凌晨的研究任务
	schedule_time = datetime.combine(next_monday, datetime.min.time()).replace(hour=2, minute=0)

	# 常用因子列表
	common_factors = [
		'rsi',
		'macd',
		'ma',
		'momentum',
		'volatility'
	]

	# 安排因子计算任务
	for factor_name in common_factors:
		current_app.send_task(
			'modules.data.tasks.research_tasks.calculate_factor_task',
			kwargs={
				'factor_name': factor_name,
				'start_date': (date.today() - timedelta(days=365)).strftime('%Y-%m-%d'),
				'end_date': date.today().strftime('%Y-%m-%d')
			},
			eta=schedule_time
		)

	# 安排因子分析任务（在所有因子计算完成后）
	schedule_time_analysis = schedule_time + timedelta(hours=2)

	current_app.send_task(
		'modules.data.tasks.research_tasks.analyze_factor_performance_task',
		kwargs={
			'factor_names': common_factors,
			'analysis_type': 'performance',
			'start_date': (date.today() - timedelta(days=365 * 3)).strftime('%Y-%m-%d'),
			'end_date': date.today().strftime('%Y-%m-%d')
		},
		eta=schedule_time_analysis
	)

	logger.info(f"每周研究任务已安排: {schedule_time}")

	return True


# 配置Celery定时任务
celery_app.conf.beat_schedule = {
	'weekly-factor-calculation': {
		'task': 'modules.data.tasks.research_tasks.calculate_factor_task',
		'schedule': crontab(hour=2, minute=0, day_of_week='monday'),  # 每周一凌晨2点
		'args': (),
		'kwargs': {
			'factor_name': 'rsi',
			'start_date': (date.today() - timedelta(days=365)).strftime('%Y-%m-%d'),
			'factor_params': {'period': 14}
		},
	},
	'monthly-factor-analysis': {
		'task': 'modules.data.tasks.research_tasks.analyze_factor_performance_task',
		'schedule': crontab(hour=3, minute=0, day_of_month='1'),  # 每月1号凌晨3点
		'args': (),
		'kwargs': {
			'factor_names': ['rsi', 'macd', 'ma', 'momentum'],
			'analysis_type': 'performance',
			'start_date': (date.today() - timedelta(days=365 * 3)).strftime('%Y-%m-%d')
		},
	},
	'quarterly-parameter-optimization': {
		'task': 'modules.data.tasks.research_tasks.optimize_factor_parameters_task',
		'schedule': crontab(hour=4, minute=0, day_of_month='1', month_of_year='1,4,7,10'),  # 每季度第一天凌晨4点
		'args': (),
		'kwargs': {
			'factor_name': 'rsi',
			'optimization_method': 'genetic',
			'parameter_ranges': {
				'period': {'min': 5, 'max': 30, 'step': 1}
			}
		},
	},
}


# 异步任务函数
async def async_calculate_factor (
		factor_name: str,
		stock_data: pd.DataFrame,
		factor_params: Dict
) -> pd.DataFrame:
	"""
	异步计算因子

	Args:
		factor_name: 因子名称
		stock_data: 股票数据
		factor_params: 因子参数

	Returns:
		因子值DataFrame
	"""
	try:
		logger.info(f"异步计算因子: {factor_name}")

		factor_calculator = FactorCalculator()

		# 在线程池中执行计算
		loop = asyncio.get_event_loop()
		factor_values = await loop.run_in_executor(
			None,
			factor_calculator.calculate_factor,
			stock_data,
			factor_name,
			**factor_params
		)

		return factor_values

	except Exception as e:
		logger.error(f"异步计算因子失败: {e}")
		raise


async def async_analyze_factors (
		factor_data: List[Dict],
		analysis_type: str,
		analysis_params: Dict
) -> Dict[str, Any]:
	"""
	异步分析因子

	Args:
		factor_data: 因子数据
		analysis_type: 分析类型
		analysis_params: 分析参数

	Returns:
		分析结果
	"""
	try:
		logger.info(f"异步分析因子")

		research_service = DataResearchService()

		# 在线程池中执行分析
		loop = asyncio.get_event_loop()
		analysis_result = await loop.run_in_executor(
			None,
			research_service.analyze_factor_performance,
			factor_data,
			analysis_type,
			**analysis_params
		)

		return analysis_result

	except Exception as e:
		logger.error(f"异步分析因子失败: {e}")
		raise


async def async_optimize_parameters (
		factor_name: str,
		test_data: List[Dict],
		optimization_method: str,
		parameter_ranges: Dict,
		objective_function: str
) -> Dict[str, Any]:
	"""
	异步优化参数

	Args:
		factor_name: 因子名称
		test_data: 测试数据
		optimization_method: 优化方法
		parameter_ranges: 参数范围
		objective_function: 目标函数

	Returns:
		优化结果
	"""
	try:
		logger.info(f"异步优化参数: {factor_name}")

		research_service = DataResearchService()

		# 在进程池中执行优化（计算密集型）
		loop = asyncio.get_event_loop()
		optimization_result = await loop.run_in_executor(
			ProcessPoolExecutor(),
			research_service.optimize_factor_parameters,
			factor_name,
			test_data,
			optimization_method,
			parameter_ranges,
			objective_function,
			{}
		)

		return optimization_result

	except Exception as e:
		logger.error(f"异步优化参数失败: {e}")
		raise


async def generate_research_report (
		start_date: str,
		end_date: str,
		factor_names: List[str],
		report_type: str = "comprehensive"
) -> Dict[str, Any]:
	"""
	生成研究报告

	Args:
		start_date: 开始日期
		end_date: 结束日期
		factor_names: 因子名称列表
		report_type: 报告类型

	Returns:
		研究报告
	"""
	try:
		logger.info(f"生成研究报告: {factor_names}")

		research_service = DataResearchService()

		# 在线程池中生成报告
		loop = asyncio.get_event_loop()
		report = await loop.run_in_executor(
			None,
			research_service.generate_factor_research_report,
			factor_names,
			start_date,
			end_date,
			report_type
		)

		return report

	except Exception as e:
		logger.error(f"生成研究报告失败: {e}")
		raise