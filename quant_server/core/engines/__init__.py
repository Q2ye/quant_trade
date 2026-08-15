"""
quant_server/core/engines/__init__.py
量化交易引擎模块

此模块包含量化交易系统的所有引擎组件，提供统一的引擎管理框架。
包括基础引擎、事件引擎、交易引擎、策略引擎等各种类型的引擎实现。

模块结构：
- base: 引擎基类和核心框架
- system: 系统引擎（事件引擎、主引擎、注册表等）
- types: 统一类型定义（枚举和实体类）
- utils: 引擎工具类（工厂、监控器等）

主要功能：
1. 统一的引擎生命周期管理
2. 引擎状态监控和健康检查
3. 事件驱动的引擎间通信
4. 可扩展的引擎架构设计
5. 完善的错误处理和恢复机制
"""

from .base import EngineBase, EngineRecord, EngineStatusValidator
from .system import (
    EventEngine,
    MainEngine,
    EngineRegistry,
    EngineRecord as SystemEngineRecord
)
from .types import (
	# 枚举类型
	SystemMode,
	ComponentStatus,
	HealthStatus,
	PriorityLevel,
	EngineType,
	EngineCategory,
	EngineErrorLevel,
	EventType,
	OrderDirection,
	OrderType,
	OrderStatus,
	TimeInForce,
	RiskLevel,
	AlertLevel,
	MetricType,

	# 实体类
	BaseEntity,
	EngineConfigEntity,
	EngineMetricsEntity,
	BarData,
	Metric,
	Alert,
	SystemConfig,
)
from .utils import (
    # 引擎工厂
    EngineDescriptor,
    EngineFactory,
    get_engine_factory,
    create_engine,
    get_engine,

    # 引擎监控
    MonitorAlert,
    EngineMetric,
    MetricStatistic,
    AlertRule,
    EngineMonitor,
)

__all__ = [
    # 基础类
    'EngineBase',
    'EngineRecord',
    'EngineStatusValidator',

    # 系统引擎
    'EventEngine',
    'MainEngine',
    'EngineRegistry',
    'SystemEngineRecord',

    # 类型定义 - 枚举
    'SystemMode',
    'ComponentStatus',
    'HealthStatus',
    'PriorityLevel',
    'EngineType',
    'EngineCategory',
    'EngineErrorLevel',
    'EventType',
    'OrderDirection',
    'OrderType',
    'OrderStatus',
    'TimeInForce',
    'RiskLevel',
    'AlertLevel',
    'MetricType',

    # 类型定义 - 实体类
    'BaseEntity',
    'BarData',
    'Metric',
    'Alert',
    'EngineConfigEntity',
    'EngineMetricsEntity',
    'SystemConfig',

    # 引擎工具
    'EngineDescriptor',
    'EngineFactory',
    'get_engine_factory',
    'create_engine',
    'get_engine',
    'MonitorAlert',
    'EngineMetric',
    'MetricStatistic',
    'AlertRule',
    'EngineMonitor',
]

# 版本信息
__version__ = '1.0.0'
__author__ = '量化交易系统团队'
__description__ = '量化交易引擎系统'
