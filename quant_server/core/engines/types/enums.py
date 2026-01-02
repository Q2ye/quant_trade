"""
系统枚举定义
集中定义量化交易系统中使用的所有枚举类型，确保类型一致性和可维护性

设计原则：
1. 单一来源：每个枚举只在一个地方定义
2. 语义清晰：枚举值具有明确的业务含义
3. 分类组织：按业务领域组织枚举
4. 扩展友好：支持新增枚举值不影响现有代码
"""

from enum import Enum
from typing import Dict


# ==================== 系统通用枚举 ====================

class SystemMode(Enum):
    """系统运行模式"""
    DEVELOPMENT = "development"  # 开发模式
    TESTING = "testing"  # 测试模式
    STAGING = "staging"  # 预发布模式
    PRODUCTION = "production"  # 生产模式
    BACKTEST = "events"  # 回测模式
    SIMULATION = "simulation"  # 模拟交易模式


class ComponentStatus(Enum):
    """组件通用状态"""
    UNINITIALIZED = "uninitialized"  # 未初始化
    INITIALIZING = "initializing"  # 初始化中
    INITIALIZED = "initialized"  # 已初始化
    STARTING = "starting"  # 启动中
    RUNNING = "running"  # 运行中
    STOPPING = "stopping"  # 停止中
    STOPPED = "stopped"  # 已停止
    ERROR = "error"  # 错误状态
    DEGRADED = "degraded"  # 降级运行


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"  # 健康
    DEGRADED = "degraded"  # 降级
    UNHEALTHY = "unhealthy"  # 不健康
    FAILED = "failed"  # 失败
    UNKNOWN = "unknown"  # 未知


class PriorityLevel(Enum):
    """优先级级别"""
    LOWEST = 0  # 最低优先级
    LOW = 1  # 低优先级
    NORMAL = 2  # 正常优先级
    HIGH = 3  # 高优先级
    HIGHEST = 4  # 最高优先级
    CRITICAL = 5  # 关键优先级


# ==================== 引擎相关枚举 ====================

class EngineType(Enum):
    """引擎类型"""
    MAIN = "main"  # 主引擎
    EVENT = "event"  # 事件引擎
    STRATEGY = "events"  # 策略引擎
    TRADE = "events"  # 交易引擎
    BACKTEST = "events"  # 回测引擎
    DATA = "events"  # 数据引擎
    RISK = "risk"  # 风控引擎
    ACCOUNT = "events"  # 账户引擎
    ANALYSIS = "events"  # 分析引擎
    MONITOR = "events"  # 监控引擎
    SYSTEM = "events"  # 系统引擎
    CUSTOM = "custom"  # 自定义引擎


class EngineCategory(Enum):
    """引擎分类"""
    CORE = "core"  # 核心引擎（系统必需）
    BUSINESS = "business"  # 业务引擎（交易相关）
    INFRASTRUCTURE = "infrastructure"  # 基础设施引擎
    SUPPORT = "support"  # 支持引擎
    UTILITY = "utility"  # 工具引擎


class EngineErrorLevel(Enum):
    """引擎错误级别"""
    INFO = "info"  # 信息
    WARNING = "warning"  # 警告
    ERROR = "error"  # 错误
    CRITICAL = "critical"  # 严重
    FATAL = "fatal"  # 致命


# ==================== 事件相关枚举 ====================

class EventType(Enum):
    """事件类型"""
    # 系统事件
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    SYSTEM_ERROR = "system_error"
    SYSTEM_WARNING = "system_warning"
    SYSTEM_HEALTH_CHECK = "system_health_check"

    # 引擎事件
    ENGINE_START = "engine_start"
    ENGINE_STOP = "engine_stop"
    ENGINE_STATUS_CHANGE = "engine_status_change"
    ENGINE_HEALTH_CHANGE = "engine_health_change"
    ENGINE_STARTED = "engine_started"
    ENGINE_STOPPED = "engine_stopped"
    ENGINE_START_FAILED = "engine_start_failed"
    ENGINE_STOP_FAILED = "engine_stop_failed"
    ENGINE_HEALTH_CHECK = "engine_health_check"

    # 市场事件
    MARKET_OPEN = "market_open"
    MARKET_CLOSE = "market_close"
    MARKET_TICK = "market_tick"
    MARKET_BAR = "market_bar"
    MARKET_INDEX = "market_index"

    # 策略事件
    STRATEGY_INIT = "strategy_init"
    STRATEGY_START = "strategy_start"
    STRATEGY_STOP = "strategy_stop"
    STRATEGY_SIGNAL = "strategy_signal"
    STRATEGY_ERROR = "strategy_error"

    # 交易事件
    ORDER_SUBMIT = "order_submit"
    ORDER_CANCEL = "order_cancel"
    ORDER_FILL = "order_fill"
    ORDER_REJECT = "order_reject"
    TRADE_EXECUTE = "trade_execute"
    POSITION_UPDATE = "position_update"

    # 风控事件
    RISK_WARNING = "risk_warning"
    RISK_ALERT = "risk_alert"
    RISK_ACTION = "risk_action"

    # 数据事件
    DATA_UPDATE = "data_update"
    DATA_SYNC = "data_sync"
    DATA_ERROR = "data_error"

    # 监控事件
    MONITOR_METRIC = "monitor_metric"
    MONITOR_ALERT = "monitor_alert"
    ENGINE_ALERT = "engine_alert"
    ENGINE_METRIC = "engine_metric"
    MONITOR_HEALTH = "monitor_health"


class EventPriority(Enum):
    """事件优先级"""
    LOW = 0  # 低优先级（日志、统计等）
    NORMAL = 1  # 正常优先级（常规业务）
    HIGH = 2  # 高优先级（交易信号）
    CRITICAL = 3  # 关键优先级（系统警报）


# ==================== 交易相关枚举 ====================

class MarketType(Enum):
    """市场类型"""
    STOCK = "stock"  # 股票
    FUTURES = "futures"  # 期货
    OPTION = "option"  # 期权
    FOREX = "forex"  # 外汇
    CRYPTO = "crypto"  # 加密货币
    BOND = "bond"  # 债券
    FUND = "fund"  # 基金


class OrderDirection(Enum):
    """订单方向"""
    BUY = "buy"  # 买入
    SELL = "sell"  # 卖出
    SHORT = "short"  # 卖空
    COVER = "cover"  # 平空


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"  # 市价单
    LIMIT = "limit"  # 限价单
    STOP = "stop"  # 止损单
    STOP_LIMIT = "stop_limit"  # 止损限价单
    ICBERG = "iceberg"  # 冰山单
    TWAP = "twap"  # 时间加权单
    VWAP = "vwap"  # 成交量加权单


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"  # 待处理
    SUBMITTED = "submitted"  # 已提交
    PARTIAL_FILLED = "partial_filled"  # 部分成交
    FILLED = "filled"  # 完全成交
    CANCELLED = "cancelled"  # 已取消
    REJECTED = "rejected"  # 已拒绝
    ERROR = "error"  # 错误状态


class TimeInForce(Enum):
    """订单有效时间"""
    DAY = "day"  # 当日有效
    GTC = "gtc"  # 撤销前有效
    IOC = "ioc"  # 立即或取消
    FOK = "fok"  # 全部或取消
    GTX = "gtx"  # 延长交易时段


class TradeSide(Enum):
    """交易方向"""
    OPEN = "open"  # 开仓
    CLOSE = "close"  # 平仓
    CLOSE_TODAY = "close_today"  # 平今仓


# ==================== 策略相关枚举 ====================

class StrategyType(Enum):
    """策略类型"""
    TECHNICAL = "technical"  # 技术指标策略
    QUANTITATIVE = "quantitative"  # 量化策略
    ARBITRAGE = "arbitrage"  # 套利策略
    HIGH_FREQUENCY = "high_frequency"  # 高频策略
    MACHINE_LEARNING = "machine_learning"  # 机器学习策略
    REINFORCEMENT_LEARNING = "reinforcement_learning"  # 强化学习策略
    CUSTOM = "custom"  # 自定义策略


class StrategyStatus(Enum):
    """策略状态"""
    LOADED = "loaded"  # 已加载
    INITIALIZED = "initialized"  # 已初始化
    RUNNING = "running"  # 运行中
    PAUSED = "paused"  # 已暂停
    STOPPED = "stopped"  # 已停止
    ERROR = "error"  # 错误状态


class SignalType(Enum):
    """信号类型"""
    BUY = "buy"  # 买入信号
    SELL = "sell"  # 卖出信号
    SHORT = "short"  # 卖空信号
    COVER = "cover"  # 平空信号
    HOLD = "hold"  # 持有信号
    EXIT = "exit"  # 退出信号


# ==================== 数据相关枚举 ====================

class DataFrequency(Enum):
    """数据频率"""
    TICK = "tick"  # Tick数据
    MINUTE = "minute"  # 分钟数据
    HOUR = "hour"  # 小时数据
    DAY = "day"  # 日数据
    WEEK = "week"  # 周数据
    MONTH = "month"  # 月数据
    QUARTER = "quarter"  # 季度数据
    YEAR = "year"  # 年数据


class DataSource(Enum):
    """数据源"""
    TUSHARE = "tushare"  # Tushare
    BAOSTOCK = "baostock"  # Baostock
    RICEQUANT = "ricequant"  # RiceQuant
    JOINQUANT = "joinquant"  # JoinQuant
    LOCAL = "local"  # 本地数据
    CUSTOM = "custom"  # 自定义数据源


class DataQuality(Enum):
    """数据质量"""
    EXCELLENT = "excellent"  # 优秀
    GOOD = "good"  # 良好
    FAIR = "fair"  # 一般
    POOR = "poor"  # 较差
    UNUSABLE = "unusable"  # 不可用


# ==================== 风控相关枚举 ====================

class RiskLevel(Enum):
    """风险级别"""
    LOW = "low"  # 低风险
    MEDIUM = "medium"  # 中风险
    HIGH = "high"  # 高风险
    EXTREME = "extreme"  # 极高风险


class RiskAction(Enum):
    """风控动作"""
    ALLOW = "allow"  # 允许
    WARN = "warn"  # 警告
    LIMIT = "limit"  # 限制
    REJECT = "reject"  # 拒绝
    STOP = "stop"  # 停止


class RiskType(Enum):
    """风险类型"""
    MARKET = "market"  # 市场风险
    CREDIT = "credit"  # 信用风险
    LIQUIDITY = "liquidity"  # 流动性风险
    OPERATIONAL = "operational"  # 操作风险
    SYSTEMIC = "systemic"  # 系统性风险


# ==================== 账户相关枚举 ====================

class AccountType(Enum):
    """账户类型"""
    STOCK = "stock"  # 股票账户
    FUTURES = "futures"  # 期货账户
    OPTION = "option"  # 期权账户
    MARGIN = "margin"  # 融资融券账户
    SIMULATION = "simulation"  # 模拟账户
    PAPER = "paper"  # 纸面账户


class PositionDirection(Enum):
    """持仓方向"""
    LONG = "long"  # 多头
    SHORT = "short"  # 空头
    NET = "net"  # 净持仓


class SettlementStatus(Enum):
    """结算状态"""
    PENDING = "pending"  # 待结算
    PROCESSING = "processing"  # 结算中
    COMPLETED = "completed"  # 已结算
    FAILED = "failed"  # 结算失败


# ==================== 监控相关枚举 ====================

class AlertLevel(Enum):
    """警报级别"""
    INFO = "info"  # 信息
    WARNING = "warning"  # 警告
    ERROR = "error"  # 错误
    CRITICAL = "critical"  # 严重
    FATAL = "fatal"  # 致命


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"  # 计数器
    GAUGE = "gauge"  # 仪表
    HISTOGRAM = "histogram"  # 直方图
    SUMMARY = "summary"  # 摘要


class CheckType(Enum):
    """检查类型"""
    HEALTH = "health"  # 健康检查
    PERFORMANCE = "performance"  # 性能检查
    AVAILABILITY = "availability"  # 可用性检查
    SECURITY = "security"  # 安全检查


# ==================== 配置相关枚举 ====================

class ConfigType(Enum):
    """配置类型"""
    STRING = "string"  # 字符串类型
    INTEGER = "integer"  # 整数类型
    FLOAT = "float"  # 浮点数类型
    BOOLEAN = "boolean"  # 布尔类型
    JSON = "json"  # JSON类型
    LIST = "list"  # 列表类型
    DICT = "dict"  # 字典类型


# ==================== 工具函数 ====================

class EnumHelper:
    """枚举工具类"""

    @staticmethod
    def get_enum_by_value(enum_class, value):
        """根据值获取枚举实例

        Args:
            enum_class: 枚举类
            value: 枚举值

        Returns:
            enum: 枚举实例，找不到时返回None
        """
        for enum in enum_class:
            if enum.value == value:
                return enum
        return None

    @staticmethod
    def get_all_values(enum_class):
        """获取枚举的所有值

        Args:
            enum_class: 枚举类

        Returns:
            list: 枚举值列表
        """
        return [enum.value for enum in enum_class]

    @staticmethod
    def get_all_names(enum_class):
        """获取枚举的所有名称

        Args:
            enum_class: 枚举类

        Returns:
            list: 枚举名称列表
        """
        return [enum.name for enum in enum_class]

    @staticmethod
    def is_valid_value(enum_class, value):
        """检查值是否为有效的枚举值

        Args:
            enum_class: 枚举类
            value: 要检查的值

        Returns:
            bool: 是否为有效枚举值
        """
        return any(enum.value == value for enum in enum_class)

    @staticmethod
    def get_enum_map(enum_class):
        """获取枚举的映射字典

        Args:
            enum_class: 枚举类

        Returns:
            Dict[str, str]: {name: value} 映射
        """
        return {enum.name: enum.value for enum in enum_class}