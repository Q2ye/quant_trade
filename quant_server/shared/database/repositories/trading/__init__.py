# quant_server/shared/database/repositories/trading/__init__.py
"""
交易领域Repository包初始化
"""
# 订单模块
from .order.order_repo import OrderRepository
from .order.trade_repo import TradeRepository
from .order.trade_instruction_repo import TradeInstructionRepository
from .order.order_template_repo import OrderTemplateRepository

# 持仓模块
from .position.position_repo import PositionRepository
from .position.position_adjustment_repo import PositionAdjustmentRepository
from .position.position_snapshot_repo import PositionSnapshotRepository

# 风险模块
from .risk.risk_rule_repo import RiskRuleRepository
from .risk.risk_event_repo import RiskEventRepository
from .risk.blacklist_repo import BlacklistRepository

# 辅助模块
from .support.trade_fee_repo import TradeFeeRepository
# from .support.broker_connection_repo import BrokerConnectionRepository

# 账户模块（兼容旧代码）
from shared.database.repositories.account.asset.account_repo import AccountRepository

__all__ = [
    # 订单模块
    "OrderRepository",
    "TradeRepository",
    "TradeInstructionRepository",
    "OrderTemplateRepository",

    # 持仓模块
    "PositionRepository",
    "PositionAdjustmentRepository",
    "PositionSnapshotRepository",

    # 风险模块
    "RiskRuleRepository",
    "RiskEventRepository",
    "BlacklistRepository",

    # 辅助模块
    "TradeFeeRepository",
    # "BrokerConnectionRepository",

    # 账户模块（兼容旧代码）
    "AccountRepository",
]