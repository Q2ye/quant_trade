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
	OrderDirection,
	OrderType,
	OrderStatus,
	TimeInForce,
	RiskLevel,
	AlertLevel,
	MetricType,
)

from .entities import (
	BaseEntity,
	EngineMetricsEntity,
	BarData,
	Metric,
	Alert,
	SystemConfig,
	EngineConfigEntity
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
	'OrderDirection',
	'OrderType',
	'OrderStatus',
	'TimeInForce',
	'RiskLevel',
	'AlertLevel',
	'MetricType',

	# 实体类
	'BaseEntity',
	'EngineMetricsEntity',
	'BarData',
	'Metric',
	'Alert',
	'EngineConfigEntity',
	'EngineMetricsEntity',
	'SystemConfig',
]

# 版本信息
__version__ = "1.0.0"
__description__ = "量化交易系统统一类型定义层"
__author__ = "Quant Trading System Team"

