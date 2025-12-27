# shared/config/constants.py
"""
系统常量定义
"""

from enum import Enum, IntEnum
from typing import Dict, Any


class ErrorCode(IntEnum):
	"""错误码枚举"""

	# 成功
	SUCCESS = 0

	# 通用错误
	UNKNOWN_ERROR = 10000
	VALIDATION_ERROR = 10001
	DATABASE_ERROR = 10002
	NETWORK_ERROR = 10003
	TIMEOUT_ERROR = 10004

	# 业务错误
	STRATEGY_NOT_FOUND = 20001
	STRATEGY_DISABLED = 20002
	INSUFFICIENT_BALANCE = 20003
	RISK_CHECK_FAILED = 20004
	ORDER_REJECTED = 20005

	# 系统错误
	CONFIG_ERROR = 30001
	SERVICE_UNAVAILABLE = 30002
	PERMISSION_DENIED = 30003
	AUTHENTICATION_FAILED = 30004


class OrderStatus(str, Enum):
	"""订单状态"""

	PENDING = "pending"  # 待提交
	SUBMITTED = "submitted"  # 已提交
	PARTIALLY_FILLED = "partially_filled"  # 部分成交
	FILLED = "filled"  # 完全成交
	CANCELLED = "cancelled"  # 已取消
	REJECTED = "rejected"  # 已拒绝
	EXPIRED = "expired"  # 已过期


class OrderType(str, Enum):
	"""订单类型"""

	MARKET = "market"  # 市价单
	LIMIT = "limit"  # 限价单
	STOP = "stop"  # 止损单
	STOP_LIMIT = "stop_limit"  # 止损限价单


class OrderDirection(str, Enum):
	"""订单方向"""

	BUY = "buy"  # 买入
	SELL = "sell"  # 卖出


class StrategyType(str, Enum):
	"""策略类型"""

	ALPHA = "alpha"  # Alpha策略
	CTA = "cta"  # CTA策略
	HFT = "hft"  # 高频策略
	AI = "ai"  # AI策略
	MANUAL = "manual"  # 手动交易


class Market(str, Enum):
	"""市场类型"""

	A_SHARE = "A"  # A股
	HK = "HK"  # 港股
	US = "US"  # 美股


# 时间常量（秒）
TIME_CONSTANTS: Dict[str, int] = {
	"SECOND": 1,
	"MINUTE": 60,
	"HOUR": 3600,
	"DAY": 86400,
	"WEEK": 604800,
	"MONTH": 2592000,  # 30天
	"YEAR": 31536000,  # 365天
}

# 交易时间
TRADING_HOURS = {
	"A_SHARE": {
		"morning_open": "09:30",
		"morning_close": "11:30",
		"afternoon_open": "13:00",
		"afternoon_close": "15:00",
	},
	"HK": {
		"morning_open": "09:30",
		"morning_close": "12:00",
		"afternoon_open": "13:00",
		"afternoon_close": "16:00",
	},
	"US": {
		"open": "09:30",
		"close": "16:00",
	}
}

# 数据频率
DATA_FREQUENCY = {
	"TICK": "tick",
	"1MIN": "1min",
	"5MIN": "5min",
	"15MIN": "15min",
	"30MIN": "30min",
	"60MIN": "60min",
	"DAILY": "daily",
	"WEEKLY": "weekly",
	"MONTHLY": "monthly",
}

# 技术指标类型
TECHNICAL_INDICATORS = {
	"TREND": ["MA", "EMA", "MACD", "BOLL"],
	"MOMENTUM": ["RSI", "KDJ", "WR", "CCI"],
	"VOLATILITY": ["ATR", "STDDEV", "BBANDS"],
	"VOLUME": ["OBV", "VOLUME_MA", "MFI"],
}

# 缓存键前缀
CACHE_KEY_PREFIX = {
	"MARKET_DATA": "market:data:",
	"STRATEGY": "strategy:",
	"ORDER": "order:",
	"ACCOUNT": "account:",
	"USER": "user:",
	"CONFIG": "config:",
}

# 分页默认值
PAGINATION_DEFAULTS = {
	"PAGE_SIZE": 20,
	"MAX_PAGE_SIZE": 100,
	"DEFAULT_PAGE": 1,
}

# 文件路径
FILE_PATHS = {
	"LOG_DIR": "logs",
	"DATA_DIR": "data",
	"CONFIG_DIR": "config",
	"STRATEGY_DIR": "strategies",
	"BACKUP_DIR": "backups",
}

# 正则表达式
REGEX_PATTERNS = {
	"STOCK_CODE": r"^[0-9]{6}\.[A-Z]{2}$",  # 000001.SZ
	"EMAIL": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
	"PHONE": r"^1[3-9]\d{9}$",
	"DATE": r"^\d{4}-\d{2}-\d{2}$",
	"DATETIME": r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$",
}