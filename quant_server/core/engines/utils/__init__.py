"""
引擎工具模块
提供引擎创建、监控和管理等核心工具服务

模块功能：
1. 引擎工厂 - 统一管理引擎的创建、配置和生命周期
2. 引擎监控 - 实时监控引擎状态、性能和健康状况
3. 其他引擎相关的工具类

设计原则：
- 高内聚低耦合，工具类独立可复用
- 支持异步操作，适合高并发场景
- 提供完整的错误处理和日志记录
"""

from .engine_factory import (
	EngineDescriptor,
	EngineFactory,
	get_engine_factory,
	create_engine,
	get_engine
)

from .engine_monitor import (
	MonitorAlert,
	EngineMetric,
	MetricStatistic,
	AlertRule,
	EngineMonitor,
)

__all__ = [
	# 引擎工厂相关
	'EngineDescriptor',
	'EngineFactory',
	'get_engine_factory',
	'create_engine',
	'get_engine',

	# 引擎监控相关
	'MonitorAlert',
	'EngineMetric',
	'MetricStatistic',
	'AlertRule',
	'EngineMonitor',
]

# 版本信息
__version__ = '1.0.0'
__author__ = '量化交易系统团队'
__description__ = '引擎工具模块，提供引擎创建、监控和管理服务'
