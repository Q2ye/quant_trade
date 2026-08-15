# -*- coding: utf-8 -*-
"""
数据模块 - 服务层导出
位置：quant_server/modules/events/services/__init__.py

设计原则：
1. 统一导出所有服务类，便于导入使用
2. 提供清晰的模块文档说明
3. 按功能分组导出，避免循环导入
"""

from modules.data.services.sync_service import DataSyncService
from modules.data.services.quality_service import DataQualityService
from modules.data.services.research_service import FactorResearchService
from modules.data.services.market_service import MarketDataService

__all__ = [
    "DataSyncService",      # 数据同步服务
    "DataQualityService",   # 数据质量服务
    "FactorResearchService", # 因子研究服务
    "MarketDataService",    # 市场数据服务
]

__version__ = "1.0.0"
__author__ = "量化交易系统团队"
__description__ = "数据模块业务服务层"