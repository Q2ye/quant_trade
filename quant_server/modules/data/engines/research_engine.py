"""
因子研究引擎 - 负责因子研究、计算和验证的引擎实现

核心职责：
1. 因子计算和生成
2. 因子性能评估
3. 因子组合优化
4. 因子数据管理

设计原则：
- 继承EngineBase，遵循事件驱动架构
- 通过事件引擎与其他模块通信
- 调用Service层执行业务逻辑
- 管理研究任务的状态和生命周期
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from enum import Enum
import uuid
import pandas as pd
import numpy as np

from core.engines.base.engine_base import EngineBase
from core.engines.base.engine_status import EngineStatus
from shared.database.session import get_db_session
from shared.cache.cache_manager import CacheManager
from modules.data.services.research_service import DataResearchService
from modules.data.events.research_events import (
	FactorResearchStartedEvent,
	FactorResearchCompletedEvent,
	FactorResearchErrorEvent,
	FactorCalculatedEvent,
	FactorValidationEvent
)

logger = logging.getLogger(__name__)


class ResearchTaskType(str, Enum):
	"""研究任务类型枚举"""
	FACTOR_CALCULATION = "factor_calculation"  # 因子计算
	FACTOR_ANALYSIS = "factor_analysis"  # 因子分析
	FACTOR_OPTIMIZATION = "factor_optimization"  # 因子优化
	FACTOR_BACKTEST = "factor_backtest"  # 因子回测
	FACTOR_SELECTION = "factor_selection"  # 因子选择


class FactorResearchEngine(EngineBase):
	"""
	因子研究引擎

	负责管理因子研究的完整生命周期，包括：
	1. 因子定义和计算
	2. 因子性能评估
	3. 因子组合优化
	4. 因子数据存储和查询
	"""

	def __init__ (
			self,
			engine_name: str = "factor_research_engine",
			event_engine=None,
			main_engine=None,
			research_service: Optional[DataResearchService] = None,
			cache_manager: Optional[CacheManager] = None,
			**kwargs
	):
		"""
		初始化因子研究引擎

		Args:
			engine_name: 引擎名称
			event_engine: 事件引擎实例
			main_engine: 主引擎实例
			research_service: 因子研究服务
			cache_manager: 缓存管理器
			**kwargs: 其他参数
		"""
		super().__init__(engine_name, event_engine, main_engine, **kwargs)

		# 服务层依赖
		self.research_service = research_service
		self.cache_manager = cache_manager

		# 引擎状态
		self.active_tasks: Dict[str, Dict] = {}  # 活跃任务 {task_id: task_info}
		self.task_history: List[Dict] = []  # 任务历史记录
		self.max_history_size = 100  # 最大历史记录数

		# 因子计算缓存
		self.factor_cache: Dict[str, Dict] = {}  # 因子数据缓存
		self.cache_ttl = 3600  # 缓存过期时间(秒)

		# 注册事件处理
		if self.event_engine:
			self.register_events()

	def register_events (self) -> None:
		"""注册事件监听"""
		if self.event_engine:
			# 监听外部请求事件
			self.event_engine.register(
				"FACTOR_RESEARCH_REQUEST",
				self.handle_research_request
			)
			self.event_engine.register(
				"FACTOR_CALCULATION_REQUEST",
				self.handle_factor_calculation
			)
			self.event_engine.register(
				"FACTOR_ANALYSIS_REQUEST",
				self.handle_factor_analysis
			)

	async def start (self) -> None:
		"""
		启动研究引擎

		初始化引擎资源，加载必要的配置和数据
		"""
		try:
			self.status = EngineStatus.INITIALIZING
			logger.info(f"开始启动因子研究引擎: {self.engine_name}")

			# 初始化研究服务
			if not self.research_service:
				from modules.data.services.research_service import DataResearchService
				self.research_service = DataResearchService()

			# 初始化缓存
			if not self.cache_manager:
				self.cache_manager = CacheManager()

			# 加载默认因子配置
			await self.load_default_factors()

			self.status = EngineStatus.RUNNING
			logger.info(f"因子研究引擎启动完成: {self.engine_name}")

			# 发布引擎启动事件
			await self.publish_engine_event("RESEARCH_ENGINE_STARTED")

		except Exception as e:
			self.status = EngineStatus.ERROR
			logger.error(f"因子研究引擎启动失败: {e}", exc_info=True)
			raise

	async def stop (self) -> None:
		"""
		停止研究引擎

		清理引擎资源，保存状态
		"""
		try:
			self.status = EngineStatus.STOPPING
			logger.info(f"开始停止因子研究引擎: {self.engine_name}")

			# 取消所有进行中的任务
			await self.cancel_all_tasks()

			# 保存缓存数据
			await self.save_factor_cache()

			# 清理资源
			self.active_tasks.clear()
			self.factor_cache.clear()

			self.status = EngineStatus.STOPPED
			logger.info(f"因子研究引擎停止完成: {self.engine_name}")

		except Exception as e:
			logger.error(f"因子研究引擎停止异常: {e}", exc_info=True)
			self.status = EngineStatus.ERROR

	async def handle_research_request (self, event) -> None:
		"""
		处理因子研究请求

		Args:
			event: 研究请求事件
		"""
		try:
			task_id = str(uuid.uuid4())
			task_info = {
				"task_id": task_id,
				"type": event.data.get("type", ResearchTaskType.FACTOR_ANALYSIS),
				"params": event.data.get("params", {}),
				"status": "pending",
				"created_at": datetime.now(),
				"progress": 0
			}

			self.active_tasks[task_id] = task_info

			# 发布任务开始事件
			start_event = FactorResearchStartedEvent(
				task_id=task_id,
				task_type=task_info["type"],
				params=task_info["params"]
			)
			await self.event_engine.put(start_event)

			# 根据任务类型执行相应处理
			task_type = task_info["type"]
			if task_type == ResearchTaskType.FACTOR_CALCULATION:
				await self.execute_factor_calculation(task_id, task_info["params"])
			elif task_type == ResearchTaskType.FACTOR_ANALYSIS:
				await self.execute_factor_analysis(task_id, task_info["params"])
			elif task_type == ResearchTaskType.FACTOR_OPTIMIZATION:
				await self.execute_factor_optimization(task_id, task_info["params"])
			elif task_type == ResearchTaskType.FACTOR_BACKTEST:
				await self.execute_factor_backtest(task_id, task_info["params"])
			elif task_type == ResearchTaskType.FACTOR_SELECTION:
				await self.execute_factor_selection(task_id, task_info["params"])
			else:
				raise ValueError(f"未知的研究任务类型: {task_type}")

		except Exception as e:
			logger.error(f"处理研究请求失败: {e}", exc_info=True)

			# 发布错误事件
			error_event = FactorResearchErrorEvent(
				task_id=task_id,
				error_message=str(e),
				task_type=event.data.get("type"),
				params=event.data.get("params", {})
			)
			await self.event_engine.put(error_event)

	async def handle_factor_calculation (self, event) -> None:
		"""
		处理因子计算请求

		Args:
			event: 因子计算事件
		"""
		try:
			task_id = str(uuid.uuid4())
			params = event.data

			self.update_task_progress(task_id, 10, "开始因子计算")

			# 提取参数
			factor_name = params.get("factor_name")
			stock_codes = params.get("stock_codes", [])
			start_date = params.get("start_date")
			end_date = params.get("end_date")
			calculation_params = params.get("params", {})

			# 执行因子计算
			result = await self.research_service.calculate_factor(
				factor_name=factor_name,
				stock_codes=stock_codes,
				start_date=start_date,
				end_date=end_date,
				params=calculation_params
			)

			self.update_task_progress(task_id, 50, "因子计算完成，正在验证")

			# 验证因子质量
			validation_result = await self.research_service.validate_factor(
				factor_data=result["factor_data"],
				factor_name=factor_name
			)

			# 缓存因子数据
			cache_key = f"factor:{factor_name}:{start_date}:{end_date}"
			await self.cache_manager.set(
				cache_key,
				{
					"factor_data": result["factor_data"],
					"metadata": result["metadata"],
					"validation": validation_result
				},
				ttl=self.cache_ttl
			)

			self.update_task_progress(task_id, 80, "因子验证完成，正在发布结果")

			# 发布因子计算完成事件
			factor_event = FactorCalculatedEvent(
				factor_name=factor_name,
				factor_data=result["factor_data"],
				metadata=result["metadata"],
				validation_result=validation_result,
				calculation_params=calculation_params
			)
			await self.event_engine.put(factor_event)

			self.update_task_progress(task_id, 100, "因子计算任务完成")

			# 更新任务状态
			self.complete_task(task_id, {
				"factor_name": factor_name,
				"data_points": len(result["factor_data"]),
				"validation_score": validation_result.get("overall_score", 0),
				"cache_key": cache_key
			})

		except Exception as e:
			logger.error(f"因子计算失败: {e}", exc_info=True)
			self.fail_task(task_id, str(e))

	async def handle_factor_analysis (self, event) -> None:
		"""
		处理因子分析请求

		Args:
			event: 因子分析事件
		"""
		try:
			task_id = str(uuid.uuid4())
			params = event.data

			self.update_task_progress(task_id, 10, "开始因子分析")

			# 提取参数
			factor_names = params.get("factor_names", [])
			analysis_type = params.get("analysis_type", "performance")
			analysis_params = params.get("params", {})

			# 执行因子分析
			analysis_result = await self.research_service.analyze_factors(
				factor_names=factor_names,
				analysis_type=analysis_type,
				params=analysis_params
			)

			self.update_task_progress(task_id, 70, "因子分析完成，正在生成报告")

			# 生成分析报告
			report = await self.research_service.generate_factor_report(
				analysis_result=analysis_result,
				analysis_type=analysis_type
			)

			# 发布验证事件
			validation_event = FactorValidationEvent(
				factor_names=factor_names,
				analysis_type=analysis_type,
				analysis_result=analysis_result,
				report=report,
				params=analysis_params
			)
			await self.event_engine.put(validation_event)

			self.update_task_progress(task_id, 100, "因子分析任务完成")

			# 更新任务状态
			self.complete_task(task_id, {
				"factor_count": len(factor_names),
				"analysis_type": analysis_type,
				"report_summary": report.get("summary", {}),
				"generated_at": datetime.now()
			})

		except Exception as e:
			logger.error(f"因子分析失败: {e}", exc_info=True)
			self.fail_task(task_id, str(e))

	async def execute_factor_calculation (self, task_id: str, params: Dict) -> None:
		"""
		执行因子计算任务

		Args:
			task_id: 任务ID
			params: 计算参数
		"""
		self.update_task_progress(task_id, 0, "初始化因子计算")

		# 实现因子计算逻辑
		factor_name = params.get("factor_name")

		# 发布因子计算事件，由事件引擎分发
		await self.event_engine.put({
			"type": "FACTOR_CALCULATION_REQUEST",
			"data": params
		})

	async def execute_factor_analysis (self, task_id: str, params: Dict) -> None:
		"""
		执行因子分析任务

		Args:
			task_id: 任务ID
			params: 分析参数
		"""
		self.update_task_progress(task_id, 0, "初始化因子分析")

		# 发布因子分析事件
		await self.event_engine.put({
			"type": "FACTOR_ANALYSIS_REQUEST",
			"data": params
		})

	async def execute_factor_optimization (self, task_id: str, params: Dict) -> None:
		"""
		执行因子优化任务

		Args:
			task_id: 任务ID
			params: 优化参数
		"""
		try:
			self.update_task_progress(task_id, 10, "开始因子优化")

			# 提取参数
			factor_names = params.get("factor_names", [])
			optimization_method = params.get("method", "genetic")
			objective_function = params.get("objective", "sharpe_ratio")
			constraints = params.get("constraints", {})

			# 执行因子优化
			optimization_result = await self.research_service.optimize_factors(
				factor_names=factor_names,
				method=optimization_method,
				objective=objective_function,
				constraints=constraints
			)

			self.update_task_progress(task_id, 100, "因子优化完成")

			# 更新任务状态
			self.complete_task(task_id, {
				"optimized_factors": optimization_result.get("optimized_factors", []),
				"optimal_weights": optimization_result.get("weights", {}),
				"objective_value": optimization_result.get("objective_value"),
				"iterations": optimization_result.get("iterations", 0)
			})

		except Exception as e:
			logger.error(f"因子优化失败: {e}", exc_info=True)
			self.fail_task(task_id, str(e))

	async def execute_factor_backtest (self, task_id: str, params: Dict) -> None:
		"""
		执行因子回测任务

		Args:
			task_id: 任务ID
			params: 回测参数
		"""
		try:
			self.update_task_progress(task_id, 10, "开始因子回测")

			# 提取参数
			factor_name = params.get("factor_name")
			backtest_params = params.get("params", {})

			# 执行因子回测
			backtest_result = await self.research_service.backtest_factor(
				factor_name=factor_name,
				params=backtest_params
			)

			self.update_task_progress(task_id, 100, "因子回测完成")

			# 更新任务状态
			self.complete_task(task_id, {
				"factor_name": factor_name,
				"backtest_period": backtest_result.get("period"),
				"performance": backtest_result.get("performance", {}),
				"transactions": backtest_result.get("transaction_count", 0)
			})

		except Exception as e:
			logger.error(f"因子回测失败: {e}", exc_info=True)
			self.fail_task(task_id, str(e))

	async def execute_factor_selection (self, task_id: str, params: Dict) -> None:
		"""
		执行因子选择任务

		Args:
			task_id: 任务ID
			params: 选择参数
		"""
		try:
			self.update_task_progress(task_id, 10, "开始因子选择")

			# 提取参数
			candidate_factors = params.get("candidate_factors", [])
			selection_method = params.get("method", "correlation")
			selection_criteria = params.get("criteria", {})

			# 执行因子选择
			selected_factors = await self.research_service.select_factors(
				candidate_factors=candidate_factors,
				method=selection_method,
				criteria=selection_criteria
			)

			self.update_task_progress(task_id, 100, "因子选择完成")

			# 更新任务状态
			self.complete_task(task_id, {
				"candidate_count": len(candidate_factors),
				"selected_count": len(selected_factors),
				"selected_factors": selected_factors,
				"selection_method": selection_method
			})

		except Exception as e:
			logger.error(f"因子选择失败: {e}", exc_info=True)
			self.fail_task(task_id, str(e))

	async def load_default_factors (self) -> None:
		"""
		加载默认因子配置

		从配置文件或数据库加载预定义的因子计算规则
		"""
		try:
			logger.info("开始加载默认因子配置")

			# 从配置加载因子定义
			default_factors = [
				{
					"name": "price_momentum",
					"description": "价格动量因子",
					"calculation_method": "technical",
					"parameters": {"lookback_period": 20}
				},
				{
					"name": "volume_ratio",
					"description": "量比因子",
					"calculation_method": "volume",
					"parameters": {"window": 5}
				},
				{
					"name": "volatility",
					"description": "波动率因子",
					"calculation_method": "statistical",
					"parameters": {"window": 20, "annualized": True}
				}
			]

			# 缓存因子定义
			for factor in default_factors:
				cache_key = f"factor_definition:{factor['name']}"
				await self.cache_manager.set(cache_key, factor, ttl=86400)

			logger.info(f"默认因子配置加载完成，共加载{len(default_factors)}个因子")

		except Exception as e:
			logger.warning(f"加载默认因子配置失败: {e}")

	async def save_factor_cache (self) -> None:
		"""保存因子缓存数据"""
		try:
			if self.factor_cache:
				# 保存到持久化存储
				for factor_key, factor_data in self.factor_cache.items():
					# 这里可以扩展到保存到数据库
					pass

				logger.info(f"因子缓存保存完成，共保存{len(self.factor_cache)}个因子")
		except Exception as e:
			logger.error(f"保存因子缓存失败: {e}")

	async def cancel_all_tasks (self) -> None:
		"""取消所有进行中的任务"""
		for task_id in list(self.active_tasks.keys()):
			task_info = self.active_tasks[task_id]
			if task_info["status"] in ["pending", "running"]:
				task_info["status"] = "cancelled"
				task_info["completed_at"] = datetime.now()
				logger.info(f"取消研究任务: {task_id}")

	def update_task_progress (self, task_id: str, progress: int, message: str = "") -> None:
		"""
		更新任务进度

		Args:
			task_id: 任务ID
			progress: 进度百分比(0-100)
			message: 进度消息
		"""
		if task_id in self.active_tasks:
			self.active_tasks[task_id]["progress"] = min(100, max(0, progress))
			if message:
				self.active_tasks[task_id]["current_step"] = message

			logger.debug(f"任务{task_id}进度更新: {progress}% - {message}")

	def complete_task (self, task_id: str, results: Dict = None) -> None:
		"""
		标记任务完成

		Args:
			task_id: 任务ID
			results: 任务结果
		"""
		if task_id in self.active_tasks:
			task_info = self.active_tasks[task_id]
			task_info["status"] = "completed"
			task_info["completed_at"] = datetime.now()
			task_info["progress"] = 100

			if results:
				task_info["results"] = results

			# 移动到历史记录
			self.task_history.append(task_info)
			if len(self.task_history) > self.max_history_size:
				self.task_history.pop(0)

			# 从活跃任务中移除
			del self.active_tasks[task_id]

			# 发布任务完成事件
			asyncio.create_task(self.publish_task_completion(task_id, task_info))

	def fail_task (self, task_id: str, error_message: str) -> None:
		"""
		标记任务失败

		Args:
			task_id: 任务ID
			error_message: 错误信息
		"""
		if task_id in self.active_tasks:
			task_info = self.active_tasks[task_id]
			task_info["status"] = "failed"
			task_info["error"] = error_message
			task_info["completed_at"] = datetime.now()

			logger.error(f"研究任务失败: {task_id} - {error_message}")

			# 移动到历史记录
			self.task_history.append(task_info)
			if len(self.task_history) > self.max_history_size:
				self.task_history.pop(0)

			# 从活跃任务中移除
			del self.active_tasks[task_id]

	async def publish_task_completion (self, task_id: str, task_info: Dict) -> None:
		"""
		发布任务完成事件

		Args:
			task_id: 任务ID
			task_info: 任务信息
		"""
		if self.event_engine:
			completion_event = FactorResearchCompletedEvent(
				task_id=task_id,
				task_type=task_info.get("type"),
				results=task_info.get("results", {}),
				duration=(task_info["completed_at"] - task_info["created_at"]).total_seconds(),
				params=task_info.get("params", {})
			)
			await self.event_engine.put(completion_event)

	async def publish_engine_event (self, event_type: str, data: Dict = None) -> None:
		"""
		发布引擎事件

		Args:
			event_type: 事件类型
			data: 事件数据
		"""
		if self.event_engine:
			event_data = {
				"engine_name": self.engine_name,
				"engine_status": self.status.value,
				"timestamp": datetime.now(),
				"data": data or {}
			}
			await self.event_engine.put({
				"type": event_type,
				"data": event_data
			})

	def get_status (self) -> Dict[str, Any]:
		"""
		获取引擎状态

		Returns:
			引擎状态字典
		"""
		return {
			"engine_name": self.engine_name,
			"engine_status": self.status.value,
			"active_tasks": len(self.active_tasks),
			"task_history": len(self.task_history),
			"factor_cache_size": len(self.factor_cache),
			"cache_ttl": self.cache_ttl,
			"active_task_ids": list(self.active_tasks.keys()),
			"uptime": (datetime.now() - self.created_at).total_seconds() if self.created_at else 0
		}

	def get_task_status (self, task_id: str) -> Optional[Dict]:
		"""
		获取指定任务状态

		Args:
			task_id: 任务ID

		Returns:
			任务状态信息，如果任务不存在则返回None
		"""
		if task_id in self.active_tasks:
			return self.active_tasks[task_id]

		# 在历史记录中查找
		for task in self.task_history:
			if task.get("task_id") == task_id:
				return task

		return None

	async def calculate_factor_on_demand (
			self,
			factor_name: str,
			stock_codes: List[str],
			start_date: str,
			end_date: str,
			params: Dict = None
	) -> Dict:
		"""
		按需计算因子（同步接口）

		Args:
			factor_name: 因子名称
			stock_codes: 股票代码列表
			start_date: 开始日期
			end_date: 结束日期
			params: 计算参数

		Returns:
			因子计算结果
		"""
		try:
			# 检查缓存
			cache_key = f"factor:{factor_name}:{start_date}:{end_date}"
			cached_data = await self.cache_manager.get(cache_key)

			if cached_data:
				logger.info(f"从缓存获取因子数据: {factor_name}")
				return {
					"cached": True,
					"factor_data": cached_data["factor_data"],
					"metadata": cached_data["metadata"]
				}

			# 执行计算
			result = await self.research_service.calculate_factor(
				factor_name=factor_name,
				stock_codes=stock_codes,
				start_date=start_date,
				end_date=end_date,
				params=params or {}
			)

			# 缓存结果
			await self.cache_manager.set(
				cache_key,
				{
					"factor_data": result["factor_data"],
					"metadata": result["metadata"]
				},
				ttl=self.cache_ttl
			)

			return {
				"cached": False,
				"factor_data": result["factor_data"],
				"metadata": result["metadata"]
			}

		except Exception as e:
			logger.error(f"按需计算因子失败: {e}", exc_info=True)
			raise