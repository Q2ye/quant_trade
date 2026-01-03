"""
数据管理器 - 负责协调数据模块的多个引擎和服务的复杂业务流程

核心职责：
1. 数据同步流程管理
2. 数据质量控制协调
3. 研究任务调度
4. 资源分配和负载均衡
5. 跨引擎状态一致性管理
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from enum import Enum
import uuid
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from ....core.engines.base.engine_status import EngineStatus
from modules.data.engines import (
	DataSyncEngine,
	DataCleanEngine,
	DataQualityEngine,
	DataResearchEngine
)
from modules.data.services import (
	DataSyncService,
	DataQualityService,
	DataResearchService
)
from shared.database.session import SessionManager
from shared.cache.cache_manager import CacheManager
from modules.data.events import (
	DataSyncedEvent,
	DataCleanedEvent,
	QualityCheckedEvent,
	ResearchCompletedEvent
)

logger = logging.getLogger(__name__)


@dataclass
class DataTask:
	"""数据任务定义"""
	task_id: str
	task_type: str
	priority: int = 1
	created_at: datetime = field(default_factory=datetime.now)
	started_at: Optional[datetime] = None
	completed_at: Optional[datetime] = None
	status: str = "pending"
	progress: int = 0
	result: Optional[Dict] = None
	error: Optional[str] = None
	dependencies: List[str] = field(default_factory=list)
	engine_assigned: Optional[str] = None


class DataManager:
	"""
	数据管理器

	负责协调数据模块的复杂业务流程，包括：
	1. 完整的数据处理流水线（同步->清洗->质量检查）
	2. 研究任务调度和资源管理
	3. 跨引擎的状态协调
	4. 异常处理和恢复机制
	"""

	def __init__ (
			self,
			event_engine=None,
			main_engine=None,
			sync_engine: Optional[DataSyncEngine] = None,
			clean_engine: Optional[DataCleanEngine] = None,
			quality_engine: Optional[DataQualityEngine] = None,
			research_engine: Optional[DataResearchEngine] = None,
			max_workers: int = 4,
			**kwargs
	):
		"""
		初始化数据管理器

		Args:
			event_engine: 事件引擎实例
			main_engine: 主引擎实例
			sync_engine: 数据同步引擎
			clean_engine: 数据清洗引擎
			quality_engine: 数据质量引擎
			research_engine: 因子研究引擎
			max_workers: 最大工作线程数
			**kwargs: 其他参数
		"""
		self.event_engine = event_engine
		self.main_engine = main_engine

		# 引擎实例
		self.sync_engine = sync_engine
		self.clean_engine = clean_engine
		self.quality_engine = quality_engine
		self.research_engine = research_engine

		# 服务实例
		self.sync_service = None
		self.quality_service = None
		self.research_service = None

		# 任务管理
		self.active_tasks: Dict[str, DataTask] = {}
		self.task_queue: List[DataTask] = []
		self.task_history: List[DataTask] = []
		self.max_history_size = 1000

		# 执行器
		self.executor = ThreadPoolExecutor(max_workers=max_workers)
		self.loop = asyncio.get_event_loop()

		# 状态
		self.is_running = False
		self.initialized = False

		# 注册事件监听
		if self.event_engine:
			self.register_event_handlers()

	async def initialize (self) -> None:
		"""
		初始化管理器

		初始化所有依赖的引擎和服务
		"""
		try:
			logger.info("开始初始化数据管理器")

			# 初始化引擎
			if not self.sync_engine:
				self.sync_engine = DataSyncEngine(
					event_engine=self.event_engine,
					main_engine=self.main_engine
				)

			if not self.clean_engine:
				self.clean_engine = DataCleanEngine(
					event_engine=self.event_engine,
					main_engine=self.main_engine
				)

			if not self.quality_engine:
				self.quality_engine = DataQualityEngine(
					event_engine=self.event_engine,
					main_engine=self.main_engine
				)

			if not self.research_engine:
				self.research_engine = DataResearchEngine(
					event_engine=self.event_engine,
					main_engine=self.main_engine
				)

			# 启动引擎
			await self.sync_engine.start()
			await self.clean_engine.start()
			await self.quality_engine.start()
			await self.research_engine.start()

			# 初始化服务
			self.sync_service = DataSyncService()
			self.quality_service = DataQualityService()
			self.research_service = DataResearchService()

			# 初始化缓存
			self.cache_manager = CacheManager()

			self.initialized = True
			self.is_running = True

			logger.info("数据管理器初始化完成")

		except Exception as e:
			logger.error(f"数据管理器初始化失败: {e}", exc_info=True)
			raise

	def register_event_handlers (self) -> None:
		"""注册事件处理器"""
		if self.event_engine:
			self.event_engine.register(
				"DATA_SYNC_REQUEST",
				self.handle_sync_request
			)
			self.event_engine.register(
				"DATA_CLEAN_REQUEST",
				self.handle_clean_request
			)
			self.event_engine.register(
				"DATA_QUALITY_CHECK_REQUEST",
				self.handle_quality_check_request
			)
			self.event_engine.register(
				"DATA_RESEARCH_REQUEST",
				self.handle_research_request
			)

			# 监听引擎事件
			self.event_engine.register(
				"SYNC_ENGINE_STATUS_CHANGED",
				self.handle_engine_status_change
			)
			self.event_engine.register(
				"CLEAN_ENGINE_STATUS_CHANGED",
				self.handle_engine_status_change
			)
			self.event_engine.register(
				"QUALITY_ENGINE_STATUS_CHANGED",
				self.handle_engine_status_change
			)
			self.event_engine.register(
				"RESEARCH_ENGINE_STATUS_CHANGED",
				self.handle_engine_status_change
			)

	async def handle_sync_request (self, event) -> None:
		"""
		处理数据同步请求

		Args:
			event: 同步请求事件
		"""
		try:
			task_id = str(uuid.uuid4())
			params = event.data

			task = DataTask(
				task_id=task_id,
				task_type="data_sync",
				priority=params.get("priority", 2),
				dependencies=params.get("dependencies", [])
			)

			self.active_tasks[task_id] = task

			# 检查依赖
			if await self.check_dependencies(task):
				await self.execute_sync_task(task, params)
			else:
				# 等待依赖完成
				logger.info(f"任务{task_id}等待依赖完成")

		except Exception as e:
			logger.error(f"处理同步请求失败: {e}", exc_info=True)

	async def handle_clean_request (self, event) -> None:
		"""
		处理数据清洗请求

		Args:
			event: 清洗请求事件
		"""
		try:
			task_id = str(uuid.uuid4())
			params = event.data

			task = DataTask(
				task_id=task_id,
				task_type="data_clean",
				priority=params.get("priority", 2)
			)

			self.active_tasks[task_id] = task
			await self.execute_clean_task(task, params)

		except Exception as e:
			logger.error(f"处理清洗请求失败: {e}", exc_info=True)

	async def handle_quality_check_request (self, event) -> None:
		"""
		处理质量检查请求

		Args:
			event: 质量检查请求事件
		"""
		try:
			task_id = str(uuid.uuid4())
			params = event.data

			task = DataTask(
				task_id=task_id,
				task_type="quality_check",
				priority=params.get("priority", 2)
			)

			self.active_tasks[task_id] = task
			await self.execute_quality_check_task(task, params)

		except Exception as e:
			logger.error(f"处理质量检查请求失败: {e}", exc_info=True)

	async def handle_research_request (self, event) -> None:
		"""
		处理研究请求

		Args:
			event: 研究请求事件
		"""
		try:
			task_id = str(uuid.uuid4())
			params = event.data

			task = DataTask(
				task_id=task_id,
				task_type="research",
				priority=params.get("priority", 1)  # 研究任务通常优先级较高
			)

			self.active_tasks[task_id] = task
			await self.execute_research_task(task, params)

		except Exception as e:
			logger.error(f"处理研究请求失败: {e}", exc_info=True)

	async def handle_engine_status_change (self, event) -> None:
		"""
		处理引擎状态变化

		Args:
			event: 引擎状态事件
		"""
		engine_name = event.data.get("engine_name")
		status = event.data.get("status")

		logger.info(f"引擎状态变化: {engine_name} -> {status}")

		# 根据引擎状态变化调整任务调度
		if status == EngineStatus.ERROR.value:
			await self.handle_engine_error(engine_name)
		elif status == EngineStatus.STOPPED.value:
			await self.handle_engine_stopped(engine_name)

	async def execute_sync_task (self, task: DataTask, params: Dict) -> None:
		"""
		执行数据同步任务

		Args:
			task: 任务对象
			params: 同步参数
		"""
		try:
			task.started_at = datetime.now()
			task.status = "running"
			task.engine_assigned = "sync_engine"

			logger.info(f"开始执行同步任务: {task.task_id}")

			# 更新进度
			self.update_task_progress(task.task_id, 10, "准备同步环境")

			# 执行同步
			result = await self.sync_engine.start_sync_task(
				sync_type=params.get("sync_type", "daily"),
				data_types=params.get("data_types", []),
				force_update=params.get("force_update", False)
			)

			# 更新进度
			self.update_task_progress(task.task_id, 50, "数据同步中")

			# 等待同步完成
			await asyncio.sleep(1)  # 这里应该等待同步引擎的事件

			# 更新任务状态
			task.completed_at = datetime.now()
			task.status = "completed"
			task.result = result
			task.progress = 100

			logger.info(f"同步任务完成: {task.task_id}")

			# 移动到历史记录
			self.move_to_history(task)

			# 触发后续处理
			if params.get("auto_clean", True):
				await self.trigger_clean_task(task.result)

		except Exception as e:
			logger.error(f"执行同步任务失败: {e}", exc_info=True)
			task.status = "failed"
			task.error = str(e)
			self.move_to_history(task)

	async def execute_clean_task (self, task: DataTask, params: Dict) -> None:
		"""
		执行数据清洗任务

		Args:
			task: 任务对象
			params: 清洗参数
		"""
		try:
			task.started_at = datetime.now()
			task.status = "running"
			task.engine_assigned = "clean_engine"

			logger.info(f"开始执行清洗任务: {task.task_id}")

			# 更新进度
			self.update_task_progress(task.task_id, 10, "准备清洗规则")

			# 执行清洗
			result = await self.clean_engine.clean_data(
				data_type=params.get("data_type"),
				clean_rules=params.get("rules", {}),
				data_source=params.get("data_source")
			)

			# 更新任务状态
			task.completed_at = datetime.now()
			task.status = "completed"
			task.result = result
			task.progress = 100

			logger.info(f"清洗任务完成: {task.task_id}")

			# 移动到历史记录
			self.move_to_history(task)

			# 触发后续处理
			if params.get("auto_quality_check", True):
				await self.trigger_quality_check_task(task.result)

		except Exception as e:
			logger.error(f"执行清洗任务失败: {e}", exc_info=True)
			task.status = "failed"
			task.error = str(e)
			self.move_to_history(task)

	async def execute_quality_check_task (self, task: DataTask, params: Dict) -> None:
		"""
		执行质量检查任务

		Args:
			task: 任务对象
			params: 质量检查参数
		"""
		try:
			task.started_at = datetime.now()
			task.status = "running"
			task.engine_assigned = "quality_engine"

			logger.info(f"开始执行质量检查任务: {task.task_id}")

			# 更新进度
			self.update_task_progress(task.task_id, 10, "加载质量检查规则")

			# 执行质量检查
			result = await self.quality_engine.check_quality(
				data_type=params.get("data_type"),
				quality_rules=params.get("rules", {}),
				data_source=params.get("data_source")
			)

			# 更新任务状态
			task.completed_at = datetime.now()
			task.status = "completed"
			task.result = result
			task.progress = 100

			logger.info(f"质量检查任务完成: {task.task_id}")

			# 移动到历史记录
			self.move_to_history(task)

			# 发布质量检查完成事件
			if self.event_engine:
				quality_event = QualityCheckedEvent(
					data_type=params.get("data_type"),
					quality_score=result.get("quality_score", 0),
					issues_found=result.get("issues", []),
					check_time=datetime.now()
				)
				await self.event_engine.put(quality_event)

		except Exception as e:
			logger.error(f"执行质量检查任务失败: {e}", exc_info=True)
			task.status = "failed"
			task.error = str(e)
			self.move_to_history(task)

	async def execute_research_task (self, task: DataTask, params: Dict) -> None:
		"""
		执行研究任务

		Args:
			task: 任务对象
			params: 研究参数
		"""
		try:
			task.started_at = datetime.now()
			task.status = "running"
			task.engine_assigned = "research_engine"

			logger.info(f"开始执行研究任务: {task.task_id}")

			# 更新进度
			self.update_task_progress(task.task_id, 10, "初始化研究环境")

			# 执行研究
			result = await self.research_engine.handle_research_request({
				"type": "FACTOR_RESEARCH_REQUEST",
				"data": params
			})

			# 更新任务状态
			task.completed_at = datetime.now()
			task.status = "completed"
			task.result = result
			task.progress = 100

			logger.info(f"研究任务完成: {task.task_id}")

			# 移动到历史记录
			self.move_to_history(task)

		except Exception as e:
			logger.error(f"执行研究任务失败: {e}", exc_info=True)
			task.status = "failed"
			task.error = str(e)
			self.move_to_history(task)

	async def trigger_clean_task (self, sync_result: Dict) -> None:
		"""
		触发数据清洗任务

		Args:
			sync_result: 同步结果
		"""
		try:
			if sync_result.get("success", False):
				# 发布清洗请求事件
				if self.event_engine:
					await self.event_engine.put({
						"type": "DATA_CLEAN_REQUEST",
						"data": {
							"data_type": sync_result.get("data_type"),
							"data_source": sync_result.get("data_source"),
							"record_count": sync_result.get("record_count"),
							"auto_quality_check": True
						}
					})
		except Exception as e:
			logger.error(f"触发清洗任务失败: {e}")

	async def trigger_quality_check_task (self, clean_result: Dict) -> None:
		"""
		触发质量检查任务

		Args:
			clean_result: 清洗结果
		"""
		try:
			if clean_result.get("success", False):
				# 发布质量检查请求事件
				if self.event_engine:
					await self.event_engine.put({
						"type": "DATA_QUALITY_CHECK_REQUEST",
						"data": {
							"data_type": clean_result.get("data_type"),
							"data_source": clean_result.get("data_source"),
							"clean_rules": clean_result.get("rules_applied", [])
						}
					})
		except Exception as e:
			logger.error(f"触发质量检查任务失败: {e}")

	async def check_dependencies (self, task: DataTask) -> bool:
		"""
		检查任务依赖是否满足

		Args:
			task: 任务对象

		Returns:
			bool: 依赖是否满足
		"""
		if not task.dependencies:
			return True

		for dep_id in task.dependencies:
			dep_task = self.active_tasks.get(dep_id) or self.find_in_history(dep_id)
			if not dep_task or dep_task.status != "completed":
				logger.info(f"任务{task.task_id}等待依赖任务{dep_id}完成")
				return False

		return True

	def find_in_history (self, task_id: str) -> Optional[DataTask]:
		"""
		在历史记录中查找任务

		Args:
			task_id: 任务ID

		Returns:
			任务对象或None
		"""
		for task in self.task_history:
			if task.task_id == task_id:
				return task
		return None

	def update_task_progress (self, task_id: str, progress: int, message: str = "") -> None:
		"""
		更新任务进度

		Args:
			task_id: 任务ID
			progress: 进度百分比
			message: 进度消息
		"""
		if task_id in self.active_tasks:
			task = self.active_tasks[task_id]
			task.progress = min(100, max(0, progress))

			if message:
				logger.debug(f"任务{task_id}进度: {progress}% - {message}")

	def move_to_history (self, task: DataTask) -> None:
		"""
		将任务移动到历史记录

		Args:
			task: 任务对象
		"""
		# 从活跃任务中移除
		if task.task_id in self.active_tasks:
			del self.active_tasks[task.task_id]

		# 添加到历史记录
		self.task_history.append(task)

		# 清理历史记录
		if len(self.task_history) > self.max_history_size:
			self.task_history = self.task_history[-self.max_history_size:]

	async def handle_engine_error (self, engine_name: str) -> None:
		"""
		处理引擎错误

		Args:
			engine_name: 引擎名称
		"""
		logger.warning(f"处理引擎错误: {engine_name}")

		# 重新分配任务
		tasks_to_redistribute = []
		for task_id, task in self.active_tasks.items():
			if task.engine_assigned == engine_name and task.status == "running":
				tasks_to_redistribute.append(task)

		for task in tasks_to_redistribute:
			logger.info(f"重新分配任务: {task.task_id}")
			task.status = "pending"
			task.engine_assigned = None
			await self.redistribute_task(task)

	async def handle_engine_stopped (self, engine_name: str) -> None:
		"""
		处理引擎停止

		Args:
			engine_name: 引擎名称
		"""
		logger.info(f"引擎停止: {engine_name}")

		# 标记相关任务为失败
		for task_id, task in self.active_tasks.items():
			if task.engine_assigned == engine_name and task.status == "running":
				task.status = "failed"
				task.error = f"引擎{engine_name}已停止"
				self.move_to_history(task)

	async def redistribute_task (self, task: DataTask) -> None:
		"""
		重新分配任务

		Args:
			task: 任务对象
		"""
		try:
			# 根据任务类型选择可用的引擎
			if task.task_type == "data_sync" and self.sync_engine.status == EngineStatus.RUNNING:
				task.engine_assigned = "sync_engine"
			# 重新执行任务逻辑
			# 这里需要根据原始参数重新执行
			elif task.task_type == "data_clean" and self.clean_engine.status == EngineStatus.RUNNING:
				task.engine_assigned = "clean_engine"
			elif task.task_type == "quality_check" and self.quality_engine.status == EngineStatus.RUNNING:
				task.engine_assigned = "quality_engine"
			elif task.task_type == "research" and self.research_engine.status == EngineStatus.RUNNING:
				task.engine_assigned = "research_engine"
			else:
				task.status = "failed"
				task.error = "没有可用的引擎"
				self.move_to_history(task)

		except Exception as e:
			logger.error(f"重新分配任务失败: {e}")
			task.status = "failed"
			task.error = str(e)
			self.move_to_history(task)

	async def execute_data_pipeline (
			self,
			pipeline_type: str,
			pipeline_params: Dict
	) -> Dict:
		"""
		执行完整的数据处理流水线

		Args:
			pipeline_type: 流水线类型
			pipeline_params: 流水线参数

		Returns:
			流水线执行结果
		"""
		try:
			pipeline_id = str(uuid.uuid4())
			logger.info(f"开始执行数据流水线: {pipeline_id}")

			results = {}

			# 根据流水线类型执行不同的步骤
			if pipeline_type == "daily_data_processing":
				# 日常数据处理流水线
				results["sync"] = await self.execute_daily_sync(pipeline_params)
				results["clean"] = await self.execute_daily_clean(pipeline_params)
				results["quality"] = await self.execute_daily_quality_check(pipeline_params)

			elif pipeline_type == "research_pipeline":
				# 研究流水线
				results["data_preparation"] = await self.prepare_research_data(pipeline_params)
				results["factor_calculation"] = await self.calculate_factors(pipeline_params)
				results["analysis"] = await self.analyze_factors(pipeline_params)

			else:
				raise ValueError(f"未知的流水线类型: {pipeline_type}")

			logger.info(f"数据流水线完成: {pipeline_id}")
			return {
				"pipeline_id": pipeline_id,
				"pipeline_type": pipeline_type,
				"success": True,
				"results": results,
				"completed_at": datetime.now()
			}

		except Exception as e:
			logger.error(f"执行数据流水线失败: {e}", exc_info=True)
			return {
				"pipeline_id": pipeline_id,
				"pipeline_type": pipeline_type,
				"success": False,
				"error": str(e),
				"completed_at": datetime.now()
			}

	async def execute_daily_sync (self, params: Dict) -> Dict:
		"""
		执行日常数据同步

		Args:
			params: 同步参数

		Returns:
			同步结果
		"""
		try:
			# 执行同步
			sync_result = await self.sync_engine.start_sync_task(
				sync_type="daily",
				data_types=params.get("data_types", ["daily_quotes", "financials"]),
				force_update=params.get("force_update", False)
			)

			return sync_result

		except Exception as e:
			logger.error(f"日常数据同步失败: {e}")
			raise

	async def execute_daily_clean (self, params: Dict) -> Dict:
		"""
		执行日常数据清洗

		Args:
			params: 清洗参数

		Returns:
			清洗结果
		"""
		try:
			# 执行清洗
			clean_result = await self.clean_engine.clean_data(
				data_type="daily_quotes",
				clean_rules=params.get("clean_rules", {}),
				data_source="recent_sync"
			)

			return clean_result

		except Exception as e:
			logger.error(f"日常数据清洗失败: {e}")
			raise

	async def execute_daily_quality_check (self, params: Dict) -> Dict:
		"""
		执行日常质量检查

		Args:
			params: 质量检查参数

		Returns:
			质量检查结果
		"""
		try:
			# 执行质量检查
			quality_result = await self.quality_engine.check_quality(
				data_type="daily_quotes",
				quality_rules=params.get("quality_rules", {}),
				data_source="cleaned_data"
			)

			return quality_result

		except Exception as e:
			logger.error(f"日常质量检查失败: {e}")
			raise

	async def prepare_research_data (self, params: Dict) -> Dict:
		"""
		准备研究数据

		Args:
			params: 数据准备参数

		Returns:
			数据准备结果
		"""
		try:
			# 确保所需数据存在
			data_types = params.get("required_data", [])
			results = {}

			for data_type in data_types:
				# 检查数据是否存在，如果不存在则同步
				data_exists = await self.check_data_exists(data_type)

				if not data_exists:
					sync_result = await self.sync_engine.start_sync_task(
						sync_type="on_demand",
						data_types=[data_type],
						force_update=True
					)
					results[data_type] = sync_result
				else:
					results[data_type] = {"cached": True, "data_type": data_type}

			return results

		except Exception as e:
			logger.error(f"准备研究数据失败: {e}")
			raise

	async def calculate_factors (self, params: Dict) -> Dict:
		"""
		计算因子

		Args:
			params: 因子计算参数

		Returns:
			因子计算结果
		"""
		try:
			factor_names = params.get("factor_names", [])
			results = {}

			for factor_name in factor_names:
				result = await self.research_engine.calculate_factor_on_demand(
					factor_name=factor_name,
					stock_codes=params.get("stock_codes", []),
					start_date=params.get("start_date"),
					end_date=params.get("end_date"),
					params=params.get("factor_params", {})
				)
				results[factor_name] = result

			return results

		except Exception as e:
			logger.error(f"计算因子失败: {e}")
			raise

	async def analyze_factors (self, params: Dict) -> Dict:
		"""
		分析因子

		Args:
			params: 分析参数

		Returns:
			分析结果
		"""
		try:
			analysis_result = await self.research_engine.handle_factor_analysis({
				"type": "FACTOR_ANALYSIS_REQUEST",
				"data": params
			})

			return analysis_result

		except Exception as e:
			logger.error(f"分析因子失败: {e}")
			raise

	async def check_data_exists (self, data_type: str) -> bool:
		"""
		检查数据是否存在

		Args:
			data_type: 数据类型

		Returns:
			bool: 数据是否存在
		"""
		try:
			# 查询数据库或缓存
			# 这里简化为总是返回True
			return True
		except Exception as e:
			logger.error(f"检查数据存在性失败: {e}")
			return False

	def get_status (self) -> Dict[str, Any]:
		"""
		获取管理器状态

		Returns:
			状态字典
		"""
		return {
			"initialized": self.initialized,
			"is_running": self.is_running,
			"active_tasks": len(self.active_tasks),
			"task_history": len(self.task_history),
			"sync_engine_status": self.sync_engine.status.value if self.sync_engine else "not_initialized",
			"clean_engine_status": self.clean_engine.status.value if self.clean_engine else "not_initialized",
			"quality_engine_status": self.quality_engine.status.value if self.quality_engine else "not_initialized",
			"research_engine_status": self.research_engine.status.value if self.research_engine else "not_initialized",
			"active_task_types": list(set(task.task_type for task in self.active_tasks.values())),
			"executor_workers": self.executor._max_workers
		}

	def get_task_info (self, task_id: str) -> Optional[Dict]:
		"""
		获取任务信息

		Args:
			task_id: 任务ID

		Returns:
			任务信息字典或None
		"""
		task = self.active_tasks.get(task_id) or self.find_in_history(task_id)
		if task:
			return {
				"task_id": task.task_id,
				"task_type": task.task_type,
				"status": task.status,
				"progress": task.progress,
				"created_at": task.created_at,
				"started_at": task.started_at,
				"completed_at": task.completed_at,
				"engine_assigned": task.engine_assigned,
				"result": task.result,
				"error": task.error,
				"dependencies": task.dependencies
			}
		return None

	async def shutdown (self) -> None:
		"""
		关闭管理器

		清理所有资源，停止所有引擎
		"""
		try:
			logger.info("开始关闭数据管理器")
			self.is_running = False

			# 停止引擎
			if self.sync_engine:
				await self.sync_engine.stop()

			if self.clean_engine:
				await self.clean_engine.stop()

			if self.quality_engine:
				await self.quality_engine.stop()

			if self.research_engine:
				await self.research_engine.stop()

			# 关闭执行器
			self.executor.shutdown(wait=True)

			# 清理任务
			self.active_tasks.clear()
			self.task_queue.clear()

			logger.info("数据管理器关闭完成")

		except Exception as e:
			logger.error(f"关闭数据管理器失败: {e}", exc_info=True)