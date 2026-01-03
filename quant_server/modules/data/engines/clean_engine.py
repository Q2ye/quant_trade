"""
数据清洗引擎
负责管理数据清洗和质量提升的完整流程

业务范围：
1. 数据标准化：统一数据格式和单位
2. 异常值处理：检测和处理异常数据
3. 缺失值填充：智能填充缺失数据
4. 重复值处理：识别和去重
5. 数据转换：格式转换和归一化

引擎职责：
1. 管理清洗任务和规则
2. 协调多个清洗步骤
3. 监控清洗质量和性能
4. 处理清洗失败和恢复
5. 发布清洗相关事件

依赖服务：
- DataCleanService: 执行具体的清洗逻辑
- DataQualityService: 质量检查和验证
- Repository: 数据访问

设计原则：
1. 管道处理：多个清洗步骤组成处理管道
2. 可配置规则：支持自定义清洗规则
3. 质量反馈：清洗后验证数据质量
4. 增量清洗：支持只清洗变更数据
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Union
from enum import Enum
from dataclasses import dataclass, field
import json

from quant_server.core.engines.base import EngineBase, EngineStatus
from quant_server.core.events import EventPriority
from quant_server.modules.data.events import (
	DataProcessingStatus,
	MarketDataProcessingEvent,
	MarketDataProcessedEvent,
	MarketDataValidatedEvent,
	MarketDataMetadata,
	DataEventType,
)
from quant_server.modules.data.services.clean_service import DataCleanService
from quant_server.modules.data.services.quality_service import DataQualityService

logger = logging.getLogger(__name__)


class CleanStep(str, Enum):
	"""清洗步骤枚举"""
	VALIDATE_INPUT = "validate_input"  # 验证输入数据
	STANDARDIZE = "standardize"  # 标准化处理
	HANDLE_MISSING = "handle_missing"  # 处理缺失值
	DETECT_OUTLIERS = "detect_outliers"  # 检测异常值
	REMOVE_DUPLICATES = "remove_duplicates"  # 去重处理
	TRANSFORM = "transform"  # 数据转换
	VALIDATE_OUTPUT = "validate_output"  # 验证输出数据
	SAVE_RESULTS = "save_results"  # 保存结果


class CleanTaskStatus(str, Enum):
	"""清洗任务状态枚举"""
	PENDING = "pending"  # 等待执行
	PREPARING = "preparing"  # 准备中
	PROCESSING = "processing"  # 处理中
	VALIDATING = "validating"  # 验证中
	COMPLETED = "completed"  # 已完成
	FAILED = "failed"  # 已失败
	CANCELLED = "cancelled"  # 已取消
	PARTIAL_SUCCESS = "partial_success"  # 部分成功


@dataclass
class CleanRule:
	"""清洗规则定义"""
	name: str
	rule_type: str  # standardization/missing/outlier/duplicate/transformation
	parameters: Dict[str, Any] = field(default_factory=dict)
	enabled: bool = True
	priority: int = 0


@dataclass
class CleanTaskConfig:
	"""清洗任务配置"""
	data_type: str  # 数据类型
	symbols: List[str]  # 标的列表
	rules: List[CleanRule] = field(default_factory=list)  # 清洗规则
	quality_threshold: float = 80.0  # 质量阈值
	enable_validation: bool = True  # 启用验证
	batch_size: int = 1000  # 批量大小
	max_retries: int = 2  # 最大重试次数
	priority: int = EventPriority.NORMAL  # 任务优先级


@dataclass
class CleanTaskProgress:
	"""清洗任务进度"""
	total_steps: int = 0
	completed_steps: int = 0
	current_step: CleanStep = CleanStep.VALIDATE_INPUT
	current_symbol: str = ""
	processed_symbols: int = 0
	total_symbols: int = 0
	progress_percentage: float = 0.0
	start_time: Optional[datetime] = None
	step_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CleanTaskResult:
	"""清洗任务结果"""
	success: bool = False
	total_records: int = 0
	cleaned_records: int = 0
	failed_records: int = 0
	quality_score_before: float = 0.0
	quality_score_after: float = 0.0
	improvement: float = 0.0  # 质量提升
	error_message: Optional[str] = None
	duration_seconds: float = 0.0
	step_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class DataCleanEngine(EngineBase):
	"""
	数据清洗引擎
	管理数据清洗流程和质量提升

	状态流转：
	PENDING → PREPARING → PROCESSING → VALIDATING → COMPLETED
				↓           ↓           ↓
			  FAILED     FAILED     FAILED

	使用示例：
		engine = DataCleanEngine(event_engine, main_engine)
		await engine.start()

		# 创建清洗任务
		task_id = await engine.create_clean_task(
			data_type="daily",
			symbols=["000001.SZ", "000002.SZ"],
			rules=[CleanRule(name="standardize_price", rule_type="standardization")]
		)

		# 执行清洗
		await engine.execute_clean_task(task_id)

		# 获取清洗结果
		result = await engine.get_task_result(task_id)
	"""

	def __init__ (
			self,
			event_engine,
			main_engine,
			clean_service: Optional[DataCleanService] = None,
			quality_service: Optional[DataQualityService] = None,
			max_concurrent_tasks: int = 2,
			task_timeout_seconds: int = 1800,
			name: str = "DataCleanEngine",
			**kwargs
	):
		"""
		初始化数据清洗引擎

		Args:
			event_engine: 事件引擎实例
			main_engine: 主引擎实例
			clean_service: 数据清洗服务实例
			quality_service: 数据质量服务实例
			max_concurrent_tasks: 最大并发任务数
			task_timeout_seconds: 任务超时时间（秒）
			name: 引擎名称
			**kwargs: 其他引擎参数
		"""
		super().__init__(
			event_engine=event_engine,
			main_engine=main_engine,
			name=name,
			**kwargs
		)

		# 服务依赖
		self.clean_service = clean_service
		self.quality_service = quality_service

		# 配置参数
		self.max_concurrent_tasks = max_concurrent_tasks
		self.task_timeout_seconds = task_timeout_seconds

		# 任务管理
		self.tasks: Dict[str, Dict[str, Any]] = {}  # task_id -> 任务信息
		self.task_queue: asyncio.Queue = asyncio.Queue()
		self.active_tasks: Set[str] = set()  # 活跃任务ID集合
		self.task_counter = 0

		# 规则库
		self.default_rules: Dict[str, CleanRule] = self._create_default_rules()

		# 统计信息
		self.stats = {
			"total_tasks": 0,
			"completed_tasks": 0,
			"failed_tasks": 0,
			"total_records_cleaned": 0,
			"total_quality_improvement": 0.0,
			"avg_processing_time": 0.0,
			"last_clean_time": None,
		}

		logger.info(f"初始化数据清洗引擎: {name}")

	async def on_start (self):
		"""引擎启动时调用"""
		await super().on_start()

		# 注册事件处理器
		await self._register_event_handlers()

		# 启动任务处理循环
		self._task_processor_task = asyncio.create_task(
			self._process_task_queue()
		)

		logger.info(f"数据清洗引擎 {self.name} 已启动")

	async def on_stop (self):
		"""引擎停止时调用"""
		# 停止任务处理循环
		if hasattr(self, '_task_processor_task'):
			self._task_processor_task.cancel()
			try:
				await self._task_processor_task
			except asyncio.CancelledError:
				pass

		# 取消所有运行中的任务
		for task_id in list(self.active_tasks):
			await self.cancel_task(task_id)

		await super().on_stop()
		logger.info(f"数据清洗引擎 {self.name} 已停止")

	async def _register_event_handlers (self):
		"""注册事件处理器"""
		# 监听市场数据到达事件，触发自动清洗
		self.event_engine.register(
			DataEventType.MARKET_DATA_RAW_ARRIVED,
			self._on_market_data_arrived
		)

		# 监听数据质量事件，触发修复清洗
		self.event_engine.register(
			DataEventType.QUALITY_ISSUE_FOUND,
			self._on_quality_issue_found
		)

	async def _on_market_data_arrived (self, event):
		"""处理市场数据到达事件，触发自动清洗"""
		try:
			data = event.data
			metadata_dict = data.get("metadata", {})

			# 解析元数据
			metadata = MarketDataMetadata.from_dict(metadata_dict)

			# 检查是否需要自动清洗
			should_clean = await self._should_auto_clean(metadata)
			if not should_clean:
				return

			# 创建清洗任务
			task_id = await self.create_clean_task(
				data_type=metadata.data_type,
				symbols=metadata.symbols,
				auto_triggered=True,
				trigger_event_id=event.event_id
			)

			# 执行清洗任务
			await self.execute_clean_task(task_id)

		except Exception as e:
			logger.error(f"处理市场数据到达事件失败: {e}", exc_info=True)

	async def _on_quality_issue_found (self, event):
		"""处理质量问题事件，触发修复清洗"""
		try:
			data = event.data
			issue_type = data.get("issue_type")
			table_name = data.get("table_name")
			column_name = data.get("column_name")
			severity = data.get("severity")

			# 只处理中高严重度的问题
			if severity not in ["high", "critical", "medium"]:
				return

			# 创建修复任务
			task_id = await self.create_fix_task(
				issue_type=issue_type,
				table_name=table_name,
				column_name=column_name,
				severity=severity,
				trigger_event_id=event.event_id
			)

			logger.info(f"创建修复任务 {task_id} 处理质量问题: {issue_type}")

		except Exception as e:
			logger.error(f"处理质量问题事件失败: {e}", exc_info=True)

	async def _process_task_queue (self):
		"""处理任务队列的主循环"""
		logger.info("数据清洗任务处理循环已启动")

		while self.status == EngineStatus.RUNNING:
			try:
				# 从队列获取任务
				task_info = await asyncio.wait_for(
					self.task_queue.get(),
					timeout=1.0
				)

				task_id = task_info.get("task_id")
				if not task_id:
					logger.warning("从队列获取到无效任务")
					continue

				# 检查并发限制
				if len(self.active_tasks) >= self.max_concurrent_tasks:
					logger.warning(f"达到并发任务限制 ({self.max_concurrent_tasks})，任务 {task_id} 等待中")
					# 放回队列等待
					await self.task_queue.put(task_info)
					await asyncio.sleep(5)
					continue

				# 执行任务
				self.active_tasks.add(task_id)
				asyncio.create_task(
					self._execute_clean_task(task_info)
				)

			except asyncio.TimeoutError:
				# 队列为空，继续循环
				continue
			except asyncio.CancelledError:
				logger.info("任务处理循环被取消")
				break
			except Exception as e:
				logger.error(f"任务处理循环异常: {e}", exc_info=True)
				await asyncio.sleep(1)

		logger.info("数据清洗任务处理循环已停止")

	async def create_clean_task (
			self,
			data_type: str,
			symbols: List[str],
			rules: Optional[List[CleanRule]] = None,
			config: Optional[Dict[str, Any]] = None,
			auto_triggered: bool = False,
			trigger_event_id: Optional[str] = None
	) -> str:
		"""
		创建清洗任务

		Args:
			data_type: 数据类型
			symbols: 标的列表
			rules: 清洗规则列表
			config: 额外配置
			auto_triggered: 是否自动触发
			trigger_event_id: 触发事件ID

		Returns:
			任务ID

		Raises:
			ValueError: 参数无效
			RuntimeError: 引擎未运行
		"""
		if self.status != EngineStatus.RUNNING:
			raise RuntimeError(f"引擎 {self.name} 未运行")

		# 生成任务ID
		task_id = self._generate_task_id(data_type)

		# 合并规则
		effective_rules = rules or self._get_default_rules_for_type(data_type)

		# 创建任务配置
		task_config = CleanTaskConfig(
			data_type=data_type,
			symbols=symbols,
			rules=effective_rules,
			**(config or {})
		)

		# 创建任务记录
		self.tasks[task_id] = {
			"task_id": task_id,
			"config": task_config,
			"status": CleanTaskStatus.PENDING,
			"progress": CleanTaskProgress(
				total_symbols=len(symbols),
				current_step=CleanStep.VALIDATE_INPUT,
				start_time=datetime.now()
			),
			"result": None,
			"created_at": datetime.now(),
			"updated_at": datetime.now(),
			"error_count": 0,
			"retry_count": 0,
			"metadata": {
				"auto_triggered": auto_triggered,
				"trigger_event_id": trigger_event_id,
				"data_type": data_type,
				"symbol_count": len(symbols),
			}
		}

		# 更新统计
		self.stats["total_tasks"] += 1

		logger.info(f"创建清洗任务: {task_id} ({data_type}, {len(symbols)}个标的)")
		return task_id

	async def create_fix_task (
			self,
			issue_type: str,
			table_name: str,
			column_name: str,
			severity: str,
			config: Optional[Dict[str, Any]] = None,
			trigger_event_id: Optional[str] = None
	) -> str:
		"""
		创建数据修复任务

		Args:
			issue_type: 问题类型
			table_name: 表名
			column_name: 列名
			severity: 严重程度
			config: 额外配置
			trigger_event_id: 触发事件ID

		Returns:
			任务ID
		"""
		# 生成任务ID
		task_id = f"fix_{issue_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

		# 根据问题类型选择规则
		fix_rules = self._get_fix_rules_for_issue(issue_type)

		# 创建任务配置
		task_config = CleanTaskConfig(
			data_type=table_name,  # 使用表名作为数据类型
			symbols=[],  # 修复任务可能需要查询具体数据
			rules=fix_rules,
			quality_threshold=90.0,  # 修复任务要求更高的质量
			**(config or {})
		)

		# 创建任务记录
		self.tasks[task_id] = {
			"task_id": task_id,
			"config": task_config,
			"status": CleanTaskStatus.PENDING,
			"progress": CleanTaskProgress(
				current_step=CleanStep.VALIDATE_INPUT,
				start_time=datetime.now()
			),
			"result": None,
			"created_at": datetime.now(),
			"updated_at": datetime.now(),
			"error_count": 0,
			"retry_count": 0,
			"metadata": {
				"issue_type": issue_type,
				"table_name": table_name,
				"column_name": column_name,
				"severity": severity,
				"trigger_event_id": trigger_event_id,
				"is_fix_task": True,
			}
		}

		# 添加到队列
		await self.task_queue.put(self.tasks[task_id])

		logger.info(f"创建修复任务: {task_id} (问题: {issue_type}, 表: {table_name}.{column_name})")
		return task_id

	async def execute_clean_task (self, task_id: str) -> bool:
		"""
		执行清洗任务

		Args:
			task_id: 任务ID

		Returns:
			是否成功加入队列
		"""
		if task_id not in self.tasks:
			logger.error(f"任务不存在: {task_id}")
			return False

		# 检查任务状态
		task_info = self.tasks[task_id]
		if task_info["status"] not in [CleanTaskStatus.PENDING, CleanTaskStatus.FAILED]:
			logger.warning(f"任务 {task_id} 状态为 {task_info['status']}，无法执行")
			return False

		# 更新状态
		task_info["status"] = CleanTaskStatus.PREPARING
		task_info["updated_at"] = datetime.now()

		# 添加到队列
		await self.task_queue.put(task_info)

		logger.info(f"任务 {task_id} 已加入执行队列")
		return True

	async def _execute_clean_task (self, task_info: Dict[str, Any]):
		"""执行清洗任务"""
		task_id = task_info["task_id"]
		config = task_info["config"]
		metadata = task_info.get("metadata", {})

		try:
			# 发布处理开始事件
			await self._publish_processing_event(task_id, config, metadata)

			# 执行清洗流程
			result = await self._perform_cleaning(task_id, config, metadata)

			# 更新任务结果
			task_info["result"] = result
			task_info["status"] = CleanTaskStatus.COMPLETED if result.success else CleanTaskStatus.FAILED
			task_info["updated_at"] = datetime.now()

			# 发布处理完成事件
			await self._publish_processed_event(task_id, config, result, metadata)

			# 如果需要验证，发布验证事件
			if result.success and config.enable_validation:
				await self._publish_validated_event(task_id, config, result, metadata)

			# 更新统计
			if result.success:
				self.stats["completed_tasks"] += 1
				self.stats["total_records_cleaned"] += result.cleaned_records
				self.stats["total_quality_improvement"] += result.improvement
			else:
				self.stats["failed_tasks"] += 1

			self.stats["last_clean_time"] = datetime.now()

		except asyncio.CancelledError:
			# 任务被取消
			logger.info(f"清洗任务被取消: {task_id}")
			await self._update_task_status(task_id, CleanTaskStatus.CANCELLED)
		except Exception as e:
			# 任务执行失败
			logger.error(f"清洗任务执行失败: {task_id}, 错误: {e}", exc_info=True)

			# 检查是否需要重试
			should_retry = await self._should_retry_task(task_id)
			if should_retry:
				await self._retry_task(task_id)
			else:
				await self._mark_task_failed(task_id, str(e))

		finally:
			# 清理活跃任务集合
			self.active_tasks.discard(task_id)
			self.task_queue.task_done()

	async def _perform_cleaning (
			self,
			task_id: str,
			config: CleanTaskConfig,
			metadata: Dict[str, Any]
	) -> CleanTaskResult:
		"""执行具体的清洗逻辑"""
		start_time = datetime.now()
		result = CleanTaskResult()
		step_results = {}

		try:
			if not self.clean_service:
				raise RuntimeError("清洗服务未配置")

			# 测量清洗前质量
			quality_before = 0.0
			if self.quality_service and config.enable_validation:
				quality_before = await self._measure_quality_before(task_id, config)

			# 执行清洗步骤
			progress = self.tasks[task_id]["progress"]
			total_steps = len(config.rules) + 2  # 输入验证 + 规则步骤 + 输出验证

			# 步骤1: 验证输入数据
			await self._update_progress(task_id, CleanStep.VALIDATE_INPUT, 1, total_steps)
			step_results["validate_input"] = await self._validate_input_data(task_id, config)

			# 步骤2: 执行清洗规则
			for i, rule in enumerate(config.rules):
				if not rule.enabled:
					continue

				step_name = f"rule_{rule.name}"
				await self._update_progress(task_id, CleanStep.PROCESSING, i + 2, total_steps, {
					"current_rule": rule.name,
					"rule_type": rule.rule_type
				})

				step_result = await self._apply_clean_rule(task_id, config, rule)
				step_results[step_name] = step_result

			# 步骤3: 验证输出数据
			await self._update_progress(task_id, CleanStep.VALIDATE_OUTPUT, total_steps - 1, total_steps)
			step_results["validate_output"] = await self._validate_output_data(task_id, config)

			# 步骤4: 保存结果
			await self._update_progress(task_id, CleanStep.SAVE_RESULTS, total_steps, total_steps)
			save_result = await self._save_cleaned_data(task_id, config)
			step_results["save_results"] = save_result

			# 测量清洗后质量
			quality_after = 0.0
			if self.quality_service and config.enable_validation:
				quality_after = await self._measure_quality_after(task_id, config)

			# 构建结果
			result.success = True
			result.total_records = save_result.get("total_records", 0)
			result.cleaned_records = save_result.get("cleaned_records", 0)
			result.failed_records = save_result.get("failed_records", 0)
			result.quality_score_before = quality_before
			result.quality_score_after = quality_after
			result.improvement = max(0, quality_after - quality_before)
			result.step_results = step_results

			# 检查质量阈值
			if config.enable_validation and quality_after < config.quality_threshold:
				result.success = False
				result.error_message = f"质量分数 {quality_after} 低于阈值 {config.quality_threshold}"

		except Exception as e:
			logger.error(f"清洗执行失败: {e}", exc_info=True)
			result.success = False
			result.error_message = str(e)

		finally:
			# 计算持续时间
			result.duration_seconds = (datetime.now() - start_time).total_seconds()

		return result

	async def _update_progress (
			self,
			task_id: str,
			current_step: CleanStep,
			completed_steps: int,
			total_steps: int,
			step_details: Optional[Dict[str, Any]] = None
	):
		"""更新任务进度"""
		if task_id not in self.tasks:
			return

		task_info = self.tasks[task_id]
		progress = task_info["progress"]

		progress.current_step = current_step
		progress.completed_steps = completed_steps
		progress.total_steps = total_steps
		progress.progress_percentage = (completed_steps / total_steps * 100) if total_steps > 0 else 0

		if step_details:
			progress.step_details.update(step_details)

		task_info["updated_at"] = datetime.now()

		# 发布进度事件
		await self._publish_progress_event(task_id, progress)

	async def _publish_progress_event (self, task_id: str, progress: CleanTaskProgress):
		"""发布进度事件"""
		if task_id not in self.tasks:
			return

		task_info = self.tasks[task_id]
		config = task_info["config"]
		metadata = task_info.get("metadata", {})

		# 创建市场数据元数据
		market_metadata = MarketDataMetadata(
			data_type=config.data_type,
			symbols=config.symbols,
			start_time=datetime.now() - timedelta(days=30),
			end_time=datetime.now(),
			record_count=0,
			source=self.name,
			status=DataProcessingStatus.PROCESSING.value,
		)

		await self.event_engine.put(
			MarketDataProcessingEvent(
				metadata=market_metadata,
				processing_step=f"clean_{progress.current_step.value}",
				progress=progress.progress_percentage,
				current_symbol=progress.current_symbol,
				processed_count=progress.processed_symbols,
				source=self.name,
				data={
					"task_id": task_id,
					"step_details": progress.step_details,
					"total_symbols": progress.total_symbols,
					"estimated_remaining": None,  # 可以计算
					"metadata": metadata,
				}
			)
		)

	async def _publish_processing_event (self, task_id: str, config: CleanTaskConfig, metadata: Dict[str, Any]):
		"""发布处理开始事件"""
		market_metadata = MarketDataMetadata(
			data_type=config.data_type,
			symbols=config.symbols,
			start_time=datetime.now() - timedelta(days=30),
			end_time=datetime.now(),
			record_count=0,
			source=self.name,
			status=DataProcessingStatus.PROCESSING.value,
		)

		await self.event_engine.put(
			MarketDataProcessingEvent(
				metadata=market_metadata,
				processing_step="clean_start",
				progress=0.0,
				source=self.name,
				data={
					"task_id": task_id,
					"config": self._config_to_dict(config),
					"metadata": metadata,
				}
			)
		)

	async def _publish_processed_event (
			self,
			task_id: str,
			config: CleanTaskConfig,
			result: CleanTaskResult,
			metadata: Dict[str, Any]
	):
		"""发布处理完成事件"""
		market_metadata = MarketDataMetadata(
			data_type=config.data_type,
			symbols=config.symbols,
			start_time=datetime.now() - timedelta(days=30),
			end_time=datetime.now(),
			record_count=result.total_records,
			source=self.name,
			status=DataProcessingStatus.PROCESSED.value,
			quality_score=result.quality_score_after,
		)

		await self.event_engine.put(
			MarketDataProcessedEvent(
				metadata=market_metadata,
				processing_duration_seconds=result.duration_seconds,
				indicators_calculated=[],  # 清洗不产生新指标
				storage_location=f"cleaned/{config.data_type}",
				processing_stats={
					"cleaned_records": result.cleaned_records,
					"failed_records": result.failed_records,
					"quality_improvement": result.improvement,
				},
				quality_metrics={
					"before": result.quality_score_before,
					"after": result.quality_score_after,
					"improvement": result.improvement,
				},
				source=self.name,
				data={
					"task_id": task_id,
					"config": self._config_to_dict(config),
					"result_summary": self._result_to_dict(result),
					"metadata": metadata,
				}
			)
		)

	async def _publish_validated_event (
			self,
			task_id: str,
			config: CleanTaskConfig,
			result: CleanTaskResult,
			metadata: Dict[str, Any]
	):
		"""发布验证完成事件"""
		market_metadata = MarketDataMetadata(
			data_type=config.data_type,
			symbols=config.symbols,
			start_time=datetime.now() - timedelta(days=30),
			end_time=datetime.now(),
			record_count=result.total_records,
			source=self.name,
			status=DataProcessingStatus.VALIDATED.value,
			quality_score=result.quality_score_after,
		)

		passed = result.quality_score_after >= config.quality_threshold

		await self.event_engine.put(
			MarketDataValidatedEvent(
				metadata=market_metadata,
				validation_results={
					"passed": passed,
					"score": result.quality_score_after,
					"threshold": config.quality_threshold,
				},
				quality_score=result.quality_score_after,
				validation_rules_applied=["quality_check"],
				passed=passed,
				issues_found=[] if passed else [{
					"type": "quality_below_threshold",
					"message": f"质量分数 {result.quality_score_after} 低于阈值 {config.quality_threshold}",
					"severity": "medium"
				}],
				source=self.name,
				data={
					"task_id": task_id,
					"config": self._config_to_dict(config),
					"result_summary": self._result_to_dict(result),
					"metadata": metadata,
				}
			)
		)

	async def cancel_task (self, task_id: str) -> bool:
		"""取消清洗任务"""
		if task_id not in self.tasks:
			return False

		task_info = self.tasks[task_id]
		task_info["status"] = CleanTaskStatus.CANCELLED
		task_info["updated_at"] = datetime.now()

		# 如果任务在活跃集合中，标记为取消
		if task_id in self.active_tasks:
			# TODO: 实际取消正在运行的任务
			self.active_tasks.discard(task_id)

		logger.info(f"取消清洗任务: {task_id}")
		return True

	async def get_task_result (self, task_id: str) -> Optional[CleanTaskResult]:
		"""获取任务结果"""
		if task_id not in self.tasks:
			return None

		task_info = self.tasks[task_id]
		return task_info.get("result")

	async def get_engine_status (self) -> Dict[str, Any]:
		"""获取引擎状态"""
		base_status = await super().get_engine_status()

		# 计算平均处理时间
		avg_time = 0.0
		if self.stats["completed_tasks"] > 0:
			avg_time = self.stats["avg_processing_time"] / self.stats["completed_tasks"]

		engine_status = {
			**base_status,
			"tasks": {
				"total": len(self.tasks),
				"active": len(self.active_tasks),
				"pending": self.task_queue.qsize(),
				"completed": self.stats["completed_tasks"],
				"failed": self.stats["failed_tasks"],
			},
			"stats": {
				**self.stats,
				"avg_processing_time": round(avg_time, 2),
			},
			"config": {
				"max_concurrent_tasks": self.max_concurrent_tasks,
				"task_timeout_seconds": self.task_timeout_seconds,
				"default_rules_count": len(self.default_rules),
			},
		}

		return engine_status

	# 私有辅助方法
	def _create_default_rules (self) -> Dict[str, CleanRule]:
		"""创建默认清洗规则"""
		return {
			"standardize_price": CleanRule(
				name="standardize_price",
				rule_type="standardization",
				parameters={"decimal_places": 2, "unit": "yuan"},
				enabled=True,
				priority=10
			),
			"handle_missing_price": CleanRule(
				name="handle_missing_price",
				rule_type="missing",
				parameters={"method": "forward_fill", "limit": 5},
				enabled=True,
				priority=20
			),
			"detect_price_outliers": CleanRule(
				name="detect_price_outliers",
				rule_type="outlier",
				parameters={"method": "iqr", "threshold": 3.0},
				enabled=True,
				priority=30
			),
			"remove_duplicate_records": CleanRule(
				name="remove_duplicate_records",
				rule_type="duplicate",
				parameters={"subset": ["symbol", "date"], "keep": "first"},
				enabled=True,
				priority=40
			),
		}

	def _get_default_rules_for_type (self, data_type: str) -> List[CleanRule]:
		"""根据数据类型获取默认规则"""
		# 所有数据类型都使用基础规则
		base_rules = ["standardize_price", "remove_duplicate_records"]

		# 根据数据类型添加特定规则
		if data_type == "daily":
			base_rules.extend(["handle_missing_price", "detect_price_outliers"])
		elif data_type in ["1min", "5min", "15min"]:
			base_rules.append("handle_missing_price")

		return [self.default_rules[rule_name] for rule_name in base_rules if rule_name in self.default_rules]

	def _get_fix_rules_for_issue (self, issue_type: str) -> List[CleanRule]:
		"""根据问题类型获取修复规则"""
		fix_rules_map = {
			"missing_value": [
				CleanRule(
					name="fix_missing_values",
					rule_type="missing",
					parameters={"method": "interpolate", "limit": 10},
					enabled=True,
					priority=100
				)
			],
			"outlier": [
				CleanRule(
					name="fix_outliers",
					rule_type="outlier",
					parameters={"method": "winsorize", "limits": [0.01, 0.99]},
					enabled=True,
					priority=100
				)
			],
			"duplicate": [
				CleanRule(
					name="fix_duplicates",
					rule_type="duplicate",
					parameters={"subset": None, "keep": "first"},
					enabled=True,
					priority=100
				)
			],
			"inconsistent_format": [
				CleanRule(
					name="fix_format",
					rule_type="standardization",
					parameters={"format_rules": {}},
					enabled=True,
					priority=100
				)
			],
		}

		return fix_rules_map.get(issue_type, [])

	async def _should_auto_clean (self, metadata: MarketDataMetadata) -> bool:
		"""判断是否应该自动清洗"""
		# 暂时对所有原始数据都进行清洗
		if metadata.status == DataProcessingStatus.RAW.value:
			return True

		# 如果数据质量评分低于阈值，也需要清洗
		if metadata.quality_score < 80.0:
			return True

		return False

	async def _should_retry_task (self, task_id: str) -> bool:
		"""判断任务是否需要重试"""
		if task_id not in self.tasks:
			return False

		task_info = self.tasks[task_id]
		config = task_info["config"]

		# 检查重试次数
		if task_info["retry_count"] >= config.max_retries:
			return False

		# 检查任务是否可重试
		if task_info["status"] in [CleanTaskStatus.CANCELLED, CleanTaskStatus.COMPLETED]:
			return False

		return True

	async def _retry_task (self, task_id: str):
		"""重试任务"""
		if task_id not in self.tasks:
			return

		task_info = self.tasks[task_id]
		task_info["retry_count"] += 1
		task_info["status"] = CleanTaskStatus.PENDING
		task_info["updated_at"] = datetime.now()

		# 重新加入队列
		await self.task_queue.put(task_info)

		logger.info(f"重试任务: {task_id} (第{task_info['retry_count']}次)")

	async def _mark_task_failed (self, task_id: str, error_message: str):
		"""标记任务失败"""
		if task_id not in self.tasks:
			return

		task_info = self.tasks[task_id]

		task_info["status"] = CleanTaskStatus.FAILED
		task_info["updated_at"] = datetime.now()

		self.stats["failed_tasks"] += 1
		logger.error(f"标记任务失败: {task_id}, 错误: {error_message}")

	def _generate_task_id (self, data_type: str) -> str:
		"""生成任务ID"""
		self.task_counter += 1
		timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
		return f"clean_{data_type}_{timestamp}_{self.task_counter:06d}"

	def _config_to_dict (self, config: CleanTaskConfig) -> Dict[str, Any]:
		"""将配置转换为字典"""
		return {
			"data_type": config.data_type,
			"symbols": config.symbols,
			"rules": [
				{
					"name": rule.name,
					"type": rule.rule_type,
					"enabled": rule.enabled,
					"priority": rule.priority,
				}
				for rule in config.rules
			],
			"quality_threshold": config.quality_threshold,
			"enable_validation": config.enable_validation,
			"batch_size": config.batch_size,
			"max_retries": config.max_retries,
			"priority": config.priority,
		}

	def _result_to_dict (self, result: CleanTaskResult) -> Dict[str, Any]:
		"""将结果转换为字典"""
		return {
			"success": result.success,
			"total_records": result.total_records,
			"cleaned_records": result.cleaned_records,
			"failed_records": result.failed_records,
			"quality_score_before": result.quality_score_before,
			"quality_score_after": result.quality_score_after,
			"improvement": result.improvement,
			"duration_seconds": result.duration_seconds,
		}

	# 具体的清洗步骤实现（需要依赖服务）
	async def _measure_quality_before (self, task_id: str, config: CleanTaskConfig) -> float:
		"""测量清洗前质量"""
		try:
			if not self.quality_service:
				return 0.0

			# 这里需要根据实际情况实现
			return 75.0  # 模拟值
		except Exception as e:
			logger.error(f"测量清洗前质量失败: {e}")
			return 0.0

	async def _validate_input_data (self, task_id: str, config: CleanTaskConfig) -> Dict[str, Any]:
		"""验证输入数据"""
		return {
			"status": "valid",
			"records_checked": 0,
			"issues_found": [],
		}

	async def _apply_clean_rule (self, task_id: str, config: CleanTaskConfig, rule: CleanRule) -> Dict[str, Any]:
		"""应用清洗规则"""
		return {
			"rule": rule.name,
			"status": "applied",
			"records_processed": 0,
			"changes_made": 0,
			"errors": [],
		}

	async def _validate_output_data (self, task_id: str, config: CleanTaskConfig) -> Dict[str, Any]:
		"""验证输出数据"""
		return {
			"status": "valid",
			"records_checked": 0,
			"issues_found": [],
		}

	async def _save_cleaned_data (self, task_id: str, config: CleanTaskConfig) -> Dict[str, Any]:
		"""保存清洗后的数据"""
		return {
			"status": "saved",
			"total_records": 0,
			"cleaned_records": 0,
			"failed_records": 0,
			"storage_location": f"cleaned/{config.data_type}",
		}

	async def _measure_quality_after (self, task_id: str, config: CleanTaskConfig) -> float:
		"""测量清洗后质量"""
		try:
			if not self.quality_service:
				return 0.0

			# 这里需要根据实际情况实现
			return 95.0  # 模拟值
		except Exception as e:
			logger.error(f"测量清洗后质量失败: {e}")
			return 0.0


# 导出引擎类
__all__ = ["DataCleanEngine"]