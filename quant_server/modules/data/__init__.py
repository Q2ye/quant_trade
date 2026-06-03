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
from typing import Dict

# 导出常量
from modules.data.constants import (
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
from modules.data.handlers import (
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
from modules.data.models import (
	BaseSyncRequest,
	BatchSyncRequest,
	DataTypeInfo
)
# 导出Schema
from modules.data.schemas import (
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
from modules.data.services import (
	DataSyncService,
	DataQualityService,
	FactorResearchService,
	MarketDataService,
	DataCleanService
)


# 模块级引擎引用（由 initialize() 创建，供 handlers 等使用）
_sync_engine = None

# 模块级取消令牌注册表: task_id → asyncio.Event
import asyncio as _asyncio
_cancel_tokens: Dict[str, "_asyncio.Event"] = {}


def get_sync_engine():
	"""获取模块级数据同步引擎实例"""
	return _sync_engine


def create_cancel_token(task_id: str) -> "_asyncio.Event":
	"""为后台同步任务创建取消令牌"""
	token = _asyncio.Event()
	_cancel_tokens[task_id] = token
	return token


def signal_cancel(task_id: str) -> bool:
	"""向指定任务发送取消信号"""
	token = _cancel_tokens.get(task_id)
	if token and not token.is_set():
		token.set()
		return True
	return False


def cleanup_cancel_token(task_id: str):
	"""清理已完成的取消令牌"""
	_cancel_tokens.pop(task_id, None)


# 模块初始化函数 - 符合主启动文件期望的接口
async def initialize (
		main_engine=None,
		event_engine=None,
		config=None
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

	global _sync_engine

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
			from shared.database.session import get_session_manager

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

		# 创建并启动数据同步引擎
		if success:
			try:
				# 提取事件引擎（优先使用传入的，否则从 main_engine 获取）
				_evt_engine = event_engine
				if not _evt_engine and main_engine and hasattr(main_engine, 'event_engine'):
					_evt_engine = main_engine.event_engine

				from modules.data.engines.sync_engine import DataSyncEngine
				from core.engines.types.entities import EngineConfigEntity
				from core.engines.types.enums import EngineType

				sync_engine_config = EngineConfigEntity(
					name="data_sync_engine",
					engine_type=EngineType.DATA_SYNC,
					config={
						"max_concurrent_tasks": 3,
						"task_timeout_seconds": 3600,
						"default_data_sources": ["tushare"],
						"cleanup_interval_hours": 24,
					}
				)
				_sync_engine = DataSyncEngine(
					config=sync_engine_config,
					event_engine=_evt_engine
				)
				await _sync_engine.initialize()
				await _sync_engine.start()
				print(f"✅ 数据同步引擎已启动: {_sync_engine.config.name}")
			except Exception as engine_err:
				print(f"⚠️  数据同步引擎启动失败（不影响模块基础功能）: {engine_err}")
				_sync_engine = None

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

	# 引擎访问器
	"get_sync_engine",

	# 取消令牌管理
	"create_cancel_token",
	"signal_cancel",
	"cleanup_cancel_token",

	# 模块初始化函数
	"initialize",
	"shutdown"
]