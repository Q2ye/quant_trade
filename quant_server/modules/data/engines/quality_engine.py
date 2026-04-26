# -*- coding: utf-8 -*-
"""
重构后的数据质量检查引擎 - 基于统一引擎框架

核心特性：
1. 继承EngineBase，遵循统一的生命周期管理
2. 使用EngineFactory进行创建和管理
3. 通过EventEngine实现事件驱动通信
4. 支持依赖注入和配置驱动
5. 提供完整的监控和健康检查
6. 支持质量规则管理和调度执行

设计模式：
1. 工厂模式：通过EngineFactory创建实例
2. 观察者模式：通过EventEngine解耦通信
3. 策略模式：支持不同类型的质量检查
4. 模板方法模式：定义质量检查标准流程

位置：quant_server/modules/data/engines/quality_engine.py
"""

import asyncio
import logging
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Union, Callable
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict

# 导入核心框架组件
from quant_server.core.engines.base.engine_base import EngineBase
from quant_server.core.engines.system.event_engine import EventEngine

# 导入类型定义
from quant_server.core.engines.types.entities import (
	EventEntity, EngineConfigEntity
)
from quant_server.core.engines.types.enums import (
	EngineType,
	ComponentStatus,
	PriorityLevel,
	EngineErrorLevel,
	ResourceType
)

# 导入数据模块组件
from quant_server.modules.data.services.quality_service import DataQualityService

logger = logging.getLogger(__name__)


class QualityCheckType(str, Enum):
	"""质量检查类型枚举"""
	FULL_CHECK = "full_check"  # 全面检查
	INCREMENTAL_CHECK = "incremental_check"  # 增量检查
	REALTIME_MONITOR = "realtime_monitor"  # 实时监控
	DIAGNOSTIC_CHECK = "diagnostic_check"  # 诊断检查
	CUSTOM_CHECK = "custom_check"  # 自定义检查


class QualityRuleType(str, Enum):
	"""质量规则类型枚举"""
	COMPLETENESS = "completeness"  # 完整性检查
	ACCURACY = "accuracy"  # 准确性检查
	CONSISTENCY = "consistency"  # 一致性检查
	TIMELINESS = "timeliness"  # 及时性检查
	VALIDITY = "validity"  # 有效性检查
	UNIQUENESS = "uniqueness"  # 唯一性检查


@dataclass
class QualityRule:
	"""质量规则定义

	Attributes:
		rule_id: 规则ID
		rule_type: 规则类型
		name: 规则名称
		description: 规则描述
		check_query: 检查查询语句
		threshold: 阈值
		severity: 严重级别
		enabled: 是否启用
		schedule: 调度表达式（cron格式）
		tags: 标签列表
	"""

	rule_id: str
	rule_type: QualityRuleType
	name: str
	description: str
	check_query: Optional[str] = None
	threshold: Optional[float] = None
	severity: str = "medium"
	enabled: bool = True
	schedule: Optional[str] = None
	tags: List[str] = field(default_factory=list)


@dataclass
class QualityTaskConfig:
	"""质量检查任务配置

	Attributes:
		check_type: 检查类型
		target_tables: 目标表列表
		rules: 检查规则列表
		enable_auto_fix: 是否启用自动修复
		notification_channels: 通知渠道列表
		priority: 任务优先级
	"""

	check_type: QualityCheckType = QualityCheckType.FULL_CHECK
	target_tables: List[str] = field(default_factory=list)
	rules: List[QualityRule] = field(default_factory=list)
	enable_auto_fix: bool = False
	notification_channels: List[str] = field(default_factory=list)
	priority: int = PriorityLevel.NORMAL.value


@dataclass
class QualityTaskProgress:
	"""质量检查任务进度

	Attributes:
		total_tables: 总表数
		checked_tables: 已检查表数
		current_table: 当前检查表
		current_rule: 当前检查规则
		total_rules: 总规则数
		checked_rules: 已检查规则数
		issues_found: 发现问题数
		progress_percentage: 进度百分比
		start_time: 开始时间
	"""

	total_tables: int = 0
	checked_tables: int = 0
	current_table: str = ""
	current_rule: str = ""
	total_rules: int = 0
	checked_rules: int = 0
	issues_found: int = 0
	progress_percentage: float = 0.0
	start_time: Optional[datetime] = None


@dataclass
class QualityTaskResult:
	"""质量检查任务结果

	Attributes:
		success: 是否成功
		total_checks: 总检查数
		passed_checks: 通过检查数
		failed_checks: 失败检查数
		issues_found: 发现问题数
		issue_summary: 问题摘要
		quality_score: 质量分数
		error_message: 错误消息
		duration_seconds: 持续时间（秒）
		detailed_report: 详细报告
	"""

	success: bool = False
	total_checks: int = 0
	passed_checks: int = 0
	failed_checks: int = 0
	issues_found: int = 0
	issue_summary: Dict[str, int] = field(default_factory=dict)
	quality_score: float = 0.0
	error_message: Optional[str] = None
	duration_seconds: float = 0.0
	detailed_report: Optional[str] = None


class DataQualityEngine(EngineBase):
	"""数据质量检查引擎

	基于统一引擎框架重构的数据质量检查引擎，负责管理和执行数据质量检查任务。
	支持多种检查类型、规则管理、调度执行和结果分析。

	核心功能：
	1. 定期质量检查：定时执行全面的数据质量检查
	2. 实时质量监控：实时监控数据质量变化
	3. 问题诊断：分析质量问题的根本原因
	4. 修复建议：提供质量问题修复建议
	5. 质量报告：生成质量报告和趋势分析

	设计原则：
	1. 规则驱动：基于规则进行质量检查
	2. 分层检查：支持不同粒度的质量检查
	3. 趋势分析：跟踪质量指标变化趋势
	4. 智能报警：根据严重程度智能报警

	Attributes:
		quality_service: 质量检查服务
		max_concurrent_tasks: 最大并发任务数
		task_timeout_seconds: 任务超时时间（秒）
		enable_scheduler: 是否启用调度器
		tasks: 任务字典 {task_id: task_info}
		task_queue: 任务队列
		active_tasks: 活跃任务集合
		quality_rules: 质量规则字典
		scheduled_tasks: 调度任务字典
		stats: 统计信息字典
		quality_trend: 质量趋势列表
	"""

	@property
	def engine_type (self) -> EngineType:
		"""获取引擎类型"""
		return EngineType.DATA_QUALITY

	def __init__ (
			self,
			config: EngineConfigEntity,
			event_engine: Optional[EventEngine] = None,
			resource_pool: Optional[Any] = None
	):
		"""初始化数据质量检查引擎

		Args:
			config: 引擎配置实体
			event_engine: 事件引擎实例
			resource_pool: 资源池管理器
		"""
		super().__init__(config, event_engine, resource_pool)

		# 依赖服务
		self.quality_service: Optional[DataQualityService] = None

		# 配置参数
		engine_config = config.config if hasattr(config, 'config') else {}
		self.max_concurrent_tasks = engine_config.get("max_concurrent_tasks", 2)
		self.task_timeout_seconds = engine_config.get("task_timeout_seconds", 3600)
		self.enable_scheduler = engine_config.get("enable_scheduler", True)

		# 任务管理
		self.tasks: Dict[str, Dict[str, Any]] = {}  # task_id -> task_info
		self.task_queue: asyncio.Queue = asyncio.Queue()
		self.active_tasks: Set[str] = set()  # 活跃任务ID集合
		self.task_counter = 0

		# 规则管理
		self.quality_rules: Dict[str, QualityRule] = self._create_default_rules()

		# 调度管理
		self.scheduled_tasks: Dict[str, asyncio.Task] = {}

		# 统计信息
		self.stats = {
			"total_tasks": 0,
			"completed_tasks": 0,
			"failed_tasks": 0,
			"total_checks": 0,
			"total_issues": 0,
			"avg_quality_score": 0.0,
			"last_check_time": None,
		}

		# 质量趋势
		self.quality_trend: List[Dict[str, Any]] = []

		# 任务处理器
		self._task_processor_task: Optional[asyncio.Task] = None
		self._scheduler_task: Optional[asyncio.Task] = None

		logger.info(f"数据质量检查引擎初始化完成: {config.name}")

	async def _on_initialize (self):
		"""引擎初始化逻辑

		执行引擎特定的初始化工作，包括：
		1. 初始化质量检查服务
		2. 注册事件处理器
		3. 初始化规则库
		"""
		logger.info(f"初始化数据质量检查引擎: {self.config.name}")

		# 初始化质量检查服务
		await self._init_quality_service()

		# 注册事件处理器
		await self._register_event_handlers()

		# 初始化默认规则
		self.quality_rules = self._create_default_rules()

		logger.info(f"数据质量检查引擎初始化完成: {self.config.name}")

	async def _init_quality_service (self):
		"""初始化质量检查服务

		尝试获取质量检查服务依赖，如果未配置则记录警告。
		"""
		try:
			# 尝试从依赖中获取质量检查服务
			if not self.quality_service:
				# 尝试从依赖中获取数据库会话
				session = None
				if hasattr(self, 'main_engine') and hasattr(self.main_engine, 'db_session'):
					session = self.main_engine.db_session
				elif hasattr(self, 'dependencies') and 'db_session' in self.dependencies:
					session = self.dependencies['db_session']
				elif hasattr(self, 'resource_pool') and hasattr(self.resource_pool, 'get_db_session'):
					# 尝试从资源池获取数据库会话
					session = self.resource_pool.get_db_session()

				if session:
					# 导入实际的DataQualityService
					from quant_server.modules.data.services.quality_service import DataQualityService
					# 创建实际的质量检查服务
					self.quality_service = DataQualityService(
						session=session,
						event_engine=self.event_engine
					)
					logger.info("质量检查服务初始化完成")
				else:
					# 创建模拟服务用于测试
					logger.warning("数据库会话未配置，使用模拟质量检查服务")
					class MockQualityService:
						@staticmethod
						async def check_data_quality (data_type: str) -> Dict[str, Any]:
							logger.debug(f"模拟检查数据质量: {data_type}")
							return {"success": True, "result": {"overall_score": 95.0, "issues": [], "total_records": 100, "valid_records": 95, "invalid_records": 5}}

					self.quality_service = MockQualityService()

		except Exception as e:
			logger.error(f"初始化质量检查服务失败: {e}")
			raise

	async def _register_event_handlers (self):
		"""注册事件处理器

		注册引擎需要处理的事件类型，包括数据同步完成、数据处理完成等事件。
		"""
		if not self.event_engine:
			logger.warning("事件引擎未配置，无法注册事件处理器")
			return

		try:
			# 监听数据同步完成事件
			await self._subscribe_to_event("data_sync_completed", self._on_sync_completed)

			# 监听数据处理完成事件
			await self._subscribe_to_event("data_processed", self._on_data_processed)

			# 监听质量检查请求事件
			await self._subscribe_to_event("quality_check_request", self._on_quality_check_request)

			logger.info(f"事件处理器注册完成: {self.config.name}")

		except Exception as e:
			logger.error(f"注册事件处理器失败: {e}")

	async def _subscribe_to_event (self, event_type: str, handler: Callable):
		"""订阅事件

		Args:
			event_type: 事件类型
			handler: 事件处理函数
		"""
		if self.event_engine:
			# 这里需要根据实际的事件引擎API进行调整
			await self.event_engine.subscribe(event_type, handler)

	async def _on_start (self):
		"""引擎启动逻辑

		执行引擎启动时的具体工作，包括：
		1. 启动任务处理循环
		2. 启动调度器
		3. 启动后台监控任务
		"""
		logger.info(f"启动数据质量检查引擎: {self.config.name}")

		# 启动任务处理循环
		self._task_processor_task = self.create_background_task(
			self._process_task_queue()
		)

		# 启动调度器
		if self.enable_scheduler:
			self._scheduler_task = self.create_background_task(
				self._run_scheduler()
			)

		# 启动质量趋势监控
		self.create_background_task(
			self._monitor_quality_trend()
		)

		logger.info(f"数据质量检查引擎已启动: {self.config.name}")

	async def _on_stop (self):
		"""引擎停止逻辑

		执行引擎停止时的清理工作，包括：
		1. 停止所有任务处理
		2. 取消所有调度任务
		3. 清理资源
		"""
		logger.info(f"停止数据质量检查引擎: {self.config.name}")

		# 停止任务处理循环
		if self._task_processor_task:
			self._task_processor_task.cancel()
			try:
				await self._task_processor_task
			except asyncio.CancelledError:
				pass

		# 停止调度器
		if self._scheduler_task:
			self._scheduler_task.cancel()
			try:
				await self._scheduler_task
			except asyncio.CancelledError:
				pass

		# 取消所有活跃任务
		for task_id in list(self.active_tasks):
			await self.cancel_task(task_id)

		# 清理任务队列
		while not self.task_queue.empty():
			try:
				self.task_queue.get_nowait()
				self.task_queue.task_done()
			except asyncio.QueueEmpty:
				break

		logger.info(f"数据质量检查引擎已停止: {self.config.name}")

	async def _on_pause (self):
		"""引擎暂停逻辑

		暂停所有正在执行的任务和调度。
		"""
		logger.info(f"暂停数据质量检查引擎: {self.config.name}")

		# 暂停任务处理循环
		if self._task_processor_task:
			self._task_processor_task.cancel()

		# 暂停调度器
		if self._scheduler_task:
			self._scheduler_task.cancel()

	async def _on_resume (self):
		"""引擎恢复逻辑

		恢复被暂停的任务和调度。
		"""
		logger.info(f"恢复数据质量检查引擎: {self.config.name}")

		# 恢复任务处理循环
		self._task_processor_task = self.create_background_task(
			self._process_task_queue()
		)

		# 恢复调度器
		if self.enable_scheduler:
			self._scheduler_task = self.create_background_task(
				self._run_scheduler()
			)

	async def _on_health_check (self) -> Dict[str, Any]:
		"""引擎健康检查逻辑

		检查引擎的健康状态，包括：
		1. 服务可用性
		2. 任务执行状态
		3. 资源使用情况
		4. 依赖服务状态

		Returns:
			Dict[str, Any]: 健康检查信息
		"""
		health_info = {
			"engine_name": self.config.name,
			"engine_type": self.engine_type.value,
			"timestamp": datetime.now().isoformat(),
			"checks": []
		}

		# 检查任务处理循环
		task_loop_healthy = self._task_processor_task and not self._task_processor_task.done()
		health_info["checks"].append({
			"name": "task_processor",
			"status": "healthy" if task_loop_healthy else "unhealthy",
			"details": {
				"task_running": task_loop_healthy,
				"queue_size": self.task_queue.qsize()
			}
		})

		# 检查调度器
		scheduler_healthy = (not self.enable_scheduler or
		                     (self._scheduler_task and not self._scheduler_task.done()))
		health_info["checks"].append({
			"name": "scheduler",
			"status": "healthy" if scheduler_healthy else "unhealthy",
			"details": {
				"enabled": self.enable_scheduler,
				"running": scheduler_healthy,
				"scheduled_tasks": len(self.scheduled_tasks)
			}
		})

		# 检查活跃任务
		health_info["checks"].append({
			"name": "active_tasks",
			"status": "healthy" if len(self.active_tasks) <= self.max_concurrent_tasks else "warning",
			"details": {
				"active_count": len(self.active_tasks),
				"max_allowed": self.max_concurrent_tasks,
				"task_ids": list(self.active_tasks)
			}
		})

		# 检查质量服务
		service_healthy = self.quality_service is not None
		health_info["checks"].append({
			"name": "quality_service",
			"status": "healthy" if service_healthy else "unhealthy",
			"details": {
				"available": service_healthy
			}
		})

		# 检查任务统计
		total_tasks = self.stats["total_tasks"]
		completed_tasks = self.stats["completed_tasks"]
		success_rate = (completed_tasks / total_tasks * 100 if total_tasks > 0 else 100)

		health_info["checks"].append({
			"name": "task_statistics",
			"status": "healthy",
			"details": {
				"total_tasks": total_tasks,
				"completed_tasks": completed_tasks,
				"failed_tasks": self.stats["failed_tasks"],
				"success_rate": success_rate
			}
		})

		return health_info

	async def _on_collect_metrics (self):
		"""收集引擎指标

		收集引擎的性能指标，包括：
		1. 任务执行指标
		2. 队列状态指标
		3. 质量分数指标
		4. 资源使用指标
		"""
		# 更新性能指标
		last_check_time = self.stats["last_check_time"]
		last_check_str = last_check_time.isoformat() if isinstance(last_check_time, datetime) else None

		self.record.update_performance_metrics({
			"task_queue_size": self.task_queue.qsize(),
			"active_tasks_count": len(self.active_tasks),
			"total_tasks_processed": self.stats["total_tasks"],
			"avg_quality_score": self.stats["avg_quality_score"],
			"total_issues_found": self.stats["total_issues"],
			"last_check_time": last_check_str,
			"quality_trend_length": len(self.quality_trend)
		})

		# 更新资源使用指标
		try:
			import psutil
			import os
			process = psutil.Process(os.getpid())

			# 内存使用
			memory_info = process.memory_info()
			self.record.update_resource_usage(ResourceType.MEMORY, memory_info.rss / 1024 / 1024)

			# CPU使用率
			cpu_percent = process.cpu_percent(interval=0.1)
			self.record.update_resource_usage(ResourceType.CPU, cpu_percent)

		except ImportError:
			logger.debug("psutil未安装，跳过系统指标收集")

	async def _on_handle_event (self, event: EventEntity):
		"""处理引擎特定事件

		Args:
			event: 事件实体
		"""
		try:
			event_type = event.event_type
			data = event.data

			if event_type == "data_sync_completed":
				await self._on_sync_completed(data)
			elif event_type == "data_processed":
				await self._on_data_processed(data)
			elif event_type == "quality_check_request":
				await self._on_quality_check_request(data)
			elif event_type == "quality_rule_update":
				await self._on_quality_rule_update(data)
			elif event_type == "quality_task_cancel":
				await self._on_quality_task_cancel(data)

		except Exception as e:
			logger.error(f"处理事件失败: {event.event_type}, 错误: {e}")
			await self.handle_error(e, EngineErrorLevel.WARNING, {"event": event.to_dict()})

	async def _on_auto_recover (self, error: Exception, context: Dict[str, Any] = None) -> bool:
		"""引擎自动恢复逻辑

		Args:
			error: 发生的异常
			context: 错误上下文

		Returns:
			bool: 恢复是否成功
		"""
		logger.info(f"尝试自动恢复数据质量检查引擎: {self.config.name}")

		try:
			# 检查任务处理循环
			if self._task_processor_task and self._task_processor_task.done():
				logger.warning("任务处理循环已停止，尝试重启")
				self._task_processor_task = self.create_background_task(
					self._process_task_queue()
				)

			# 检查调度器
			if self.enable_scheduler and self._scheduler_task and self._scheduler_task.done():
				logger.warning("调度器已停止，尝试重启")
				self._scheduler_task = self.create_background_task(
					self._run_scheduler()
				)

			# 清理失败的任务
			failed_tasks = []
			for task_id, task_info in self.tasks.items():
				if task_info.get("status") == "failed" and task_id in self.active_tasks:
					failed_tasks.append(task_id)

			for task_id in failed_tasks:
				self.active_tasks.discard(task_id)
				logger.info(f"清理失败任务: {task_id}")

			logger.info(f"数据质量检查引擎自动恢复成功: {self.config.name}")
			return True

		except Exception as recover_error:
			logger.error(f"自动恢复失败: {recover_error}")
			return False

	# ==================== 核心业务逻辑 ====================

	async def _on_sync_completed (self, data: Dict[str, Any]):
		"""处理数据同步完成事件

		Args:
			data: 事件数据
		"""
		try:
			sync_type = data.get("sync_type")
			sync_tables = data.get("tables", [])

			if not sync_tables:
				sync_tables = self._get_tables_for_sync_type(sync_type)

			if not sync_tables:
				logger.debug(f"没有需要检查的表: {sync_type}")
				return

			# 创建增量检查任务
			task_id = await self.create_quality_task(
				check_type=QualityCheckType.INCREMENTAL_CHECK,
				target_tables=sync_tables,
				trigger_event_id=data.get("event_id")
			)

			logger.info(f"创建增量质量检查任务: {task_id}, 表: {len(sync_tables)}个")

			# 发布任务创建事件
			await self._publish_event("quality_task_created", {
				"task_id": task_id,
				"check_type": QualityCheckType.INCREMENTAL_CHECK.value,
				"target_tables": sync_tables,
				"trigger": "sync_completed",
				"sync_type": sync_type
			})

		except Exception as e:
			logger.error(f"处理同步完成事件失败: {e}")
			await self.handle_error(e, EngineErrorLevel.ERROR, {"data": data})

	async def _on_data_processed (self, data: Dict[str, Any]):
		"""处理数据处理完成事件

		Args:
			data: 事件数据
		"""
		try:
			metadata = data.get("metadata", {})
			data_type = metadata.get("data_type")
			table_name = metadata.get("table_name")

			if not table_name:
				table_name = f"{data_type}_processed" if data_type else "unknown_table"

			# 创建实时监控任务
			task_id = await self.create_quality_task(
				check_type=QualityCheckType.REALTIME_MONITOR,
				target_tables=[table_name],
				trigger_event_id=data.get("event_id"),
				config={"real_time": True, "immediate": True}
			)

			logger.debug(f"创建实时质量监控任务: {task_id}, 表: {table_name}")

		except Exception as e:
			logger.error(f"处理数据完成事件失败: {e}")
			await self.handle_error(e, EngineErrorLevel.WARNING, {"data": data})

	async def _on_quality_check_request (self, data: Dict[str, Any]):
		"""处理质量检查请求事件

		Args:
			data: 事件数据
		"""
		try:
			check_type = data.get("check_type", QualityCheckType.FULL_CHECK.value)
			target_tables = data.get("target_tables", [])
			rules = data.get("rules", [])

			# 转换规则对象
			quality_rules = []
			for rule_data in rules:
				rule = QualityRule(
					rule_id=rule_data.get("rule_id", str(uuid.uuid4())),
					rule_type=QualityRuleType(rule_data.get("rule_type", "completeness")),
					name=rule_data.get("name", "未命名规则"),
					description=rule_data.get("description", ""),
					check_query=rule_data.get("check_query"),
					threshold=rule_data.get("threshold"),
					severity=rule_data.get("severity", "medium"),
					enabled=rule_data.get("enabled", True),
					schedule=rule_data.get("schedule"),
					tags=rule_data.get("tags", [])
				)
				quality_rules.append(rule)

			# 创建质量检查任务
			task_id = await self.create_quality_task(
				check_type=QualityCheckType(check_type),
				target_tables=target_tables,
				rules=quality_rules if quality_rules else None,
				config=data.get("config", {})
			)

			logger.info(f"创建质量检查任务: {task_id}, 类型: {check_type}, 表: {len(target_tables)}个")

			# 返回任务ID
			await self._publish_event("quality_task_response", {
				"request_id": data.get("request_id"),
				"task_id": task_id,
				"status": "created",
				"timestamp": datetime.now().isoformat()
			})

		except Exception as e:
			logger.error(f"处理质量检查请求失败: {e}")

			# 返回错误响应
			await self._publish_event("quality_task_response", {
				"request_id": data.get("request_id"),
				"error": str(e),
				"status": "error",
				"timestamp": datetime.now().isoformat()
			})

			await self.handle_error(e, EngineErrorLevel.ERROR, {"data": data})

	async def _on_quality_rule_update (self, data: Dict[str, Any]):
		"""处理质量规则更新事件

		Args:
			data: 事件数据
		"""
		try:
			operation = data.get("operation")  # add, update, delete, enable, disable
			rule_data = data.get("rule", {})

			if operation == "add" or operation == "update":
				rule_id = rule_data.get("rule_id", str(uuid.uuid4()))
				rule = QualityRule(
					rule_id=rule_id,
					rule_type=QualityRuleType(rule_data.get("rule_type", "completeness")),
					name=rule_data.get("name", "未命名规则"),
					description=rule_data.get("description", ""),
					check_query=rule_data.get("check_query"),
					threshold=rule_data.get("threshold"),
					severity=rule_data.get("severity", "medium"),
					enabled=rule_data.get("enabled", True),
					schedule=rule_data.get("schedule"),
					tags=rule_data.get("tags", [])
				)
				self.quality_rules[rule_id] = rule
				logger.info(f"更新质量规则: {rule_id} ({rule.name})")

			elif operation == "delete":
				rule_id = rule_data.get("rule_id")
				if rule_id in self.quality_rules:
					del self.quality_rules[rule_id]
					logger.info(f"删除质量规则: {rule_id}")

			elif operation == "enable":
				rule_id = rule_data.get("rule_id")
				if rule_id in self.quality_rules:
					self.quality_rules[rule_id].enabled = True
					logger.info(f"启用质量规则: {rule_id}")

			elif operation == "disable":
				rule_id = rule_data.get("rule_id")
				if rule_id in self.quality_rules:
					self.quality_rules[rule_id].enabled = False
					logger.info(f"禁用质量规则: {rule_id}")

			# 发布规则更新完成事件
			await self._publish_event("quality_rule_updated", {
				"operation": operation,
				"rule_id": rule_data.get("rule_id"),
				"total_rules": len(self.quality_rules),
				"timestamp": datetime.now().isoformat()
			})

		except Exception as e:
			logger.error(f"处理质量规则更新失败: {e}")
			await self.handle_error(e, EngineErrorLevel.ERROR, {"data": data})

	async def _on_quality_task_cancel (self, data: Dict[str, Any]):
		"""处理质量任务取消事件

		Args:
			data: 事件数据
		"""
		try:
			task_id = data.get("task_id")
			force = data.get("force", False)

			if not task_id:
				logger.warning("任务取消请求缺少task_id")
				return

			success = await self.cancel_task(task_id, force)

			# 发布任务取消响应
			await self._publish_event("quality_task_cancel_response", {
				"task_id": task_id,
				"success": success,
				"force": force,
				"timestamp": datetime.now().isoformat()
			})

		except Exception as e:
			logger.error(f"处理任务取消请求失败: {e}")
			await self.handle_error(e, EngineErrorLevel.WARNING, {"data": data})

	async def _run_scheduler (self):
		"""运行定时任务调度器"""
		logger.info("质量检查任务调度器已启动")

		try:
			while self.record.status == ComponentStatus.RUNNING:
				try:
					# 等待暂停事件
					await self.pause_event.wait()

					# 检查是否应该关闭
					if self.shutdown_event.is_set():
						break

					current_time = datetime.now()

					# 检查定时任务
					await self._check_scheduled_tasks(current_time)

					# 每小时执行一次全面的质量检查
					if current_time.minute == 0:
						await self._schedule_hourly_check()

					# 每天凌晨执行深度质量检查
					if current_time.hour == 2 and current_time.minute == 0:
						await self._schedule_daily_check()

					# 每分钟检查一次
					await asyncio.sleep(60)

				except asyncio.CancelledError:
					break
				except Exception as e:
					logger.error(f"调度器循环异常: {e}")
					await asyncio.sleep(60)

		except Exception as e:
			logger.error(f"调度器意外退出: {e}")
		finally:
			logger.info("质量检查任务调度器已停止")

	async def _check_scheduled_tasks (self, current_time: datetime):
		"""检查并执行定时任务

		Args:
			current_time: 当前时间
		"""
		scheduled_count = 0
		executed_count = 0

		try:
			for rule_id, rule in self.quality_rules.items():
				if not rule.enabled or not rule.schedule:
					continue

				scheduled_count += 1

				# 检查是否应该执行
				last_execution = self._get_last_execution_time(rule_id)
				should_execute = await self._should_execute_rule(rule, last_execution, current_time)

				if should_execute:
					try:
						# 获取规则适用的表
						target_tables = self._get_tables_for_rule(rule)
						if not target_tables:
							logger.debug(f"规则 {rule.name} 没有适用的表，跳过执行")
							continue

						# 创建并执行任务
						task_id = await self.create_quality_task(
							check_type=QualityCheckType.CUSTOM_CHECK,
							target_tables=target_tables,
							rules=[rule],
							config={
								"rule_id": rule_id,
								"scheduled": True,
								"schedule_time": current_time.isoformat(),
								"schedule": rule.schedule
							}
						)

						# 记录执行时间
						self._update_last_execution_time(rule_id, current_time)

						executed_count += 1
						logger.info(f"执行定时质量规则: {rule.name}, 任务ID: {task_id}")

					except Exception as e:
						logger.error(f"执行定时规则 {rule.name} 失败: {e}")
						continue

			logger.info(f"定时任务检查完成: 共 {scheduled_count} 个规则, 执行 {executed_count} 个任务")

		except Exception as e:
			logger.error(f"检查定时任务失败: {e}")

	async def _schedule_hourly_check (self):
		"""调度每小时质量检查"""
		try:
			# 获取需要每小时检查的表
			hourly_tables = ["stock_daily", "stock_minute", "index_daily", "financial_data"]

			task_id = await self.create_quality_task(
				check_type=QualityCheckType.FULL_CHECK,
				target_tables=hourly_tables,
				config={
					"scheduled": True,
					"schedule_type": "hourly",
					"priority": PriorityLevel.LOW.value
				}
			)

			logger.info(f"调度每小时质量检查, 任务ID: {task_id}")

		except Exception as e:
			logger.error(f"调度每小时检查失败: {e}")

	async def _schedule_daily_check (self):
		"""调度每日质量检查"""
		try:
			# 获取所有需要每日检查的表
			all_tables = [
				"stock_daily", "stock_minute", "index_daily",
				"financial_data", "company_info", "trade_calendar",
				"dividend_data", "split_data", "capital_change"
			]

			task_id = await self.create_quality_task(
				check_type=QualityCheckType.FULL_CHECK,
				target_tables=all_tables,
				config={
					"scheduled": True,
					"schedule_type": "daily",
					"deep_check": True,
					"priority": PriorityLevel.NORMAL.value
				}
			)

			logger.info(f"调度每日质量检查, 任务ID: {task_id}")

		except Exception as e:
			logger.error(f"调度每日检查失败: {e}")

	async def _process_task_queue (self):
		"""处理任务队列的主循环"""
		logger.info("质量检查任务处理循环已启动")

		try:
			while self.record.status == ComponentStatus.RUNNING:
				try:
					# 等待暂停事件
					await self.pause_event.wait()

					# 检查是否应该关闭
					if self.shutdown_event.is_set():
						break

					# 从队列获取任务
					try:
						task_info = await asyncio.wait_for(
							self.task_queue.get(),
							timeout=1.0
						)
					except asyncio.TimeoutError:
						# 队列为空，继续循环
						continue

					task_id = task_info.get("task_id")
					if not task_id:
						logger.warning("从队列获取到无效任务")
						self.task_queue.task_done()
						continue

					# 检查并发限制
					if len(self.active_tasks) >= self.max_concurrent_tasks:
						logger.warning(f"达到并发任务限制 ({self.max_concurrent_tasks}), 任务 {task_id} 等待中")
						# 放回队列等待
						await self.task_queue.put(task_info)
						self.task_queue.task_done()
						await asyncio.sleep(5)
						continue

					# 执行任务
					self.active_tasks.add(task_id)
					self.create_background_task(
						self._execute_quality_task(task_info)
					)

				except asyncio.CancelledError:
					break
				except Exception as e:
					logger.error(f"任务处理循环异常: {e}")
					await asyncio.sleep(1)

		except Exception as e:
			logger.error(f"任务处理循环意外退出: {e}")
		finally:
			logger.info("质量检查任务处理循环已停止")

	async def create_quality_task (
			self,
			check_type: Union[str, QualityCheckType],
			target_tables: List[str],
			rules: Optional[List[QualityRule]] = None,
			config: Optional[Dict[str, Any]] = None,
			trigger_event_id: Optional[str] = None
	) -> str:
		"""创建质量检查任务

		Args:
			check_type: 检查类型
			target_tables: 目标表列表
			rules: 检查规则列表
			config: 额外配置
			trigger_event_id: 触发事件ID

		Returns:
			str: 任务ID

		Raises:
			ValueError: 参数无效
			RuntimeError: 引擎未运行
		"""
		if self.record.status != ComponentStatus.RUNNING:
			raise RuntimeError(f"引擎 {self.config.name} 未运行")

		# 参数验证
		if isinstance(check_type, str):
			check_type = QualityCheckType(check_type)

		if not target_tables:
			raise ValueError("目标表列表不能为空")

		# 生成任务ID
		task_id = self._generate_task_id(check_type)

		# 合并规则
		effective_rules = rules or self._get_default_rules_for_tables(target_tables)

		# 获取配置值
		config_dict = config or {}
		priority_str = config_dict.get("priority", PriorityLevel.NORMAL.value)
		priority = int(priority_str) if isinstance(priority_str,
		                                           str) and priority_str.isdigit() else PriorityLevel.NORMAL.value

		# 创建任务配置
		task_config = QualityTaskConfig(
			check_type=check_type,
			target_tables=target_tables,
			rules=effective_rules,
			enable_auto_fix=config_dict.get("enable_auto_fix", False),
			notification_channels=config_dict.get("notification_channels", []),
			priority=priority
		)

		# 创建任务记录
		self.tasks[task_id] = {
			"task_id": task_id,
			"config": task_config,
			"status": "pending",
			"progress": QualityTaskProgress(
				total_tables=len(target_tables),
				total_rules=len(effective_rules),
				start_time=datetime.now()
			),
			"result": None,
			"created_at": datetime.now(),
			"updated_at": datetime.now(),
			"error_count": 0,
			"retry_count": 0,
			"metadata": {
				"trigger_event_id": trigger_event_id,
				"check_type": check_type.value,
				"table_count": len(target_tables),
				"rule_count": len(effective_rules),
				"config": config or {}
			}
		}

		# 添加到队列
		await self.task_queue.put(self.tasks[task_id])

		# 更新统计
		self.stats["total_tasks"] += 1

		# 发布任务开始事件
		await self._publish_event("quality_check_started", {
			"task_id": task_id,
			"check_type": check_type.value,
			"target_tables": target_tables,
			"check_rules": [rule.name for rule in effective_rules],
			"queue_position": self.task_queue.qsize(),
			"timestamp": datetime.now().isoformat()
		})

		logger.info(f"创建质量检查任务: {task_id} ({check_type.value}, {len(target_tables)}个表)")
		return task_id

	async def _execute_quality_task (self, task_info: Dict[str, Any]):
		"""执行质量检查任务

		Args:
			task_info: 任务信息
		"""
		task_id = task_info["task_id"]
		config = task_info["config"]
		metadata = task_info.get("metadata", {})

		try:
			# 更新任务状态
			task_info["status"] = "checking"
			task_info["updated_at"] = datetime.now()

			# 执行超时控制
			async with asyncio.timeout(self.task_timeout_seconds):
				# 执行质量检查
				result = await self._perform_quality_check(task_id, config, metadata)

			# 更新任务结果
			task_info["result"] = result
			task_info["status"] = "completed" if result.success else "failed"
			task_info["updated_at"] = datetime.now()

			# 发布检查完成事件
			await self._publish_check_completed(task_id, config, result, metadata)

			# 处理发现的问题
			if result.issues_found > 0:
				await self._handle_quality_issues(task_id, config, result, metadata)

			# 更新统计和趋势
			await self._update_stats_and_trend(result)

			# 更新统计
			if result.success:
				self.stats["completed_tasks"] += 1
			else:
				self.stats["failed_tasks"] += 1

			self.stats["last_check_time"] = datetime.now().timestamp()

			logger.info(f"质量检查任务完成: {task_id}, 分数: {result.quality_score:.2f}")

		except asyncio.CancelledError:
			# 任务被取消
			logger.info(f"质量检查任务被取消: {task_id}")
			task_info["status"] = "cancelled"
			task_info["updated_at"] = datetime.now()

		except asyncio.TimeoutError:
			# 任务超时
			logger.error(f"质量检查任务超时: {task_id}")
			task_info["status"] = "timeout"
			task_info["updated_at"] = datetime.now()
			await self._mark_task_failed(task_id, "任务执行超时")

		except Exception as e:
			# 任务执行失败
			logger.error(f"质量检查任务执行失败: {task_id}, 错误: {e}", exc_info=True)

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

	async def _perform_quality_check (
			self,
			task_id: str,
			config: QualityTaskConfig,
			_metadata: Dict[str, Any]
	) -> QualityTaskResult:
		"""执行具体的质量检查逻辑

		Args:
			task_id: 任务ID
			config: 任务配置
			_metadata: 任务元数据

		Returns:
			QualityTaskResult: 检查结果
		"""
		start_time = datetime.now()
		result = QualityTaskResult()
		issue_summary = defaultdict(int)

		try:
			if not self.quality_service:
				raise RuntimeError("质量检查服务未配置")

			# 执行质量检查
			total_checks = 0
			passed_checks = 0
			failed_checks = 0
			issues_found = 0

			# 遍历所有表和规则
			progress = self.tasks[task_id]["progress"]
			progress.total_tables = len(config.target_tables)
			progress.total_rules = len(config.rules)

			for table_idx, table_name in enumerate(config.target_tables):
				# 更新进度
				progress.current_table = table_name
				progress.checked_tables = table_idx + 1
				progress.progress_percentage = (table_idx + 1) / len(config.target_tables) * 50
				await self._update_task_progress(task_id, progress)

				for rule_idx, rule in enumerate(config.rules):
					if not rule.enabled:
						continue

					# 更新进度
					progress.current_rule = rule.name
					progress.checked_rules = rule_idx + 1
					progress.progress_percentage = 50 + (rule_idx + 1) / len(config.rules) * 50
					await self._update_task_progress(task_id, progress)

					# 执行规则检查
					check_result = await self._execute_quality_rule(table_name, rule)
					total_checks += 1

					if check_result.get("passed", False):
						passed_checks += 1
					else:
						failed_checks += 1
						issues_count = check_result.get("issues_count", 0)
						issues_found += issues_count

						# 记录问题摘要
						severity = check_result.get("severity", "medium")
						issue_summary[severity] += issues_count

						# 发布问题发现事件
						await self._publish_issue_found(task_id, table_name, rule, check_result)

			# 计算质量分数
			quality_score = (passed_checks / total_checks * 100) if total_checks > 0 else 100

			# 构建结果
			result.success = True
			result.total_checks = total_checks
			result.passed_checks = passed_checks
			result.failed_checks = failed_checks
			result.issues_found = issues_found
			result.issue_summary = dict(issue_summary)
			result.quality_score = quality_score
			result.detailed_report = self._generate_report(config, result)
			result.duration_seconds = (datetime.now() - start_time).total_seconds()

		except Exception as e:
			logger.error(f"质量检查执行失败: {e}", exc_info=True)
			result.success = False
			result.error_message = str(e)
			result.duration_seconds = (datetime.now() - start_time).total_seconds()

		return result

	async def _execute_quality_rule (self, table_name: str, rule: QualityRule) -> Dict[str, Any]:
		"""执行单个质量规则检查

		Args:
			table_name: 表名
			rule: 质量规则

		Returns:
			Dict[str, Any]: 检查结果
		"""
		try:
			if not self.quality_service:
				return {"passed": True, "issues_count": 0}

			# 根据表名映射到数据类型
			data_type_map = {
				"stock_daily": "daily_quotes",
				"stock_minute": "daily_quotes",
				"index_daily": "daily_quotes",
				"financial_data": "financial_data",
				"company_info": "stock_list",
				"factor_data": "factor_data",
				"trade_calendar": "daily_quotes",
				"dividend_data": "financial_data",
				"split_data": "financial_data",
				"capital_change": "financial_data"
			}

			data_type = data_type_map.get(table_name, table_name)

			# 调用实际的质量检查服务
			result = await self.quality_service.check_data_quality(data_type)

			# 解析结果
			success = result.get("success", False)
			quality_metrics = result.get("result", {})
			overall_score = quality_metrics.get("overall_score", 0)
			issues = quality_metrics.get("issues", [])
			issues_count = len(issues)

			# 根据规则类型调整阈值
			threshold = rule.threshold if rule.threshold else 90.0
			if rule.rule_type == QualityRuleType.COMPLETENESS:
				threshold = 95.0  # 完整性检查要求更高
			elif rule.rule_type == QualityRuleType.ACCURACY:
				threshold = 92.0  # 准确性检查要求较高

			# 判断是否通过
			passed = success and overall_score >= threshold

			# 确保返回标准格式
			return {
				"passed": passed,
				"rule_id": rule.rule_id,
				"rule_name": rule.name,
				"rule_type": rule.rule_type.value,
				"table_name": table_name,
				"issues_count": issues_count,
				"severity": rule.severity,
				"details": {
					"overall_score": overall_score,
					"threshold": threshold,
					"issues": issues,
					"total_records": quality_metrics.get("total_records", 0),
					"valid_records": quality_metrics.get("valid_records", 0),
					"invalid_records": quality_metrics.get("invalid_records", 0),
					"missing_records": quality_metrics.get("missing_records", 0),
					"duplicate_records": quality_metrics.get("duplicate_records", 0)
				},
			}

		except Exception as e:
			logger.error(f"执行质量规则失败: {rule.name} on {table_name}, 错误: {e}")
			return {
				"passed": False,
				"rule_id": rule.rule_id,
				"rule_name": rule.name,
				"rule_type": rule.rule_type.value,
				"table_name": table_name,
				"issues_count": 1,
				"severity": "high",
				"details": {
					"message": f"规则执行失败: {str(e)}",
					"error": str(e),
				},
			}

	async def _publish_issue_found (
			self,
			task_id: str,
			table_name: str,
			rule: QualityRule,
			check_result: Dict[str, Any]
	):
		"""发布问题发现事件

		Args:
			task_id: 任务ID
			table_name: 表名
			rule: 质量规则
			check_result: 检查结果
		"""
		await self._publish_event("quality_issue_found", {
			"task_id": task_id,
			"table_name": table_name,
			"rule_id": rule.rule_id,
			"rule_name": rule.name,
			"rule_type": rule.rule_type.value,
			"severity": check_result.get("severity", rule.severity),
			"issues_count": check_result.get("issues_count", 0),
			"details": check_result.get("details", {}),
			"timestamp": datetime.now().isoformat()
		})

	async def _publish_check_completed (
			self,
			task_id: str,
			config: QualityTaskConfig,
			result: QualityTaskResult,
			metadata: Dict[str, Any]
	):
		"""发布检查完成事件

		Args:
			task_id: 任务ID
			config: 任务配置
			result: 检查结果
			metadata: 任务元数据
		"""
		await self._publish_event("quality_check_completed", {
			"task_id": task_id,
			"check_type": config.check_type.value,
			"total_checks": result.total_checks,
			"passed_checks": result.passed_checks,
			"failed_checks": result.failed_checks,
			"issues_found": result.issues_found,
			"issue_summary": result.issue_summary,
			"quality_score": result.quality_score,
			"duration_seconds": result.duration_seconds,
			"success": result.success,
			"error_message": result.error_message,
			"metadata": metadata,
			"timestamp": datetime.now().isoformat()
		})

	async def _handle_quality_issues (
			self,
			task_id: str,
			config: QualityTaskConfig,
			result: QualityTaskResult,
			metadata: Dict[str, Any]
	):
		"""处理发现的质量问题

		Args:
			task_id: 任务ID
			config: 任务配置
			result: 检查结果
			metadata: 任务元数据
		"""
		if config.enable_auto_fix and result.issues_found > 0:
			logger.info(f"任务 {task_id} 发现 {result.issues_found} 个问题，启用自动修复")

			# 发布自动修复请求事件
			await self._publish_event("quality_auto_fix_request", {
				"task_id": task_id,
				"issues_count": result.issues_found,
				"issue_summary": result.issue_summary,
				"quality_score": result.quality_score,
				"metadata": metadata,
				"timestamp": datetime.now().isoformat()
			})

		# 发送通知
		await self._send_quality_notification(task_id, config, result, metadata)

	async def _send_quality_notification (
			self,
			task_id: str,
			config: QualityTaskConfig,
			result: QualityTaskResult,
			_metadata: Dict[str, Any]
	):
		"""发送质量通知

		Args:
			task_id: 任务ID
			config: 任务配置
			result: 检查结果
			_metadata: 任务元数据
		"""
		if not config.notification_channels:
			return

		notification_data = {
			"task_id": task_id,
			"check_type": config.check_type.value,
			"total_checks": result.total_checks,
			"passed_checks": result.passed_checks,
			"failed_checks": result.failed_checks,
			"issues_found": result.issues_found,
			"quality_score": result.quality_score,
			"success": result.success,
			"error_message": result.error_message,
			"timestamp": datetime.now().isoformat()
		}

		# 根据通知渠道发送通知
		for channel in config.notification_channels:
			try:
				if channel == "email":
					await self._send_email_notification(notification_data)
				elif channel == "webhook":
					await self._send_webhook_notification(notification_data)
				elif channel == "slack":
					await self._send_slack_notification(notification_data)
				elif channel == "teams":
					await self._send_teams_notification(notification_data)
			# 可以添加更多通知渠道

			except Exception as e:
				logger.error(f"发送通知失败, 渠道: {channel}, 错误: {e}")

	@staticmethod
	async def _send_email_notification (data: Dict[str, Any]):
		"""发送邮件通知

		Args:
			data: 通知数据
		"""
		# 实现邮件发送逻辑
		# 这里可以集成邮件服务或使用SMTP
		logger.debug(f"发送邮件通知: {data['task_id']}")

	@staticmethod
	async def _send_webhook_notification (data: Dict[str, Any]):
		"""发送Webhook通知

		Args:
			data: 通知数据
		"""
		# 实现Webhook发送逻辑
		logger.debug(f"发送Webhook通知: {data['task_id']}")

	@staticmethod
	async def _send_slack_notification (data: Dict[str, Any]):
		"""发送Slack通知

		Args:
			data: 通知数据
		"""
		# 实现Slack发送逻辑
		logger.debug(f"发送Slack通知: {data['task_id']}")

	@staticmethod
	async def _send_teams_notification (data: Dict[str, Any]):
		"""发送Teams通知

		Args:
			data: 通知数据
		"""
		# 实现Teams发送逻辑
		logger.debug(f"发送Teams通知: {data['task_id']}")

	async def _update_stats_and_trend (self, result: QualityTaskResult):
		"""更新统计信息和质量趋势

		Args:
			result: 检查结果
		"""
		if not result.success:
			return

		# 更新统计
		self.stats["total_checks"] += result.total_checks
		self.stats["total_issues"] += result.issues_found

		# 更新平均质量分数
		current_avg = self.stats["avg_quality_score"]
		total_completed = self.stats["completed_tasks"]

		if total_completed == 0:
			self.stats["avg_quality_score"] = result.quality_score
		else:
			self.stats["avg_quality_score"] = (current_avg * total_completed + result.quality_score) / (
						total_completed + 1)

		# 更新质量趋势
		trend_entry = {
			"timestamp": datetime.now().isoformat(),
			"quality_score": result.quality_score,
			"total_checks": result.total_checks,
			"passed_checks": result.passed_checks,
			"failed_checks": result.failed_checks,
			"issues_found": result.issues_found,
		}

		self.quality_trend.append(trend_entry)

		# 限制趋势数据长度
		if len(self.quality_trend) > 1000:
			self.quality_trend = self.quality_trend[-1000:]

	async def _monitor_quality_trend (self):
		"""监控质量趋势"""
		logger.info("质量趋势监控已启动")

		try:
			while self.record.status == ComponentStatus.RUNNING:
				try:
					# 等待暂停事件
					await self.pause_event.wait()

					# 检查是否应该关闭
					if self.shutdown_event.is_set():
						break

					# 分析质量趋势
					if len(self.quality_trend) >= 10:  # 至少有10个数据点
						await self._analyze_quality_trend()

					# 每小时分析一次
					await asyncio.sleep(3600)

				except asyncio.CancelledError:
					break
				except Exception as e:
					logger.error(f"质量趋势监控异常: {e}")
					await asyncio.sleep(3600)

		except Exception as e:
			logger.error(f"质量趋势监控意外退出: {e}")
		finally:
			logger.info("质量趋势监控已停止")

	async def _analyze_quality_trend (self):
		"""分析质量趋势"""
		try:
			# 计算最近24小时的质量趋势
			cutoff_time = datetime.now() - timedelta(hours=24)
			recent_trend = [
				entry for entry in self.quality_trend
				if datetime.fromisoformat(entry["timestamp"]) > cutoff_time
			]

			if not recent_trend:
				return

			# 计算平均质量分数
			avg_scores = [entry["quality_score"] for entry in recent_trend]
			avg_score = sum(avg_scores) / len(avg_scores)

			# 计算趋势（上升、下降、稳定）
			if len(avg_scores) >= 2:
				first_half = avg_scores[:len(avg_scores) // 2]
				second_half = avg_scores[len(avg_scores) // 2:]

				first_avg = sum(first_half) / len(first_half) if first_half else 0
				second_avg = sum(second_half) / len(second_half) if second_half else 0

				if second_avg > first_avg + 1:  # 上升超过1%
					trend = "improving"
				elif second_avg < first_avg - 1:  # 下降超过1%
					trend = "deteriorating"
				else:
					trend = "stable"
			else:
				trend = "unknown"

			# 发布趋势分析事件
			await self._publish_event("quality_trend_analysis", {
				"avg_score": avg_score,
				"trend": trend,
				"samples": len(recent_trend),
				"time_range": "24h",
				"timestamp": datetime.now().isoformat()
			})

		except Exception as e:
			logger.error(f"分析质量趋势失败: {e}")

	async def cancel_task (self, task_id: str, force: bool = False) -> bool:
		"""取消质量检查任务

		Args:
			task_id: 任务ID
			force: 是否强制取消

		Returns:
			bool: 取消是否成功
		"""
		if task_id not in self.tasks:
			logger.error(f"任务不存在: {task_id}")
			return False

		task_info = self.tasks[task_id]

		# 检查任务状态
		status = task_info["status"]
		if status in ["completed", "cancelled", "failed"]:
			logger.warning(f"任务 {task_id} 状态为 {status}，无法取消")
			return False

		# 更新任务状态
		task_info["status"] = "cancelled"
		task_info["updated_at"] = datetime.now()

		# 如果任务在活跃集合中，移除
		if task_id in self.active_tasks:
			self.active_tasks.discard(task_id)

		logger.info(f"任务已取消: {task_id} (强制: {force})")
		return True

	async def get_task_result (self, task_id: str) -> Optional[QualityTaskResult]:
		"""获取任务结果

		Args:
			task_id: 任务ID

		Returns:
			Optional[QualityTaskResult]: 任务结果，不存在返回None
		"""
		if task_id not in self.tasks:
			return None

		return self.tasks[task_id].get("result")

	async def get_quality_trend (
			self,
			days: int = 7,
			aggregation: str = "daily"
	) -> List[Dict[str, Any]]:
		"""获取质量趋势数据

		Args:
			days: 天数
			aggregation: 聚合方式（hourly/daily/weekly）

		Returns:
			List[Dict[str, Any]]: 质量趋势数据
		"""
		cutoff_time = datetime.now() - timedelta(days=days)

		filtered_trend = [
			entry for entry in self.quality_trend
			if datetime.fromisoformat(entry["timestamp"]) > cutoff_time
		]

		# 根据聚合方式处理数据
		if aggregation == "hourly":
			return self._aggregate_by_hour(filtered_trend)
		elif aggregation == "daily":
			return self._aggregate_by_day(filtered_trend)
		elif aggregation == "weekly":
			return self._aggregate_by_week(filtered_trend)
		else:
			return filtered_trend

	async def get_engine_metrics (self) -> Dict[str, Any]:
		"""获取引擎性能指标

		Returns:
			Dict[str, Any]: 性能指标
		"""
		last_check_time = self.stats["last_check_time"]
		last_check_str = last_check_time.isoformat() if isinstance(last_check_time, datetime) else None

		return {
			"engine_id": self.engine_id,
			"engine_name": self.config.name,
			"engine_type": self.engine_type.value,
			"status": self.record.status.value,
			"health": self.record.health.value,
			"uptime": self.record.get_uptime(),
			"tasks": {
				"total": len(self.tasks),
				"active": len(self.active_tasks),
				"pending": self.task_queue.qsize(),
				"completed": self.stats["completed_tasks"],
				"failed": self.stats["failed_tasks"],
			},
			"stats": self.stats.copy(),
			"quality": {
				"avg_score": round(self.stats["avg_quality_score"], 2),
				"trend_length": len(self.quality_trend),
				"last_check": last_check_str,
			},
			"config": {
				"max_concurrent_tasks": self.max_concurrent_tasks,
				"task_timeout_seconds": self.task_timeout_seconds,
				"enable_scheduler": self.enable_scheduler,
				"rule_count": len(self.quality_rules),
			},
			"timestamp": datetime.now().isoformat()
		}

	# ==================== 辅助方法 ====================

	@staticmethod
	def _create_default_rules () -> Dict[str, QualityRule]:
		"""创建默认质量规则

		Returns:
			Dict[str, QualityRule]: 默认规则字典
		"""
		return {
			"completeness_stock_daily": QualityRule(
				rule_id="completeness_stock_daily",
				rule_type=QualityRuleType.COMPLETENESS,
				name="股票日线数据完整性检查",
				description="检查股票日线数据是否存在缺失",
				threshold=0.95,
				severity="high",
				enabled=True,
				schedule="0 0 * * *",
				tags=["stock", "daily", "completeness"]
			),
			"accuracy_price_range": QualityRule(
				rule_id="accuracy_price_range",
				rule_type=QualityRuleType.ACCURACY,
				name="价格范围准确性检查",
				description="检查价格是否在合理范围内",
				threshold=0.99,
				severity="high",
				enabled=True,
				tags=["price", "accuracy"]
			),
			"consistency_market_cap": QualityRule(
				rule_id="consistency_market_cap",
				rule_type=QualityRuleType.CONSISTENCY,
				name="市值数据一致性检查",
				description="检查市值数据是否一致",
				severity="medium",
				enabled=True,
				tags=["market_cap", "consistency"]
			),
			"timeliness_data_freshness": QualityRule(
				rule_id="timeliness_data_freshness",
				rule_type=QualityRuleType.TIMELINESS,
				name="数据新鲜度检查",
				description="检查数据是否及时更新",
				threshold=24,
				severity="medium",
				enabled=True,
				schedule="0 */1 * * *",
				tags=["freshness", "timeliness"]
			),
			"validity_trade_volume": QualityRule(
				rule_id="validity_trade_volume",
				rule_type=QualityRuleType.VALIDITY,
				name="交易量有效性检查",
				description="检查交易量是否为有效正数",
				severity="low",
				enabled=True,
				tags=["volume", "validity"]
			),
			"uniqueness_daily_record": QualityRule(
				rule_id="uniqueness_daily_record",
				rule_type=QualityRuleType.UNIQUENESS,
				name="日记录唯一性检查",
				description="检查每日记录是否唯一",
				severity="medium",
				enabled=True,
				tags=["uniqueness", "daily"]
			)
		}

	def _get_default_rules_for_tables (self, tables: List[str]) -> List[QualityRule]:
		"""根据表名获取默认规则

		Args:
			tables: 表名列表

		Returns:
			List[QualityRule]: 适用的规则列表
		"""
		applicable_rules = []

		for rule in self.quality_rules.values():
			if not rule.enabled:
				continue

			# 根据标签匹配规则
			rule_tags = set(rule.tags)
			for table in tables:
				table_tags = self._get_tags_for_table(table)
				if rule_tags.intersection(table_tags):
					applicable_rules.append(rule)
					break

		return applicable_rules

	@staticmethod
	def _get_tags_for_table (table_name: str) -> List[str]:
		"""根据表名获取标签

		Args:
			table_name: 表名

		Returns:
			Set[str]: 标签集合
		"""
		tag_map = {
			"stock_daily": {"stock", "daily"},
			"stock_minute": {"stock", "minute"},
			"index_daily": {"index", "daily"},
			"financial_data": {"financial"},
			"company_info": {"company"},
			"trade_calendar": {"calendar"},
		}
		return list(tag_map.get(table_name, set()))

	@staticmethod
	def _get_tables_for_sync_type (sync_type: str) -> List[str]:
		"""根据同步类型获取需要检查的表

		Args:
			sync_type: 同步类型

		Returns:
			List[str]: 表名列表
		"""
		table_map = {
			"daily": ["stock_daily", "index_daily"],
			"minute": ["stock_minute"],
			"financial": ["financial_data"],
			"company": ["company_info"],
			"all": ["stock_daily", "stock_minute", "index_daily", "financial_data", "company_info"],
		}
		return table_map.get(sync_type, [])

	@staticmethod
	def _get_tables_for_rule (rule: QualityRule) -> List[str]:
		"""根据规则获取需要检查的表

		Args:
			rule: 质量规则

		Returns:
			List[str]: 表名列表
		"""
		tables = []
		rule_tags = set(rule.tags)

		table_tag_map = {
			"stock_daily": {"stock", "daily"},
			"stock_minute": {"stock", "minute"},
			"index_daily": {"index", "daily"},
			"financial_data": {"financial"},
			"company_info": {"company"},
			"trade_calendar": {"calendar"},
		}

		for table, tags in table_tag_map.items():
			if rule_tags.intersection(tags):
				tables.append(table)

		return tables

	def _get_last_execution_time (self, rule_id: str) -> Optional[datetime]:
		"""获取规则上次执行时间

		Args:
			rule_id: 规则ID

		Returns:
			Optional[datetime]: 上次执行时间
		"""
		# 从内存缓存中获取上次执行时间
		if hasattr(self, '_last_execution_times'):
			return self._last_execution_times.get(rule_id)
		# 初始化执行时间缓存
		self._last_execution_times = {}
		return None

	def _update_last_execution_time (self, rule_id: str, execution_time: datetime):
		"""更新规则上次执行时间

		Args:
			rule_id: 规则ID
			execution_time: 执行时间
		"""
		# 确保执行时间缓存存在
		if not hasattr(self, '_last_execution_times'):
			self._last_execution_times = {}
		# 更新执行时间
		self._last_execution_times[rule_id] = execution_time

	@staticmethod
	async def _should_execute_rule (
			rule: QualityRule,
			last_execution: Optional[datetime],
			current_time: datetime
	) -> bool:
		"""判断规则是否应该执行

		Args:
			rule: 质量规则
			last_execution: 上次执行时间
			current_time: 当前时间

		Returns:
			bool: 是否应该执行
		"""
		if not rule.schedule:
			return False

		# 解析schedule字段（支持cron表达式或简单的时间间隔）
		schedule = rule.schedule
		
		# 处理简单的时间间隔格式（如 "1h", "2d"）
		if isinstance(schedule, str):
			# 检查是否是时间间隔格式
			if schedule.endswith('h'):
				# 小时间隔
				try:
					hours = int(schedule[:-1])
					if last_execution:
						time_since_last = current_time - last_execution
						return time_since_last.total_seconds() >= hours * 3600
					return True
				except ValueError:
					pass
			elif schedule.endswith('d'):
				# 天间隔
				try:
					days = int(schedule[:-1])
					if last_execution:
						time_since_last = current_time - last_execution
						return time_since_last.total_seconds() >= days * 24 * 3600
					return True
				except ValueError:
					pass
			# TODO: 支持cron表达式解析

		# 默认逻辑：如果上次执行时间超过24小时，则执行
		if last_execution:
			time_since_last = current_time - last_execution
			return time_since_last.total_seconds() >= 24 * 3600

		return True

	async def _should_retry_task (self, task_id: str) -> bool:
		"""判断任务是否需要重试

		Args:
			task_id: 任务ID

		Returns:
			bool: 是否需要重试
		"""
		if task_id not in self.tasks:
			return False

		task_info = self.tasks[task_id]

		# 检查重试次数
		if task_info["retry_count"] >= 3:
			return False

		# 检查任务是否可重试
		if task_info["status"] in ["cancelled", "completed"]:
			return False

		return True

	async def _retry_task (self, task_id: str):
		"""重试任务

		Args:
			task_id: 任务ID
		"""
		if task_id not in self.tasks:
			return

		task_info = self.tasks[task_id]
		task_info["retry_count"] += 1
		task_info["status"] = "pending"
		task_info["updated_at"] = datetime.now()

		# 重新加入队列
		await self.task_queue.put(task_info)

		logger.info(f"重试任务: {task_id} (第{task_info['retry_count']}次)")

	async def _mark_task_failed (self, task_id: str, error_message: str):
		"""标记任务失败

		Args:
			task_id: 任务ID
			error_message: 错误消息
		"""
		if task_id not in self.tasks:
			return

		task_info = self.tasks[task_id]
		task_info["status"] = "failed"
		task_info["updated_at"] = datetime.now()

		self.stats["failed_tasks"] += 1
		logger.error(f"标记任务失败: {task_id}, 错误: {error_message}")

	async def _update_task_progress (self, task_id: str, progress: QualityTaskProgress):
		"""更新任务进度

		Args:
			task_id: 任务ID
			progress: 进度信息
		"""
		if task_id not in self.tasks:
			return

		task_info = self.tasks[task_id]
		task_info["progress"] = progress
		task_info["updated_at"] = datetime.now()

		# 发布进度更新事件
		await self._publish_event("quality_task_progress", {
			"task_id": task_id,
			"progress_percentage": progress.progress_percentage,
			"current_table": progress.current_table,
			"current_rule": progress.current_rule,
			"checked_tables": progress.checked_tables,
			"total_tables": progress.total_tables,
			"checked_rules": progress.checked_rules,
			"total_rules": progress.total_rules,
			"issues_found": progress.issues_found,
			"timestamp": datetime.now().isoformat()
		})

	def _generate_task_id (self, check_type: QualityCheckType) -> str:
		"""生成任务ID

		Args:
			check_type: 检查类型

		Returns:
			str: 任务ID
		"""
		self.task_counter += 1
		timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
		return f"quality_{check_type.value}_{timestamp}_{self.task_counter:06d}"

	def _generate_report (self, config: QualityTaskConfig, result: QualityTaskResult) -> str:
		"""生成质量检查报告

		Args:
			config: 任务配置
			result: 检查结果

		Returns:
			str: JSON格式的报告
		"""
		report = {
			"check_type": config.check_type.value,
			"target_tables": config.target_tables,
			"check_time": datetime.now().isoformat(),
			"summary": {
				"total_checks": result.total_checks,
				"passed_checks": result.passed_checks,
				"failed_checks": result.failed_checks,
				"issues_found": result.issues_found,
				"quality_score": result.quality_score,
				"duration_seconds": result.duration_seconds,
			},
			"issue_summary": result.issue_summary,
			"recommendations": self._generate_recommendations(result),
		}

		return json.dumps(report, ensure_ascii=False, indent=2)

	@staticmethod
	def _generate_recommendations (result: QualityTaskResult) -> List[str]:
		"""根据检查结果生成建议

		Args:
			result: 检查结果

		Returns:
			List[str]: 建议列表
		"""
		recommendations = []

		if result.quality_score < 80:
			recommendations.append("数据质量较低，建议进行全面数据清洗")

		if result.issue_summary.get("critical", 0) > 0:
			recommendations.append("发现严重问题，建议立即处理")

		if result.issue_summary.get("high", 0) > 5:
			recommendations.append("发现多个高风险问题，建议优先处理")

		if result.failed_checks > result.total_checks * 0.3:
			recommendations.append("检查失败率较高，建议检查规则配置")

		if not recommendations:
			recommendations.append("数据质量良好，继续保持")

		return recommendations

	@staticmethod
	def _aggregate_trend_data (trend_data: List[Dict[str, Any]], key_func, timestamp_func) -> List[Dict[str, Any]]:
		"""通用趋势数据聚合函数

		Args:
			trend_data: 原始趋势数据
			key_func: 生成聚合键的函数
			timestamp_func: 生成时间戳的函数

		Returns:
			List[Dict[str, Any]]: 聚合后的数据
		"""
		if not trend_data:
			return []

		aggregated = {}

		for entry in trend_data:
			timestamp = datetime.fromisoformat(entry["timestamp"])
			key = key_func(timestamp)

			if key not in aggregated:
				aggregated[key] = {
					"timestamp": timestamp_func(timestamp),
					"quality_score": 0,
					"total_checks": 0,
					"passed_checks": 0,
					"failed_checks": 0,
					"issues_found": 0,
					"count": 0
				}

			agg = aggregated[key]
			agg["quality_score"] += entry["quality_score"]
			agg["total_checks"] += entry["total_checks"]
			agg["passed_checks"] += entry["passed_checks"]
			agg["failed_checks"] += entry["failed_checks"]
			agg["issues_found"] += entry["issues_found"]
			agg["count"] += 1

		# 计算平均值
		result = []
		for key, agg in aggregated.items():
			if agg["count"] > 0:
				agg["quality_score"] /= agg["count"]
				result.append({
					"timestamp": agg["timestamp"],
					"quality_score": round(agg["quality_score"], 2),
					"total_checks": agg["total_checks"],
					"passed_checks": agg["passed_checks"],
					"failed_checks": agg["failed_checks"],
					"issues_found": agg["issues_found"]
				})

		result.sort(key=lambda x: x["timestamp"])
		return result

	@staticmethod
	def _aggregate_by_hour (trend_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		"""按小时聚合趋势数据

		Args:
			trend_data: 原始趋势数据

		Returns:
			List[Dict[str, Any]]: 聚合后的数据
		"""
		def hour_key_func(timestamp):
			return timestamp.strftime("%Y-%m-%d %H:00")

		def hour_timestamp_func(timestamp):
			return timestamp.strftime("%Y-%m-%d %H:00:00")

		return DataQualityEngine._aggregate_trend_data(trend_data, hour_key_func, hour_timestamp_func)

	@staticmethod
	def _aggregate_by_day (trend_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		"""按天聚合趋势数据

		Args:
			trend_data: 原始趋势数据

		Returns:
			List[Dict[str, Any]]: 聚合后的数据
		"""
		def day_key_func(timestamp):
			return timestamp.strftime("%Y-%m-%d")

		def day_timestamp_func(timestamp):
			return timestamp.strftime("%Y-%m-%d")

		return DataQualityEngine._aggregate_trend_data(trend_data, day_key_func, day_timestamp_func)

	@staticmethod
	def _aggregate_by_week (trend_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		"""按周聚合趋势数据

		Args:
			trend_data: 原始趋势数据

		Returns:
			List[Dict[str, Any]]: 聚合后的数据
		"""
		def week_key_func(timestamp):
			year, week, _ = timestamp.isocalendar()
			return f"{year}-W{week:02d}"

		def week_timestamp_func(timestamp):
			year, week, _ = timestamp.isocalendar()
			return f"{year}-W{week:02d}"

		return DataQualityEngine._aggregate_trend_data(trend_data, week_key_func, week_timestamp_func)

	def __str__ (self) -> str:
		"""字符串表示

		Returns:
			str: 引擎字符串表示
		"""
		return (f"DataQualityEngine(name='{self.config.name}', "
		        f"status={self.record.status.value}, "
		        f"tasks={len(self.tasks)}, "
		        f"active={len(self.active_tasks)})")


# ==================== 引擎工厂注册 ====================

def register_quality_engine ():
	"""注册数据质量检查引擎到工厂"""
	try:
		from quant_server.core.engines.utils.engine_factory import EngineFactory, EngineDescriptor
		from quant_server.core.engines.types.enums import EngineType, EngineCategory

		factory = EngineFactory()

		# 创建引擎描述符
		descriptor = EngineDescriptor(
			engine_type=EngineType.DATA_QUALITY,
			engine_class=DataQualityEngine,
			name="data_quality_engine",
			description="数据质量检查引擎，负责管理和执行数据质量检查任务",
			version="1.0.0",
			category=EngineCategory.DATA,
			dependencies=[EngineType.EVENT],  # 依赖事件引擎
			config_schema={
				"required": [],
				"default": {
					"max_concurrent_tasks": 2,
					"task_timeout_seconds": 3600,
					"enable_scheduler": True,
					"enable_auto_fix": False,
					"notification_channels": [],
					"health_check_interval": 60,
					"graceful_shutdown_timeout": 30
				}
			},
			tags=["data", "quality", "monitoring", "check"]
		)

		# 注册引擎
		factory.register_engine(descriptor)
		logger.info("数据质量检查引擎已注册到工厂")

		return True

	except Exception as e:
		logger.error(f"注册数据质量检查引擎失败: {e}")
		return False


# 导出引擎类和注册函数
__all__ = ["DataQualityEngine", "QualityCheckType", "QualityRuleType",
           "QualityRule", "QualityTaskConfig", "QualityTaskProgress", "QualityTaskResult",
           "register_quality_engine"]


# ==================== 便捷函数 ====================

async def create_data_quality_engine(
    config: Optional[Dict[str, Any]] = None,
    instance_name: Optional[str] = None
) -> DataQualityEngine:
    """
    创建数据质量检查引擎（便捷函数）

    Args:
        config: 引擎配置
        instance_name: 实例名称

    Returns:
        DataQualityEngine: 创建的引擎实例
    """
    from quant_server.core.engines.utils.engine_factory import create_engine
    from quant_server.core.engines.types.enums import EngineType

    engine = await create_engine(
        engine_type=EngineType.DATA_QUALITY,
        config=config,
        instance_name=instance_name
    )

    if isinstance(engine, DataQualityEngine):
        return engine
    else:
        raise TypeError(f"创建的引擎类型不正确，期望 DataQualityEngine，实际是 {type(engine).__name__}")


async def get_data_quality_engine(
    instance_name: str = "data_quality_engine"
) -> Optional[DataQualityEngine]:
    """
    获取数据质量检查引擎（便捷函数）

    Args:
        instance_name: 引擎实例名称

    Returns:
        Optional[DataQualityEngine]: 数据质量检查引擎实例
    """
    from quant_server.core.engines.utils.engine_factory import get_engine

    engine = await get_engine(instance_name)

    if engine and isinstance(engine, DataQualityEngine):
        return engine

    return None