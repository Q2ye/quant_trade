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
    get_industry_tree, get_industry_heatmap, get_industry_heatmap_multi_window,
    get_industry_detail, get_industry_history, get_industry_trend,
)
from modules.market.services.market_state_service import get_market_state, get_style_rotation

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


async def do_screener_industries(session: AsyncSession) -> list:
    """选股器行业下拉：stock_basic.industry 去重（东财口径）"""
    from modules.market.services.screener_service import list_industries
    return await list_industries(session)


async def do_screener_etf_types(session: AsyncSession) -> list:
    """选股器 ETF 模式类型下拉：etf_basic.fund_type 去重"""
    from modules.market.services.screener_service import list_etf_types
    return await list_etf_types(session)


async def do_industry_tree(session: AsyncSession) -> list:
    return await get_industry_tree(session)


async def do_industry_detail(session: AsyncSession, code: str) -> Optional[dict]:
    return await get_industry_detail(session, code)


async def do_industry_heatmap(session: AsyncSession) -> list:
    return await get_industry_heatmap(session)


async def do_industry_history(session: AsyncSession, code: str, limit: int = 90) -> list:
    return await get_industry_history(session, code, limit)


async def do_industry_heatmap_multi(
    session: AsyncSession, windows: list = None
) -> list:
    return await get_industry_heatmap_multi_window(session, windows)


async def do_industry_trend(session: AsyncSession, days: int = 60) -> dict:
    return await get_industry_trend(session, days)


async def do_financial_compare(session: AsyncSession, codes: list, end_date=None) -> list:
    from modules.market.services.financial_service import get_indicators_compare
    return await get_indicators_compare(session, codes, end_date)


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


async def do_index_weights(session: AsyncSession, code: str, offset: int = 0, limit: int = 50):
    from modules.market.services.index_service import get_index_weights
    return await get_index_weights(session, code, offset, limit)


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


async def do_index_sector_exposure(session: AsyncSession, code: str) -> list:
    from modules.market.services.index_service import get_index_sector_exposure
    return await get_index_sector_exposure(session, code)


async def do_sector_moneyflow(session: AsyncSession) -> list:
    from modules.market.services.moneyflow_service import get_sector_moneyflow
    return await get_sector_moneyflow(session)


async def do_stock_signals(session: AsyncSession, ts_code: str, recent: int = 20) -> list:
    from modules.market.services.stock_service import get_stock_signals
    return await get_stock_signals(session, ts_code, recent)


async def do_stock_kline_range(
    session: AsyncSession, ts_code: str, period: str = "daily",
    before_date: Optional[str] = None, limit: int = 500,
) -> list:
    from modules.market.services.stock_service import get_stock_kline_range
    return await get_stock_kline_range(session, ts_code, period, before_date, limit)


async def do_stock_factor_scores(session: AsyncSession, ts_code: str) -> Optional[dict]:
    from modules.market.services.stock_service import get_stock_factor_scores
    return await get_stock_factor_scores(session, ts_code)


async def do_limit_analysis(
    session: AsyncSession,
    trade_date: Optional[str] = None,
    exchange: Optional[str] = None,
    board: Optional[str] = None,
) -> dict:
    from modules.market.services.limit_service import get_limit_stocks
    return await get_limit_stocks(session, trade_date, exchange, board)


async def do_style_factors(session: AsyncSession) -> list:
    from modules.market.services.dashboard_service import get_style_factors
    return await get_style_factors(session)


async def do_sector_turnover(session: AsyncSession) -> dict:
    from modules.market.services.dashboard_service import get_sector_turnover
    return await get_sector_turnover(session)


async def do_market_state(session: AsyncSession, days: int = 60) -> dict:
    """大盘状态雷达数据"""
    return await get_market_state(session, days)


async def do_style_rotation(session: AsyncSession, days: int = 60) -> dict:
    """风格轮动数据"""
    return await get_style_rotation(session, days)


async def do_get_watchlist(session: AsyncSession, user_id: str) -> list:
    """获取当前用户自选股 + 最新行情"""
    from sqlalchemy import text
    pref = await session.execute(
        text("SELECT display_settings FROM user_preferences WHERE user_id = :uid"),
        {"uid": user_id},
    )
    row = pref.fetchone()
    codes = []
    if row and row[0]:
        import json
        ds = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        codes = ds.get("watchlist", []) if isinstance(ds, dict) else []

    if not codes:
        return []

    from sqlalchemy import text as txt
    result = await session.execute(
        txt("""
            SELECT DISTINCT ON (ts_code) ts_code, name, close, pct_chg
            FROM stock_daily d
            JOIN stock_basic b ON d.ts_code = b.ts_code
            WHERE d.ts_code = ANY(:codes)
            ORDER BY ts_code, trade_date DESC
        """),
        {"codes": codes},
    )
    return [dict(r._mapping) for r in result.fetchall()]


async def do_save_watchlist(session: AsyncSession, user_id: str, codes: list) -> bool:
    """保存自选股列表"""
    from sqlalchemy import text
    import json
    pref = await session.execute(
        text("SELECT display_settings FROM user_preferences WHERE user_id = :uid"),
        {"uid": user_id},
    )
    row = pref.fetchone()
    ds = {}
    if row and row[0]:
        ds = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    if not isinstance(ds, dict):
        ds = {}
    ds["watchlist"] = codes
    await session.execute(
        text("""
            INSERT INTO user_preferences (user_id, display_settings)
            VALUES (:uid, CAST(:ds AS jsonb))
            ON CONFLICT (user_id) DO UPDATE SET display_settings = CAST(:ds AS jsonb)
        """),
        {"uid": user_id, "ds": json.dumps(ds)},
    )
    await session.commit()
    return True


async def do_dashboard_temperature(session: AsyncSession) -> dict:
    """市场温度计（N1）：估值/情绪/资金/技术四维分位 → 单温度"""
    from modules.market.services.market_temperature_service import get_market_temperature
    return await get_market_temperature(session)


async def do_limit_ladder(session: AsyncSession, trade_date: Optional[str] = None) -> dict:
    """涨停梯队（N3）：连板高度分布 + 炸板率 + 封板资金近似 + 情绪周期"""
    from modules.market.services.limit_service import get_limit_ladder
    return await get_limit_ladder(session, trade_date)


async def do_breadth_leaders(session: AsyncSession) -> dict:
    """强弱榜（N6）：创20日新高/新低/连涨≥5日 TOP10"""
    from modules.market.services.breadth_service import get_breadth_leaders
    return await get_breadth_leaders(session)


async def do_dashboard_crowding(session: AsyncSession) -> dict:
    """拥挤度（N4）：全市场成交额分位 + 申万 L1 行业成交额分位 TOP5"""
    from modules.market.services.crowding_service import get_crowding
    return await get_crowding(session)


async def do_breadth_metrics(session: AsyncSession) -> dict:
    """市场宽度补全（N2）+ 波动率分位（N5）"""
    from modules.market.services.breadth_service import get_breadth_metrics
    return await get_breadth_metrics(session)
