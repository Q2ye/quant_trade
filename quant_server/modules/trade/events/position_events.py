# 持仓相关事件

from dataclasses import dataclass
from typing import Dict, Any

from core.events import BaseEvent


@dataclass
class PositionEvent(BaseEvent):
	"""持仓事件基类"""
	event_type: str = "position_event"
	symbol: str = None
	source: str = "position_events"
	module: str = "trade"


@dataclass
class PositionUpdateEvent(BaseEvent):
	"""持仓更新事件"""
	event_type: str = "position_update"
	symbol: str = None
	position_data: Dict[str, Any] = None
	source: str = "position_events"
	module: str = "trade"


@dataclass
class PositionChangeEvent(BaseEvent):
	"""持仓变化事件"""
	event_type: str = "position_change"
	symbol: str = None
	direction: str = None  # buy/sell
	quantity: float = 0.0
	price: float = 0.0
	source: str = "position_events"
	module: str = "trade"


@dataclass
class PositionRiskEvent(BaseEvent):
	"""持仓风险事件"""
	event_type: str = "position_risk"
	symbol: str = None
	risk_type: str = None
	risk_level: str = None
	message: str = None
	source: str = "position_events"
	module: str = "trade"


@dataclass
class AccountUpdateEvent(BaseEvent):
	"""账户更新事件"""
	event_type: str = "account_update"
	account_data: Dict[str, Any] = None
	source: str = "position_events"
	module: str = "trade"


@dataclass
class CapitalChangeEvent(BaseEvent):
	"""资金变化事件"""
	event_type: str = "capital_change"
	change_type: str = None  # deposit/withdraw/trade
	amount: float = 0.0
	balance: float = 0.0
	source: str = "position_events"
	module: str = "trade"


@dataclass
class MarginCallEvent(BaseEvent):
	"""保证金追缴事件"""
	event_type: str = "margin_call"
	required_amount: float = 0.0
	current_balance: float = 0.0
	message: str = None
	source: str = "position_events"
	module: str = "trade"


@dataclass
class PositionLimitEvent(BaseEvent):
	"""持仓限制事件"""
	event_type: str = "position_limit"
	symbol: str = None
	current_position: float = 0.0
	max_position: float = 0.0
	message: str = None
	source: str = "position_events"
	module: str = "trade"
