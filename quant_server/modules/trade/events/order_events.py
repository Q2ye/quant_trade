"""
订单相关事件
"""
from datetime import datetime
from typing import Optional

from core.events import BaseEvent


class OrderEvent(BaseEvent):
	"""订单事件基类"""
	def __init__(self, order_id: str, symbol: str, **kwargs):
		super().__init__(**kwargs)
		self.order_id = order_id
		self.symbol = symbol


class OrderUpdateEvent(BaseEvent):
	"""订单更新事件"""
	def __init__(self, order_id: str, status: str, **kwargs):
		super().__init__(**kwargs)
		self.order_id = order_id
		self.status = status


class OrderCreatedEvent(BaseEvent):
	"""订单创建事件"""

	def __init__ (
			self,
			order_id: str,
			symbol: str,
			order_type: str,  # LIMIT/MARKET
			side: str,  # BUY/SELL
			price: float,
			volume: int,
			strategy_id: Optional[str] = None,
			account_id: str = "",
	):
		super().__init__(
			event_type="order_created",
			module="trade",
			source="order_events"
		)

		self.data = {
			"order_id": order_id,
			"symbol": symbol,
			"order_type": order_type,
			"side": side,
			"price": price,
			"volume": volume,
			"strategy_id": strategy_id,
			"account_id": account_id,
			"creation_time": datetime.now().isoformat(),
			"status": "CREATED"
		}


class OrderFilledEvent(BaseEvent):
	"""订单成交事件"""

	event_type: str = "order_filled"

	def __init__ (
			self,
			order_id: str,
			symbol: str,
			filled_price: float,
			filled_volume: int,
			commission: float = 0.0,
			tax: float = 0.0,
	):
		super().__init__(
			event_type="order_filled",
			module="trade",
			source="order_events"
		)

		self.data = {
			"order_id": order_id,
			"symbol": symbol,
			"filled_price": filled_price,
			"filled_volume": filled_volume,
			"commission": commission,
			"tax": tax,
			"fill_time": datetime.now().isoformat(),
			"status": "FILLED"
		}


class OrderCancelledEvent(BaseEvent):
	"""订单取消事件"""

	def __init__ (
			self,
			order_id: str,
			symbol: str,
			cancelled_volume: int,
			reason: str = "user",
	):
		super().__init__(
			event_type="order_cancelled",
			module="trade",
			source="order_events"
		)

		self.data = {
			"order_id": order_id,
			"symbol": symbol,
			"cancelled_volume": cancelled_volume,
			"reason": reason,
			"cancel_time": datetime.now().isoformat(),
			"status": "CANCELLED"
		}