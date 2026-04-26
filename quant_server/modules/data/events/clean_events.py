"""
数据清洗相关事件定义
负责数据清洗流程中的事件通知

设计原则：
1. 继承核心事件基类：所有事件都继承自core.events.BaseEvent
2. 状态跟踪：跟踪清洗任务的开始、进度、完成、应用等状态
3. 详细上下文：包含清洗任务的详细上下文信息
4. 可序列化：支持JSON序列化用于网络传输和持久化
"""

from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

# 导入核心事件基类
from quant_server.core.events import BaseEvent
from quant_server.modules.data.events.types import DataEventType, DataEventPriority


class DataCleanStatus(str, Enum):
	"""数据清洗状态枚举"""
	PENDING = "pending"  # 等待中
	RUNNING = "running"  # 运行中
	COMPLETED = "completed"  # 已完成
	FAILED = "failed"  # 失败
	APPLIED = "applied"  # 已应用
	CANCELLED = "cancelled"  # 已取消


@dataclass
class DataCleanMetadata:
	"""数据清洗元数据"""
	clean_id: str  # 清洗任务ID
	data_type: str  # 数据类型
	clean_rules: List[str]  # 清洗规则列表
	start_date: Optional[datetime] = None  # 开始日期
	end_date: Optional[datetime] = None  # 结束日期
	ts_codes: Optional[List[str]] = None  # 股票代码列表
	user_id: Optional[int] = None  # 用户ID
	created_at: datetime = field(default_factory=datetime.now)  # 创建时间


@dataclass
class DataCleanIssue:
	"""数据清洗问题定义"""
	type: str  # 问题类型: missing/duplicate/outlier/inconsistent
	severity: str  # 严重程度: low/medium/high
	ts_code: Optional[str] = None  # 股票代码
	count: int = 1  # 问题数量
	description: str = ""  # 问题描述
	details: Dict[str, Any] = field(default_factory=dict)  # 详细数据
	suggested_fix: Optional[str] = None  # 建议修复方法


@dataclass
class DataCleanResult:
	"""数据清洗结果"""
	total_issues: int = 0  # 总问题数
	issues: List[DataCleanIssue] = field(default_factory=list)  # 问题列表
	issue_distribution: Dict[str, int] = field(default_factory=dict)  # 问题分布
	severity_groups: Dict[str, int] = field(default_factory=dict)  # 严重程度分组
	cleaned_at: Optional[datetime] = None  # 清洗完成时间
	applied: bool = False  # 是否已应用
	applied_count: int = 0  # 已应用数量


class DataCleanEvent(BaseEvent):
	"""数据清洗事件基类"""

	def __init__ (
			self,
			clean_id: str,
			data_type: str,
			user_id: Optional[int] = None,
			**kwargs
	):
		"""
		初始化数据清洗事件

		Args:
			clean_id: 清洗任务ID
			data_type: 数据类型
			user_id: 用户ID
			timestamp: 事件时间戳
			**kwargs: 其他参数
		"""
		super().__init__(
			event_type="data.clean.base",
			source="data_module",
			module="data",
			data=kwargs
		)
		self.clean_id = clean_id
		self.data_type = data_type
		self.user_id = user_id

		# 将其他参数添加到事件数据中
		for key, value in kwargs.items():
			setattr(self, key, value)


class DataCleanStartedEvent(DataCleanEvent):
	"""数据清洗开始事件"""

	def __init__ (
			self,
			clean_id: str,
			data_type: str,
			clean_rules: List[str],
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			ts_codes: Optional[List[str]] = None,
			user_id: Optional[int] = None,
			timestamp: Optional[datetime] = None
	):
		super().__init__(
			event_type=DataEventType.CLEAN_STARTED.value,
			event_priority=DataEventPriority.NORMAL,
			clean_id=clean_id,
			data_type=data_type,
			user_id=user_id,
			timestamp=timestamp
		)
		self.clean_rules = clean_rules
		self.start_date = start_date
		self.end_date = end_date
		self.ts_codes = ts_codes
		self.status = DataCleanStatus.RUNNING.value
		self.message = f"数据清洗任务 {clean_id} 开始执行"


class DataCleanProgressEvent(DataCleanEvent):
	"""数据清洗进度事件"""

	def __init__ (
			self,
			clean_id: str,
			data_type: str,
			progress: float,  # 0-100
			current_rule: str,
			processed_count: int = 0,
			total_count: int = 0,
			user_id: Optional[int] = None,
			timestamp: Optional[datetime] = None
	):
		super().__init__(
			event_type=DataEventType.CLEAN_PROGRESS.value,
			event_priority=DataEventPriority.LOW,
			clean_id=clean_id,
			data_type=data_type,
			user_id=user_id,
			timestamp=timestamp
		)
		self.progress = progress
		self.current_rule = current_rule
		self.processed_count = processed_count
		self.total_count = total_count
		self.status = DataCleanStatus.RUNNING.value
		self.message = f"数据清洗进度: {progress:.1f}% - 当前规则: {current_rule}"


class DataCleanCompletedEvent(DataCleanEvent):
	"""数据清洗完成事件"""

	def __init__ (
			self,
			clean_id: str,
			data_type: str,
			result: DataCleanResult,
			duration_seconds: float,
			user_id: Optional[int] = None,
			timestamp: Optional[datetime] = None
	):
		super().__init__(
			event_type=DataEventType.CLEAN_COMPLETED.value,
			event_priority=DataEventPriority.NORMAL,
			clean_id=clean_id,
			data_type=data_type,
			user_id=user_id,
			timestamp=timestamp
		)
		self.result = result
		self.duration_seconds = duration_seconds
		self.status = DataCleanStatus.COMPLETED.value
		self.total_issues = result.total_issues
		self.message = f"数据清洗完成，发现 {result.total_issues} 个问题"


class DataCleanFailedEvent(DataCleanEvent):
	"""数据清洗失败事件"""

	def __init__ (
			self,
			clean_id: str,
			data_type: str,
			error_message: str,
			error_details: Optional[Dict] = None,
			user_id: Optional[int] = None,
			timestamp: Optional[datetime] = None
	):
		super().__init__(
			event_type=DataEventType.CLEAN_FAILED.value,
			event_priority=DataEventPriority.HIGH,
			clean_id=clean_id,
			data_type=data_type,
			user_id=user_id,
			timestamp=timestamp
		)
		self.error_message = error_message
		self.error_details = error_details or {}
		self.status = DataCleanStatus.FAILED.value
		self.message = f"数据清洗失败: {error_message}"


class DataCleanAppliedEvent(DataCleanEvent):
	"""数据清洗应用事件"""

	def __init__ (
			self,
			clean_id: str,
			apply_id: str,
			data_type: str,
			applied_count: int,
			total_issues: int,
			dry_run: bool = False,
			user_id: Optional[int] = None,
			timestamp: Optional[datetime] = None
	):
		super().__init__(
			event_type=DataEventType.CLEAN_APPLIED.value,
			event_priority=DataEventPriority.NORMAL,
			clean_id=clean_id,
			data_type=data_type,
			user_id=user_id,
			timestamp=timestamp
		)
		self.apply_id = apply_id
		self.applied_count = applied_count
		self.total_issues = total_issues
		self.dry_run = dry_run
		self.status = DataCleanStatus.APPLIED.value
		action = "试运行应用" if dry_run else "应用"
		self.message = f"{action}清洗结果，成功处理 {applied_count}/{total_issues} 个问题"


class DataCleanValidatedEvent(DataCleanEvent):
	"""数据验证事件"""

	def __init__ (
			self,
			clean_id: str,
			data_type: str,
			ts_code: str,
			trade_date: datetime,
			validation_results: Dict[str, Any],
			is_valid: bool,
			error_count: int,
			user_id: Optional[int] = None,
			timestamp: Optional[datetime] = None
	):
		super().__init__(
			event_type=DataEventType.CLEAN_VALIDATION_COMPLETED.value,
			event_priority=DataEventPriority.LOW,
			clean_id=clean_id,
			data_type=data_type,
			user_id=user_id,
			timestamp=timestamp
		)
		self.ts_code = ts_code
		self.trade_date = trade_date
		self.validation_results = validation_results
		self.is_valid = is_valid
		self.error_count = error_count
		self.status = "validated"
		validity = "有效" if is_valid else "无效"
		self.message = f"数据验证完成: {ts_code} - {trade_date.date()} ({validity}, 错误数: {error_count})"


# 简化的DataCleanEvent（用于向后兼容）
class DataCleanEvent(BaseEvent):
	"""数据清洗事件（简化版，用于clean_service.py的直接使用）"""

	def __init__ (
			self,
			clean_id: str,
			event_type: str,
			data_type: Optional[str] = None,
			user_id: Optional[int] = None,
			**kwargs
	):
		"""
		初始化数据清洗事件（简化版）

		注意：这个类是向后兼容的简化版本，推荐使用具体的事件类
		"""
		super().__init__(
			event_type=event_type,
			source="data_module",
			module="data",
			data=kwargs
		)
		self.clean_id = clean_id
		self.data_type = data_type
		self.user_id = user_id

		# 将其他参数添加到事件数据中
		for key, value in kwargs.items():
			setattr(self, key, value)


# 导出所有清洗事件类
__all__ = [
	# 元数据和辅助类
	"DataCleanStatus",
	"DataCleanMetadata",
	"DataCleanIssue",
	"DataCleanResult",

	# 具体事件类
	"DataCleanStartedEvent",
	"DataCleanProgressEvent",
	"DataCleanCompletedEvent",
	"DataCleanFailedEvent",
	"DataCleanAppliedEvent",
	"DataCleanValidatedEvent",

	# 简化事件类（向后兼容）
	"DataCleanEvent",
]