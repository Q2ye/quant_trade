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
from builtins import int
from enum import Enum
from typing import Type


# ==================== 系统模式枚举 ====================

class SystemMode(str, Enum):
    """
    系统模式枚举

    定义系统的运行模式，不同模式下系统行为可能不同。
    """

    DEVELOPMENT = "development"      # 开发模式
    TESTING = "testing"              # 测试模式
    STAGING = "staging"              # 预发布模式
    PRODUCTION = "production"        # 生产模式
    SIMULATION = "simulation"        # 模拟模式
    BACKTEST = "backtest"            # 回测模式


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
    """

    # 未初始化状态
    UNINITIALIZED = ("uninitialized", 0)
    INITIALIZING = ("initializing", 1)
    INITIALIZED = ("initialized", 2)

    # 运行状态
    STARTING = ("starting", 3)
    RUNNING = ("running", 4)
    PAUSED = ("paused", 9)
    DEGRADED = ("degraded", 8)

    # 停止状态
    STOPPING = ("stopping", 5)
    STOPPED = ("stopped", 6)

    # 错误状态
    ERROR = ("error", 7)

    def __new__(cls, value: str, code: int):
        """创建枚举实例，同时绑定字符串值和整数状态码"""
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj._code = code
        return obj

    @property
    def code(self) -> int:
        """获取整数状态码"""
        return self._code

    @classmethod
    def from_code(cls, code: int) -> 'ComponentStatus':
        """根据状态码反向查找枚举成员"""
        for member in cls:
            if member._code == code:
                return member
        raise ValueError(f"No ComponentStatus with code {code}")

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
    HEALTHY = ("healthy", 0)

    # 亚健康状态，功能受限但仍在运行
    DEGRADED = ("degraded", 1)

    # 不健康状态，功能异常但未完全失效
    UNHEALTHY = ("unhealthy", 2)

    # 失败状态，功能完全失效
    FAILED = ("failed", 3)

    # 未知状态，无法确定健康状况
    UNKNOWN = ("unknown", 4)

    def __new__(cls, value: str, code: int):
        """创建枚举实例，同时绑定字符串值和整数状态码"""
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj._code = code
        return obj

    @property
    def code(self) -> int:
        """获取整数状态码"""
        return self._code

    @classmethod
    def from_code(cls, code: int) -> 'HealthStatus':
        """根据状态码反向查找枚举成员"""
        for member in cls:
            if member._code == code:
                return member
        raise ValueError(f"No HealthStatus with code {code}")

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


# ==================== 引擎分类枚举 ====================

class EngineCategory(str, Enum):
    """
    引擎分类枚举

    定义引擎的业务分类。
    """

    SYSTEM = "system"               # 系统引擎
    DATA = "data"                   # 数据引擎
    STRATEGY = "strategy"           # 策略引擎
    TRADE = "trade"                 # 交易引擎
    BACKTEST = "backtest"           # 回测引擎
    ANALYSIS = "analysis"           # 分析引擎
    ACCOUNT = "account"             # 账户引擎
    MONITOR = "monitor"             # 监控引擎
    CUSTOM = "custom"               # 自定义引擎
    TEST = "test"                   # 测试引擎


class EngineType(str, Enum):
    """
    引擎类型枚举

    定义系统中所有引擎的类型。
    每个业务引擎都应该有明确的类型标识。
    """

    # 系统引擎
    MAIN = "main"
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


# ==================== 事件优先级枚举 ====================

class EventPriority(str, Enum):
    """
    事件优先级枚举

    定义事件的优先级，用于事件队列处理顺序。
    """

    HIGHEST = "highest"              # 最高优先级
    HIGH = "high"                    # 高优先级
    NORMAL = "normal"                # 正常优先级
    LOW = "low"                      # 低优先级
    LOWEST = "lowest"                # 最低优先级


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


# ==================== 市场类型枚举 ====================

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


# ==================== 订单类型枚举 ====================

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


# ==================== 订单方向枚举 ====================

class OrderDirection(str, Enum):
    """
    订单方向枚举

    定义订单的交易方向。
    """

    BUY = "buy"                      # 买入
    SELL = "sell"                    # 卖出
    SHORT = "short"                  # 卖空（做空）
    COVER = "cover"                  # 平仓（空头平仓）


# ==================== 订单状态枚举 ====================

class OrderStatus(str, Enum):
    """
    订单状态枚举

    定义订单的生命周期状态。
    """

    PENDING = "pending"              # 待处理
    SUBMITTING = "submitting"        # 提交中
    SUBMITTED = "submitted"          # 已提交
    PARTIALLY_FILLED = "partially_filled"  # 部分成交
    FILLED = "filled"                # 全部成交
    CANCELLING = "cancelling"        # 取消中
    CANCELLED = "cancelled"          # 已取消
    REJECTED = "rejected"            # 已拒绝
    EXPIRED = "expired"              # 已过期
    ERROR = "error"                  # 错误状态


# ==================== 订单方向枚举（兼容旧版本） ====================

class OrderSide(str, Enum):
    """
    订单方向枚举

    定义交易订单方向。
    """

    BUY = "buy"                # 买入
    SELL = "sell"              # 卖出
    SHORT = "short"            # 卖空
    COVER = "cover"            # 平仓


# ==================== 交易方向枚举 ====================

class TradeSide(str, Enum):
    """
    交易方向枚举

    定义成交的交易方向。
    """

    BUY = "buy"                      # 买入
    SELL = "sell"                    # 卖出
    BUY_OPEN = "buy_open"            # 买入开仓（期货）
    SELL_OPEN = "sell_open"          # 卖出开仓（期货）
    BUY_CLOSE = "buy_close"          # 买入平仓（期货）
    SELL_CLOSE = "sell_close"        # 卖出平仓（期货）


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


# ==================== 策略类型枚举 ====================

class StrategyType(str, Enum):
    """
    策略类型枚举

    定义量化策略的类型。
    """

    ALPHA = "alpha"                  # Alpha策略
    BETA = "beta"                    # Beta策略
    CTA = "cta"                      # 商品交易顾问策略
    ARBITRAGE = "arbitrage"          # 套利策略
    MARKET_MAKING = "market_making"  # 做市策略
    HEDGING = "hedging"              # 对冲策略
    FACTOR = "factor"                # 因子策略
    MACHINE_LEARNING = "machine_learning"  # 机器学习策略
    DEEP_LEARNING = "deep_learning"  # 深度学习策略
    REINFORCEMENT_LEARNING = "reinforcement_learning"  # 强化学习策略
    QUANTITATIVE = "quantitative"    # 量化策略
    DISCRETIONARY = "discretionary"  # 主观交易策略
    HYBRID = "hybrid"                # 混合策略


# ==================== 策略状态枚举 ====================

class StrategyRuntimeStatus(str, Enum):
    """
    策略运行状态枚举

    定义策略的运行状态。
    """

    STOPPED = "stopped"              # 已停止
    STARTING = "starting"            # 启动中
    RUNNING = "running"              # 运行中
    PAUSED = "paused"                # 已暂停
    STOPPING = "stopping"            # 停止中
    ERROR = "error"                  # 错误状态
    BACKTESTING = "backtesting"      # 回测中
    OPTIMIZING = "optimizing"        # 优化中


# ==================== 信号类型枚举 ====================

class SignalType(str, Enum):
    """
    信号类型枚举

    定义交易信号的类型。
    """

    BUY = "buy"                      # 买入信号
    SELL = "sell"                    # 卖出信号
    HOLD = "hold"                    # 持有信号
    STOP_LOSS = "stop_loss"          # 止损信号
    TAKE_PROFIT = "take_profit"      # 止盈信号
    ENTRY = "entry"                  # 入场信号
    EXIT = "exit"                    # 出场信号
    REBALANCE = "rebalance"          # 再平衡信号
    HEDGE = "hedge"                  # 对冲信号

# ==================== 信号方向枚举 v2.4 ====================

class SignalDirection(str, Enum):
    """
    信号方向枚举 — 策略层使用，需映射到 OrderDirection 才能写入 DB

    适用场景：策略产生信号时使用的方向语义（做多/做空/平仓）
    DB 持久化前须通过 SIGNAL_TO_TRADE_DIRECTION 映射为 OrderDirection。
    """

    LONG = "long"              # 做多/买入 → OrderDirection.BUY
    SHORT = "short"            # 做空/卖出 → OrderDirection.SHORT
    CLOSE_LONG = "close_long"  # 平多仓 → OrderDirection.SELL
    CLOSE_SHORT = "close_short" # 平空仓 → OrderDirection.COVER

# 信号方向 → 交易方向映射（唯一权威映射表）
SIGNAL_TO_TRADE_DIRECTION = {
    SignalDirection.LONG: OrderDirection.BUY,
    SignalDirection.SHORT: OrderDirection.SHORT,
    SignalDirection.CLOSE_LONG: OrderDirection.SELL,
    SignalDirection.CLOSE_SHORT: OrderDirection.COVER,
}

# 反向映射：交易方向 → 信号方向
TRADE_TO_SIGNAL_DIRECTION = {v: k for k, v in SIGNAL_TO_TRADE_DIRECTION.items()}

def signal_to_order_direction(signal_dir: str) -> str:
    """v2.4: 将策略信号方向转换为 DB 订单方向

    Args:
        signal_dir: 信号方向字符串 (long/short/close_long/close_short)

    Returns:
        DB 订单方向字符串 (buy/sell/short/cover)，无效输入返回 "buy"
    """
    mapping = {
        "long": "buy",
        "short": "short",
        "close_long": "sell",
        "close_short": "cover",
    }
    return mapping.get(signal_dir, "buy")


# ==================== 数据频率枚举 ====================

class DataFrequency(str, Enum):
    """
    数据频率枚举

    定义市场数据的频率。
    """

    TICK = "tick"                    # Tick级数据
    SECOND = "1s"                    # 1秒数据
    MINUTE_1 = "1m"                  # 1分钟数据
    MINUTE_5 = "5m"                  # 5分钟数据
    MINUTE_15 = "15m"                # 15分钟数据
    MINUTE_30 = "30m"                # 30分钟数据
    HOUR = "1h"                      # 1小时数据
    DAY = "1d"                       # 日数据
    WEEK = "1w"                      # 周数据
    MONTH = "1M"                     # 月数据
    QUARTER = "1Q"                   # 季度数据
    YEAR = "1Y"                      # 年数据


# ==================== 数据源枚举 ====================

class DataSource(str, Enum):
    """
    数据源枚举

    定义市场数据的来源。
    """

    LOCAL = "local"                  # 本地数据源
    TUSHARE = "tushare"              # TuShare数据源
    AKSHARE = "akshare"              # AKShare数据源
    BAOSTOCK = "baostock"            # 聚宽数据源
    RICEQUANT = "ricequant"          # RiceQuant数据源
    JOINQUANT = "joinquant"          # JoinQuant数据源
    WIND = "wind"                    # Wind数据源
    BLOOMBERG = "bloomberg"          # 彭博数据源
    REUTERS = "reuters"              # 路透数据源
    CUSTOM = "custom"                # 自定义数据源
    EXCHANGE = "exchange"            # 交易所数据源
    BROKER = "broker"                # 券商数据源


# ==================== 数据质量枚举 ====================

class DataQuality(str, Enum):
    """
    数据质量枚举

    定义数据的质量等级。
    """

    EXCELLENT = "excellent"          # 优秀：数据完整、准确
    GOOD = "good"                    # 良好：少量缺失或错误
    FAIR = "fair"                    # 一般：部分数据缺失
    POOR = "poor"                    # 较差：大量数据缺失
    UNUSABLE = "unusable"            # 不可用：数据严重错误
    UNKNOWN = "unknown"              # 未知质量


# ==================== 风险等级枚举 ====================

class RiskLevel(str, Enum):
    """
    风险等级枚举

    定义风险的等级。
    """

    LOW = "low"                      # 低风险
    MEDIUM = "medium"                # 中风险
    HIGH = "high"                    # 高风险
    VERY_HIGH = "very_high"          # 极高风险
    CRITICAL = "critical"            # 致命风险


# ==================== 风险操作枚举 ====================

class RiskAction(str, Enum):
    """
    风险操作枚举

    定义风险触发后的操作。
    """

    WARN = "warn"                    # 警告
    REJECT = "reject"                # 拒绝
    STOP = "stop"                    # 停止
    LIQUIDATE = "liquidate"          # 强制平仓
    REDUCE = "reduce"                # 减仓
    NOTIFY = "notify"                # 通知
    LOG = "log"                      # 记录日志
    IGNORE = "ignore"                # 忽略


# ==================== 风险类型枚举 ====================

class RiskType(str, Enum):
    """
    风险类型枚举

    定义风险的类型。
    """

    MARKET = "market"                # 市场风险
    CREDIT = "credit"                # 信用风险
    LIQUIDITY = "liquidity"          # 流动性风险
    OPERATIONAL = "operational"      # 操作风险
    SYSTEMATIC = "systematic"        # 系统性风险
    MODEL = "model"                  # 模型风险
    CONCENTRATION = "concentration"  # 集中度风险
    LEVERAGE = "leverage"            # 杠杆风险
    COUNTERPARTY = "counterparty"    # 交易对手风险
    SETTLEMENT = "settlement"        # 结算风险


# ==================== 账户类型枚举 ====================

class AccountType(str, Enum):
    """
    账户类型枚举

    定义账户的类型。
    """

    STOCK = "stock"                  # 股票账户
    FUTURES = "futures"              # 期货账户
    OPTIONS = "options"              # 期权账户
    FOREX = "forex"                  # 外汇账户
    CRYPTO = "crypto"                # 加密货币账户
    MARGIN = "margin"                # 保证金账户
    CASH = "cash"                    # 现金账户
    SIMULATION = "simulation"        # 模拟账户
    PAPER = "paper"                  # 纸上交易账户
    INSTITUTIONAL = "institutional"  # 机构账户
    RETAIL = "retail"                # 零售账户


# ==================== 持仓方向枚举 ====================

class PositionDirection(str, Enum):
    """
    持仓方向枚举

    定义持仓的方向。
    """

    LONG = "long"                    # 多头持仓
    SHORT = "short"                  # 空头持仓
    NET = "net"                      # 净持仓
    BOTH = "both"                    # 双向持仓


# ==================== 结算状态枚举 ====================

class SettlementStatus(str, Enum):
    """
    结算状态枚举

    定义交易的结算状态。
    """

    PENDING = "pending"              # 待结算
    SETTLED = "settled"              # 已结算
    FAILED = "failed"                # 结算失败
    CANCELLED = "cancelled"          # 已取消
    REVERSED = "reversed"            # 已冲正


# ==================== 警报级别枚举 ====================

class AlertLevel(str, Enum):
    """
    警报级别枚举

    定义警报的严重级别。
    """

    INFO = "info"                    # 信息
    WARNING = "warning"              # 警告
    ERROR = "error"                  # 错误
    CRITICAL = "critical"            # 严重
    EMERGENCY = "emergency"          # 紧急


# ==================== 指标类型枚举 ====================

class MetricType(str, Enum):
    """
    指标类型枚举

    定义监控指标的类型。
    """

    GAUGE = "gauge"                  # 瞬时值
    COUNTER = "counter"              # 计数器
    HISTOGRAM = "histogram"          # 直方图
    SUMMARY = "summary"              # 摘要
    RATE = "rate"                    # 速率
    PERCENTILE = "percentile"        # 百分位数
    TREND = "trend"                  # 趋势
    VOLUME = "volume"                # 成交量
    PRICE = "price"                  # 价格
    PERFORMANCE = "performance"      # 性能


# ==================== 检查类型枚举 ====================

class CheckType(str, Enum):
    """
    检查类型枚举

    定义健康检查的类型。
    """

    PING = "ping"                    # Ping检查
    HTTP = "http"                    # HTTP检查
    TCP = "tcp"                      # TCP检查
    DATABASE = "database"            # 数据库检查
    API = "api"                      # API检查
    DISK = "disk"                    # 磁盘检查
    MEMORY = "memory"                # 内存检查
    CPU = "cpu"                      # CPU检查
    CUSTOM = "custom"                # 自定义检查


# ==================== 枚举辅助类 ====================

class EnumHelper:
    """
    枚举辅助类

    提供枚举操作的辅助方法。
    """

    @staticmethod
    def get_display_name(enum_class: Type[Enum], value: str) -> str:
        """
        获取枚举值的显示名称

        Args:
            enum_class: 枚举类
            value: 枚举值

        Returns:
            str: 显示名称
        """
        try:
            member = getattr(enum_class, value.upper())
            return member.value
        except AttributeError:
            return value

    @staticmethod
    def get_choices(enum_class: Type[Enum]) -> list:
        """
        获取枚举的选择列表（用于Django等框架）

        Args:
            enum_class: 枚举类

        Returns:
            list: [(value, display_name), ...]
        """
        return [(member.value, member.value) for member in enum_class]

    @staticmethod
    def is_valid(enum_class: Type[Enum], value: str) -> bool:
        """
        检查值是否为有效的枚举值

        Args:
            enum_class: 枚举类
            value: 待检查的值

        Returns:
            bool: 是否为有效的枚举值
        """
        return any(member.value == value for member in enum_class)

    @staticmethod
    def get_all_values(enum_class: Type[Enum]) -> list:
        """
        获取枚举的所有值

        Args:
            enum_class: 枚举类

        Returns:
            list: 所有枚举值的列表
        """
        return [member.value for member in enum_class]

    @staticmethod
    def get_by_value(enum_class: Type[Enum], value: str) -> Enum:
        """
        根据值获取枚举成员

        Args:
            enum_class: 枚举类
            value: 枚举值

        Returns:
            Enum: 枚举成员

        Raises:
            ValueError: 如果值无效
        """
        for member in enum_class:
            if member.value == value:
                return member
        raise ValueError(f"Invalid value '{value}' for enum {enum_class.__name__}")


# ==================== 辅助函数 ====================

def get_enum_values(enum_class: Type[Enum]) -> list:
    """
    获取枚举类的所有值

    Args:
        enum_class: 枚举类

    Returns:
        list: 枚举值列表
    """
    return [member.value for member in enum_class]


def get_enum_from_value(enum_class: Type[Enum], value: str) -> Enum:
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
    # 系统模式枚举
    "SystemMode",

    # 核心状态枚举
    "ComponentStatus",
    "HealthStatus",
    "PriorityLevel",

    # 引擎相关枚举
    "EngineCategory",
    "EngineType",
    "EngineErrorLevel",

    # 资源相关枚举
    "ResourceType",

    # 事件相关枚举
    "EventPriority",
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
    "OrderDirection",
    "OrderStatus",
    "OrderSide",
    "TradeSide",
    "TimeInForce",

    # 策略相关枚举
    "StrategyType",
    "StrategyRuntimeStatus",

    # 信号相关枚举
    "SignalType",
    "SignalDirection",
    "SIGNAL_TO_TRADE_DIRECTION",
    "signal_to_order_direction",

    # 数据相关枚举
    "DataFrequency",
    "DataSource",
    "DataQuality",

    # 风险相关枚举
    "RiskLevel",
    "RiskAction",
    "RiskType",

    # 账户相关枚举
    "AccountType",
    "PositionDirection",

    # 结算相关枚举
    "SettlementStatus",

    # 监控相关枚举
    "AlertLevel",
    "MetricType",
    "CheckType",

    # 枚举辅助类
    "EnumHelper",

    # 辅助函数
    "get_enum_values",
    "get_enum_from_value"
]