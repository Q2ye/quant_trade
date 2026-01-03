"""
事件类型和优先级定义
提供事件系统的核心类型定义

设计原则：
1. 类型安全：使用枚举和类型别名
2. 可扩展：支持自定义事件类型
3. 文档化：清晰的类型定义和文档
"""

from enum import IntEnum, Enum
from typing import Dict, Any, Optional, Union, List


class EventPriority(IntEnum):
	"""
	事件优先级枚举

	优先级影响事件处理顺序，数值越大优先级越高
	系统会优先处理高优先级事件

	分级说明：
	- CRITICAL: 系统关键事件，需要立即处理
	- HIGH: 重要事件，尽快处理
	- NORMAL: 普通事件，正常处理
	- LOW: 低优先级事件，可以延迟处理
	"""
	LOW = 10
	NORMAL = 50
	HIGH = 80
	CRITICAL = 100

	@classmethod
	def from_string (cls, priority_str: str) -> "EventPriority":
		"""从字符串转换为优先级"""
		priority_map = {
			"low": cls.LOW,
			"normal": cls.NORMAL,
			"high": cls.HIGH,
			"critical": cls.CRITICAL,
		}
		return priority_map.get(priority_str.lower(), cls.NORMAL)

	def __str__ (self) -> str:
		"""字符串表示"""
		return self.name.lower()


class EventStatus(str, Enum):
	"""
	事件状态枚举

	表示事件在处理流程中的状态
	"""
	CREATED = "created"  # 事件已创建
	PROCESSING = "processing"  # 事件正在处理
	PROCESSED = "processed"  # 事件处理完成
	FAILED = "failed"  # 事件处理失败
	FILTERED = "filtered"  # 事件被过滤
	DROPPED = "dropped"  # 事件被丢弃

	@classmethod
	def is_terminal (cls, status: "EventStatus") -> bool:
		"""判断是否为终止状态（不会再有状态变化）"""
		terminal_states = {cls.PROCESSED, cls.FAILED, cls.FILTERED, cls.DROPPED}
		return status in terminal_states


class EventCategory(str, Enum):
	"""
	事件类别枚举

	用于对事件进行分类，便于过滤和处理
	"""
	SYSTEM = "system"  # 系统事件
	BUSINESS = "business"  # 业务事件
	MONITOR = "monitor"  # 监控事件
	AUDIT = "audit"  # 审计事件
	DEBUG = "debug"  # 调试事件

	@classmethod
	def get_category_description (cls, category: "EventCategory") -> str:
		"""获取类别描述"""
		descriptions = {
			cls.SYSTEM: "系统运行、配置、维护相关事件",
			cls.BUSINESS: "具体业务逻辑相关事件",
			cls.MONITOR: "系统监控、性能、健康度相关事件",
			cls.AUDIT: "安全审计、操作记录相关事件",
			cls.DEBUG: "调试、开发、测试相关事件",
		}
		return descriptions.get(category, "未知类别")


class EventType:
	"""
	事件类型工具类

	提供事件类型的构建和解析方法
	事件类型格式：{模块}.{领域}.{动作}.{状态}

	示例：
		data.sync.started
		trade.order.submitted
		strategy.signal.generated
	"""

	@staticmethod
	def create (module: str, domain: str, action: str, status: str) -> str:
		"""
		创建事件类型字符串

		Args:
			module: 模块名，如 data, trade, strategy
			domain: 领域名，如 sync, order, signal
			action: 动作名，如 start, submit, generate
			status: 状态名，如 started, submitted, generated

		Returns:
			事件类型字符串
		"""
		return f"{module}.{domain}.{action}.{status}"

	@staticmethod
	def parse (event_type: str) -> Dict[str, str]:
		"""
		解析事件类型字符串

		Args:
			event_type: 事件类型字符串

		Returns:
			解析后的组件字典

		Raises:
			ValueError: 事件类型格式不正确
		"""
		parts = event_type.split(".")
		if len(parts) < 3:
			raise ValueError(f"事件类型格式不正确: {event_type}")

		result = {"full": event_type}

		if len(parts) >= 1:
			result["module"] = parts[0]
		if len(parts) >= 2:
			result["domain"] = parts[1]
		if len(parts) >= 3:
			result["action"] = parts[2]
		if len(parts) >= 4:
			result["status"] = parts[3]

		# 处理可能的额外部分
		if len(parts) > 4:
			result["extra"] = ".".join(parts[4:])

		return result

	@staticmethod
	def get_module (event_type: str) -> str:
		"""获取事件类型中的模块名"""
		try:
			parsed = EventType.parse(event_type)
			return parsed.get("module", "")
		except ValueError:
			return ""

	@staticmethod
	def get_domain (event_type: str) -> str:
		"""获取事件类型中的领域名"""
		try:
			parsed = EventType.parse(event_type)
			return parsed.get("domain", "")
		except ValueError:
			return ""

	@staticmethod
	def is_system_event (event_type: str) -> bool:
		"""判断是否为系统事件"""
		return event_type.startswith("system.")

	@staticmethod
	def is_business_event (event_type: str) -> bool:
		"""判断是否为业务事件"""
		return not EventType.is_system_event(event_type)


# 常用事件类型常量（不包含具体业务事件）
class CommonEventTypes:
	"""通用事件类型常量"""

	# 系统事件
	SYSTEM_STARTED = "system.started"
	SYSTEM_STOPPED = "system.stopped"
	SYSTEM_HEARTBEAT = "system.heartbeat"
	SYSTEM_ALERT = "system.alert"

	# 模块事件
	MODULE_STARTED = "module.started"
	MODULE_STOPPED = "module.stopped"
	MODULE_READY = "module.ready"
	MODULE_ERROR = "module.error"

	# 生命周期事件
	PROCESS_STARTED = "process.started"
	PROCESS_COMPLETED = "process.completed"
	PROCESS_FAILED = "process.failed"

	# 监控事件
	HEALTH_CHECK = "health.check"
	METRIC_UPDATE = "metric.update"
	PERFORMANCE_ALERT = "performance.alert"

	# 审计事件
	USER_LOGIN = "audit.user.login"
	USER_LOGOUT = "audit.user.logout"
	OPERATION_LOG = "audit.operation.log"


# 事件过滤器类型定义
EventFilterFunc = Any  # 类型提示占位符

__all__ = [
	"EventPriority",
	"EventStatus",
	"EventCategory",
	"EventType",
	"CommonEventTypes",
	"EventFilterFunc",
]