"""
策略管理相关事件
"""
from datetime import datetime
from typing import Dict, Any, Optional

from core.events.base import BaseEvent, EventPriority
from quant_server.modules.strategy.events.types import StrategyEventType


class StrategyCreatedEvent(BaseEvent):
	"""策略创建事件"""

	def __init__ (
			self,
			strategy_id: str,
			strategy_name: str,
			strategy_type: str,
			creator_id: str,
			parameters: Optional[Dict[str, Any]] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=StrategyEventType.CREATED.value,
			priority=EventPriority.NORMAL,
			**kwargs
		)

		self.data = {
			"strategy_id": strategy_id,
			"strategy_name": strategy_name,
			"strategy_type": strategy_type,
			"creator_id": creator_id,
			"parameters": parameters or {},
			"creation_time": datetime.now().isoformat()
		}


class StrategyStartedEvent(BaseEvent):
	"""策略启动事件"""

	def __init__ (
			self,
			strategy_id: str,
			strategy_name: str,
			user_id: str,
			initial_capital: float = 0.0,
			parameters: Optional[Dict[str, Any]] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=StrategyEventType.STARTED.value,
			priority=EventPriority.NORMAL,
			**kwargs
		)

		self.data = {
			"strategy_id": strategy_id,
			"strategy_name": strategy_name,
			"user_id": user_id,
			"initial_capital": initial_capital,
			"parameters": parameters or {},
			"start_time": datetime.now().isoformat()
		}


class StrategyStoppedEvent(BaseEvent):
	"""策略停止事件"""

	def __init__ (
			self,
			strategy_id: str,
			strategy_name: str,
			user_id: str,
			reason: str = "manual",
			performance_summary: Optional[Dict[str, Any]] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=StrategyEventType.STOPPED.value,
			priority=EventPriority.NORMAL,
			**kwargs
		)

		self.data = {
			"strategy_id": strategy_id,
			"strategy_name": strategy_name,
			"user_id": user_id,
			"reason": reason,
			"performance_summary": performance_summary or {},
			"stop_time": datetime.now().isoformat()
		}


class StrategySignalEvent(BaseEvent):
	"""策略信号事件"""

	def __init__ (
			self,
			strategy_id: str,
			symbol: str,
			signal_type: str,  # BUY/SELL/HOLD
			price: float,
			volume: int,
			reason: str,
			confidence: float = 1.0,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=StrategyEventType.SIGNAL_GENERATED.value,
			priority=EventPriority.HIGH,  # 信号事件优先级较高
			**kwargs
		)

		self.data = {
			"strategy_id": strategy_id,
			"symbol": symbol,
			"signal_type": signal_type,
			"price": price,
			"volume": volume,
			"reason": reason,
			"confidence": confidence,
			"generation_time": datetime.now().isoformat()
		}