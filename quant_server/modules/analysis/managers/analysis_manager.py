#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析管理器

负责协调多个分析服务，管理分析任务的调度和执行。
"""

import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.engines.system.event_engine import EventEngine
from modules.analysis.events.task_events import (
	AnalysisCompletedEvent,
	AnalysisFailedEvent,
	AnalysisProgressEvent,
	AnalysisStartedEvent,
)
from modules.analysis.models import (
	AnalysisReport,
	AttributionAnalysis,
	PerformanceMetrics,
	TradeAnalysis,
)
from modules.analysis.services.attribution_service import AttributionService
from modules.analysis.services.comparison_service import ComparisonService
from modules.analysis.services.performance_service import PerformanceService
from modules.analysis.services.trade_analysis_service import TradeAnalysisService
from shared.database.repositories import (
	AccountRepository,
	BacktestTaskRepository,
	StrategyRepository,
	TradeRepository,
)


class AnalysisManager:
	"""分析管理器"""

	def __init__ (
			self,
			session: AsyncSession,
			event_engine: Optional[EventEngine] = None
	):
		"""
		初始化分析管理器

		Args:
			session: 数据库会话
			event_engine: 事件引擎
		"""
		self.session = session
		self.event_engine = event_engine

		# 初始化Repository
		self.strategy_repo = StrategyRepository(session)
		self.account_repo = AccountRepository(session)
		self.backtest_repo = BacktestTaskRepository(session)
		self.trade_repo = TradeRepository(session)

		# 初始化服务
		self.performance_service = PerformanceService(
			session=session,
			strategy_repo=self.strategy_repo,
			account_repo=self.account_repo,
			backtest_repo=self.backtest_repo,
			trade_repo=self.trade_repo
		)

		self.attribution_service = AttributionService(
			session=session,
			strategy_repo=self.strategy_repo,
			account_repo=self.account_repo
		)

		self.comparison_service = ComparisonService(
			session=session,
			strategy_repo=self.strategy_repo,
			account_repo=self.account_repo,
			performance_service=self.performance_service
		)

		self.trade_analysis_service = TradeAnalysisService(
			session=session,
			trade_repo=self.trade_repo
		)

		# 分析任务队列
		self.analysis_queue = asyncio.Queue()
		self.running_tasks: Dict[str, asyncio.Task] = {}

	async def start_analysis (
			self,
			analysis_type: str,
			parameters: Dict[str, Any],
			user_id: str
	) -> str:
		"""
		启动分析任务

		Args:
			analysis_type: 分析类型 ('performance', 'attribution', 'comparison', 'trade_analysis', 'comprehensive')
			parameters: 分析参数
			user_id: 用户ID

		Returns:
			分析任务ID
		"""
		try:
			# 生成任务ID
			task_id = f"analysis_{analysis_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

			# 发布分析开始事件
			if self.event_engine:
				await self.event_engine.put(
					AnalysisStartedEvent(
						task_id=task_id,
						analysis_type=analysis_type,
						user_id=user_id,
						parameters=parameters
					)
				)

			# 启动异步任务
			task = asyncio.create_task(
				self._execute_analysis(task_id, analysis_type, parameters, user_id)
			)

			# 保存任务引用
			self.running_tasks[task_id] = task

			# 设置任务完成回调
			task.add_done_callback(
				lambda t: self._on_analysis_complete(task_id)
			)

			return task_id

		except Exception as e:
			raise ValueError(f"启动分析任务失败: {str(e)}")

	async def _execute_analysis (
			self,
			task_id: str,
			analysis_type: str,
			parameters: Dict[str, Any],
			user_id: str
	) -> Dict[str, Any]:
		"""
		执行分析任务

		Args:
			task_id: 任务ID
			analysis_type: 分析类型
			parameters: 分析参数
			user_id: 用户ID

		Returns:
			分析结果
		"""
		try:
			# 更新进度
			await self._update_progress(task_id, 10, "开始分析...")

			if analysis_type == 'performance':
				result = await self._execute_performance_analysis(
					task_id, parameters, user_id
				)

			elif analysis_type == 'attribution':
				result = await self._execute_attribution_analysis(
					task_id, parameters, user_id
				)

			elif analysis_type == 'comparison':
				result = await self._execute_comparison_analysis(
					task_id, parameters, user_id
				)

			elif analysis_type == 'trade_analysis':
				result = await self._execute_trade_analysis(
					task_id, parameters, user_id
				)

			elif analysis_type == 'comprehensive':
				result = await self._execute_comprehensive_analysis(
					task_id, parameters, user_id
				)

			else:
				raise ValueError(f"不支持的分析类型: {analysis_type}")

			# 更新进度
			await self._update_progress(task_id, 100, "分析完成")

			# 发布分析完成事件
			if self.event_engine:
				await self.event_engine.put(
					AnalysisCompletedEvent(
						task_id=task_id,
						analysis_type=analysis_type,
						user_id=user_id,
						result=result
					)
				)

			return result

		except Exception as e:
			# 发布分析失败事件
			if self.event_engine:
				await self.event_engine.put(
					AnalysisFailedEvent(
						task_id=task_id,
						analysis_type=analysis_type,
						user_id=user_id,
						error_message=str(e)
					)
				)

			raise

	async def _execute_performance_analysis (
			self,
			task_id: str,
			parameters: Dict[str, Any],
			user_id: str
	) -> Dict[str, Any]:
		"""
		执行绩效分析

		Args:
			task_id: 任务ID
			parameters: 分析参数
			user_id: 用户ID

		Returns:
			绩效分析结果
		"""
		# 提取参数
		entity_type = parameters.get('entity_type', 'strategy')
		entity_id = parameters.get('entity_id')
		start_date = parameters.get('start_date')
		end_date = parameters.get('end_date', date.today())
		benchmark = parameters.get('benchmark')

		if not entity_id:
			raise ValueError("缺少实体ID参数")

		if not start_date:
			# 默认分析最近一年
			start_date = end_date - timedelta(days=365)

		# 更新进度
		await self._update_progress(task_id, 30, "计算绩效指标...")

		# 执行分析
		if entity_type == 'strategy':
			metrics = await self.performance_service.calculate_strategy_performance(
				strategy_id=entity_id,
				start_date=start_date,
				end_date=end_date,
				benchmark=benchmark
			)
		elif entity_type == 'account':
			metrics = await self.performance_service.calculate_account_performance(
				account_id=entity_id,
				start_date=start_date,
				end_date=end_date
			)
		else:
			raise ValueError(f"不支持的实体类型: {entity_type}")

		# 更新进度
		await self._update_progress(task_id, 80, "生成分析报告...")

		# 构建分析报告
		report = AnalysisReport(
			report_id=task_id,
			user_id=user_id,
			report_type='performance',
			title=f"{entity_type.capitalize()}绩效分析: {entity_id}",
			description=f"{start_date} 至 {end_date} 的绩效分析报告",
			parameters=parameters,
			performance_metrics=metrics,
			status='completed',
			progress=100.0,
			completed_at=datetime.now()
		)

		return report.to_dict()

	async def _execute_attribution_analysis (
			self,
			task_id: str,
			parameters: Dict[str, Any],
			user_id: str
	) -> Dict[str, Any]:
		"""
		执行归因分析

		Args:
			task_id: 任务ID
			parameters: 分析参数
			user_id: 用户ID

		Returns:
			归因分析结果
		"""
		# 提取参数
		portfolio_id = parameters.get('portfolio_id')
		start_date = parameters.get('start_date')
		end_date = parameters.get('end_date', date.today())
		benchmark = parameters.get('benchmark')
		attribution_model = parameters.get('model', 'brinson')

		if not portfolio_id:
			raise ValueError("缺少组合ID参数")

		if not start_date:
			# 默认分析最近一年
			start_date = end_date - timedelta(days=365)

		if attribution_model == 'brinson' and not benchmark:
			raise ValueError("Brinson归因需要基准参数")

		# 更新进度
		await self._update_progress(task_id, 30, "执行归因分析...")

		# 执行分析
		if attribution_model == 'brinson':
			attribution = await self.attribution_service.perform_brinson_attribution(
				portfolio_id=portfolio_id,
				start_date=start_date,
				end_date=end_date,
				benchmark=benchmark
			)
		elif attribution_model == 'factor':
			attribution = await self.attribution_service.perform_factor_attribution(
				portfolio_id=portfolio_id,
				start_date=start_date,
				end_date=end_date,
				factor_model=parameters.get('factor_model', 'Fama-French')
			)
		else:
			# 比较多个模型
			attributions = await self.attribution_service.compare_attribution_models(
				portfolio_id=portfolio_id,
				start_date=start_date,
				end_date=end_date,
				benchmark=benchmark
			)

			attribution = list(attributions.values())[0] if attributions else None

		# 更新进度
		await self._update_progress(task_id, 80, "生成分析报告...")

		# 构建分析报告
		report = AnalysisReport(
			report_id=task_id,
			user_id=user_id,
			report_type='attribution',
			title=f"归因分析: {portfolio_id}",
			description=f"{start_date} 至 {end_date} 的归因分析报告",
			parameters=parameters,
			attribution_analysis=attribution,
			status='completed',
			progress=100.0,
			completed_at=datetime.now()
		)

		return report.to_dict()

	async def _execute_comparison_analysis (
			self,
			task_id: str,
			parameters: Dict[str, Any],
			user_id: str
	) -> Dict[str, Any]:
		"""
		执行对比分析

		Args:
			task_id: 任务ID
			parameters: 分析参数
			user_id: 用户ID

		Returns:
			对比分析结果
		"""
		# 提取参数
		strategy_ids = parameters.get('strategy_ids', [])
		category = parameters.get('category')
		start_date = parameters.get('start_date')
		end_date = parameters.get('end_date', date.today())
		benchmark = parameters.get('benchmark')
		top_n = parameters.get('top_n', 10)

		if not strategy_ids and not category:
			raise ValueError("需要指定策略ID列表或策略类别")

		if not start_date:
			# 默认分析最近一年
			start_date = end_date - timedelta(days=365)

		# 更新进度
		await self._update_progress(task_id, 30, "执行策略对比...")

		# 执行分析
		if strategy_ids:
			comparison = await self.comparison_service.compare_strategies(
				strategy_ids=strategy_ids,
				start_date=start_date,
				end_date=end_date,
				benchmark=benchmark
			)
		else:
			comparison = await self.comparison_service.compare_strategies_by_category(
				category=category,
				start_date=start_date,
				end_date=end_date,
				top_n=top_n,
				benchmark=benchmark
			)

		# 更新进度
		await self._update_progress(task_id, 80, "生成分析报告...")

		# 构建分析报告
		report = AnalysisReport(
			report_id=task_id,
			user_id=user_id,
			report_type='comparison',
			title=f"策略对比分析",
			description=f"{start_date} 至 {end_date} 的策略对比报告",
			parameters=parameters,
			comparison_analysis=comparison,
			status='completed',
			progress=100.0,
			completed_at=datetime.now()
		)

		return report.to_dict()

	async def _execute_trade_analysis (
			self,
			task_id: str,
			parameters: Dict[str, Any],
			user_id: str
	) -> Dict[str, Any]:
		"""
		执行交易分析

		Args:
			task_id: 任务ID
			parameters: 分析参数
			user_id: 用户ID

		Returns:
			交易分析结果
		"""
		# 提取参数
		strategy_id = parameters.get('strategy_id')
		account_id = parameters.get('account_id')
		start_date = parameters.get('start_date')
		end_date = parameters.get('end_date', date.today())

		if not strategy_id and not account_id:
			raise ValueError("需要指定策略ID或账户ID")

		if not start_date:
			# 默认分析最近一个月
			start_date = end_date - timedelta(days=30)

		# 更新进度
		await self._update_progress(task_id, 30, "分析交易记录...")

		# 执行分析
		analysis = await self.trade_analysis_service.analyze_trades(
			strategy_id=strategy_id,
			account_id=account_id,
			start_date=start_date,
			end_date=end_date
		)

		# 更新进度
		await self._update_progress(task_id, 80, "生成分析报告...")

		# 构建分析报告
		report = AnalysisReport(
			report_id=task_id,
			user_id=user_id,
			report_type='trade_analysis',
			title=f"交易分析",
			description=f"{start_date} 至 {end_date} 的交易分析报告",
			parameters=parameters,
			trade_analysis=analysis,
			status='completed',
			progress=100.0,
			completed_at=datetime.now()
		)

		return report.to_dict()

	async def _execute_comprehensive_analysis (
			self,
			task_id: str,
			parameters: Dict[str, Any],
			user_id: str
	) -> Dict[str, Any]:
		"""
		执行综合分析

		Args:
			task_id: 任务ID
			parameters: 分析参数
			user_id: 用户ID

		Returns:
			综合分析结果
		"""
		# 提取参数
		entity_id = parameters.get('entity_id')
		entity_type = parameters.get('entity_type', 'strategy')
		start_date = parameters.get('start_date')
		end_date = parameters.get('end_date', date.today())
		benchmark = parameters.get('benchmark')

		if not entity_id:
			raise ValueError("缺少实体ID参数")

		if not start_date:
			# 默认分析最近一年
			start_date = end_date - timedelta(days=365)

		# 并行执行多种分析
		tasks = []

		# 绩效分析
		if entity_type == 'strategy':
			tasks.append(
				self.performance_service.calculate_strategy_performance(
					strategy_id=entity_id,
					start_date=start_date,
					end_date=end_date,
					benchmark=benchmark
				)
			)
		else:
			tasks.append(
				self.performance_service.calculate_account_performance(
					account_id=entity_id,
					start_date=start_date,
					end_date=end_date
				)
			)

		# 归因分析（如果有基准）
		if benchmark:
			tasks.append(
				self.attribution_service.perform_brinson_attribution(
					portfolio_id=entity_id,
					start_date=start_date,
					end_date=end_date,
					benchmark=benchmark
				)
			)

		# 交易分析
		if entity_type == 'strategy':
			tasks.append(
				self.trade_analysis_service.analyze_trades(
					strategy_id=entity_id,
					account_id=parameters.get('account_id', 'default'),
					start_date=start_date,
					end_date=end_date
				)
			)

		# 更新进度
		await self._update_progress(task_id, 50, "并行执行多项分析...")

		# 等待所有任务完成
		results = await asyncio.gather(*tasks, return_exceptions=True)

		# 提取结果
		performance_metrics = None
		attribution_analysis = None
		trade_analysis = None

		for result in results:
			if isinstance(result, Exception):
				continue

			if isinstance(result, PerformanceMetrics):
				performance_metrics = result
			elif isinstance(result, AttributionAnalysis):
				attribution_analysis = result
			elif isinstance(result, TradeAnalysis):
				trade_analysis = result

		# 更新进度
		await self._update_progress(task_id, 90, "整合分析结果...")

		# 构建综合分析报告
		report = AnalysisReport(
			report_id=task_id,
			user_id=user_id,
			report_type='comprehensive',
			title=f"综合分析: {entity_id}",
			description=f"{start_date} 至 {end_date} 的全面分析报告",
			parameters=parameters,
			performance_metrics=performance_metrics,
			attribution_analysis=attribution_analysis,
			trade_analysis=trade_analysis,
			status='completed',
			progress=100.0,
			completed_at=datetime.now()
		)

		return report.to_dict()

	async def _update_progress (
			self,
			task_id: str,
			progress: float,
			message: str
	):
		"""
		更新分析进度

		Args:
			task_id: 任务ID
			progress: 进度百分比
			message: 进度消息
		"""
		if self.event_engine:
			await self.event_engine.put(
				AnalysisProgressEvent(
					task_id=task_id,
					progress=progress,
					message=message
				)
			)

	def _on_analysis_complete (self, task_id: str):
		"""
		分析任务完成回调

		Args:
			task_id: 任务ID
		"""
		# 从运行任务中移除
		if task_id in self.running_tasks:
			del self.running_tasks[task_id]

	async def get_analysis_status (self, task_id: str) -> Dict[str, Any]:
		"""
		获取分析任务状态

		Args:
			task_id: 任务ID

		Returns:
			任务状态
		"""
		if task_id in self.running_tasks:
			task = self.running_tasks[task_id]

			return {
				'task_id': task_id,
				'status': 'running',
				'done': task.done(),
				'cancelled': task.cancelled()
			}
		else:
			return {
				'task_id': task_id,
				'status': 'completed_or_not_found'
			}

	async def cancel_analysis (self, task_id: str) -> bool:
		"""
		取消分析任务

		Args:
			task_id: 任务ID

		Returns:
			是否取消成功
		"""
		if task_id in self.running_tasks:
			task = self.running_tasks[task_id]

			if not task.done():
				task.cancel()

				try:
					await task
				except asyncio.CancelledError:
					pass

				# 从运行任务中移除
				del self.running_tasks[task_id]

				return True

		return False

	@staticmethod
	async def get_available_analysis_types () -> List[Dict[str, Any]]:
		"""
		获取可用的分析类型

		Returns:
			分析类型列表
		"""
		return [
			{
				'type': 'performance',
				'name': '绩效分析',
				'description': '分析策略或账户的绩效指标',
				'parameters': [
					{'name': 'entity_type', 'type': 'str', 'required': True, 'options': ['strategy', 'account']},
					{'name': 'entity_id', 'type': 'str', 'required': True},
					{'name': 'start_date', 'type': 'date', 'required': False},
					{'name': 'end_date', 'type': 'date', 'required': False},
					{'name': 'benchmark', 'type': 'str', 'required': False}
				]
			},
			{
				'type': 'attribution',
				'name': '归因分析',
				'description': '分析收益的来源和贡献',
				'parameters': [
					{'name': 'portfolio_id', 'type': 'str', 'required': True},
					{'name': 'start_date', 'type': 'date', 'required': False},
					{'name': 'end_date', 'type': 'date', 'required': False},
					{'name': 'benchmark', 'type': 'str', 'required': True},
					{'name': 'model', 'type': 'str', 'required': False, 'options': ['brinson', 'factor']}
				]
			},
			{
				'type': 'comparison',
				'name': '对比分析',
				'description': '比较多个策略的绩效',
				'parameters': [
					{'name': 'strategy_ids', 'type': 'list', 'required': False},
					{'name': 'category', 'type': 'str', 'required': False,
					 'options': ['technical', 'alpha', 'ai', 'all']},
					{'name': 'start_date', 'type': 'date', 'required': False},
					{'name': 'end_date', 'type': 'date', 'required': False},
					{'name': 'benchmark', 'type': 'str', 'required': False},
					{'name': 'top_n', 'type': 'int', 'required': False}
				]
			},
			{
				'type': 'trade_analysis',
				'name': '交易分析',
				'description': '分析交易行为和质量',
				'parameters': [
					{'name': 'strategy_id', 'type': 'str', 'required': False},
					{'name': 'account_id', 'type': 'str', 'required': False},
					{'name': 'start_date', 'type': 'date', 'required': False},
					{'name': 'end_date', 'type': 'date', 'required': False}
				]
			},
			{
				'type': 'comprehensive',
				'name': '综合分析',
				'description': '执行全面的分析，包含多种分析类型',
				'parameters': [
					{'name': 'entity_id', 'type': 'str', 'required': True},
					{'name': 'entity_type', 'type': 'str', 'required': False, 'options': ['strategy', 'account']},
					{'name': 'start_date', 'type': 'date', 'required': False},
					{'name': 'end_date', 'type': 'date', 'required': False},
					{'name': 'benchmark', 'type': 'str', 'required': False}
				]
			}
		]
