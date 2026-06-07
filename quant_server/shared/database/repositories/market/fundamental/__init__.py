# -*- coding: utf-8 -*-
"""
基本面数据仓库模块 - 统一导出接口
位置：quant_server/shared/database/repositories/market/fundamental/__init__.py

包含财务报表、公司公告、每日基本面指标、资金流向等基本面数据仓库
所有仓库都遵循纯数据访问原则，不包含业务逻辑
"""
from .company_announcement_repo import CompanyAnnouncementRepository
from .financial_statement_repo import FinancialStatementRepository
from .stock_daily_basic_repo import StockDailyBasicRepository
from .stock_moneyflow_repo import StockMoneyflowRepository
from .forecast_repo import StockForecastRepository
from .express_repo import StockExpressRepository
from .dividend_repo import StockDividendRepository
from .fina_indicator_repo import StockFinaIndicatorRepository
from .audit_opinion_repo import StockAuditOpinionRepository
from .business_income_repo import StockBusinessIncomeRepository
from .etf_share_repo import EtfShareRepository
from .hsgt_repo import StockHsgtRepository
from .st_risk_repo import StockStRiskRepository
from .disclosure_date_repo import DisclosureDateRepository
from .share_float_repo import StockShareFloatRepository
from .suspend_info_repo import StockSuspendInfoRepository

__all__ = [
    "CompanyAnnouncementRepository",
    "FinancialStatementRepository",
    "StockDailyBasicRepository",
    "StockMoneyflowRepository",
    "StockForecastRepository",
    "StockExpressRepository",
    "StockDividendRepository",
    "StockFinaIndicatorRepository",
    "StockAuditOpinionRepository",
    "StockBusinessIncomeRepository",
    "EtfShareRepository",
    "StockHsgtRepository",
    "StockStRiskRepository",
    "DisclosureDateRepository",
    "StockShareFloatRepository",
    "StockSuspendInfoRepository",
]