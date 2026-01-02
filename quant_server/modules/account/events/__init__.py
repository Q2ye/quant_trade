"""
账户模块事件定义
负责账户管理、资金、持仓、结算等相关事件通知

按照业务功能分类：
1. 资金余额事件 (balance_events.py): 账户资金变动相关事件
2. 账户持仓事件 (position_events.py): 持仓管理相关事件
3. 结算对账事件 (settlement_events.py): 结算对账相关事件

业务场景：
1. 账户资金变动通知
2. 持仓状态更新通知
3. 结算对账过程通知
4. 账户资产统计通知

设计原则：
1. 每个事件类对应一个具体的账户业务动作
2. 事件数据包含完整的账户上下文信息
3. 支持资金流水和持仓变动的追溯
"""

from .balance_events import (
	AccountBalanceUpdatedEvent,
	AccountDepositCompletedEvent,
	AccountWithdrawCompletedEvent,
	AccountAssetUpdatedEvent
)

from .position_events import (
	AccountPositionUpdatedEvent,
	AccountPositionOpenedEvent,
	AccountPositionClosedEvent,
	AccountPositionAdjustedEvent
)

from .settlement_events import (
	AccountSettlementStartedEvent,
	AccountSettlementCompletedEvent,
	AccountReconciliationStartedEvent,
	AccountReconciliationCompletedEvent
)

# 导出所有账户事件类
__all__ = [
	# 资金余额事件
	"AccountBalanceUpdatedEvent",
	"AccountDepositCompletedEvent",
	"AccountWithdrawCompletedEvent",
	"AccountAssetUpdatedEvent",

	# 账户持仓事件
	"AccountPositionUpdatedEvent",
	"AccountPositionOpenedEvent",
	"AccountPositionClosedEvent",
	"AccountPositionAdjustedEvent",

	# 结算对账事件
	"AccountSettlementStartedEvent",
	"AccountSettlementCompletedEvent",
	"AccountReconciliationStartedEvent",
	"AccountReconciliationCompletedEvent",
]