# broker_adapter.py    # 券商适配器接口

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class BrokerAdapter(ABC):
	"""券商适配器抽象基类"""

	@abstractmethod
	async def connect (self) -> bool:
		"""连接券商接口"""
		pass

	@abstractmethod
	async def disconnect (self) -> bool:
		"""断开券商接口"""
		pass

	@abstractmethod
	async def send_order (self, order_data: Dict[str, Any]) -> Dict[str, Any]:
		"""发送订单"""
		pass

	@abstractmethod
	async def cancel_order (self, order_id: str) -> bool:
		"""取消订单"""
		pass

	@abstractmethod
	async def get_order_status (self, order_id: str) -> Dict[str, Any]:
		"""获取订单状态"""
		pass

	@abstractmethod
	async def get_position (self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
		"""获取持仓"""
		pass

	@abstractmethod
	async def get_account (self) -> Dict[str, Any]:
		"""获取账户信息"""
		pass

	@abstractmethod
	def is_connected (self) -> bool:
		"""检查是否连接"""
		pass
