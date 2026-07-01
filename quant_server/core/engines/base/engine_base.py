# -*- coding: utf-8 -*-
"""
核心引擎基类 - 量化交易系统引擎框架

基于混合架构设计原则，提供统一的生命周期管理、状态监控和资源管理基础框架。
位置：quant_server/core/engines/base/engine_base.py

设计原则：
1. 统一的生命周期管理（start/stop/restart/pause/resume）
2. 标准化的状态管理（状态枚举、转换验证、状态持久化）
3. 依赖注入和依赖管理（基于配置的依赖解析）
4. 事件驱动的内部通信（通过事件引擎解耦）
5. 统一的错误处理和恢复机制（重试策略、降级处理）
6. 标准化的监控接口（健康检查、性能指标、运行时统计）
7. 资源池管理（连接池、线程池、内存池）
8. 配置驱动（支持动态配置更新）

架构层次：
- 稳定层：提供稳定的引擎框架和基础设施
- 灵活层：支持业务引擎的快速扩展和定制
- 通信中枢：通过事件引擎实现模块间解耦

所有业务引擎（策略引擎、交易引擎、回测引擎等）都必须继承自此基类。
"""

import asyncio
import logging
import uuid
import traceback
from abc import ABC, abstractmethod
from dataclasses import field, dataclass, replace
from typing import Optional, Dict, Any, List, Set, Callable
from datetime import datetime
from enum import Enum
from contextlib import asynccontextmanager
from functools import wraps

# 导入系统核心类型定义
from core.events.engine_events import EngineLifecycleEvent

from ..types.entities import (
	EngineMetricsEntity,
	EngineConfigEntity,
)
from ..types.enums import (
	ComponentStatus,
	HealthStatus,
	PriorityLevel,
	EngineType,
	EngineErrorLevel,
	ResourceType
)
from ...exceptions import BusinessException

logger = logging.getLogger(__name__)


class EngineStatusValidator:
	"""
	引擎状态验证器

	实现状态机模式，确保引擎状态转换的合法性和一致性。
	基于设计文档中的状态转换规则，提供严格的验证机制。

	设计原则：
	1. 状态转换必须显式声明
	2. 支持状态转换钩子（前置/后置处理）
	3. 支持状态转换的回滚机制
	4. 提供状态转换历史追踪

	状态转换规则（设计文档定义）：
	UNINITIALIZED -> INITIALIZING
	INITIALIZING -> INITIALIZED | ERROR
	INITIALIZED -> STARTING | STOPPED
	STARTING -> RUNNING | ERROR
	RUNNING -> STOPPING | ERROR | DEGRADED
	STOPPING -> STOPPED | ERROR
	STOPPED -> STARTING | UNINITIALIZED
	ERROR -> STOPPED | STARTING
	DEGRADED -> RUNNING | STOPPING | ERROR
	"""

	# 定义有效的状态转换映射
	_VALID_TRANSITIONS = {
		ComponentStatus.UNINITIALIZED: [ComponentStatus.INITIALIZING],
		ComponentStatus.INITIALIZING: [ComponentStatus.INITIALIZED, ComponentStatus.ERROR],
		ComponentStatus.INITIALIZED: [ComponentStatus.STARTING, ComponentStatus.STOPPED],
		ComponentStatus.STARTING: [ComponentStatus.RUNNING, ComponentStatus.ERROR],
		ComponentStatus.RUNNING: [
			ComponentStatus.STOPPING,
			ComponentStatus.ERROR,
			ComponentStatus.DEGRADED,
			ComponentStatus.PAUSED  # 新增暂停状态
		],
		ComponentStatus.STOPPING: [ComponentStatus.STOPPED, ComponentStatus.ERROR],
		ComponentStatus.STOPPED: [ComponentStatus.STARTING, ComponentStatus.UNINITIALIZED],
		ComponentStatus.ERROR: [ComponentStatus.STOPPED, ComponentStatus.STARTING],
		ComponentStatus.DEGRADED: [
			ComponentStatus.RUNNING,
			ComponentStatus.STOPPING,
			ComponentStatus.ERROR
		],
		ComponentStatus.PAUSED: [
			ComponentStatus.RUNNING,
			ComponentStatus.STOPPING,
			ComponentStatus.ERROR
		]
	}

	# 定义状态转换钩子类型
	class TransitionHook(Enum):
		BEFORE = "before"  # 状态转换前执行
		AFTER = "after"  # 状态转换后执行
		ROLLBACK = "rollback"  # 状态转换回滚时执行

	def __init__ (self):
		"""初始化状态验证器"""
		self._transition_history: List[Dict[str, Any]] = []
		self._hooks: Dict[ComponentStatus, Dict[ComponentStatus, Dict[str, List[Callable]]]] = {}

	@classmethod
	def is_valid_transition (cls, current: ComponentStatus, next_status: ComponentStatus) -> bool:
		"""
		检查状态转换是否有效

		Args:
			current: 当前状态
			next_status: 目标状态

		Returns:
			bool: 转换是否有效

		Raises:
			ValueError: 当状态值无效时
		"""

		valid_transitions = cls._VALID_TRANSITIONS.get(current, [])
		return next_status in valid_transitions

	def register_transition_hook (
			self,
			from_state: ComponentStatus,
			to_state: ComponentStatus,
			hook_type: 'TransitionHook',
			hook_func: Callable
	):
		"""
		注册状态转换钩子

		Args:
			from_state: 起始状态
			to_state: 目标状态
			hook_type: 钩子类型
			hook_func: 钩子函数

		Raises:
			ValueError: 当钩子类型无效或转换不合法时
		"""
		if not self.is_valid_transition(from_state, to_state):
			raise ValueError(f"无效的状态转换: {from_state} -> {to_state}")

		if not isinstance(hook_type, self.TransitionHook):
			raise ValueError(f"无效的钩子类型: {hook_type}")

		# 初始化钩子存储结构
		if from_state not in self._hooks:
			self._hooks[from_state] = {}
		if to_state not in self._hooks[from_state]:
			self._hooks[from_state][to_state] = {
				self.TransitionHook.BEFORE.value: [],
				self.TransitionHook.AFTER.value: [],
				self.TransitionHook.ROLLBACK.value: []
			}

		self._hooks[from_state][to_state][hook_type.value].append(hook_func)
		logger.debug(f"注册状态转换钩子: {from_state}->{to_state} [{hook_type.value}]")

	async def execute_transition_hooks (
			self,
			from_state: ComponentStatus,
			to_state: ComponentStatus,
			hook_type: 'TransitionHook',
			context: Dict[str, Any] = None
	):
		"""
		执行状态转换钩子

		Args:
			from_state: 起始状态
			to_state: 目标状态
			hook_type: 钩子类型
			context: 钩子执行上下文

		Returns:
			bool: 所有钩子执行是否成功
		"""
		if context is None:
			context = {}

		# 获取钩子列表
		hooks = self._hooks.get(from_state, {}).get(to_state, {}).get(hook_type.value, [])

		for hook in hooks:
			try:
				if asyncio.iscoroutinefunction(hook):
					await hook(context)
				else:
					hook(context)
			except Exception as e:
				logger.error(f"状态转换钩子执行失败: {hook_type.value}, 错误: {e}")
				return False

		return True

	def record_transition (
			self,
			from_state: ComponentStatus,
			to_state: ComponentStatus,
			success: bool,
			error: str = None,
			metadata: Dict[str, Any] = None
	):
		"""
		记录状态转换历史

		Args:
			from_state: 起始状态
			to_state: 目标状态
			success: 是否成功
			error: 错误信息
			metadata: 附加元数据
		"""
		record = {
			"timestamp": datetime.now().isoformat(),
			"from_state": from_state.value,
			"to_state": to_state.value,
			"success": success,
			"error": error,
			"metadata": metadata or {},
			"stack_trace": traceback.format_stack() if not success else None
		}

		self._transition_history.append(record)

		# 限制历史记录长度
		if len(self._transition_history) > 1000:
			self._transition_history = self._transition_history[-1000:]

		logger.debug(f"记录状态转换: {from_state.value} -> {to_state.value} ({'成功' if success else '失败'})")

	def get_transition_history (
			self,
			limit: int = 100,
			filter_by_state: ComponentStatus = None
	) -> List[Dict[str, Any]]:
		"""
		获取状态转换历史

		Args:
			limit: 返回记录数量限制
			filter_by_state: 按状态过滤

		Returns:
			List[Dict[str, Any]]: 状态转换历史
		"""
		history = self._transition_history.copy()

		if filter_by_state:
			history = [
				record for record in history
				if record["to_state"] == filter_by_state.value or record["from_state"] == filter_by_state.value
			]

		return history[-limit:] if limit else history


@dataclass
class EngineRecord:
	"""
	引擎状态记录实体

	记录引擎的完整状态信息，支持序列化和持久化。
	基于设计文档中的引擎监控需求，提供全面的状态追踪。

	字段设计：
	- 基础标识：engine_id, engine_name, engine_type
	- 状态信息：status, health, error信息
	- 时间信息：生命周期时间戳
	- 运行时数据：性能指标、依赖关系
	- 元数据：自定义扩展数据
	"""

	# 基础标识字段
	engine_id: str
	engine_name: str
	engine_type: EngineType
	version: str = "1.0.0"

	# 状态字段
	status: ComponentStatus = ComponentStatus.UNINITIALIZED
	health: HealthStatus = HealthStatus.UNKNOWN
	error_message: Optional[str] = None
	error_level: Optional[EngineErrorLevel] = None
	error_details: Optional[Dict[str, Any]] = None

	# 时间字段
	created_at: datetime = field(default_factory=datetime.now)
	updated_at: datetime = field(default_factory=datetime.now)
	start_time: Optional[datetime] = None
	end_time: Optional[datetime] = None
	last_health_check: Optional[datetime] = None
	last_error_time: Optional[datetime] = None

	# 运行时字段
	dependencies: List[str] = field(default_factory=list)
	resource_usage: Dict[ResourceType, float] = field(default_factory=dict)
	performance_metrics: Dict[str, Any] = field(default_factory=dict)

	# 元数据字段
	metadata: Dict[str, Any] = field(default_factory=dict)

	def __post_init__ (self):
		"""数据类初始化后处理"""
		# 确保时间字段类型正确
		if isinstance(self.created_at, str):
			self.created_at = datetime.fromisoformat(self.created_at)
		if isinstance(self.updated_at, str):
			self.updated_at = datetime.fromisoformat(self.updated_at)

	def update_status (
			self,
			status: ComponentStatus,
			message: str = "",
			metadata: Dict[str, Any] = None
	):
		"""
		更新引擎状态

		Args:
			status: 新状态
			message: 状态更新消息
			metadata: 附加元数据
		"""
		old_status = self.status
		self.status = status
		self.updated_at = datetime.now()

		# 记录状态变更
		status_change = {
			"timestamp": self.updated_at.isoformat(),
			"old_status": old_status.value,
			"new_status": status.value,
			"message": message
		}

		# 更新元数据
		if "status_history" not in self.metadata:
			self.metadata["status_history"] = []
		self.metadata["status_history"].append(status_change)

		# 限制历史记录长度
		if len(self.metadata["status_history"]) > 100:
			self.metadata["status_history"] = self.metadata["status_history"][-100:]

		# 添加自定义元数据
		if metadata:
			self.metadata.update(metadata)

		logger.debug(f"引擎状态更新: {self.engine_name} [{old_status.value} -> {status.value}] {message}")

	def update_health (
			self,
			health: HealthStatus,
			reason: str = "",
			details: Dict[str, Any] = None
	):
		"""
		更新健康状态

		Args:
			health: 新健康状态
			reason: 原因描述
			details: 详细信息
		"""
		old_health = self.health
		self.health = health
		self.updated_at = datetime.now()
		self.last_health_check = datetime.now()

		# 记录健康状态变更
		health_change = {
			"timestamp": self.updated_at.isoformat(),
			"old_health": old_health.value,
			"new_health": health.value,
			"reason": reason,
			"details": details or {}
		}

		# 更新元数据
		if "health_history" not in self.metadata:
			self.metadata["health_history"] = []
		self.metadata["health_history"].append(health_change)

		# 限制历史记录长度
		if len(self.metadata["health_history"]) > 100:
			self.metadata["health_history"] = self.metadata["health_history"][-100:]

		logger.debug(f"引擎健康状态更新: {self.engine_name} [{old_health.value} -> {health.value}] {reason}")

	def record_error (
			self,
			error_message: str,
			error_level: EngineErrorLevel = EngineErrorLevel.ERROR,
			error_details: Dict[str, Any] = None
	):
		"""
		记录错误信息

		Args:
			error_message: 错误消息
			error_level: 错误级别
			error_details: 错误详情
		"""
		self.error_message = error_message
		self.error_level = error_level
		self.error_details = error_details or {}
		self.last_error_time = datetime.now()
		self.updated_at = datetime.now()

		# 记录错误历史
		error_record = {
			"timestamp": self.last_error_time.isoformat(),
			"message": error_message,
			"level": error_level.value,
			"details": self.error_details,
			"stack_trace": traceback.format_exc()
		}

		if "error_history" not in self.metadata:
			self.metadata["error_history"] = []
		self.metadata["error_history"].append(error_record)

		# 限制历史记录长度
		if len(self.metadata["error_history"]) > 100:
			self.metadata["error_history"] = self.metadata["error_history"][-100:]

		logger.error(f"引擎错误记录: {self.engine_name} [{error_level.value}] {error_message}")

	def clear_error (self):
		"""清除错误信息"""
		self.error_message = None
		self.error_level = None
		self.error_details = None
		self.updated_at = datetime.now()

		logger.debug(f"清除引擎错误: {self.engine_name}")

	def update_performance_metrics (self, metrics: Dict[str, Any]):
		"""
		更新性能指标

		Args:
			metrics: 性能指标字典
		"""
		self.performance_metrics.update(metrics)
		self.updated_at = datetime.now()

		# 记录指标更新时间戳
		self.metadata["last_metrics_update"] = self.updated_at.isoformat()

		logger.debug(f"更新引擎性能指标: {self.engine_name} - {metrics}")

	def update_resource_usage (self, resource_type: ResourceType, usage: float):
		"""
		更新资源使用情况

		Args:
			resource_type: 资源类型
			usage: 使用量（百分比或绝对值）
		"""
		self.resource_usage[resource_type] = usage
		self.updated_at = datetime.now()

		logger.debug(f"更新引擎资源使用: {self.engine_name} [{resource_type.value}] = {usage}")

	def get_uptime (self) -> Optional[float]:
		"""
		获取运行时长（秒）

		Returns:
			Optional[float]: 运行时长（秒），未运行则为None
		"""
		if self.start_time:
			if self.end_time:
				return (self.end_time - self.start_time).total_seconds()
			return (datetime.now() - self.start_time).total_seconds()
		return None

	def to_dict (self) -> Dict[str, Any]:
		"""
		转换为字典（支持序列化）

		Returns:
			Dict[str, Any]: 字典表示
		"""
		result = {
			"engine_id": self.engine_id,
			"engine_name": self.engine_name,
			"engine_type": self.engine_type.value,
			"version": self.version,
			"status": self.status.value,
			"health": self.health.value,
			"error_message": self.error_message,
			"error_level": self.error_level.value if self.error_level else None,
			"error_details": self.error_details,
			"created_at": self.created_at.isoformat(),
			"updated_at": self.updated_at.isoformat(),
			"start_time": self.start_time.isoformat() if self.start_time else None,
			"end_time": self.end_time.isoformat() if self.end_time else None,
			"last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
			"last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
			"dependencies": self.dependencies,
			"resource_usage": {k.value: v for k, v in self.resource_usage.items()},
			"performance_metrics": self.performance_metrics,
			"metadata": self.metadata
		}

		# 计算运行时长
		uptime = self.get_uptime()
		if uptime is not None:
			result["uptime"] = uptime

		return result

	def clone (self) -> 'EngineRecord':
		"""
		创建副本

		Returns:
			EngineRecord: 新的引擎记录副本
		"""
		import copy
		return EngineRecord(
			engine_id=self.engine_id,
			engine_name=self.engine_name,
			engine_type=self.engine_type,
			version=self.version,
			status=self.status,
			health=self.health,
			error_message=self.error_message,
			error_level=self.error_level,
			error_details=copy.deepcopy(self.error_details) if self.error_details else None,
			created_at=self.created_at,
			updated_at=self.updated_at,
			start_time=self.start_time,
			end_time=self.end_time,
			last_health_check=self.last_health_check,
			last_error_time=self.last_error_time,
			dependencies=copy.deepcopy(self.dependencies),
			resource_usage=copy.deepcopy(self.resource_usage),
			performance_metrics=copy.deepcopy(self.performance_metrics),
			metadata=copy.deepcopy(self.metadata)
		)


class EngineMetricsUpdater:
	"""
	EngineMetrics 更新器

	由于 EngineMetricsEntity 可能是一个不可变的数据类，
	这个类提供了安全地更新 EngineMetrics 的方法。
	"""

	@staticmethod
	def update_uptime (metrics: EngineMetricsEntity, uptime: float) -> EngineMetricsEntity:
		"""
		更新运行时长

		Args:
			metrics: 原始指标对象
			uptime: 运行时长（秒）

		Returns:
			EngineMetricsEntity: 更新后的指标对象
		"""
		# 如果 EngineMetricsEntity 有 update 方法，使用它
		if hasattr(metrics, 'update'):
			return metrics.update(uptime=uptime)
		# 否则尝试使用 replace 方法
		elif hasattr(metrics, 'replace'):
			return metrics.replace(uptime=uptime)
		# 最后尝试直接创建新对象
		else:
			try:
				return replace(metrics, uptime=uptime)
			except (ValueError, TypeError):
				# 如果都没有，创建新的字典并构建新对象
				metrics_dict = metrics.to_dict() if hasattr(metrics, 'to_dict') else {}
				metrics_dict['uptime'] = uptime
				return EngineMetricsEntity(**metrics_dict)

	@staticmethod
	def update_last_stop_time (metrics: EngineMetricsEntity, last_stop_time: datetime) -> EngineMetricsEntity:
		"""
		更新最后停止时间

		Args:
			metrics: 原始指标对象
			last_stop_time: 最后停止时间

		Returns:
			EngineMetricsEntity: 更新后的指标对象
		"""
		if hasattr(metrics, 'update'):
			return metrics.update(last_stop_time=last_stop_time)
		elif hasattr(metrics, 'replace'):
			return metrics.replace(last_stop_time=last_stop_time)
		else:
			try:
				return replace(metrics, last_stop_time=last_stop_time)
			except (ValueError, TypeError):
				metrics_dict = metrics.to_dict() if hasattr(metrics, 'to_dict') else {}
				metrics_dict['last_stop_time'] = last_stop_time
				return EngineMetricsEntity(**metrics_dict)

	@staticmethod
	def update_last_update_time (metrics: EngineMetricsEntity, last_update_time: datetime) -> EngineMetricsEntity:
		"""
		更新最后更新时间

		Args:
			metrics: 原始指标对象
			last_update_time: 最后更新时间

		Returns:
			EngineMetricsEntity: 更新后的指标对象
		"""
		if hasattr(metrics, 'update'):
			return metrics.update(last_update_time=last_update_time)
		elif hasattr(metrics, 'replace'):
			return metrics.replace(last_update_time=last_update_time)
		else:
			try:
				return replace(metrics, last_update_time=last_update_time)
			except (ValueError, TypeError):
				metrics_dict = metrics.to_dict() if hasattr(metrics, 'to_dict') else {}
				metrics_dict['last_update_time'] = last_update_time
				return EngineMetricsEntity(**metrics_dict)

	@staticmethod
	def update_last_success_time (metrics: EngineMetricsEntity, last_success_time: datetime) -> EngineMetricsEntity:
		"""
		更新最后成功时间

		Args:
			metrics: 原始指标对象
			last_success_time: 最后成功时间

		Returns:
			EngineMetricsEntity: 更新后的指标对象
		"""
		if hasattr(metrics, 'update'):
			return metrics.update(last_success_time=last_success_time)
		elif hasattr(metrics, 'replace'):
			return metrics.replace(last_success_time=last_success_time)
		else:
			try:
				return replace(metrics, last_success_time=last_success_time)
			except (ValueError, TypeError):
				metrics_dict = metrics.to_dict() if hasattr(metrics, 'to_dict') else {}
				metrics_dict['last_success_time'] = last_success_time
				return EngineMetricsEntity(**metrics_dict)

	@staticmethod
	def update_last_error_time (metrics: EngineMetricsEntity, last_error_time: datetime) -> EngineMetricsEntity:
		"""
		更新最后错误时间

		Args:
			metrics: 原始指标对象
			last_error_time: 最后错误时间

		Returns:
			EngineMetricsEntity: 更新后的指标对象
		"""
		if hasattr(metrics, 'update'):
			return metrics.update(last_error_time=last_error_time)
		elif hasattr(metrics, 'replace'):
			return metrics.replace(last_error_time=last_error_time)
		else:
			try:
				return replace(metrics, last_error_time=last_error_time)
			except (ValueError, TypeError):
				metrics_dict = metrics.to_dict() if hasattr(metrics, 'to_dict') else {}
				metrics_dict['last_error_time'] = last_error_time
				return EngineMetricsEntity(**metrics_dict)

	@staticmethod
	def increment_processed_events (metrics: EngineMetricsEntity) -> EngineMetricsEntity:
		"""
		增加处理事件计数

		Args:
			metrics: 原始指标对象

		Returns:
			EngineMetricsEntity: 更新后的指标对象
		"""
		current_count = getattr(metrics, 'processed_events', 0)
		if hasattr(metrics, 'update'):
			return metrics.update(processed_events=current_count + 1)
		elif hasattr(metrics, 'replace'):
			return metrics.replace(processed_events=current_count + 1)
		else:
			try:
				return replace(metrics, processed_events=current_count + 1)
			except (ValueError, TypeError):
				metrics_dict = metrics.to_dict() if hasattr(metrics, 'to_dict') else {}
				metrics_dict['processed_events'] = current_count + 1
				return EngineMetricsEntity(**metrics_dict)

	@staticmethod
	def increment_error_count (metrics: EngineMetricsEntity) -> EngineMetricsEntity:
		"""
		增加错误计数

		Args:
			metrics: 原始指标对象

		Returns:
			EngineMetricsEntity: 更新后的指标对象
		"""
		current_count = getattr(metrics, 'error_count', 0)
		if hasattr(metrics, 'update'):
			return metrics.update(error_count=current_count + 1)
		elif hasattr(metrics, 'replace'):
			return metrics.replace(error_count=current_count + 1)
		else:
			try:
				return replace(metrics, error_count=current_count + 1)
			except (ValueError, TypeError):
				metrics_dict = metrics.to_dict() if hasattr(metrics, 'to_dict') else {}
				metrics_dict['error_count'] = current_count + 1
				return EngineMetricsEntity(**metrics_dict)

	@staticmethod
	def update_metrics (metrics: EngineMetricsEntity, **kwargs) -> EngineMetricsEntity:
		"""
		通用更新方法

		Args:
			metrics: 原始指标对象
			**kwargs: 要更新的字段

		Returns:
			EngineMetricsEntity: 更新后的指标对象
		"""
		if hasattr(metrics, 'update'):
			return metrics.update(**kwargs)
		elif hasattr(metrics, 'replace'):
			return metrics.replace(**kwargs)
		else:
			try:
				return replace(metrics, **kwargs)
			except (ValueError, TypeError):
				metrics_dict = metrics.to_dict() if hasattr(metrics, 'to_dict') else {}
				metrics_dict.update(kwargs)
				return EngineMetricsEntity(**metrics_dict)


class EngineBase(ABC):
	"""
	引擎基类 - 统一生命周期管理框架

	基于混合架构设计原则，提供所有业务引擎的统一基础框架。
	实现设计文档中定义的所有核心功能：
	1. 生命周期管理（start/stop/restart/pause/resume）
	2. 状态管理（状态机、状态持久化、状态恢复）
	3. 依赖管理（依赖注入、依赖检查、循环依赖检测）
	4. 事件驱动通信（通过事件引擎解耦）
	5. 错误处理（重试机制、降级处理、熔断器）
	6. 监控和指标收集（健康检查、性能指标、运行时统计）
	7. 资源管理（连接池、线程池、内存管理）
	8. 配置管理（动态配置、配置验证、配置热更新）

	设计模式：
	- 模板方法模式：定义引擎生命周期骨架
	- 观察者模式：通过事件引擎实现解耦通信
	- 状态模式：管理引擎状态转换
	- 策略模式：支持不同的错误处理和重试策略
	- 工厂模式：支持引擎实例的创建和管理

	属性说明：
	- engine_id: 引擎唯一标识
	- config: 引擎配置实体
	- record: 引擎状态记录
	- metrics: 性能指标实体
	- dependencies: 依赖的引擎实例映射
	- event_engine: 事件引擎引用
	- resource_pool: 资源池管理器
	- retry_strategy: 重试策略配置
	- circuit_breaker: 熔断器实例
	"""

	def __init__ (
			self,
			config: EngineConfigEntity,
			event_engine=None,
			resource_pool=None
	):
		"""
		初始化引擎基类

		Args:
			config: 引擎配置实体，包含引擎的所有配置参数
			event_engine: 事件引擎实例，用于发布和订阅事件
			resource_pool: 资源池管理器，用于管理连接池等资源
		"""
		# 生成唯一标识（基于配置名称和UUID）
		self.engine_id = f"{config.name}_{uuid.uuid4().hex[:8]}"

		# 核心属性
		self.config = config
		self.event_engine = event_engine
		self.resource_pool = resource_pool

		# 状态管理
		self.record = EngineRecord(
			engine_id=self.engine_id,
			engine_name=config.name,
			engine_type=EngineType.CUSTOM,  # 子类需要重写engine_type属性
			dependencies=config.dependencies or []
		)

		# 性能指标
		self.metrics = EngineMetricsEntity()

		# 依赖管理
		self.dependencies: Dict[str, 'EngineBase'] = {}
		self.dependents: Set[str] = set()  # 依赖于本引擎的其他引擎

		# 异步任务和锁管理
		self.monitoring_task: Optional[asyncio.Task] = None
		self.background_tasks: Set[asyncio.Task] = set()
		self._state_lock = asyncio.Lock()  # 状态变更锁
		self._init_lock = asyncio.Lock()  # 初始化专用锁
		self.shutdown_event = asyncio.Event()  # 关闭事件
		self.pause_event = asyncio.Event()  # 暂停事件
		self.pause_event.set()  # 初始状态为运行

		# 重试策略
		self.retry_strategy = {
			"max_retries": getattr(config, 'max_retries', 3) or 3,
			"retry_delay": getattr(config, 'retry_delay', 1.0) or 1.0,
			"backoff_factor": getattr(config, 'backoff_factor', 2.0) or 2.0,
			"max_delay": getattr(config, 'max_delay', 30.0) or 30.0
		}

		# 状态验证器
		self.status_validator = EngineStatusValidator()

		# 错误处理配置
		self.error_handlers: Dict[EngineErrorLevel, Callable] = {}

		# 信号处理（用于优雅关闭）
		self._setup_signal_handlers()

		logger.info(f"引擎初始化完成: {self.config.name} ({self.engine_id})")

	# ==================== 属性访问器 ====================

	@property
	def engine_type (self) -> EngineType:
		"""
		获取引擎类型

		子类必须重写此属性，返回具体的引擎类型。

		Returns:
			EngineType: 引擎类型枚举
		"""
		return EngineType.CUSTOM

	@property
	def is_running (self) -> bool:
		"""
		检查引擎是否正在运行

		Returns:
			bool: 引擎是否处于运行状态
		"""
		return self.record.status == ComponentStatus.RUNNING

	@property
	def is_paused (self) -> bool:
		"""
		检查引擎是否暂停

		Returns:
			bool: 引擎是否处于暂停状态
		"""
		return self.record.status == ComponentStatus.PAUSED

	@property
	def is_healthy (self) -> bool:
		"""
		检查引擎是否健康

		Returns:
			bool: 引擎健康状态是否为HEALTHY
		"""
		return self.record.health == HealthStatus.HEALTHY

	@property
	def uptime (self) -> Optional[float]:
		"""
		获取运行时长

		Returns:
			Optional[float]: 运行时长（秒），未运行则为None
		"""
		return self.record.get_uptime()

	# ==================== 生命周期管理 ====================

	async def initialize (self) -> bool:
		"""
		初始化引擎

		执行引擎的初始化逻辑，包括配置验证、资源准备等。
		这是引擎生命周期的第一步。

		Returns:
			bool: 初始化是否成功

		Raises:
			RuntimeError: 当初始化失败时
		"""
		async with self._init_lock:
			# 检查当前状态
			if self.record.status != ComponentStatus.UNINITIALIZED:
				raise RuntimeError(
					f"引擎状态不正确，无法初始化: {self.record.status.value}"
				)

			# 验证状态转换
			if not self.status_validator.is_valid_transition(
					self.record.status, ComponentStatus.INITIALIZING
			):
				raise RuntimeError(
					f"无效的状态转换: {self.record.status.value} -> INITIALIZING"
				)

			# 执行状态转换钩子
			await self.status_validator.execute_transition_hooks(
				self.record.status,
				ComponentStatus.INITIALIZING,
				EngineStatusValidator.TransitionHook.BEFORE,
				{"engine": self}
			)

			# 更新状态
			self.record.update_status(ComponentStatus.INITIALIZING, "开始初始化引擎")
			logger.info(f"初始化引擎: {self.config.name}")

			try:
				# 验证配置
				self._validate_config()

				# 执行引擎特定的初始化逻辑
				await self._on_initialize()

				# 注册错误处理器
				self._register_default_error_handlers()

				# 更新状态
				self.record.update_status(ComponentStatus.INITIALIZED, "引擎初始化成功")
				self.record.update_health(HealthStatus.HEALTHY, "初始化成功")

				# 执行状态转换钩子
				await self.status_validator.execute_transition_hooks(
					ComponentStatus.INITIALIZING,
					ComponentStatus.INITIALIZED,
					EngineStatusValidator.TransitionHook.AFTER,
					{"engine": self}
				)

				# 记录状态转换
				self.status_validator.record_transition(
					ComponentStatus.UNINITIALIZED,
					ComponentStatus.INITIALIZED,
					True
				)

				# 发布初始化完成事件
				await self._publish_event("engine_initialized", {
					"engine_id": self.engine_id,
					"engine_name": self.config.name,
					"engine_type": self.engine_type.value,
					"timestamp": datetime.now().isoformat()
				})

				logger.info(f"引擎初始化成功: {self.config.name}")
				return True

			except Exception as e:
				# 记录错误
				self.record.record_error(
					f"初始化失败: {str(e)}",
					EngineErrorLevel.ERROR,
					{"exception_type": type(e).__name__}
				)

				# 更新状态
				self.record.update_status(ComponentStatus.ERROR, f"初始化失败: {str(e)}")
				self.record.update_health(HealthStatus.FAILED, f"初始化失败: {str(e)}")

				# 执行状态转换钩子
				await self.status_validator.execute_transition_hooks(
					ComponentStatus.INITIALIZING,
					ComponentStatus.ERROR,
					EngineStatusValidator.TransitionHook.AFTER,
					{"engine": self, "error": str(e)}
				)

				# 记录状态转换
				self.status_validator.record_transition(
					ComponentStatus.UNINITIALIZED,
					ComponentStatus.ERROR,
					False,
					str(e)
				)

				# 发布初始化失败事件
				await self._publish_event("engine_initialize_failed", {
					"engine_id": self.engine_id,
					"engine_name": self.config.name,
					"error": str(e),
					"timestamp": datetime.now().isoformat()
				})

				logger.error(f"引擎初始化失败: {self.config.name}, 错误: {e}")
				raise

	async def start (self) -> bool:
		"""
		启动引擎

		完整的启动流程，包括依赖检查、状态转换、资源初始化和监控启动。
		支持自动重试机制，基于配置的重试策略。

		Returns:
			bool: 启动是否成功

		Raises:
			RuntimeError: 当引擎已经运行或依赖检查失败时
			Exception: 启动过程中发生的任何异常
		"""
		async with self._state_lock:
			# 检查当前状态
			if self.record.status == ComponentStatus.RUNNING:
				logger.warning(f"引擎已在运行中: {self.config.name}")
				return True

			# 如果引擎未初始化，先初始化
			if self.record.status == ComponentStatus.UNINITIALIZED:
				await self.initialize()

			# 验证状态转换
			if not self.status_validator.is_valid_transition(
					self.record.status, ComponentStatus.STARTING
			):
				raise RuntimeError(
					f"无效的状态转换: {self.record.status.value} -> STARTING"
				)

			# 执行状态转换钩子
			await self.status_validator.execute_transition_hooks(
				self.record.status,
				ComponentStatus.STARTING,
				EngineStatusValidator.TransitionHook.BEFORE,
				{"engine": self}
			)

			# 更新状态
			old_status = self.record.status
			self.record.update_status(ComponentStatus.STARTING, "开始启动引擎")
			logger.info(f"启动引擎: {self.config.name}")

			# 启动重试逻辑
			max_retries = self.retry_strategy["max_retries"]
			retry_delay = self.retry_strategy["retry_delay"]
			backoff_factor = self.retry_strategy["backoff_factor"]
			max_delay = self.retry_strategy["max_delay"]

			for attempt in range(max_retries + 1):
				try:
					# 检查依赖
					await self._check_dependencies()

					# 执行引擎特定的启动逻辑
					await self._on_start()

					# 记录启动时间
					self.record.start_time = datetime.now()
					self.record.end_time = None  # 重置结束时间

					# 更新状态
					self.record.update_status(ComponentStatus.RUNNING, "引擎启动成功")
					self.record.update_health(HealthStatus.HEALTHY, "启动成功")
					self.record.clear_error()

					# 重置暂停事件
					self.pause_event.set()

					# 执行状态转换钩子
					await self.status_validator.execute_transition_hooks(
						ComponentStatus.STARTING,
						ComponentStatus.RUNNING,
						EngineStatusValidator.TransitionHook.AFTER,
						{"engine": self}
					)

					# 记录状态转换
					self.status_validator.record_transition(
						old_status,
						ComponentStatus.RUNNING,
						True
					)

					# 启动监控任务
					self.monitoring_task = asyncio.create_task(
						self._monitoring_loop(),
						name=f"engine_monitor_{self.config.name}"
					)

					# 启动后台任务
					await self._start_background_tasks()

					# 发布启动事件
					await self._publish_event("engine_started", {
						"engine_id": self.engine_id,
						"engine_name": self.config.name,
						"engine_type": self.engine_type.value,
						"start_time": self.record.start_time.isoformat(),
						"config": self.config.to_dict(),
						"attempt": attempt + 1
					})

					logger.info(f"引擎启动成功: {self.config.name} (尝试次数: {attempt + 1})")
					return True

				except (RuntimeError, ValueError, TypeError, ConnectionError) as e:
					# 记录错误
					self.record.record_error(
						f"启动失败: {str(e)}",
						EngineErrorLevel.ERROR,
						{
							"exception_type": type(e).__name__,
							"attempt": attempt + 1,
							"max_retries": max_retries
						}
					)

					if attempt < max_retries:
						# 计算等待时间（指数退避）
						wait_time = min(
							retry_delay * (backoff_factor ** attempt),
							max_delay
						)

						logger.warning(
							f"引擎启动失败，将在 {wait_time:.1f} 秒后重试 "
							f"({attempt + 1}/{max_retries}): {e}"
						)

						# 执行状态转换钩子
						await self.status_validator.execute_transition_hooks(
							ComponentStatus.STARTING,
							ComponentStatus.ERROR,
							EngineStatusValidator.TransitionHook.ROLLBACK,
							{"engine": self, "error": str(e), "attempt": attempt}
						)

						# 等待重试
						await asyncio.sleep(wait_time)
					else:
						# 超过最大重试次数，标记为错误状态
						self.record.update_status(ComponentStatus.ERROR, f"启动失败: {str(e)}")
						self.record.update_health(HealthStatus.FAILED, f"启动失败: {str(e)}")

						# 执行状态转换钩子
						await self.status_validator.execute_transition_hooks(
							ComponentStatus.STARTING,
							ComponentStatus.ERROR,
							EngineStatusValidator.TransitionHook.AFTER,
							{"engine": self, "error": str(e)}
						)

						# 记录状态转换
						self.status_validator.record_transition(
							old_status,
							ComponentStatus.ERROR,
							False,
							str(e),
							{"attempts": attempt + 1}
						)

						# 发布错误事件
						await self._publish_event("engine_start_failed", {
							"engine_id": self.engine_id,
							"engine_name": self.config.name,
							"error": str(e),
							"attempts": attempt + 1,
							"timestamp": datetime.now().isoformat()
						})

						logger.error(f"引擎启动失败，超过最大重试次数: {self.config.name}, 错误: {e}")
						raise
				except Exception as e:
					# 捕获其他异常
					self.record.record_error(
						f"启动失败: {str(e)}",
						EngineErrorLevel.CRITICAL,
						{
							"exception_type": type(e).__name__,
							"attempt": attempt + 1,
							"max_retries": max_retries
						}
					)
					raise

			return False

	async def stop (self, force: bool = False, timeout: float = 30.0) -> bool:
		"""
		停止引擎

		优雅停止引擎，首先尝试优雅停止，如果超时则强制停止。
		支持超时控制和强制停止选项。

		Args:
			force: 是否强制停止（跳过优雅停止）
			timeout: 停止超时时间（秒）

		Returns:
			bool: 停止是否成功

		Raises:
			RuntimeError: 停止过程中发生错误
			asyncio.TimeoutError: 停止超时
		"""
		async with self._state_lock:
			# 检查当前状态
			if self.record.status == ComponentStatus.STOPPED:
				logger.info(f"引擎已经停止: {self.config.name}")
				return True

			# 验证状态转换（错误状态可以直接停止）
			if (self.record.status != ComponentStatus.ERROR and
					not self.status_validator.is_valid_transition(
						self.record.status, ComponentStatus.STOPPING
					)):
				raise RuntimeError(
					f"无效的状态转换: {self.record.status.value} -> STOPPING"
				)

			# 执行状态转换钩子
			await self.status_validator.execute_transition_hooks(
				self.record.status,
				ComponentStatus.STOPPING,
				EngineStatusValidator.TransitionHook.BEFORE,
				{"engine": self, "force": force, "timeout": timeout}
			)

			# 更新状态
			previous_status = self.record.status
			self.record.update_status(ComponentStatus.STOPPING, "开始停止引擎")
			logger.info(f"停止引擎: {self.config.name}")

			try:
				# 设置关闭事件
				self.shutdown_event.set()

				# 停止监控任务
				if self.monitoring_task:
					self.monitoring_task.cancel()
					try:
						await asyncio.wait_for(self.monitoring_task, timeout=5.0)
					except (asyncio.CancelledError, asyncio.TimeoutError):
						pass
					finally:
						self.monitoring_task = None

				# 停止后台任务
				await self._stop_background_tasks()

				# 执行引擎特定的停止逻辑
				if not force:
					# 尝试优雅停止
					try:
						await asyncio.wait_for(self._on_stop(), timeout=timeout)
					except asyncio.TimeoutError:
						logger.warning(f"优雅停止超时，尝试强制停止: {self.config.name}")
						if force:
							await self._on_force_stop()
						else:
							raise
				else:
					# 强制停止
					await self._on_force_stop()

				# 更新状态
				self.record.update_status(ComponentStatus.STOPPED, "引擎停止成功")
				self.record.end_time = datetime.now()

				# 计算运行时长
				uptime = self.record.get_uptime()

				# 使用 EngineMetricsUpdater 更新指标
				self.metrics = EngineMetricsUpdater.update_uptime(self.metrics, uptime or 0)
				self.metrics = EngineMetricsUpdater.update_last_stop_time(self.metrics, self.record.end_time)

				# 执行状态转换钩子
				await self.status_validator.execute_transition_hooks(
					ComponentStatus.STOPPING,
					ComponentStatus.STOPPED,
					EngineStatusValidator.TransitionHook.AFTER,
					{"engine": self, "uptime": uptime}
				)

				# 记录状态转换
				self.status_validator.record_transition(
					previous_status,
					ComponentStatus.STOPPED,
					True,
					metadata={"uptime": uptime, "force": force}
				)

				# 发布停止事件
				await self._publish_event("engine_stopped", {
					"engine_id": self.engine_id,
					"engine_name": self.config.name,
					"previous_status": previous_status.value,
					"uptime": uptime,
					"end_time": self.record.end_time.isoformat(),
					"force": force,
					"metrics": self.metrics.to_dict()
				})

				logger.info(f"引擎停止成功: {self.config.name}, 运行时长: {uptime:.1f}秒")
				return True

			except (asyncio.TimeoutError, RuntimeError) as e:
				# 记录错误
				self.record.record_error(
					f"停止失败: {str(e)}",
					EngineErrorLevel.ERROR,
					{"exception_type": type(e).__name__, "force": force}
				)

				# 更新状态
				self.record.update_status(ComponentStatus.ERROR, f"停止失败: {str(e)}")
				self.record.update_health(HealthStatus.FAILED, f"停止失败: {str(e)}")

				# 执行状态转换钩子
				await self.status_validator.execute_transition_hooks(
					ComponentStatus.STOPPING,
					ComponentStatus.ERROR,
					EngineStatusValidator.TransitionHook.AFTER,
					{"engine": self, "error": str(e)}
				)

				# 记录状态转换
				self.status_validator.record_transition(
					previous_status,
					ComponentStatus.ERROR,
					False,
					str(e),
					{"force": force}
				)

				# 发布错误事件
				await self._publish_event("engine_stop_failed", {
					"engine_id": self.engine_id,
					"engine_name": self.config.name,
					"error": str(e),
					"force": force,
					"timestamp": datetime.now().isoformat()
				})

				logger.error(f"引擎停止失败: {self.config.name}, 错误: {e}")
				raise
			except Exception as e:
				# 捕获其他异常
				self.record.record_error(
					f"停止失败: {str(e)}",
					EngineErrorLevel.CRITICAL,
					{"exception_type": type(e).__name__, "force": force}
				)
				raise

	async def restart (self) -> bool:
		"""
		重启引擎

		先停止再启动，提供原子性的重启操作。
		支持优雅重启和热重启选项。

		Returns:
			bool: 重启是否成功
		"""
		logger.info(f"重启引擎: {self.config.name}")

		try:
			# 发布重启开始事件
			await self._publish_event("engine_restart_started", {
				"engine_id": self.engine_id,
				"engine_name": self.config.name,
				"timestamp": datetime.now().isoformat()
			})

			# 先停止引擎
			await self.stop()

			# 重置关闭事件
			self.shutdown_event.clear()

			# 重置结束时间
			self.record.end_time = None

			# 再启动引擎
			result = await self.start()

			# 发布重启完成事件
			await self._publish_event("engine_restart_completed", {
				"engine_id": self.engine_id,
				"engine_name": self.config.name,
				"success": result,
				"timestamp": datetime.now().isoformat()
			})

			return result

		except (RuntimeError, ValueError) as e:
			logger.error(f"引擎重启失败: {self.config.name}, 错误: {e}")

			# 发布重启失败事件
			await self._publish_event("engine_restart_failed", {
				"engine_id": self.engine_id,
				"engine_name": self.config.name,
				"error": str(e),
				"timestamp": datetime.now().isoformat()
			})

			raise
		except Exception as e:
			logger.error(f"引擎重启失败: {self.config.name}, 错误: {e}")
			raise

	async def pause (self) -> bool:
		"""
		暂停引擎

		暂停引擎的执行，但保持资源状态。
		适用于临时停止处理但不释放资源的场景。

		Returns:
			bool: 暂停是否成功
		"""
		async with self._state_lock:
			# 检查当前状态
			if self.record.status != ComponentStatus.RUNNING:
				raise RuntimeError(f"引擎不在运行状态，无法暂停: {self.record.status.value}")

			# 验证状态转换
			if not self.status_validator.is_valid_transition(
					ComponentStatus.RUNNING, ComponentStatus.PAUSED
			):
				raise RuntimeError(f"无法从运行状态转换到暂停状态")

			# 执行状态转换钩子
			await self.status_validator.execute_transition_hooks(
				ComponentStatus.RUNNING,
				ComponentStatus.PAUSED,
				EngineStatusValidator.TransitionHook.BEFORE,
				{"engine": self}
			)

			# 更新状态
			self.record.update_status(ComponentStatus.PAUSED, "暂停引擎")
			self.pause_event.clear()  # 设置暂停事件

			# 执行引擎特定的暂停逻辑
			await self._on_pause()

			# 执行状态转换钩子
			await self.status_validator.execute_transition_hooks(
				ComponentStatus.RUNNING,
				ComponentStatus.PAUSED,
				EngineStatusValidator.TransitionHook.AFTER,
				{"engine": self}
			)

			# 记录状态转换
			self.status_validator.record_transition(
				ComponentStatus.RUNNING,
				ComponentStatus.PAUSED,
				True
			)

			# 发布暂停事件
			await self._publish_event("engine_paused", {
				"engine_id": self.engine_id,
				"engine_name": self.config.name,
				"timestamp": datetime.now().isoformat()
			})

			logger.info(f"引擎已暂停: {self.config.name}")
			return True

	async def resume (self) -> bool:
		"""
		恢复引擎

		从暂停状态恢复执行。

		Returns:
			bool: 恢复是否成功
		"""
		async with self._state_lock:
			# 检查当前状态
			if self.record.status != ComponentStatus.PAUSED:
				raise RuntimeError(f"引擎不在暂停状态，无法恢复: {self.record.status.value}")

			# 验证状态转换
			if not self.status_validator.is_valid_transition(
					ComponentStatus.PAUSED, ComponentStatus.RUNNING
			):
				raise RuntimeError(f"无法从暂停状态转换到运行状态")

			# 执行状态转换钩子
			await self.status_validator.execute_transition_hooks(
				ComponentStatus.PAUSED,
				ComponentStatus.RUNNING,
				EngineStatusValidator.TransitionHook.BEFORE,
				{"engine": self}
			)

			# 更新状态
			self.record.update_status(ComponentStatus.RUNNING, "恢复引擎")
			self.pause_event.set()  # 清除暂停事件

			# 执行引擎特定的恢复逻辑
			await self._on_resume()

			# 执行状态转换钩子
			await self.status_validator.execute_transition_hooks(
				ComponentStatus.PAUSED,
				ComponentStatus.RUNNING,
				EngineStatusValidator.TransitionHook.AFTER,
				{"engine": self}
			)

			# 记录状态转换
			self.status_validator.record_transition(
				ComponentStatus.PAUSED,
				ComponentStatus.RUNNING,
				True
			)

			# 发布恢复事件
			await self._publish_event("engine_resumed", {
				"engine_id": self.engine_id,
				"engine_name": self.config.name,
				"timestamp": datetime.now().isoformat()
			})

			logger.info(f"引擎已恢复: {self.config.name}")
			return True

	# ==================== 依赖管理 ====================

	def add_dependency (self, engine: 'EngineBase'):
		"""
		添加引擎依赖

		建立引擎间的依赖关系，用于依赖检查和启动顺序控制。

		Args:
			engine: 依赖的引擎实例
		"""
		if engine.config.name in self.dependencies:
			logger.warning(f"引擎依赖已存在: {self.config.name} -> {engine.config.name}")
			return

		# 检查循环依赖
		if self._check_circular_dependency(engine):
			raise RuntimeError(f"检测到循环依赖: {self.config.name} -> {engine.config.name}")

		self.dependencies[engine.config.name] = engine
		engine.add_dependent(self.engine_id)

		# 更新记录中的依赖列表
		if engine.config.name not in self.record.dependencies:
			self.record.dependencies.append(engine.config.name)

		logger.debug(f"添加引擎依赖: {self.config.name} -> {engine.config.name}")

	def add_dependent (self, engine_id: str):
		"""
		添加依赖于本引擎的引擎

		Args:
			engine_id: 依赖于本引擎的引擎ID
		"""
		self.dependents.add(engine_id)
		logger.debug(f"添加依赖引擎: {engine_id} -> {self.config.name}")

	def remove_dependency (self, engine_name: str):
		"""
		移除引擎依赖

		Args:
			engine_name: 依赖的引擎名称
		"""
		if engine_name in self.dependencies:
			engine = self.dependencies[engine_name]
			engine.remove_dependent(self.engine_id)
			del self.dependencies[engine_name]

			# 更新记录中的依赖列表
			if engine_name in self.record.dependencies:
				self.record.dependencies.remove(engine_name)

			logger.debug(f"移除引擎依赖: {self.config.name} -> {engine_name}")

	def remove_dependent (self, engine_id: str):
		"""
		移除依赖于本引擎的引擎

		Args:
			engine_id: 依赖于本引擎的引擎ID
		"""
		if engine_id in self.dependents:
			self.dependents.remove(engine_id)
			logger.debug(f"移除依赖引擎: {engine_id} -> {self.config.name}")

	async def _check_dependencies (self):
		"""
		检查引擎依赖

		确保所有依赖的引擎都处于运行状态。
		如果依赖不满足，抛出异常。
		"""
		missing_deps = []
		unhealthy_deps = []

		for dep_name in self.config.dependencies or []:
			if dep_name not in self.dependencies:
				missing_deps.append(dep_name)
				continue

			dep_engine = self.dependencies[dep_name]
			if dep_engine.record.status != ComponentStatus.RUNNING:
				unhealthy_deps.append(f"{dep_name}({dep_engine.record.status.value})")

			# 检查依赖的健康状态
			if dep_engine.record.health != HealthStatus.HEALTHY:
				logger.warning(f"依赖引擎健康状态不佳: {dep_name} ({dep_engine.record.health.value})")

		if missing_deps:
			raise RuntimeError(f"缺少依赖的引擎: {missing_deps}")

		if unhealthy_deps:
			raise RuntimeError(f"依赖引擎未运行: {unhealthy_deps}")

	def _check_circular_dependency (self, engine: 'EngineBase', visited: Set[str] = None) -> bool:
		"""
		检查循环依赖

		Args:
			engine: 要检查的引擎
			visited: 已访问的引擎集合

		Returns:
			bool: 是否存在循环依赖
		"""
		if visited is None:
			visited = set()

		# 如果引擎已经在访问路径中，存在循环依赖
		if engine.engine_id in visited:
			return True

		visited.add(engine.engine_id)

		# 递归检查引擎的依赖
		for dep_engine in engine.dependencies.values():
			if self._check_circular_dependency(dep_engine, visited.copy()):
				return True

		return False

	# ==================== 健康检查和监控 ====================

	async def health_check (self) -> Dict[str, Any]:
		"""
		执行健康检查

		检查引擎的健康状态，返回详细的健康信息。
		包括引擎状态、依赖健康、性能指标等。

		Returns:
			Dict[str, Any]: 健康检查结果，包括状态、指标和详细信息
		"""
		health_info = {
			"engine_id": self.engine_id,
			"engine_name": self.config.name,
			"engine_type": self.engine_type.value,
			"status": self.record.status.value,
			"health": self.record.health.value,
			"uptime": self.record.get_uptime(),
			"error_message": self.record.error_message,
			"error_level": self.record.error_level.value if self.record.error_level else None,
			"dependencies": list(self.dependencies.keys()),
			"dependents": list(self.dependents),
			"metrics": self.metrics.to_dict(),
			"resource_usage": {k.value: v for k, v in self.record.resource_usage.items()},
			"performance_metrics": self.record.performance_metrics,
			"timestamp": datetime.now().isoformat(),
			"config_summary": {
				"name": self.config.name,
				"description": getattr(self.config, 'description', ''),
				"version": getattr(self.config, 'version', '1.0.0'),
				"max_retries": getattr(self.config, 'max_retries', 3),
				"health_check_interval": getattr(self.config, 'health_check_interval', 5.0)
			}
		}

		# 执行引擎特定的健康检查
		engine_health = await self._on_health_check()
		if engine_health:
			health_info.update({"engine_specific": engine_health})

		# 检查依赖的健康状态
		dependency_health = {}
		all_dependencies_healthy = True

		for dep_name, dep_engine in self.dependencies.items():
			try:
				dep_health = await dep_engine.health_check()
				dependency_health[dep_name] = dep_health

				# 如果依赖不健康，本引擎也可能降级
				if (dep_health["health"] in [HealthStatus.UNHEALTHY.value, HealthStatus.FAILED.value] and
						self.record.health == HealthStatus.HEALTHY):
					self.record.update_health(HealthStatus.DEGRADED, f"依赖 {dep_name} 不健康")
					health_info["health"] = HealthStatus.DEGRADED.value
					all_dependencies_healthy = False

			except (RuntimeError, ValueError) as e:
				dependency_health[dep_name] = {"error": str(e), "health": HealthStatus.FAILED.value}
				logger.warning(f"检查依赖健康状态失败: {dep_name}, 错误: {e}")
				all_dependencies_healthy = False
			except Exception as e:
				dependency_health[dep_name] = {"error": str(e), "health": HealthStatus.FAILED.value}
				logger.warning(f"检查依赖健康状态失败: {dep_name}, 错误: {e}")
				all_dependencies_healthy = False

		health_info["dependency_health"] = dependency_health
		health_info["all_dependencies_healthy"] = all_dependencies_healthy

		# 更新最后一次健康检查时间
		self.record.last_health_check = datetime.now()

		# 如果没有错误且依赖都健康，更新为健康状态
		if (not self.record.error_message and
				all_dependencies_healthy and
				self.record.health != HealthStatus.HEALTHY and
				self.record.status == ComponentStatus.RUNNING):
			self.record.update_health(HealthStatus.HEALTHY, "健康检查通过")
			health_info["health"] = HealthStatus.HEALTHY.value

		return health_info

	async def _monitoring_loop (self):
		"""
		监控循环

		定期执行健康检查和指标收集。
		在引擎停止时自动退出。
		"""
		logger.info(f"启动引擎监控循环: {self.config.name}")

		check_interval = getattr(self.config, 'health_check_interval', 5.0) or 5.0

		try:
			while self.record.status == ComponentStatus.RUNNING:
				try:
					# 等待暂停事件（如果引擎被暂停）
					await self.pause_event.wait()

					# 检查是否应该关闭
					if self.shutdown_event.is_set():
						break

					# 执行健康检查
					health_info = await self.health_check()

					# 发布健康状态事件
					await self._publish_event("engine_health_check", health_info)

					# 收集性能指标
					await self._collect_metrics()

					# 收集系统资源指标
					await self._collect_system_metrics()

					# 等待下次检查
					await asyncio.sleep(check_interval)

				except asyncio.CancelledError:
					# 任务被取消，正常退出，重新抛出异常
					raise
				except (RuntimeError, ValueError) as e:
					logger.error(f"监控循环异常: {self.config.name}, 错误: {e}")

					# 记录错误但不停止监控
					self.record.record_error(
						f"监控循环异常: {str(e)}",
						EngineErrorLevel.WARNING
					)

					# 短暂等待后继续
					await asyncio.sleep(min(check_interval, 1.0))
				except Exception as e:
					logger.error(f"监控循环异常: {self.config.name}, 错误: {e}")
					await asyncio.sleep(min(check_interval, 1.0))

		except asyncio.CancelledError:
			# 任务被取消是正常的，重新抛出异常
			logger.info(f"引擎监控循环被取消: {self.config.name}")
			raise
		except Exception as e:
			logger.error(f"监控循环意外退出: {self.config.name}, 错误: {e}")
		finally:
			logger.info(f"引擎监控循环结束: {self.config.name}")

	async def _collect_metrics (self):
		"""
		收集性能指标

		子类可以重写此方法以收集特定指标。
		基类收集通用指标（如处理事件数、错误数等）。
		"""
		# 使用 EngineMetricsUpdater 更新最后更新时间
		self.metrics = EngineMetricsUpdater.update_last_update_time(self.metrics, datetime.now())

		# 子类可以在这里添加特定指标收集
		await self._on_collect_metrics()

	async def _collect_system_metrics (self):
		"""
		收集系统资源指标

		收集CPU、内存等系统资源使用情况。
		需要psutil库支持。
		"""
		# 预先定义变量，避免引用前未赋值

		try:
			import psutil
			psutil_module = psutil
			import os
		except ImportError:
			# psutil不可用，跳过系统指标收集
			if not hasattr(self, "_psutil_warning_logged"):
				logger.debug("psutil未安装，跳过系统指标收集")
				self._psutil_warning_logged = True
			return

		try:
			process = psutil_module.Process(os.getpid())

			# 收集内存使用情况
			memory_info = process.memory_info()
			self.record.update_resource_usage(ResourceType.MEMORY, memory_info.rss / 1024 / 1024)  # MB

			# 收集CPU使用率
			cpu_percent = process.cpu_percent(interval=0.1)
			self.record.update_resource_usage(ResourceType.CPU, cpu_percent)

			# 收集线程数
			thread_count = process.num_threads()
			self.record.update_resource_usage(ResourceType.THREADS, thread_count)

			# 收集网络连接数（使用net_connections方法）
			if hasattr(process, 'net_connections'):
				try:
					connections = process.net_connections()
					self.record.update_resource_usage(ResourceType.NETWORK_CONNECTIONS, len(connections))
				except (psutil_module.AccessDenied, psutil_module.NoSuchProcess):
					pass

			# 更新性能指标
			self.record.update_performance_metrics({
				"memory_rss_mb": memory_info.rss / 1024 / 1024,
				"memory_vms_mb": memory_info.vms / 1024 / 1024,
				"cpu_percent": cpu_percent,
				"thread_count": thread_count,
				"create_time": process.create_time()
			})

		except (psutil_module.AccessDenied, psutil_module.NoSuchProcess) as e:
			logger.debug(f"收集系统指标失败（权限或进程问题）: {self.config.name}, 错误: {e}")
		except Exception as e:
			logger.debug(f"收集系统指标失败: {self.config.name}, 错误: {e}")

	# ==================== 事件处理 ====================

	async def _publish_event (self, event_type: str, data: Dict[str, Any]):
		"""
		发布事件到事件引擎

		Args:
			event_type: 事件类型
			data: 事件数据
		"""
		if self.event_engine:
			try:
				event = EngineLifecycleEvent(
					engine_name=self.config.name,
					lifecycle_stage=event_type.replace("engine_", ""),
					engine_status=self.get_status().value if hasattr(self, 'get_status') else "unknown",
					details=data,
					priority=PriorityLevel.NORMAL.value,
				)

				await self.event_engine.put(event)

				# 使用 EngineMetricsUpdater 更新指标
				self.metrics = EngineMetricsUpdater.increment_processed_events(self.metrics)
				self.metrics = EngineMetricsUpdater.update_last_success_time(self.metrics, datetime.now())

				logger.debug("引擎发布事件: %s | 引擎: %s", event_type, self.config.name)

			except (RuntimeError, ValueError) as e:
				logger.error(f"发布事件失败: {self.config.name}, 错误: {e}")

				# 使用 EngineMetricsUpdater 更新错误指标
				self.metrics = EngineMetricsUpdater.increment_error_count(self.metrics)
				self.metrics = EngineMetricsUpdater.update_last_error_time(self.metrics, datetime.now())

				# 记录错误但不抛出异常
				self.record.record_error(
					f"发布事件失败: {str(e)}",
					EngineErrorLevel.WARNING,
					{"event_type": event_type}
				)
			except Exception as e:
				logger.error(f"发布事件失败: {self.config.name}, 错误: {e}")
				self.record.record_error(
					f"发布事件失败: {str(e)}",
					EngineErrorLevel.WARNING,
					{"event_type": event_type}
				)

	async def _handle_event (self, event: EngineLifecycleEvent):
		"""
		处理事件

		子类可以重写此方法来处理特定事件。

		Args:
			event: 事件实体
		"""
		# 基类提供默认的事件处理逻辑
		if event.event_type == "engine_command":
			await self._handle_engine_command(event.data)
		elif event.event_type == "config_update":
			await self._handle_config_update(event.data)

		# 调用子类的事件处理
		await self._on_handle_event(event)

	async def _handle_engine_command (self, command_data: Dict[str, Any]):
		"""
		处理引擎命令

		Args:
			command_data: 命令数据
		"""
		command = command_data.get("command")

		if command == "restart":
			await self.restart()
		elif command == "pause":
			await self.pause()
		elif command == "resume":
			await self.resume()
		elif command == "health_check":
			# 立即执行健康检查
			health_info = await self.health_check()
			await self._publish_event("engine_health_check_immediate", health_info)
		elif command == "get_status":
			# 返回状态信息
			status_info = self.get_status_info()
			await self._publish_event("engine_status_response", {
				"engine_id": self.engine_id,
				"status": status_info
			})

	async def _handle_config_update (self, config_data: Dict[str, Any]):
		"""
		处理配置更新

		Args:
			config_data: 配置数据
		"""
		# 验证配置数据
		if not self._validate_config_update(config_data):
			logger.error(f"配置更新验证失败: {self.config.name}")
			return

		# 应用配置更新
		await self._apply_config_update(config_data)

		logger.info(f"引擎配置已更新: {self.config.name}")

		# 发布配置更新事件
		await self._publish_event("engine_config_updated", {
			"engine_id": self.engine_id,
			"engine_name": self.config.name,
			"config_changes": config_data,
			"timestamp": datetime.now().isoformat()
		})

	# ==================== 错误处理 ====================

	def _register_default_error_handlers (self):
		"""注册默认的错误处理器"""
		self.error_handlers = {
			EngineErrorLevel.DEBUG: self._handle_debug_error,
			EngineErrorLevel.INFO: self._handle_info_error,
			EngineErrorLevel.WARNING: self._handle_warning_error,
			EngineErrorLevel.ERROR: self._handle_error_error,
			EngineErrorLevel.CRITICAL: self._handle_critical_error
		}

	def register_error_handler (self, error_level: EngineErrorLevel, handler: Callable):
		"""
		注册错误处理器

		Args:
			error_level: 错误级别
			handler: 错误处理函数
		"""
		self.error_handlers[error_level] = handler
		logger.debug(f"注册错误处理器: {error_level.value} -> {handler.__name__}")

	async def handle_error (
			self,
			error: Exception,
			error_level: EngineErrorLevel = EngineErrorLevel.ERROR,
			context: Dict[str, Any] = None
	):
		"""
		处理错误

		Args:
			error: 异常对象
			error_level: 错误级别
			context: 错误上下文
		"""
		# 记录错误
		self.record.record_error(
			str(error),
			error_level,
			{
				"exception_type": type(error).__name__,
				"context": context or {},
				"stack_trace": traceback.format_exc()
			}
		)

		# 使用 EngineMetricsUpdater 更新错误指标
		self.metrics = EngineMetricsUpdater.increment_error_count(self.metrics)
		self.metrics = EngineMetricsUpdater.update_last_error_time(self.metrics, datetime.now())

		# 根据错误级别调用相应的处理器
		handler = self.error_handlers.get(error_level)
		if handler:
			try:
				if asyncio.iscoroutinefunction(handler):
					await handler(error, context)
				else:
					handler(error, context)
			except Exception as e:
				logger.error(f"错误处理器执行失败: {e}")

		# 发布错误事件
		await self._publish_event("engine_error", {
			"engine_id": self.engine_id,
			"engine_name": self.config.name,
			"error": str(error),
			"error_level": error_level.value,
			"context": context or {},
			"timestamp": datetime.now().isoformat()
		})

	async def _handle_debug_error (self, error: Exception):
		"""处理DEBUG级别错误"""
		logger.debug(f"引擎DEBUG错误: {self.config.name}, 错误: {error}")

	async def _handle_info_error (self, error: Exception):
		"""处理INFO级别错误"""
		logger.info(f"引擎INFO错误: {self.config.name}, 错误: {error}")

	async def _handle_warning_error (self, error: Exception, context: Dict[str, Any] = None):
		"""处理WARNING级别错误"""
		logger.warning(f"引擎WARNING错误: {self.config.name}, 错误: {error}")

		# 如果是运行状态，可以尝试自动恢复
		if self.record.status == ComponentStatus.RUNNING:
			await self._try_auto_recover(error, context)

	async def _handle_error_error (self, error: Exception, context: Dict[str, Any] = None):
		"""处理ERROR级别错误"""
		logger.error(f"引擎ERROR错误: {self.config.name}, 错误: {error}")

		# 更新健康状态
		self.record.update_health(HealthStatus.UNHEALTHY, f"发生错误: {str(error)}")

		# 尝试自动恢复
		recovery_success = await self._try_auto_recover(error, context)

		if not recovery_success and getattr(self.config, 'auto_restart_on_error', False):
			# 自动重启
			logger.info(f"尝试自动重启引擎: {self.config.name}")
			try:
				await self.restart()
			except Exception as restart_error:
				logger.error(f"自动重启失败: {self.config.name}, 错误: {restart_error}")

	async def _handle_critical_error (self, error: Exception):
		"""处理CRITICAL级别错误"""
		logger.critical(f"引擎CRITICAL错误: {self.config.name}, 错误: {error}")

		# 更新状态和健康状态
		self.record.update_status(ComponentStatus.ERROR, f"严重错误: {str(error)}")
		self.record.update_health(HealthStatus.FAILED, f"严重错误: {str(error)}")

		# 尝试紧急停止
		try:
			await self.stop(force=True)
		except Exception as stop_error:
			logger.error(f"紧急停止失败: {self.config.name}, 错误: {stop_error}")

	async def _try_auto_recover (self, error: Exception, context: Dict[str, Any] = None) -> bool:
		"""
		尝试自动恢复

		Args:
			error: 异常对象
			context: 错误上下文

		Returns:
			bool: 恢复是否成功
		"""
		logger.info(f"尝试自动恢复: {self.config.name}")

		try:
			# 调用引擎特定的恢复逻辑
			recovery_success = await self._on_auto_recover(error, context)

			if recovery_success:
				logger.info(f"自动恢复成功: {self.config.name}")
				self.record.update_health(HealthStatus.HEALTHY, "自动恢复成功")

				# 发布恢复成功事件
				await self._publish_event("engine_auto_recovered", {
					"engine_id": self.engine_id,
					"engine_name": self.config.name,
					"error": str(error),
					"timestamp": datetime.now().isoformat()
				})
			else:
				logger.warning(f"自动恢复失败: {self.config.name}")

			return recovery_success

		except Exception as recover_error:
			logger.error(f"自动恢复过程中发生错误: {self.config.name}, 错误: {recover_error}")
			return False

	# ==================== 抽象方法（子类必须实现） ====================

	@abstractmethod
	async def _on_initialize (self):
		"""
		引擎初始化时的具体逻辑

		子类必须实现此方法，包含引擎特定的初始化逻辑。
		例如：验证配置、初始化数据结构、准备资源等。

		注意事项：
		1. 不要在此方法中启动任何长期运行的任务
		2. 只进行必要的初始化工作
		3. 可以抛出异常，但会被基类捕获并处理
		"""
		pass

	@abstractmethod
	async def _on_start (self):
		"""
		引擎启动时的具体逻辑

		子类必须实现此方法，包含引擎特定的启动逻辑。
		例如：初始化资源、建立连接、启动内部循环等。

		注意事项：
		1. 可以启动长期运行的任务
		2. 应该处理启动失败的情况
		3. 可以发布启动相关的事件
		"""
		pass

	@abstractmethod
	async def _on_stop (self):
		"""
		引擎停止时的具体逻辑

		子类必须实现此方法，包含引擎特定的停止逻辑。
		例如：释放资源、断开连接、清理临时数据等。

		注意事项：
		1. 应该优雅地停止所有任务
		2. 清理所有分配的资源
		3. 可以发布停止相关的事件
		"""
		pass

	async def _on_force_stop (self):
		"""
		引擎强制停止时的具体逻辑

		子类可以选择实现此方法，用于处理强制停止的情况。
		默认实现调用_on_stop()。
		"""
		await self._on_stop()

	async def _on_pause (self):
		"""
		引擎暂停时的具体逻辑

		子类可以选择实现此方法，用于处理暂停的情况。
		默认实现不执行任何操作。
		"""
		pass

	async def _on_resume (self):
		"""
		引擎恢复时的具体逻辑

		子类可以选择实现此方法，用于处理恢复的情况。
		默认实现不执行任何操作。
		"""
		pass

	async def _on_health_check (self) -> Dict[str, Any]:
		"""
		引擎特定的健康检查逻辑

		子类可以选择实现此方法，用于执行引擎特定的健康检查。
		返回的字典会被合并到健康检查结果中。

		Returns:
			Dict[str, Any]: 引擎特定的健康检查信息
		"""
		return {}

	async def _on_collect_metrics (self):
		"""
		引擎特定的指标收集逻辑

		子类可以选择实现此方法，用于收集引擎特定的性能指标。
		"""
		pass

	async def _on_handle_event (self, event: EngineLifecycleEvent):
		"""
		引擎特定的事件处理逻辑

		子类可以选择实现此方法，用于处理特定的事件。

		Args:
			event: 事件实体
		"""
		pass

	async def _on_auto_recover (self, error: Exception, context: Dict[str, Any] = None) -> bool:
		"""
		引擎特定的自动恢复逻辑

		子类可以选择实现此方法，用于执行引擎特定的恢复操作。

		Args:
			error: 发生的异常
			context: 错误上下文

		Returns:
			bool: 恢复是否成功
		"""
		return False

	# ==================== 工具方法 ====================

	def _validate_config (self):
		"""
		验证配置

		检查引擎配置的有效性。
		子类可以重写此方法以添加特定的配置验证。

		Raises:
			ValueError: 当配置无效时
		"""
		if not self.config.name:
			raise ValueError("引擎名称不能为空")

		max_retries = getattr(self.config, 'max_retries', None)
		if max_retries is not None and max_retries < 0:
			raise ValueError("最大重试次数不能为负数")

		health_check_interval = getattr(self.config, 'health_check_interval', None)
		if health_check_interval is not None and health_check_interval <= 0:
			raise ValueError("健康检查间隔必须大于0")

		logger.debug(f"引擎配置验证通过: {self.config.name}")

	@staticmethod
	def _validate_config_update (config_data: Dict[str, Any]) -> bool:
		"""
		验证配置更新

		Args:
			config_data: 配置更新数据

		Returns:
			bool: 配置更新是否有效
		"""
		# 检查不允许动态更新的配置项
		immutable_fields = ["name", "engine_type", "version"]

		for field_name in immutable_fields:
			if field_name in config_data:
				logger.warning(f"尝试更新不可变配置项: {field_name}")
				return False

		# 验证配置值
		if "max_retries" in config_data and config_data["max_retries"] < 0:
			logger.error(f"无效的最大重试次数: {config_data['max_retries']}")
			return False

		if "health_check_interval" in config_data and config_data["health_check_interval"] <= 0:
			logger.error(f"无效的健康检查间隔: {config_data['health_check_interval']}")
			return False

		return True

	async def _apply_config_update (self, config_data: Dict[str, Any]):
		"""
		应用配置更新

		Args:
			config_data: 配置更新数据
		"""
		# 更新配置对象
		for key, value in config_data.items():
			if hasattr(self.config, key):
				setattr(self.config, key, value)

		# 更新重试策略
		if any(field_name in config_data for field_name in
		       ["max_retries", "retry_delay", "backoff_factor", "max_delay"]):
			self.retry_strategy = {
				"max_retries": getattr(self.config, 'max_retries', 3) or 3,
				"retry_delay": getattr(self.config, 'retry_delay', 1.0) or 1.0,
				"backoff_factor": getattr(self.config, 'backoff_factor', 2.0) or 2.0,
				"max_delay": getattr(self.config, 'max_delay', 30.0) or 30.0
			}

		logger.info(f"引擎配置已应用更新: {self.config.name}")

	def _setup_signal_handlers (self):
		"""设置信号处理器（用于优雅关闭）"""
		try:
			import signal

			# 定义信号处理函数
			def signal_handler (signum, _):
				logger.info(f"接收到信号 {signum}，准备优雅关闭引擎: {self.config.name}")
				asyncio.create_task(self._graceful_shutdown())

			# 注册信号处理器
			signal.signal(signal.SIGINT, signal_handler)
			signal.signal(signal.SIGTERM, signal_handler)

		except (ImportError, AttributeError, ValueError):
			# 在某些环境中可能无法设置信号处理器
			logger.debug("无法设置信号处理器（可能不在主线程中）")

	async def _graceful_shutdown (self):
		"""优雅关闭引擎"""
		logger.info(f"开始优雅关闭引擎: {self.config.name}")

		try:
			# 发布关闭开始事件
			await self._publish_event("engine_graceful_shutdown_started", {
				"engine_id": self.engine_id,
				"engine_name": self.config.name,
				"timestamp": datetime.now().isoformat()
			})

			# 执行优雅停止
			await self.stop()

			# 发布关闭完成事件
			await self._publish_event("engine_graceful_shutdown_completed", {
				"engine_id": self.engine_id,
				"engine_name": self.config.name,
				"timestamp": datetime.now().isoformat()
			})

			logger.info(f"引擎优雅关闭完成: {self.config.name}")

		except (RuntimeError, asyncio.TimeoutError) as e:
			logger.error(f"优雅关闭失败: {self.config.name}, 错误: {e}")

			# 发布关闭失败事件
			await self._publish_event("engine_graceful_shutdown_failed", {
				"engine_id": self.engine_id,
				"engine_name": self.config.name,
				"error": str(e),
				"timestamp": datetime.now().isoformat()
			})
		except Exception as e:
			logger.error(f"优雅关闭失败: {self.config.name}, 错误: {e}")

	async def _start_background_tasks (self):
		"""启动后台任务"""
		# 子类可以重写此方法以启动特定的后台任务
		pass

	async def _stop_background_tasks (self):
		"""停止后台任务"""
		# 停止所有后台任务
		for bg_task in self.background_tasks:
			if not bg_task.done():
				bg_task.cancel()
				try:
					await bg_task
				except asyncio.CancelledError:
					pass

		self.background_tasks.clear()

	def create_background_task (self, core) -> asyncio.Task:
		"""
		创建后台任务

		Args:
			core: 协程对象

		Returns:
			asyncio.Task: 后台任务
		"""
		task = asyncio.create_task(core, name=f"{self.config.name}_background_task")
		self.background_tasks.add(task)

		# 添加完成回调以从集合中移除任务
		def remove_task (t):
			self.background_tasks.discard(t)

		task.add_done_callback(remove_task)

		return task

	def get_status_info (self) -> Dict[str, Any]:
		"""
		获取引擎状态信息

		Returns:
			Dict[str, Any]: 包含引擎完整状态信息的字典
		"""
		return {
			"engine_id": self.engine_id,
			"engine_name": self.config.name,
			"engine_type": self.engine_type.value,
			"status": self.record.status.value,
			"health": self.record.health.value,
			"start_time": self.record.start_time.isoformat() if self.record.start_time else None,
			"end_time": self.record.end_time.isoformat() if self.record.end_time else None,
			"uptime": self.record.get_uptime(),
			"error_message": self.record.error_message,
			"error_level": self.record.error_level.value if self.record.error_level else None,
			"error_details": self.record.error_details,
			"dependencies": list(self.dependencies.keys()),
			"dependents": list(self.dependents),
			"metrics": self.metrics.to_dict(),
			"resource_usage": {k.value: v for k, v in self.record.resource_usage.items()},
			"performance_metrics": self.record.performance_metrics,
			"config": self.config.to_dict(),
			"retry_strategy": self.retry_strategy,
			"record": self.record.to_dict()
		}

	@asynccontextmanager
	async def safe_context (self):
		"""
		安全上下文管理器

		确保在引擎运行状态下执行代码块，如果引擎停止则取消执行。
		支持暂停/恢复机制。

		Example:
			async with engine.safe_context():
				# 在这里执行需要引擎运行状态的操作
				await engine.process_data(events)
		"""
		if self.record.status != ComponentStatus.RUNNING:
			raise RuntimeError(
				f"引擎未运行: {self.config.name}, 当前状态: {self.record.status.value}"
			)

		# 等待暂停事件（如果引擎被暂停）
		await self.pause_event.wait()

		# 检查是否应该关闭
		if self.shutdown_event.is_set():
			raise RuntimeError(f"引擎正在关闭: {self.config.name}")

		try:
			yield self
		except asyncio.CancelledError:
			# 如果引擎正在关闭，任务被取消是正常的
			if self.shutdown_event.is_set():
				logger.debug(f"引擎上下文被优雅取消: {self.config.name}")
				raise
			else:
				logger.warning(f"引擎上下文意外取消: {self.config.name}")
				raise
		except (RuntimeError, ValueError) as e:
			logger.error(f"引擎上下文执行异常: {self.config.name}, 错误: {e}")

			# 自动处理错误
			await self.handle_error(e, EngineErrorLevel.ERROR)
			raise
		except Exception as e:
			logger.error(f"引擎上下文执行异常: {self.config.name}, 错误: {e}")
			await self.handle_error(e, EngineErrorLevel.ERROR)
			raise

	def with_retry (self, func: Callable) -> Callable:
		"""
		重试装饰器

		为函数添加重试机制，基于引擎的配置重试策略。

		Args:
			func: 要装饰的函数

		Returns:
			Callable: 装饰后的函数
		"""

		@wraps(func)
		async def wrapper (*args, **kwargs):
			max_retries = self.retry_strategy["max_retries"]
			retry_delay = self.retry_strategy["retry_delay"]
			backoff_factor = self.retry_strategy["backoff_factor"]
			max_delay = self.retry_strategy["max_delay"]

			last_exception = None

			for attempt in range(max_retries + 1):
				try:
					return await func(*args, **kwargs)
				except (RuntimeError, ValueError, ConnectionError) as e:
					last_exception = e

					if attempt < max_retries:
						# 计算等待时间（指数退避）
						wait_time = min(
							retry_delay * (backoff_factor ** attempt),
							max_delay
						)

						logger.warning(
							f"函数执行失败，将在 {wait_time:.1f} 秒后重试 "
							f"({attempt + 1}/{max_retries}): {e}"
						)

						# 记录错误
						await self.handle_error(
							e,
							EngineErrorLevel.WARNING,
							{
								"function": func.__name__,
								"attempt": attempt + 1,
								"max_retries": max_retries
							}
						)

						await asyncio.sleep(wait_time)
					else:
						# 超过最大重试次数
						logger.error(
							f"函数执行失败，超过最大重试次数 "
							f"({max_retries}): {e}"
						)

						# 记录错误
						await self.handle_error(
							e,
							EngineErrorLevel.ERROR,
							{
								"function": func.__name__,
								"attempts": max_retries + 1
							}
						)

						raise
				except Exception as e:
					# 捕获其他异常，直接抛出
					logger.error(f"函数执行失败: {e}")
					await self.handle_error(e, EngineErrorLevel.ERROR)
					raise

			# 理论上不会执行到这里
			raise last_exception

		return wrapper

	def __str__ (self) -> str:
		"""
		字符串表示

		Returns:
			str: 引擎的字符串表示
		"""
		return (f"Engine({self.config.name}, "
		        f"id={self.engine_id[:8]}, "
		        f"type={self.engine_type.value}, "
		        f"status={self.record.status.value}, "
		        f"health={self.record.health.value})")

	def __repr__ (self) -> str:
		"""
		详细表示

		Returns:
			str: 引擎的详细表示
		"""
		return (f"EngineBase(name='{self.config.name}', "
		        f"id='{self.engine_id}', "
		        f"type={self.engine_type}, "
		        f"status={self.record.status}, "
		        f"health={self.record.health}, "
		        f"start_time={self.record.start_time})")

	async def __aenter__ (self):
		"""异步上下文管理器入口"""
		await self.start()
		return self

	async def __aexit__ (self, exc_type, exc_val, exc_tb):
		"""异步上下文管理器出口"""
		await self.stop()

	def __del__ (self):
		"""析构函数"""
		# 尝试清理资源
		try:
			if hasattr(self, 'background_tasks'):
				for bg_task in self.background_tasks:
					if not bg_task.done():
						bg_task.cancel()

			logger.debug(f"引擎资源清理: {getattr(self, 'config', None) and getattr(self.config, 'name', 'unknown') or 'unknown'}")
		except BusinessException:
			# 析构函数中使用宽泛异常捕获，确保不会因异常而影响程序退出
			pass