"""
系统实体类定义
集中定义量化交易系统中的核心数据模型，确保数据一致性和类型安全

设计原则：
1. 不可变性：实体类一旦创建，状态不可改变
2. 验证：构造函数中包含数据验证
3. 序列化：支持转换为字典和JSON
4. 业务语义：字段命名反映业务含义
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any, List, Optional


# ==================== 基础实体类 ====================

@dataclass(frozen=True)
class BaseEntity:
    """基础实体类

    所有实体类的基类，提供通用的序列化和验证功能
    使用frozen=True确保实体不可变
    """

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            Dict[str, Any]: 字典表示
        """
        return asdict(self)

    def to_json(self, **kwargs) -> str:
        """转换为JSON字符串

        Args:
            **kwargs: json.dumps的额外参数

        Returns:
            str: JSON字符串
        """
        return json.dumps(self.to_dict(), **kwargs)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """从字典创建实例

        Args:
            data: 字典数据

        Returns:
            BaseEntity: 实体实例

        Raises:
            TypeError: 当传入的字典包含无效字段或缺少必需字段时
        """
        try:
            if hasattr(cls, '__annotations__'):
                valid_keys = cls.__annotations__.keys()
                filtered_data = {k: v for k, v in data.items() if k in valid_keys}
                
                # 检查必需字段
                import inspect
                sig = inspect.signature(cls.__init__)
                required_params = [p.name for p in sig.parameters.values() 
                                 if p.default == inspect.Parameter.empty and p.name != 'self']
                
                missing_fields = [f for f in required_params if f not in filtered_data]
                if missing_fields:
                    raise TypeError(f"缺少必需字段: {missing_fields}")
                
                try:
                    return cls(**filtered_data)
                except TypeError as e:
                    if "unexpected keyword argument" in str(e):
                        # 处理意外实参错误
                        valid_fields = list(getattr(cls, '__annotations__', {}).keys())
                        invalid_fields = [k for k in filtered_data.keys() if k not in valid_fields]
                        raise TypeError(f"无效字段: {invalid_fields}. 有效字段: {valid_fields}")
                    raise
            else:
                try:
                    return cls(**data)
                except TypeError as e:
                    if "unexpected keyword argument" in str(e):
                        # 处理意外实参错误
                        valid_fields = list(getattr(cls, '__annotations__', {}).keys())
                        invalid_fields = [k for k in data.keys() if k not in valid_fields]
                        raise TypeError(f"无效字段: {invalid_fields}. 有效字段: {valid_fields}")
                    raise
        except TypeError as e:
            # 提供更详细的错误信息
            if "unexpected keyword argument" in str(e):
                invalid_fields = [k for k in data.keys() if k not in getattr(cls, '__annotations__', {})]
                raise TypeError(f"无效字段: {invalid_fields}. 有效字段: {list(getattr(cls, '__annotations__', {}).keys())}")
            elif "missing required" in str(e):
                raise
            else:
                # 重新抛出其他TypeError
                raise

    @classmethod
    def from_json(cls, json_str: str):
        """从JSON字符串创建实例

        Args:
            json_str: JSON字符串

        Returns:
            BaseEntity: 实体实例
        """
        data = json.loads(json_str)
        return cls.from_dict(data)


# ==================== 引擎相关实体 ====================

@dataclass(frozen=True)
class EngineConfigEntity(BaseEntity):
    """引擎配置

    定义引擎的初始化参数和运行配置
    """
    name: str                       # 引擎名称（唯一标识）
    engine_type: str                # 引擎类型
    auto_start: bool = True         # 是否自动启动
    max_retries: int = 3            # 最大重试次数
    retry_delay: float = 1.0        # 重试延迟（秒）
    config: Dict[str, Any] = field(default_factory=dict)  # 引擎特定配置
    dependencies: List[str] = field(default_factory=list)  # 依赖的引擎名称
    health_check_interval: float = 60.0  # 健康检查间隔（秒）
    graceful_shutdown_timeout: float = 30.0  # 优雅停止超时（秒）

    def __post_init__(self):
        """后初始化验证"""
        if not self.name:
            raise ValueError("引擎名称不能为空")
        if self.max_retries < 0:
            raise ValueError("最大重试次数必须大于等于0")
        if self.retry_delay < 0:
            raise ValueError("重试延迟必须大于等于0")
        if self.health_check_interval <= 0:
            raise ValueError("健康检查间隔必须大于0")
        if self.graceful_shutdown_timeout < 0:
            raise ValueError("优雅停止超时必须大于等于0")


@dataclass(frozen=True)
class EngineMetricsEntity(BaseEntity):
    """引擎性能指标"""
    uptime: float = 0.0                     # 运行时长（秒）
    processed_events: int = 0               # 处理的事件数量
    success_rate: float = 1.0               # 成功率（0-1）
    avg_processing_time: float = 0.0        # 平均处理时间（毫秒）
    memory_usage_mb: float = 0.0            # 内存使用（MB）
    cpu_percent: float = 0.0                # CPU使用率（%）
    error_count: int = 0                    # 错误计数
    last_error_time: Optional[datetime] = None  # 最后错误时间
    last_success_time: Optional[datetime] = None  # 最后成功时间
    last_update_time: Optional[datetime] = None  # 最后更新时间
    last_stop_time: Optional[datetime] = None  # 最后停止时间
    custom_metrics: Dict[str, Any] = field(default_factory=dict)  # 自定义指标


@dataclass(frozen=True)
class EngineStatus(BaseEntity):
    """引擎状态"""
    engine_name: str                        # 引擎名称
    status: str                            # 状态值
    health: str                            # 健康状态
    uptime: float                          # 运行时长（秒）
    last_update: datetime                  # 最后更新时间
    error: Optional[str] = None            # 错误信息
    warning: Optional[str] = None          # 警告信息
    metrics: EngineMetricsEntity = field(default_factory=EngineMetricsEntity)  # 性能指标
    dependencies: List[str] = field(default_factory=list)  # 依赖状态


# ==================== 交易相关实体 ====================

@dataclass(frozen=True)
class Order(BaseEntity):
    """订单实体"""
    order_id: str                          # 订单ID（唯一）
    strategy_id: str                       # 策略ID
    account_id: str                        # 账户ID
    symbol: str                           # 交易标的
    direction: str                        # 订单方向
    order_type: str                       # 订单类型
    quantity: Decimal                     # 数量
    price: Optional[Decimal] = None       # 价格（市价单为None）
    filled_quantity: Decimal = Decimal("0")  # 已成交数量
    avg_price: Optional[Decimal] = None   # 平均成交价格
    status: str = "pending"               # 订单状态
    time_in_force: str = "day"            # 订单有效期
    create_time: datetime = field(default_factory=datetime.now)  # 创建时间
    update_time: datetime = field(default_factory=datetime.now)  # 更新时间
    cancel_time: Optional[datetime] = None  # 取消时间
    fill_time: Optional[datetime] = None  # 成交时间
    remarks: Optional[str] = None         # 备注

    def __post_init__(self):
        """验证订单数据"""
        if self.quantity <= Decimal("0"):
            raise ValueError("订单数量必须大于0")
        if self.order_type == "limit" and self.price is None:
            raise ValueError("限价单必须指定价格")
        if self.filled_quantity > self.quantity:
            raise ValueError("已成交数量不能超过订单数量")


@dataclass(frozen=True)
class Trade(BaseEntity):
    """成交实体"""
    trade_id: str                          # 成交ID（唯一）
    order_id: str                          # 订单ID
    strategy_id: str                       # 策略ID
    account_id: str                        # 账户ID
    symbol: str                           # 交易标的
    direction: str                        # 成交方向
    price: Decimal                        # 成交价格
    quantity: Decimal                     # 成交数量
    amount: Decimal                       # 成交金额（price * quantity）
    commission: Decimal = Decimal("0")    # 手续费
    tax: Decimal = Decimal("0")           # 税费
    net_amount: Decimal = Decimal("0")    # 净金额（amount - commission - tax）
    trade_time: datetime = field(default_factory=datetime.now)  # 成交时间
    settlement_date: Optional[date] = None  # 结算日期
    remarks: Optional[str] = None         # 备注


@dataclass(frozen=True)
class Position(BaseEntity):
    """持仓实体"""
    account_id: str                        # 账户ID
    symbol: str                           # 交易标的
    direction: str                        # 持仓方向
    quantity: Decimal                     # 持仓数量
    available_quantity: Decimal           # 可用数量
    cost_price: Decimal                   # 成本价
    market_price: Decimal                 # 市价
    market_value: Decimal                 # 市值
    pnl: Decimal                          # 浮动盈亏
    pnl_rate: Decimal                     # 盈亏比例
    update_time: datetime = field(default_factory=datetime.now)  # 更新时间
    strategy_id: Optional[str] = None     # 策略ID（None表示总持仓）
    frozen_quantity: Decimal = Decimal("0")  # 冻结数量

    @property
    def total_value(self) -> Decimal:
        """总价值（成本+盈亏）"""
        return self.cost_price * self.quantity + self.pnl


@dataclass(frozen=True)
class Account(BaseEntity):
    """账户实体"""
    account_id: str                        # 账户ID（唯一）
    account_type: str                      # 账户类型
    account_name: str                      # 账户名称
    broker: str                           # 券商/经纪商
    total_asset: Decimal                  # 总资产
    available_cash: Decimal               # 可用资金
    frozen_cash: Decimal = Decimal("0")   # 冻结资金
    market_value: Decimal = Decimal("0")  # 持仓市值
    pnl: Decimal = Decimal("0")           # 浮动盈亏
    pnl_rate: Decimal = Decimal("0")      # 盈亏比例
    risk_level: str = "medium"            # 风险等级
    status: str = "active"                # 账户状态
    create_time: datetime = field(default_factory=datetime.now)  # 创建时间
    update_time: datetime = field(default_factory=datetime.now)  # 更新时间
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据


# ==================== 策略相关实体 ====================

@dataclass(frozen=True)
class StrategyConfig(BaseEntity):
    """策略配置"""
    strategy_id: str                       # 策略ID（唯一）
    strategy_name: str                     # 策略名称
    strategy_type: str                     # 策略类型
    class_name: str                       # 策略类名
    module_path: str                      # 模块路径
    parameters: Dict[str, Any] = field(default_factory=dict)  # 策略参数
    enabled: bool = True                  # 是否启用
    auto_start: bool = False              # 是否自动启动
    initial_capital: Decimal = Decimal("1000000")  # 初始资金
    max_position_ratio: Decimal = Decimal("1.0")  # 最大仓位比例
    max_drawdown: Decimal = Decimal("0.2")  # 最大回撤限制
    create_time: datetime = field(default_factory=datetime.now)  # 创建时间
    update_time: datetime = field(default_factory=datetime.now)  # 更新时间


@dataclass(frozen=True)
class StrategyStatusEntity(BaseEntity):
    """策略状态数据实体"""
    strategy_id: str                       # 策略ID
    status: str                           # 运行状态
    health: str                           # 健康状态
    start_time: Optional[datetime] = None  # 启动时间
    stop_time: Optional[datetime] = None  # 停止时间
    total_pnl: Decimal = Decimal("0")     # 总盈亏
    total_trades: int = 0                 # 总交易次数
    win_rate: Decimal = Decimal("0")      # 胜率
    sharpe_ratio: Decimal = Decimal("0")  # 夏普比率
    max_drawdown: Decimal = Decimal("0")  # 最大回撤
    update_time: datetime = field(default_factory=datetime.now)  # 更新时间


@dataclass(frozen=True)
class Signal(BaseEntity):
    """交易信号"""
    signal_id: str                         # 信号ID（唯一）
    strategy_id: str                       # 策略ID
    symbol: str                           # 交易标的
    signal_type: str                      # 信号类型
    strength: Decimal = Decimal("1.0")    # 信号强度（0-1）
    price: Optional[Decimal] = None       # 建议价格
    quantity: Optional[Decimal] = None    # 建议数量
    confidence: Decimal = Decimal("0.5")  # 置信度（0-1）
    reason: Optional[str] = None          # 信号原因
    create_time: datetime = field(default_factory=datetime.now)  # 创建时间
    expire_time: Optional[datetime] = None  # 过期时间


# ==================== 市场数据实体 ====================

@dataclass(frozen=True)
class MarketData(BaseEntity):
    """市场数据基类"""
    symbol: str                           # 交易标的
    timestamp: datetime                   # 时间戳
    data_type: str                       # 数据类型
    source: str = "default"              # 数据源


@dataclass(frozen=True)
class TickData(BaseEntity):
    """Tick数据"""
    price: Decimal                       # 最新价
    volume: Decimal                      # 成交量
    amount: Decimal                      # 成交额
    bid_price_1: Optional[Decimal] = None  # 买一价
    bid_volume_1: Optional[Decimal] = None  # 买一量
    ask_price_1: Optional[Decimal] = None  # 卖一价
    ask_volume_1: Optional[Decimal] = None  # 卖一量
    open_interest: Optional[Decimal] = None  # 持仓量（期货）


@dataclass(frozen=True)
class BarData(BaseEntity):
    """K线数据"""
    ts_code: str                         # 交易标的代码
    period: str                          # 周期（1min, 5min, daily等）
    open: float                          # 开盘价
    high: float                          # 最高价
    low: float                           # 最低价
    close: float                         # 收盘价
    volume: float                        # 成交量
    amount: float = 0.0                  # 成交额
    turnover: float = 0.0                #  turnover
    trade_date: Any = None               # 交易日期
    trade_time: Optional[datetime] = None  # 交易时间


@dataclass(frozen=True)
class DepthData(MarketData):
    """深度数据"""
    bids: List[Dict[str, Decimal]] = field(default_factory=list)  # 买盘
    asks: List[Dict[str, Decimal]] = field(default_factory=list)  # 卖盘
    depth_level: int = 10                # 深度级别


# ==================== 风控相关实体 ====================

@dataclass(frozen=True)
class RiskRule(BaseEntity):
    """风控规则"""
    rule_id: str                          # 规则ID（唯一）
    rule_name: str                        # 规则名称
    rule_type: str                        # 规则类型
    condition: str                        # 条件表达式
    action: str                          # 触发动作
    level: str = "warning"               # 风险级别
    enabled: bool = True                  # 是否启用
    priority: int = 0                     # 优先级
    description: Optional[str] = None     # 规则描述
    parameters: Dict[str, Any] = field(default_factory=dict)  # 参数
    create_time: datetime = field(default_factory=datetime.now)  # 创建时间


@dataclass(frozen=True)
class RiskAlert(BaseEntity):
    """风险警报"""
    alert_id: str                         # 警报ID（唯一）
    rule_id: str                          # 规则ID
    alert_type: str                       # 警报类型
    level: str                           # 警报级别
    message: str                         # 警报消息
    data: Dict[str, Any] = field(default_factory=dict)  # 相关数据
    create_time: datetime = field(default_factory=datetime.now)  # 创建时间
    acknowledged: bool = False            # 是否已确认
    acknowledged_by: Optional[str] = None  # 确认人
    acknowledged_time: Optional[datetime] = None  # 确认时间
    resolved: bool = False                # 是否已解决
    resolved_time: Optional[datetime] = None  # 解决时间


# ==================== 监控相关实体 ====================

@dataclass(frozen=True)
class Metric(BaseEntity):
    """监控指标"""
    metric_id: str                        # 指标ID（唯一）
    metric_name: str                      # 指标名称
    metric_type: str                      # 指标类型
    value: Any                           # 指标值
    timestamp: datetime = field(default_factory=datetime.now)  # 时间戳
    tags: Dict[str, str] = field(default_factory=dict)  # 标签
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据


@dataclass(frozen=True)
class Alert(BaseEntity):
    """监控警报"""
    alert_id: str                         # 警报ID（唯一）
    alert_name: str                       # 警报名称
    alert_type: str                       # 警报类型
    level: str                           # 警报级别
    message: str                         # 警报消息
    source: str                          # 警报来源
    data: Dict[str, Any] = field(default_factory=dict)  # 相关数据
    create_time: datetime = field(default_factory=datetime.now)  # 创建时间
    acknowledged: bool = False            # 是否已确认
    resolved: bool = False                # 是否已解决
    resolved_time: Optional[datetime] = None  # 解决时间


# ==================== 事件相关实体 ====================

@dataclass(frozen=True)
class EventEntity(BaseEntity):
    """事件实体"""
    event_id: str                         # 事件ID（唯一）
    event_type: str                       # 事件类型
    source: str                          # 事件来源
    data: Dict[str, Any] = field(default_factory=dict)  # 事件数据
    timestamp: datetime = field(default_factory=datetime.now)  # 时间戳
    priority: str = "normal"                     # 优先级
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据


# ==================== 系统配置实体 ====================

@dataclass(frozen=True)
class SystemConfig(BaseEntity):
    """系统配置"""
    system_name: str = "量化交易系统"  # 系统名称
    version: str = "1.0.0"  # 系统版本
    mode: str = "development"  # 系统模式
    auto_start_engines: bool = True  # 是否自动启动引擎
    enable_monitoring: bool = True  # 是否启用监控
    enable_web_socket: bool = True  # 是否启用WebSocket
    max_concurrent_tasks: int = 100  # 最大并发任务数
    shutdown_timeout: float = 30.0  # 关闭超时时间（秒）
    engine_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # 引擎配置

    def validate(self) -> List[str]:
        """验证配置

        Returns:
            List[str]: 错误信息列表
        """
        errors = []

        if not self.system_name or not isinstance(self.system_name, str):
            errors.append("系统名称必须是非空字符串")

        if not self.version or not isinstance(self.version, str):
            errors.append("系统版本必须是非空字符串")

        if self.max_concurrent_tasks <= 0:
            errors.append("最大并发任务数必须大于0")

        if self.shutdown_timeout < 0:
            errors.append("关闭超时时间必须大于等于0")

        return errors


@dataclass(frozen=True)
class ConfigItem(BaseEntity):
    """配置项"""
    config_id: str                        # 配置ID（唯一）
    config_key: str                       # 配置键
    config_value: Any                     # 配置值
    config_type: str = "string"           # 配置类型
    description: Optional[str] = None     # 配置描述
    is_required: bool = False             # 是否必需
    default_value: Optional[Any] = None   # 默认值
    create_time: datetime = field(default_factory=datetime.now)  # 创建时间
    update_time: datetime = field(default_factory=datetime.now)  # 更新时间


# ==================== 引擎状态实体 ====================

@dataclass(frozen=True)
class EngineHealthInfo(BaseEntity):
    """引擎健康信息"""
    engine_name: str                        # 引擎名称
    status: str                            # 状态
    health: str                            # 健康状态
    uptime: float                          # 运行时长
    error: Optional[str] = None            # 错误信息
    error_level: Optional[str] = None      # 错误级别
    dependencies: List[str] = field(default_factory=list)  # 依赖列表
    metrics: Dict[str, Any] = field(default_factory=dict)  # 指标
    dependency_health: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # 依赖健康
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())  # 时间戳


@dataclass(frozen=True)
class SystemStatus(BaseEntity):
    """系统状态"""
    system_name: str                        # 系统名称
    version: str                           # 版本
    mode: str                              # 模式
    startup_time: Optional[str] = None     # 启动时间
    status: Dict[str, Any] = field(default_factory=dict)  # 状态信息
    engines: Dict[str, Any] = field(default_factory=dict)  # 引擎信息
    monitoring: Dict[str, Any] = field(default_factory=dict)  # 监控信息
    web_socket: Dict[str, Any] = field(default_factory=dict)  # WebSocket信息
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())  # 时间戳


# ==================== 监控相关实体 ====================

@dataclass(frozen=True)
class MonitorStatus(BaseEntity):
    """监控器状态"""
    is_monitoring: bool = False            # 是否正在监控
    monitoring_interval: float = 5.0       # 监控间隔
    engine_count: int = 0                  # 引擎数量
    metric_count: int = 0                  # 指标数量
    alert_rule_count: int = 0              # 警报规则数量
    active_alert_count: int = 0            # 活跃警报数量
    total_alert_count: int = 0             # 总警报数量
    alert_handler_count: int = 0           # 警报处理器数量
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())  # 时间戳


@dataclass(frozen=True)
class EngineMonitorRecord(BaseEntity):
    """引擎监控记录"""
    engine_name: str                        # 引擎名称
    metric_name: str                        # 指标名称
    value: float                           # 指标值
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())  # 时间戳
    tags: Dict[str, str] = field(default_factory=dict)  # 标签


# ==================== 工具函数 ====================

class EntityFactory:
    """实体工厂"""

    @staticmethod
    def create_order(**kwargs) -> Order:
        """创建订单

        Args:
            **kwargs: 订单参数

        Returns:
            Order: 订单实例
        """
        return Order(**kwargs)

    @staticmethod
    def create_trade(**kwargs) -> Trade:
        """创建成交

        Args:
            **kwargs: 成交参数

        Returns:
            Trade: 成交实例
        """
        return Trade(**kwargs)

    @staticmethod
    def create_position(**kwargs) -> Position:
        """创建持仓

        Args:
            **kwargs: 持仓参数

        Returns:
            Position: 持仓实例
        """
        return Position(**kwargs)

    @staticmethod
    def create_strategy_config(**kwargs) -> StrategyConfig:
        """创建策略配置

        Args:
            **kwargs: 策略配置参数

        Returns:
            StrategyConfig: 策略配置实例
        """
        return StrategyConfig(**kwargs)

    @staticmethod
    def create_event(**kwargs) -> EventEntity:
        """创建事件

        Args:
            **kwargs: 事件参数

        Returns:
            Event: 事件实例
        """
        return EventEntity(**kwargs)

    @staticmethod
    def create_metric(**kwargs) -> Metric:
        """创建指标

        Args:
            **kwargs: 指标参数

        Returns:
            Metric: 指标实例
        """
        return Metric(**kwargs)

    @staticmethod
    def create_alert(**kwargs) -> Alert:
        """创建警报

        Args:
            **kwargs: 警报参数

        Returns:
            Alert: 警报实例
        """
        return Alert(**kwargs)

    @staticmethod
    def batch_create_from_dicts(entity_class, dict_list: List[Dict[str, Any]]):
        """批量从字典创建实体

        Args:
            entity_class: 实体类
            dict_list: 字典列表

        Returns:
            List[BaseEntity]: 实体列表
        """
        return [entity_class.from_dict(data) for data in dict_list]