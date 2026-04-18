# AccountEventType枚举
from enum import Enum
from typing import Callable, Any

from sqlalchemy.sql.coercions import cls


class AccountEventType(Enum):
	"""
	账户事件类型枚举

	定义账户相关的所有事件类型
	"""
	# 资金余额事件
	BALANCE_UPDATED = "account.balance.updated"
	DEPOSIT_COMPLETED = "account.deposit.completed"
	WITHDRAW_COMPLETED = "account.withdraw.completed"
	ASSET_UPDATED = "account.asset.updated"
	STATUS_CHANGED = "account.status.changed"

	# 持仓事件
	POSITION_UPDATED = "account.position.updated"
	POSITION_OPENED = "account.position.opened"
	POSITION_CLOSED = "account.position.closed"
	POSITION_ADJUSTED = "account.position.adjusted"

	# 结算事件
	SETTLEMENT_STARTED = "account.settlement.started"
	SETTLEMENT_COMPLETED = "account.settlement.completed"
	RECONCILIATION_STARTED = "account.reconciliation.started"
	RECONCILIATION_COMPLETED = "account.reconciliation.completed"

	@property
	def value (self) -> Callable[[], Any]:
		"""返回事件类型值"""
		return super().value

	@classmethod
	def from_value (cls, value: str) -> "AccountEventType":
		"""根据值获取事件类型"""
		for event_type in cls:
			if event_type.value == value:
				return event_type
		raise ValueError(f"未知的账户事件类型: {value}")

	def is_balance_event (self) -> bool:
		"""判断是否为资金余额事件"""
		return self in [
			cls.BALANCE_UPDATED,
			cls.DEPOSIT_COMPLETED,
			cls.WITHDRAW_COMPLETED,
			cls.ASSET_UPDATED,
			cls.STATUS_CHANGED
		]

	def is_position_event (self) -> bool:
		"""判断是否为持仓事件"""
		return self in [
			cls.POSITION_UPDATED,
			cls.POSITION_OPENED,
			cls.POSITION_CLOSED,
			cls.POSITION_ADJUSTED
		]

	def is_settlement_event (self) -> bool:
		"""判断是否为结算事件"""
		return self in [
			cls.SETTLEMENT_STARTED,
			cls.SETTLEMENT_COMPLETED,
			cls.RECONCILIATION_STARTED,
			cls.RECONCILIATION_COMPLETED
		]


__all__ = ["AccountEventType"]
