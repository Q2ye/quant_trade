# constants.py           # 交易模块常量

# 交易相关常量

# 订单状态
ORDER_STATUS = {
    "PENDING": "pending",
    "FILLED": "filled",
    "CANCELLED": "cancelled",
    "REJECTED": "rejected",
    "FAILED": "failed"
}

# 交易方向
TRADE_DIRECTION = {
    "BUY": "buy",
    "SELL": "sell"
}

# 订单类型
ORDER_TYPE = {
    "LIMIT": "limit",
    "MARKET": "market"
}

# 风险级别
RISK_LEVEL = {
    "INFO": "info",
    "WARNING": "warning",
    "DANGER": "danger"
}

# 信号状态
SIGNAL_STATUS = {
    "RECEIVED": "received",
    "PROCESSING": "processing",
    "EXECUTED": "executed",
    "REJECTED": "rejected",
    "FAILED": "failed",
    "ERROR": "error"
}

# 默认配置
DEFAULT_CONFIG = {
    "simulated_trading": True,
    "initial_capital": 1000000,
    "broker": "sim",
    "risk_check_enabled": True,
    "stop_loss_percent": 0.05,
    "max_position_ratio": 0.8,
    "max_single_position_ratio": 0.3,
    "position_risk_threshold": 0.1
}

# 交易费用
TRADING_FEES = {
    "commission_rate": 0.0003,  # 佣金率
    "min_commission": 5,  # 最低佣金
    "stamp_duty": 0.001,  # 印花税
    "transfer_fee": 0.00002  # 过户费
}