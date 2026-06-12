# -*- coding: utf-8 -*-
"""Market 数据展示模块 — Dashboard/StockDetail/Screener/Industry/Financial/MoneyFlow/Macro"""

from .schemas import (
    DashboardOverviewResponse,
    StockFullResponse,
    IndexOverviewItem,
    IndustryHeatmapItem,
    MarketBreadth,
    TopVolumeItem,
    TopMoneyflowItem,
    HsgtFlowItem,
)

from .handlers import (
    get_dashboard,
    get_stock_detail_full,
    do_screener,
    do_industry_tree,
    do_industry_detail,
    do_industry_heatmap,
    do_financial_compare,
    do_financial_statements,
    do_financial_events,
    do_top_moneyflow,
    do_hsgt_history,
    do_stock_moneyflow_detail,
    do_macro,
    do_index_weights,
    do_index_valuation,
    do_index_history,
    do_etf_shares,
    do_etf_benchmark,
)

__all__ = [
    # Schemas
    "DashboardOverviewResponse",
    "StockFullResponse",
    "IndexOverviewItem",
    "IndustryHeatmapItem",
    "MarketBreadth",
    "TopVolumeItem",
    "TopMoneyflowItem",
    "HsgtFlowItem",
    # Handlers
    "get_dashboard",
    "get_stock_detail_full",
    "do_screener",
    "do_industry_tree",
    "do_industry_detail",
    "do_industry_heatmap",
    "do_financial_compare",
    "do_financial_statements",
    "do_financial_events",
    "do_top_moneyflow",
    "do_hsgt_history",
    "do_stock_moneyflow_detail",
    "do_macro",
    "do_index_weights",
    "do_index_valuation",
    "do_index_history",
    "do_etf_shares",
    "do_etf_benchmark",
]
