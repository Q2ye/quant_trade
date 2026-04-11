# types.py              # 事件类型定义

# 交易相关事件类型
EVENT_TRADE_SIGNAL = "trade.signal"
EVENT_TRADE_ORDER = "trade.order"
EVENT_TRADE_EXECUTION = "trade.execution"
EVENT_TRADE_POSITION = "trade.position"
EVENT_TRADE_RISK = "trade.risk"
EVENT_TRADE_ACCOUNT = "trade.account"

# 订单状态
ORDER_STATUS_PENDING = "pending"
ORDER_STATUS_FILLED = "filled"
ORDER_STATUS_CANCELLED = "cancelled"
ORDER_STATUS_REJECTED = "rejected"
ORDER_STATUS_FAILED = "failed"

# 交易方向
TRADE_DIRECTION_BUY = "buy"
TRADE_DIRECTION_SELL = "sell"

# 订单类型
ORDER_TYPE_LIMIT = "limit"
ORDER_TYPE_MARKET = "market"

# 风险级别
RISK_LEVEL_INFO = "info"
RISK_LEVEL_WARNING = "warning"
RISK_LEVEL_DANGER = "danger"

# 信号状态
SIGNAL_STATUS_RECEIVED = "received"
SIGNAL_STATUS_PROCESSING = "processing"
SIGNAL_STATUS_EXECUTED = "executed"
SIGNAL_STATUS_REJECTED = "rejected"
SIGNAL_STATUS_FAILED = "failed"
SIGNAL_STATUS_ERROR = "error"