"""
对账事件定义
用于对账过程中的事件通知
"""

from datetime import datetime, date
from typing import Dict, Any

from quant_server.core.events.base import BaseEvent, EventPriority


class ReconciliationEvent(BaseEvent):
	"""
	对账事件

	触发时机：
	- 对账任务完成

	事件数据：
	- reconciliation_type: 对账类型
	- trading_day: 交易日
	- results: 对账结果
	"""

	def __init__ (
			self,
			reconciliation_type: str,
			trading_day: date,
			results: Dict[str, Any],
			**kwargs
	):
		super().__init__(
			module="events",
			event_type="events.reconciliation",  # 自定义事件类型
			priority=EventPriority.NORMAL,
			source="reconciliation_service",
			**kwargs
		)

		self.data = {
			"reconciliation_type": reconciliation_type,
			"trading_day": trading_day.isoformat(),
			"results": results,
			"timestamp": datetime.now().isoformat()
		}