# -*- coding: utf-8 -*-
"""
quant_server/modules/data/__init__.py
数据模块 - 量化交易系统的数据管理模块
基于混合架构设计，提供数据同步、质量检查、因子研究等功能

数据模块 (modules/events/)
├── engines/     # 有状态引擎：管理数据同步、清洗、研究任务
├── services/    # 无状态服务：数据计算、验证、转换逻辑
└── events/      # 数据模块事件：同步完成、质量警报等

设计原则：
1. 单一职责：每个组件只负责一个明确的业务功能
2. 依赖注入：通过依赖注入获取共享基础设施
3. 事件驱动：模块间通过事件引擎通信
4. 统一异常处理：模块内错误不泄漏到外部
"""

# 导出常量
from quant_server.modules.data.constants import (
	ModuleConfig,
	SyncStatus,
	SyncErrorCode,
	DataSource,
	DataType,
	MarketCode,
	StockStatus,
	QualityMetricCode,
	QualityLevelThreshold,
	FactorCategoryCode,
	StandardFactors,
	ErrorCode,
	DateTimeFormat,
	TradingTime,
	TableName,
	APIPath,
	CacheKey,
	EventType,
	Permission
)
# 导出Handlers
from quant_server.modules.data.handlers import (
	get_stock_list,
	get_stock_detail,
	get_historical_quotes,
	batch_sync_data,
	quick_sync_data,
	get_sync_status,
	cancel_sync,
	get_data_quality,
	get_factor_data,
	research_factor,
	initialize_data_module,
	check_data_module_health
)
# 导出模型
from quant_server.modules.data.models import (
	BaseSyncRequest,
	BatchSyncRequest,
	DataTypeInfo
)
# 导出Schema
from quant_server.modules.data.schemas import (
	StockListRequest,
	StockListResponse,
	StockDetailRequest,
	StockDetailResponse,
	HistoricalQuotesRequest,
	HistoricalQuotesResponse,
	BatchSyncRequest,
	BatchSyncResponse,
	SyncStatusResponse,
	DataQualityRequest,
	DataQualityResponse,
	FactorRequest,
	FactorResponse,
	ResearchRequest,
	ResearchResponse
)
# 导出Services
from quant_server.modules.data.services import (
	DataSyncService,
	DataQualityService,
	FactorResearchService,
	MarketDataService,
	DataCleanService
)


# 模块初始化函数 - 符合主启动文件期望的接口
async def initialize (
		main_engine=None,
		event_engine=None,  # 未使用参数
		config=None  # 未使用参数
) -> bool:
	"""
	数据模块初始化函数

	Args:
		main_engine: 主引擎实例
		event_engine: 事件引擎实例
		config: 模块配置

	Returns:
		bool: 初始化是否成功
	"""

	# 初始化变量
	success = False
	init_result = {}

	try:
		# 获取数据库会话 - 使用正确的上下文管理器方式
		if main_engine and hasattr(main_engine, 'get_async_session'):
			# 如果主引擎提供会话，使用主引擎的会话
			session = main_engine.get_async_session()

			# 调用原有的初始化函数
			init_result = await initialize_data_module(
				session=session
			)

			success = init_result.get('status') != 'failed'
		else:
			# 使用共享层的会话管理器，通过上下文管理器正确获取
			from quant_server.shared.database.session import get_session_manager

			session_manager = get_session_manager()
			async with session_manager.get_session() as session:
				# 调用原有的初始化函数
				init_result = await initialize_data_module(
					session=session
				)

				success = init_result.get('status') != 'failed'

		# 记录初始化结果
		if success:
			print(f"✅ 数据模块初始化成功: {init_result.get('message', '完成')}")
		else:
			print(f"⚠️  数据模块初始化警告: {init_result.get('message', '存在警告')}")

		return success

	except Exception as e:
		print(f"❌ 数据模块初始化失败: {str(e)}")
		return False


async def shutdown(main_engine=None) -> None:
	"""数据模块关闭函数"""
	import logging
	logging.getLogger(__name__).info("数据模块已关闭")


# 模块元数据
__version__ = "1.0.0"
__author__ = "量化交易系统团队"
__description__ = "量化交易系统数据管理模块"
__all__ = [
	# 常量
	"ModuleConfig", "SyncStatus", "SyncErrorCode", "DataSource", "DataType",
	"MarketCode", "StockStatus", "QualityMetricCode", "QualityLevelThreshold",
	"FactorCategoryCode", "StandardFactors", "ErrorCode", "DateTimeFormat",
	"TradingTime", "TableName", "APIPath", "CacheKey", "EventType", "Permission",

	# 模型
	"BaseSyncRequest", "BatchSyncRequest", "DataTypeInfo",

	# Schema
	"StockListRequest", "StockListResponse", "StockDetailRequest", "StockDetailResponse",
	"HistoricalQuotesRequest", "HistoricalQuotesResponse", "BatchSyncRequest", "BatchSyncResponse",
	"SyncStatusResponse", "DataQualityRequest", "DataQualityResponse", "FactorRequest",
	"FactorResponse", "ResearchRequest", "ResearchResponse",

	# Handlers
	"get_stock_list", "get_stock_detail", "get_historical_quotes",
	"batch_sync_data", "quick_sync_data", "get_sync_status", "cancel_sync",
	"get_data_quality", "get_factor_data", "research_factor", "initialize_data_module",
	"check_data_module_health",

	# Services
	"DataSyncService", "DataQualityService", "FactorResearchService", "MarketDataService", "DataCleanService",

	# 模块初始化函数
	"initialize",
	"shutdown"
]