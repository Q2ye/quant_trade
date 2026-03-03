# -*- coding: utf-8 -*-
"""
基本面数据仓库模块 - 统一导出接口
位置：quant_server/shared/database/repositories/market/fundamental/__init__.py

包含财务报表、公司公告、每日基本面指标、资金流向等基本面数据仓库
所有仓库都遵循纯数据访问原则，不包含业务逻辑
"""

# from .company_announcement_repo import CompanyAnnouncementRepository
from .financial_statement_repo import FinancialStatementRepository
from .stock_daily_basic_repo import StockDailyBasicRepository
from .stock_moneyflow_repo import StockMoneyflowRepository

__all__ = [
    # "CompanyAnnouncementRepository",
    "FinancialStatementRepository",
    "StockDailyBasicRepository",
    "StockMoneyflowRepository",
]