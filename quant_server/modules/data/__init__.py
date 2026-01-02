# -*- coding: utf-8 -*-
"""
数据模块 - 量化交易系统的数据管理模块
基于混合架构设计，提供数据同步、质量检查、因子研究等功能

数据模块 (modules/events/)
├── engines/     # 有状态引擎：管理数据同步、清洗、研究任务
├── services/    # 无状态服务：数据计算、验证、转换逻辑
└── events/      # 数据模块事件：同步完成、质量警报等

模块结构：
modules/events/
├── __init__.py              # 模块导出文件
├── constants.py             # 模块常量定义
├── handlers.py              # API处理函数
├── schemas.py               # API请求/响应模型
├── models.py                # 业务模型定义
├── engines/                 # 业务引擎
│   ├── __init__.py
│   ├── sync_engine.py      # 数据同步引擎
│   ├── clean_engine.py     # 数据清洗引擎
│   ├── research_engine.py  # 因子研究引擎
│   └── quality_engine.py   # 质量检查引擎
├── services/                # 业务服务
│   ├── __init__.py
│   ├── sync_service.py     # 数据同步服务
│   ├── quality_service.py  # 数据质量服务
│   ├── research_service.py # 因子研究服务
│   ├── market_service.py   # 市场数据服务
│   └── clean_service.py    # 数据清洗服务
├── managers/                # 管理器
│   ├── __init__.py
│   ├── data_manager.py     # 数据管理器
│   └── research_manager.py # 研究管理器
├── tasks/                   # 异步任务
│   ├── __init__.py
│   ├── sync_tasks.py       # 数据同步任务
│   ├── quality_tasks.py    # 质量检查任务
│   └── research_tasks.py   # 研究任务
├── utils/                   # 模块工具
│   ├── __init__.py
│   ├── data_formatter.py   # 数据格式化
│   ├── factor_calculator.py # 因子计算器
│   └── quality_checker.py  # 质量检查器
└── tests/                   # 模块测试
    ├── __init__.py
    ├── test_services.py
    └── test_engines.py

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

# 导出Handlers
from quant_server.modules.data.handlers import (
	get_stock_list,
	get_stock_detail,
	get_historical_quotes,
	sync_market_data,
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

# 导出Services
from quant_server.modules.data.services import (
	DataSyncService,
	DataQualityService,
	FactorResearchService,
	MarketDataService,
	DataCleanService
)

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
	"get_stock_list", "get_stock_detail", "get_historical_quotes", "sync_market_data",
	"batch_sync_data", "quick_sync_data", "get_sync_status", "cancel_sync",
	"get_data_quality", "get_factor_data", "research_factor", "initialize_data_module",
	"check_data_module_health",

	# Services
	"DataSyncService", "DataQualityService", "FactorResearchService", "MarketDataService", "DataCleanService"
]