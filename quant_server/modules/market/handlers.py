# -*- coding: utf-8 -*-
"""Market 模块业务处理层 — API 路由 -> service 层的桥接"""
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from modules.market.schemas import DashboardOverviewResponse, StockFullResponse
from modules.market.services.dashboard_service import get_dashboard_overview
from modules.market.services.stock_service import get_stock_full
from modules.market.services.screener_service import screener as screener_query
from modules.market.services.industry_service import (
    get_industry_tree, get_industry_heatmap,
    get_industry_detail, get_industry_history,
)

logger = logging.getLogger(__name__)


async def get_dashboard(session: AsyncSession) -> DashboardOverviewResponse:
    data = await get_dashboard_overview(session)
    return DashboardOverviewResponse(**data)


async def get_stock_detail_full(session: AsyncSession, ts_code: str) -> Optional[StockFullResponse]:
    data = await get_stock_full(session, ts_code)
    if data is None:
        return None
    return StockFullResponse(**data)


async def do_screener(session: AsyncSession, params: dict) -> dict:
    return await screener_query(session, **params)


async def do_industry_tree(session: AsyncSession) -> list:
    return await get_industry_tree(session)


async def do_industry_detail(session: AsyncSession, code: str) -> Optional[dict]:
    return await get_industry_detail(session, code)


async def do_industry_heatmap(session: AsyncSession) -> list:
    return await get_industry_heatmap(session)

async def do_financial_compare(session: AsyncSession, codes: list, metrics=None, end_date=None) -> list:
    from modules.market.services.financial_service import get_indicators_compare
    return await get_indicators_compare(session, codes, metrics, end_date)


async def do_financial_statements(session: AsyncSession, code: str, stmt_type: str, limit: int = 20) -> list:
    from modules.market.services.financial_service import get_statements
    return await get_statements(session, code, stmt_type, limit)


async def do_financial_events(session: AsyncSession, code: str, event_type: str, limit: int = 10) -> list:
    from modules.market.services.financial_service import get_events
    return await get_events(session, code, event_type, limit)


async def do_top_moneyflow(session: AsyncSession, direction: str = "net_inflow", limit: int = 20) -> list:
    from modules.market.services.moneyflow_service import get_top_moneyflow
    return await get_top_moneyflow(session, direction, limit)


async def do_hsgt_history(session: AsyncSession, days: int = 60) -> list:
    from modules.market.services.moneyflow_service import get_hsgt_history
    return await get_hsgt_history(session, days)


async def do_stock_moneyflow_detail(session: AsyncSession, code: str, days: int = 60) -> list:
    from modules.market.services.moneyflow_service import get_stock_moneyflow_detail
    return await get_stock_moneyflow_detail(session, code, days)
async def do_macro(session: AsyncSession, indicator: str, limit: int = 24) -> list:
    from modules.market.services.macro_service import get_macro
    return await get_macro(session, indicator, limit)


async def do_index_weights(session: AsyncSession, code: str) -> list:
    from modules.market.services.index_service import get_index_weights
    return await get_index_weights(session, code)


async def do_index_valuation(session: AsyncSession, code: str, limit: int = 60) -> list:
    from modules.market.services.index_service import get_index_valuation
    return await get_index_valuation(session, code, limit)


async def do_etf_shares(session: AsyncSession, code: str, limit: int = 120) -> list:
    from modules.market.services.index_service import get_etf_shares
    return await get_etf_shares(session, code, limit)


async def do_etf_benchmark(session: AsyncSession, code: str):
    from modules.market.services.index_service import get_etf_benchmark
    return await get_etf_benchmark(session, code)

async def do_index_history(session: AsyncSession, code: str, limit: int = 60) -> list:
    from modules.market.services.index_service import get_index_history
    return await get_index_history(session, code, limit)
