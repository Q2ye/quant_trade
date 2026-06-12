# -*- coding: utf-8 -*-
"""Market 模块服务层 — 对外暴露各 service 的核心查询函数"""

from .dashboard_service import get_dashboard_overview
from .stock_service import get_stock_full
from .screener_service import screener
from .industry_service import (
    get_industry_tree,
    get_industry_heatmap,
    get_industry_detail,
    get_industry_history,
)
from .financial_service import (
    get_indicators_compare,
    get_statements,
    get_events,
)
from .moneyflow_service import (
    get_top_moneyflow,
    get_hsgt_history,
    get_stock_moneyflow_detail,
)
from .macro_service import get_macro
from .index_service import (
    get_index_weights,
    get_index_valuation,
    get_index_history,
    get_etf_shares,
    get_etf_benchmark,
)

__all__ = [
    "get_dashboard_overview",
    "get_stock_full",
    "screener",
    "get_industry_tree",
    "get_industry_heatmap",
    "get_industry_detail",
    "get_industry_history",
    "get_indicators_compare",
    "get_statements",
    "get_events",
    "get_top_moneyflow",
    "get_hsgt_history",
    "get_stock_moneyflow_detail",
    "get_macro",
    "get_index_weights",
    "get_index_valuation",
    "get_index_history",
    "get_etf_shares",
    "get_etf_benchmark",
]
