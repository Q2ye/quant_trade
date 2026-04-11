# 风险控制事件

from quant_server.core.events.base import BaseEvent
from quant_server.core.events.types import EventPriority, EventCategory


class RiskEvent(BaseEvent):
	"""风险事件基类"""

	def __init__ (self, event_type: str, risk_type: str, **kwargs):
		super().__init__(
			event_type=event_type,
			source="risk_events",
			module="trade",
			priority=EventPriority.HIGH,
			category=EventCategory.MONITOR,
			**kwargs
		)
		self.data["risk_type"] = risk_type


class RiskAlertEvent(BaseEvent):
	"""风险预警事件"""

	def __init__ (self, risk_type: str, risk_level: str, message: str, **kwargs):
		super().__init__(
			event_type="trade.risk.alert",
			source="risk_events",
			module="trade",
			priority=EventPriority.HIGH,
			category=EventCategory.MONITOR,
			**kwargs
		)
		self.data.update({
			"risk_type": risk_type,
			"risk_level": risk_level,
			"message": message
		})


class RiskCheckEvent(BaseEvent):
	"""风险检查事件"""

	def __init__ (self, check_type: str, result: bool, message: str, **kwargs):
		super().__init__(
			event_type="trade.risk.check",
			source="risk_events",
			module="trade",
			priority=EventPriority.NORMAL,
			category=EventCategory.BUSINESS,
			**kwargs
		)
		self.data.update({
			"check_type": check_type,
			"result": result,
			"message": message
		})


class RiskViolationEvent(BaseEvent):
	"""风险违规事件"""

	def __init__ (self, violation_type: str, severity: str, message: str, **kwargs):
		super().__init__(
			event_type="trade.risk.violation",
			source="risk_events",
			module="trade",
			priority=EventPriority.CRITICAL,
			category=EventCategory.MONITOR,
			**kwargs
		)
		self.data.update({
			"violation_type": violation_type,
			"severity": severity,
			"message": message
		})


class RiskLimitEvent(BaseEvent):
	"""风险限制事件"""

	def __init__ (self, limit_type: str, current_value: float, limit_value: float, message: str, **kwargs):
		super().__init__(
			event_type="trade.risk.limit",
			source="risk_events",
			module="trade",
			priority=EventPriority.HIGH,
			category=EventCategory.MONITOR,
			**kwargs
		)
		self.data.update({
			"limit_type": limit_type,
			"current_value": current_value,
			"limit_value": limit_value,
			"message": message
		})


class RiskActionEvent(BaseEvent):
	"""风险操作事件"""

	def __init__ (self, action_type: str, action_result: bool, message: str, **kwargs):
		super().__init__(
			event_type="trade.risk.action",
			source="risk_events",
			module="trade",
			priority=EventPriority.NORMAL,
			category=EventCategory.AUDIT,
			**kwargs
		)
		self.data.update({
			"action_type": action_type,
			"action_result": action_result,
			"message": message
		})


class PositionRiskEvent(BaseEvent):
	"""持仓风险事件"""

	def __init__ (self, symbol: str, risk_type: str, risk_level: str, message: str, **kwargs):
		super().__init__(
			event_type="trade.risk.position",
			source="risk_events",
			module="trade",
			priority=EventPriority.HIGH,
			category=EventCategory.MONITOR,
			**kwargs
		)
		self.data.update({
			"symbol": symbol,
			"risk_type": risk_type,
			"risk_level": risk_level,
			"message": message
		})


class AccountRiskEvent(BaseEvent):
	"""账户风险事件"""

	def __init__ (self, risk_type: str, risk_level: str, message: str, **kwargs):
		super().__init__(
			event_type="trade.risk.account",
			source="risk_events",
			module="trade",
			priority=EventPriority.HIGH,
			category=EventCategory.MONITOR,
			**kwargs
		)
		self.data.update({
			"risk_type": risk_type,
			"risk_level": risk_level,
			"message": message
		})
