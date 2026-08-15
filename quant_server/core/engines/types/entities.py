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




# ==================== 交易相关实体 ====================



# ==================== 策略相关实体 ====================



# ==================== 市场数据实体 ====================



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
    # v2.5: SW 行业指数扩展字段（默认值保持向后兼容）
    name: str = ""                       # 行业/标的名称
    pe: float = 0.0                      # 市盈率
    pb: float = 0.0                      # 市净率
    float_mv: float = 0.0                # 流通市值
    pct_chg: float = 0.0                 # 涨跌幅




# ==================== 风控相关实体 ====================



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




# ==================== 引擎状态实体 ====================



# ==================== 监控相关实体 ====================



# ==================== 工具函数 ====================
