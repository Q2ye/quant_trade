"""
统一类型定义层
集中管理系统中所有的枚举和实体类定义
quant_server/core/engines/types/__init__.py
"""

from .enums import (
	SystemMode,
	ComponentStatus,
	HealthStatus,
	PriorityLevel,
	EngineType,
	EngineCategory,
	EngineErrorLevel,
	EventType,
	EventPriority,
	MarketType,
	OrderDirection,
	OrderType,
	OrderStatus,
	TimeInForce,
	TradeSide,
	StrategyType,
	StrategyRuntimeStatus,
	SignalType,
	DataFrequency,
	DataSource,
	DataQuality,
	RiskLevel,
	RiskAction,
	RiskType,
	AccountType,
	PositionDirection,
	SettlementStatus,
	AlertLevel,
	MetricType,
	CheckType,
	EnumHelper
)

from .entities import (
	BaseEntity,
	EngineMetricsEntity,
	EngineStatus,
	Order,
	Trade,
	Position,
	Account,
	StrategyConfig,
	StrategyStatusEntity,
	Signal,
	MarketData,
	TickData,
	BarData,
	DepthData,
	RiskRule,
	RiskAlert,
	Metric,
	Alert,
	SystemConfig,
	EntityFactory, EngineConfigEntity
)

__all__ = [
	# 枚举
	'SystemMode',
	'ComponentStatus',
	'HealthStatus',
	'PriorityLevel',
	'EngineType',
	'EngineCategory',
	'EngineErrorLevel',
	'EventType',
	'EventPriority',
	'MarketType',
	'OrderDirection',
	'OrderType',
	'OrderStatus',
	'TimeInForce',
	'TradeSide',
	'StrategyType',
	'StrategyRuntimeStatus',
	'SignalType',
	'DataFrequency',
	'DataSource',
	'DataQuality',
	'RiskLevel',
	'RiskAction',
	'RiskType',
	'AccountType',
	'PositionDirection',
	'SettlementStatus',
	'AlertLevel',
	'MetricType',
	'CheckType',
	'EnumHelper',

	# 实体类
	'BaseEntity',
	'EngineMetricsEntity',
	'EngineStatus',
	'Order',
	'Trade',
	'Position',
	'Account',
	'StrategyConfig',
	'StrategyStatusEntity',
	'Signal',
	'MarketData',
	'TickData',
	'BarData',
	'DepthData',
	'RiskRule',
	'RiskAlert',
	'Metric',
	'Alert',
	'EngineConfigEntity',
	'EngineMetricsEntity',
	'SystemConfig',
	'EntityFactory'
]

# 版本信息
__version__ = "1.0.0"
__description__ = "量化交易系统统一类型定义层"
__author__ = "Quant Trading System Team"

