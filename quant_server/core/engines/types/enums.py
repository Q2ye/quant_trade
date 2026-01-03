"""
枚举类型定义 - 量化交易系统核心枚举

位置：quant_server/core/engines/types/enums.py

此文件定义了系统中使用的所有枚举类型，包括：
- 组件状态：EngineStatus, ComponentStatus
- 健康状态：HealthStatus
- 优先级：PriorityLevel
- 引擎类型：EngineType
- 引擎错误级别：EngineErrorLevel
- 资源类型：ResourceType（新增）
- 事件类型：EventType（部分）
- 任务状态：TaskStatus

设计原则：
1. 统一命名规范：使用PascalCase命名枚举类，使用UPPER_CASE命名枚举值
2. 语义化值：枚举值使用明确的字符串描述
3. 向后兼容：新增枚举值不影响现有代码
4. 扩展性：预留足够的枚举值供未来扩展
"""

from enum import Enum, IntEnum, auto


class ComponentStatus(str, Enum):
    """
    组件状态枚举

    定义系统组件（引擎、服务等）的生命周期状态。
    基于状态机设计，确保状态转换的合法性。

    状态转换规则（设计文档定义）：
    UNINITIALIZED -> INITIALIZING
    INITIALIZING -> INITIALIZED | ERROR
    INITIALIZED -> STARTING | STOPPED
    STARTING -> RUNNING | ERROR
    RUNNING -> STOPPING | ERROR | DEGRADED | PAUSED
    STOPPING -> STOPPED | ERROR
    STOPPED -> STARTING | UNINITIALIZED
    ERROR -> STOPPED | STARTING
    DEGRADED -> RUNNING | STOPPING | ERROR
    PAUSED -> RUNNING | STOPPING | ERROR
    """

    # 未初始化状态
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"

    # 运行状态
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"

    # 停止状态
    STOPPING = "stopping"
    STOPPED = "stopped"

    # 错误状态
    ERROR = "error"

    @classmethod
    def is_running_state(cls, status: 'ComponentStatus') -> bool:
        """检查是否为运行状态

        Args:
            status: 组件状态

        Returns:
            bool: 是否为运行状态
        """
        return status in [cls.RUNNING, cls.DEGRADED, cls.PAUSED]

    @classmethod
    def is_stopped_state(cls, status: 'ComponentStatus') -> bool:
        """检查是否为停止状态

        Args:
            status: 组件状态

        Returns:
            bool: 是否为停止状态
        """
        return status in [cls.STOPPED, cls.ERROR]

    @classmethod
    def is_transient_state(cls, status: 'ComponentStatus') -> bool:
        """检查是否为过渡状态

        Args:
            status: 组件状态

        Returns:
            bool: 是否为过渡状态
        """
        return status in [cls.INITIALIZING, cls.STARTING, cls.STOPPING]


class HealthStatus(str, Enum):
    """
    健康状态枚举

    定义组件的健康状态，用于监控和告警。
    健康状态独立于运行状态，反映组件的内部健康情况。
    """

    # 健康状态良好
    HEALTHY = "healthy"

    # 亚健康状态，功能受限但仍在运行
    DEGRADED = "degraded"

    # 不健康状态，功能异常但未完全失效
    UNHEALTHY = "unhealthy"

    # 失败状态，功能完全失效
    FAILED = "failed"

    # 未知状态，无法确定健康状况
    UNKNOWN = "unknown"

    @classmethod
    def is_healthy(cls, health: 'HealthStatus') -> bool:
        """检查是否为健康状态

        Args:
            health: 健康状态

        Returns:
            bool: 是否为健康状态
        """
        return health == cls.HEALTHY

    @classmethod
    def needs_attention(cls, health: 'HealthStatus') -> bool:
        """检查是否需要关注

        Args:
            health: 健康状态

        Returns:
            bool: 是否需要关注
        """
        return health in [cls.DEGRADED, cls.UNHEALTHY, cls.FAILED]


class PriorityLevel(str, Enum):
    """
    优先级级别枚举

    定义事件、任务、消息的优先级。
    用于资源调度和任务处理顺序控制。
    """

    # 最高优先级：系统关键操作，必须立即处理
    CRITICAL = "critical"

    # 高优先级：重要业务操作，需要尽快处理
    HIGH = "high"

    # 普通优先级：一般业务操作，按顺序处理
    NORMAL = "normal"

    # 低优先级：后台任务，可延迟处理
    LOW = "low"

    # 最低优先级：非紧急任务，可批量处理
    BACKGROUND = "background"

    @classmethod
    def get_priority_value(cls, priority: 'PriorityLevel') -> int:
        """获取优先级数值（数值越小优先级越高）

        Args:
            priority: 优先级级别

        Returns:
            int: 优先级数值
        """
        priority_map = {
            cls.CRITICAL: 1,
            cls.HIGH: 2,
            cls.NORMAL: 3,
            cls.LOW: 4,
            cls.BACKGROUND: 5
        }
        return priority_map.get(priority, 3)


class EngineType(str, Enum):
    """
    引擎类型枚举

    定义系统中所有引擎的类型。
    每个业务引擎都应该有明确的类型标识。
    """

    # 系统引擎
    SYSTEM = "system"
    EVENT = "event"
    SCHEDULER = "scheduler"
    MONITOR = "monitor"

    # 数据引擎
    DATA_SYNC = "data_sync"
    DATA_CLEAN = "data_clean"
    DATA_QUALITY = "data_quality"
    DATA_RESEARCH = "data_research"

    # 策略引擎
    STRATEGY_MANAGER = "strategy_manager"
    ALPHA_ENGINE = "alpha_engine"
    CTA_ENGINE = "cta_engine"
    AI_ENGINE = "ai_engine"

    # 交易引擎
    SIGNAL_ENGINE = "signal_engine"
    RISK_ENGINE = "risk_engine"
    EXECUTION_ENGINE = "execution_engine"
    POSITION_ENGINE = "position_engine"

    # 回测引擎
    BACKTEST_ENGINE = "backtest_engine"
    SIMULATION_ENGINE = "simulation_engine"
    OPTIMIZATION_ENGINE = "optimization_engine"
    REPORT_ENGINE = "report_engine"

    # 分析引擎
    PERFORMANCE_ENGINE = "performance_engine"
    ATTRIBUTION_ENGINE = "attribution_engine"
    COMPARISON_ENGINE = "comparison_engine"

    # 账户引擎
    ACCOUNT_ENGINE = "account_engine"
    ASSET_ENGINE = "asset_engine"
    POSITION_SERVICE = "position_service"
    CASH_ENGINE = "cash_engine"

    # 监控引擎
    SYSTEM_MONITOR = "system_monitor"
    RISK_MONITOR = "risk_monitor"
    BUSINESS_MONITOR = "business_monitor"
    ALERT_ENGINE = "alert_engine"

    # 通用/自定义引擎
    CUSTOM = "custom"
    TEST = "test"

    @classmethod
    def get_engine_category(cls, engine_type: 'EngineType') -> str:
        """获取引擎类别

        Args:
            engine_type: 引擎类型

        Returns:
            str: 引擎类别
        """
        category_map = {
            # 系统引擎
            cls.SYSTEM: "system",
            cls.EVENT: "system",
            cls.SCHEDULER: "system",
            cls.MONITOR: "system",

            # 数据引擎
            cls.DATA_SYNC: "data",
            cls.DATA_CLEAN: "data",
            cls.DATA_QUALITY: "data",
            cls.DATA_RESEARCH: "data",

            # 策略引擎
            cls.STRATEGY_MANAGER: "strategy",
            cls.ALPHA_ENGINE: "strategy",
            cls.CTA_ENGINE: "strategy",
            cls.AI_ENGINE: "strategy",

            # 交易引擎
            cls.SIGNAL_ENGINE: "trade",
            cls.RISK_ENGINE: "trade",
            cls.EXECUTION_ENGINE: "trade",
            cls.POSITION_ENGINE: "trade",

            # 回测引擎
            cls.BACKTEST_ENGINE: "backtest",
            cls.SIMULATION_ENGINE: "backtest",
            cls.OPTIMIZATION_ENGINE: "backtest",
            cls.REPORT_ENGINE: "backtest",

            # 分析引擎
            cls.PERFORMANCE_ENGINE: "analysis",
            cls.ATTRIBUTION_ENGINE: "analysis",
            cls.COMPARISON_ENGINE: "analysis",

            # 账户引擎
            cls.ACCOUNT_ENGINE: "account",
            cls.ASSET_ENGINE: "account",
            cls.POSITION_SERVICE: "account",
            cls.CASH_ENGINE: "account",

            # 监控引擎
            cls.SYSTEM_MONITOR: "monitor",
            cls.RISK_MONITOR: "monitor",
            cls.BUSINESS_MONITOR: "monitor",
            cls.ALERT_ENGINE: "monitor",

            # 通用引擎
            cls.CUSTOM: "custom",
            cls.TEST: "test"
        }

        return category_map.get(engine_type, "unknown")


class EngineErrorLevel(str, Enum):
    """
    引擎错误级别枚举

    定义引擎错误的严重程度。
    用于错误处理策略和告警级别判断。
    """

    # 调试级别：用于调试的详细信息，通常不需要关注
    DEBUG = "debug"

    # 信息级别：常规操作信息，用于追踪系统状态
    INFO = "info"

    # 警告级别：潜在问题或非关键错误，需要关注但不会影响核心功能
    WARNING = "warning"

    # 错误级别：明确的错误，影响部分功能但系统仍可运行
    ERROR = "error"

    # 严重级别：严重错误，影响核心功能，需要立即处理
    CRITICAL = "critical"

    @classmethod
    def is_actionable(cls, error_level: 'EngineErrorLevel') -> bool:
        """检查是否需要采取行动

        Args:
            error_level: 错误级别

        Returns:
            bool: 是否需要采取行动
        """
        return error_level in [cls.WARNING, cls.ERROR, cls.CRITICAL]

    @classmethod
    def needs_alert(cls, error_level: 'EngineErrorLevel') -> bool:
        """检查是否需要告警

        Args:
            error_level: 错误级别

        Returns:
            bool: 是否需要告警
        """
        return error_level in [cls.ERROR, cls.CRITICAL]


class ResourceType(str, Enum):
    """
    资源类型枚举

    定义系统中监控和管理的资源类型。
    用于资源使用统计、容量规划和性能优化。

    基于混合架构设计文档，资源类型分为：
    1. 计算资源：CPU、内存、线程等
    2. 存储资源：内存、磁盘、数据库连接等
    3. 网络资源：连接数、带宽、延迟等
    4. 应用资源：队列长度、缓存命中率等
    """

    # ==================== 计算资源 ====================

    # CPU使用率（百分比）
    CPU = "cpu"

    # 内存使用量（MB或百分比）
    MEMORY = "memory"

    # 物理内存使用量（MB）
    MEMORY_RSS = "memory_rss"

    # 虚拟内存使用量（MB）
    MEMORY_VMS = "memory_vms"

    # 线程数量
    THREADS = "threads"

    # 进程数量
    PROCESSES = "processes"

    # GPU使用率（百分比）
    GPU = "gpu"

    # GPU内存使用量（MB）
    GPU_MEMORY = "gpu_memory"

    # ==================== 存储资源 ====================

    # 磁盘使用率（百分比）
    DISK = "disk"

    # 磁盘IOPS（每秒IO操作数）
    DISK_IOPS = "disk_iops"

    # 磁盘吞吐量（MB/s）
    DISK_THROUGHPUT = "disk_throughput"

    # 数据库连接数
    DATABASE_CONNECTIONS = "database_connections"

    # 数据库连接池使用率（百分比）
    DATABASE_POOL = "database_pool"

    # Redis连接数
    REDIS_CONNECTIONS = "redis_connections"

    # Redis内存使用量（MB）
    REDIS_MEMORY = "redis_memory"

    # 文件描述符数量
    FILE_DESCRIPTORS = "file_descriptors"

    # ==================== 网络资源 ====================

    # 网络连接数
    NETWORK_CONNECTIONS = "network_connections"

    # 网络带宽使用率（百分比）
    NETWORK_BANDWIDTH = "network_bandwidth"

    # 网络延迟（毫秒）
    NETWORK_LATENCY = "network_latency"

    # TCP连接数
    TCP_CONNECTIONS = "tcp_connections"

    # UDP连接数
    UDP_CONNECTIONS = "udp_connections"

    # WebSocket连接数
    WEBSOCKET_CONNECTIONS = "websocket_connections"

    # HTTP请求数
    HTTP_REQUESTS = "http_requests"

    # ==================== 应用资源 ====================

    # 消息队列长度
    QUEUE_LENGTH = "queue_length"

    # 缓存命中率（百分比）
    CACHE_HIT_RATE = "cache_hit_rate"

    # 缓存使用量（MB或百分比）
    CACHE_USAGE = "cache_usage"

    # 事件处理速率（事件/秒）
    EVENT_RATE = "event_rate"

    # 任务队列长度
    TASK_QUEUE = "task_queue"

    # 线程池使用率（百分比）
    THREAD_POOL = "thread_pool"

    # 连接池使用率（百分比）
    CONNECTION_POOL = "connection_pool"

    # 数据库查询速率（查询/秒）
    DATABASE_QUERIES = "database_queries"

    # API调用速率（调用/秒）
    API_CALLS = "api_calls"

    # ==================== 业务资源 ====================

    # 策略实例数
    STRATEGY_INSTANCES = "strategy_instances"

    # 持仓数量
    POSITION_COUNT = "position_count"

    # 订单处理速率（订单/秒）
    ORDER_RATE = "order_rate"

    # 交易对数量
    TRADING_PAIRS = "trading_pairs"

    # 账户数量
    ACCOUNT_COUNT = "account_count"

    # 监控指标数量
    METRIC_COUNT = "metric_count"

    # 告警数量
    ALERT_COUNT = "alert_count"

    # ==================== 自定义资源 ====================

    # 自定义资源类型1
    CUSTOM_1 = "custom_1"

    # 自定义资源类型2
    CUSTOM_2 = "custom_2"

    # 自定义资源类型3
    CUSTOM_3 = "custom_3"

    @classmethod
    def get_resource_category(cls, resource_type: 'ResourceType') -> str:
        """获取资源类别

        Args:
            resource_type: 资源类型

        Returns:
            str: 资源类别
        """
        # 计算资源
        if resource_type in [
            cls.CPU, cls.MEMORY, cls.MEMORY_RSS, cls.MEMORY_VMS,
            cls.THREADS, cls.PROCESSES, cls.GPU, cls.GPU_MEMORY
        ]:
            return "compute"

        # 存储资源
        elif resource_type in [
            cls.DISK, cls.DISK_IOPS, cls.DISK_THROUGHPUT,
            cls.DATABASE_CONNECTIONS, cls.DATABASE_POOL,
            cls.REDIS_CONNECTIONS, cls.REDIS_MEMORY,
            cls.FILE_DESCRIPTORS
        ]:
            return "storage"

        # 网络资源
        elif resource_type in [
            cls.NETWORK_CONNECTIONS, cls.NETWORK_BANDWIDTH, cls.NETWORK_LATENCY,
            cls.TCP_CONNECTIONS, cls.UDP_CONNECTIONS,
            cls.WEBSOCKET_CONNECTIONS, cls.HTTP_REQUESTS
        ]:
            return "network"

        # 应用资源
        elif resource_type in [
            cls.QUEUE_LENGTH, cls.CACHE_HIT_RATE, cls.CACHE_USAGE,
            cls.EVENT_RATE, cls.TASK_QUEUE, cls.THREAD_POOL,
            cls.CONNECTION_POOL, cls.DATABASE_QUERIES, cls.API_CALLS
        ]:
            return "application"

        # 业务资源
        elif resource_type in [
            cls.STRATEGY_INSTANCES, cls.POSITION_COUNT, cls.ORDER_RATE,
            cls.TRADING_PAIRS, cls.ACCOUNT_COUNT, cls.METRIC_COUNT, cls.ALERT_COUNT
        ]:
            return "business"

        # 自定义资源
        elif resource_type in [cls.CUSTOM_1, cls.CUSTOM_2, cls.CUSTOM_3]:
            return "custom"

        else:
            return "unknown"

    @classmethod
    def get_resource_units(cls, resource_type: 'ResourceType') -> str:
        """获取资源单位

        Args:
            resource_type: 资源类型

        Returns:
            str: 资源单位
        """
        unit_map = {
            # 计算资源
            cls.CPU: "percent",
            cls.MEMORY: "mb",
            cls.MEMORY_RSS: "mb",
            cls.MEMORY_VMS: "mb",
            cls.THREADS: "count",
            cls.PROCESSES: "count",
            cls.GPU: "percent",
            cls.GPU_MEMORY: "mb",

            # 存储资源
            cls.DISK: "percent",
            cls.DISK_IOPS: "iops",
            cls.DISK_THROUGHPUT: "mbps",
            cls.DATABASE_CONNECTIONS: "count",
            cls.DATABASE_POOL: "percent",
            cls.REDIS_CONNECTIONS: "count",
            cls.REDIS_MEMORY: "mb",
            cls.FILE_DESCRIPTORS: "count",

            # 网络资源
            cls.NETWORK_CONNECTIONS: "count",
            cls.NETWORK_BANDWIDTH: "mbps",
            cls.NETWORK_LATENCY: "ms",
            cls.TCP_CONNECTIONS: "count",
            cls.UDP_CONNECTIONS: "count",
            cls.WEBSOCKET_CONNECTIONS: "count",
            cls.HTTP_REQUESTS: "count",

            # 应用资源
            cls.QUEUE_LENGTH: "count",
            cls.CACHE_HIT_RATE: "percent",
            cls.CACHE_USAGE: "mb",
            cls.EVENT_RATE: "eps",
            cls.TASK_QUEUE: "count",
            cls.THREAD_POOL: "percent",
            cls.CONNECTION_POOL: "percent",
            cls.DATABASE_QUERIES: "qps",
            cls.API_CALLS: "rps",

            # 业务资源
            cls.STRATEGY_INSTANCES: "count",
            cls.POSITION_COUNT: "count",
            cls.ORDER_RATE: "ops",
            cls.TRADING_PAIRS: "count",
            cls.ACCOUNT_COUNT: "count",
            cls.METRIC_COUNT: "count",
            cls.ALERT_COUNT: "count",

            # 自定义资源
            cls.CUSTOM_1: "custom",
            cls.CUSTOM_2: "custom",
            cls.CUSTOM_3: "custom",
        }

        return unit_map.get(resource_type, "unknown")

    @classmethod
    def get_display_name(cls, resource_type: 'ResourceType') -> str:
        """获取资源显示名称

        Args:
            resource_type: 资源类型

        Returns:
            str: 显示名称
        """
        display_map = {
            # 计算资源
            cls.CPU: "CPU使用率",
            cls.MEMORY: "内存使用量",
            cls.MEMORY_RSS: "物理内存",
            cls.MEMORY_VMS: "虚拟内存",
            cls.THREADS: "线程数",
            cls.PROCESSES: "进程数",
            cls.GPU: "GPU使用率",
            cls.GPU_MEMORY: "GPU内存",

            # 存储资源
            cls.DISK: "磁盘使用率",
            cls.DISK_IOPS: "磁盘IOPS",
            cls.DISK_THROUGHPUT: "磁盘吞吐量",
            cls.DATABASE_CONNECTIONS: "数据库连接数",
            cls.DATABASE_POOL: "数据库连接池",
            cls.REDIS_CONNECTIONS: "Redis连接数",
            cls.REDIS_MEMORY: "Redis内存",
            cls.FILE_DESCRIPTORS: "文件描述符",

            # 网络资源
            cls.NETWORK_CONNECTIONS: "网络连接数",
            cls.NETWORK_BANDWIDTH: "网络带宽",
            cls.NETWORK_LATENCY: "网络延迟",
            cls.TCP_CONNECTIONS: "TCP连接数",
            cls.UDP_CONNECTIONS: "UDP连接数",
            cls.WEBSOCKET_CONNECTIONS: "WebSocket连接数",
            cls.HTTP_REQUESTS: "HTTP请求数",

            # 应用资源
            cls.QUEUE_LENGTH: "队列长度",
            cls.CACHE_HIT_RATE: "缓存命中率",
            cls.CACHE_USAGE: "缓存使用量",
            cls.EVENT_RATE: "事件处理速率",
            cls.TASK_QUEUE: "任务队列",
            cls.THREAD_POOL: "线程池",
            cls.CONNECTION_POOL: "连接池",
            cls.DATABASE_QUERIES: "数据库查询速率",
            cls.API_CALLS: "API调用速率",

            # 业务资源
            cls.STRATEGY_INSTANCES: "策略实例数",
            cls.POSITION_COUNT: "持仓数量",
            cls.ORDER_RATE: "订单处理速率",
            cls.TRADING_PAIRS: "交易对数量",
            cls.ACCOUNT_COUNT: "账户数量",
            cls.METRIC_COUNT: "监控指标数量",
            cls.ALERT_COUNT: "告警数量",

            # 自定义资源
            cls.CUSTOM_1: "自定义资源1",
            cls.CUSTOM_2: "自定义资源2",
            cls.CUSTOM_3: "自定义资源3",
        }

        return display_map.get(resource_type, resource_type.value)


class EventType(str, Enum):
    """
    事件类型枚举（部分）

    定义系统中核心事件类型。
    完整的事件类型定义在专门的events模块中。
    """

    # 系统事件
    SYSTEM_STARTED = "system_started"
    SYSTEM_STOPPED = "system_stopped"
    SYSTEM_ERROR = "system_error"

    # 引擎事件
    ENGINE_INITIALIZED = "engine_initialized"
    ENGINE_STARTED = "engine_started"
    ENGINE_STOPPED = "engine_stopped"
    ENGINE_ERROR = "engine_error"
    ENGINE_HEALTH_CHECK = "engine_health_check"
    ENGINE_CONFIG_UPDATED = "engine_config_updated"

    # 监控事件
    METRIC_UPDATED = "metric_updated"
    ALERT_TRIGGERED = "alert_triggered"
    HEALTH_STATUS_CHANGED = "health_status_changed"

    # 数据事件
    DATA_SYNC_STARTED = "data_sync_started"
    DATA_SYNC_COMPLETED = "data_sync_completed"
    DATA_SYNC_FAILED = "data_sync_failed"

    # 策略事件
    STRATEGY_STARTED = "strategy_started"
    STRATEGY_STOPPED = "strategy_stopped"
    STRATEGY_SIGNAL_GENERATED = "strategy_signal_generated"

    # 交易事件
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    TRADE_EXECUTED = "trade_executed"

    # 风险事件
    RISK_RULE_TRIGGERED = "risk_rule_triggered"
    RISK_ALERT_RAISED = "risk_alert_raised"

    # 账户事件
    ACCOUNT_UPDATED = "account_updated"
    POSITION_UPDATED = "position_updated"
    BALANCE_UPDATED = "balance_updated"


class TaskStatus(str, Enum):
    """
    任务状态枚举

    定义异步任务的生命周期状态。
    """

    # 任务已创建但未开始执行
    PENDING = "pending"

    # 任务正在执行中
    RUNNING = "running"

    # 任务执行成功完成
    SUCCESS = "success"

    # 任务执行失败
    FAILED = "failed"

    # 任务被取消
    CANCELLED = "cancelled"

    # 任务超时
    TIMEOUT = "timeout"

    # 任务被挂起（暂停）
    SUSPENDED = "suspended"

    # 任务重试中
    RETRYING = "retrying"


class LogLevel(str, Enum):
    """
    日志级别枚举

    定义日志记录级别，与Python标准库logging级别对应。
    """

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @classmethod
    def to_logging_level(cls, log_level: 'LogLevel') -> int:
        """转换为Python logging级别

        Args:
            log_level: 日志级别

        Returns:
            int: logging级别数值
        """
        import logging
        level_map = {
            cls.DEBUG: logging.DEBUG,
            cls.INFO: logging.INFO,
            cls.WARNING: logging.WARNING,
            cls.ERROR: logging.ERROR,
            cls.CRITICAL: logging.CRITICAL
        }
        return level_map.get(log_level, logging.INFO)


class DatabaseType(str, Enum):
    """
    数据库类型枚举

    定义支持的数据库类型。
    """

    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    REDIS = "redis"
    MONGODB = "mongodb"
    INFLUXDB = "influxdb"
    ELASTICSEARCH = "elasticsearch"


class MarketType(str, Enum):
    """
    市场类型枚举

    定义交易市场类型。
    """

    STOCK = "stock"            # 股票市场
    FUTURES = "futures"        # 期货市场
    OPTIONS = "options"        # 期权市场
    FOREX = "forex"            # 外汇市场
    CRYPTO = "crypto"          # 加密货币市场
    BOND = "bond"              # 债券市场
    COMMODITY = "commodity"    # 商品市场
    INDEX = "index"            # 指数市场


class OrderType(str, Enum):
    """
    订单类型枚举

    定义交易订单类型。
    """

    MARKET = "market"          # 市价单
    LIMIT = "limit"            # 限价单
    STOP = "stop"              # 止损单
    STOP_LIMIT = "stop_limit"  # 止损限价单
    IOC = "ioc"                # 立即成交否则取消
    FOK = "fok"                # 全部成交否则取消


class OrderSide(str, Enum):
    """
    订单方向枚举

    定义交易订单方向。
    """

    BUY = "buy"                # 买入
    SELL = "sell"              # 卖出
    SHORT = "short"            # 卖空
    COVER = "cover"            # 平仓


class TimeInForce(str, Enum):
    """
    订单有效时间枚举

    定义订单的有效时间。
    """

    DAY = "day"                # 当日有效
    GTC = "gtc"                # 撤销前有效
    IOC = "ioc"                # 立即成交否则取消
    FOK = "fok"                # 全部成交否则取消
    GTD = "gtd"                # 指定日期前有效


# ==================== 辅助函数 ====================

def get_enum_values(enum_class: Enum) -> list:
    """
    获取枚举类的所有值

    Args:
        enum_class: 枚举类

    Returns:
        list: 枚举值列表
    """
    return [member.value for member in enum_class]


def get_enum_from_value(enum_class: Enum, value: str) -> Enum:
    """
    根据值获取枚举成员

    Args:
        enum_class: 枚举类
        value: 枚举值

    Returns:
        Enum: 枚举成员

    Raises:
        ValueError: 当值无效时
    """
    for member in enum_class:
        if member.value == value:
            return member
    raise ValueError(f"Invalid value '{value}' for enum {enum_class.__name__}")


# ==================== 导出所有枚举 ====================

__all__ = [
    # 核心状态枚举
    "ComponentStatus",
    "HealthStatus",
    "PriorityLevel",

    # 引擎相关枚举
    "EngineType",
    "EngineErrorLevel",

    # 资源相关枚举（新增）
    "ResourceType",

    # 事件相关枚举
    "EventType",

    # 任务相关枚举
    "TaskStatus",

    # 日志相关枚举
    "LogLevel",

    # 数据库相关枚举
    "DatabaseType",

    # 市场相关枚举
    "MarketType",

    # 交易相关枚举
    "OrderType",
    "OrderSide",
    "TimeInForce",

    # 辅助函数
    "get_enum_values",
    "get_enum_from_value"
]