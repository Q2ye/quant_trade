# -*- coding: utf-8 -*-
"""行业分析查询 — 申万行业分类、行情、成分股"""
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def _all(session: AsyncSession, sql: str, params: dict) -> list:
    r = await session.execute(text(sql), params)
    return [dict(row._mapping) for row in r.fetchall()]


async def _first(session: AsyncSession, sql: str, params: dict) -> Optional[dict]:
    r = await session.execute(text(sql), params)
    row = r.fetchone()
    return dict(row._mapping) if row else None


async def get_industry_tree(session: AsyncSession) -> list:
    """申万行业分类树（L1/L2/L3）"""
    return await _all(session, """
        SELECT index_code AS code, industry_name AS name, level, parent_code
        FROM index_sw_classify
        ORDER BY level, index_code
    """, {})


async def get_industry_heatmap(session: AsyncSession) -> list:
    """申万一级行业当日行情"""
    return await _all(session, """
        SELECT d.ts_code AS code, c.industry_name AS name,
               d.pct_change AS pct_chg, d.close, d.vol, d.amount
        FROM index_sw_daily d
        JOIN index_sw_classify c ON d.ts_code = c.index_code
        WHERE d.trade_date = (SELECT MAX(trade_date) FROM index_sw_daily)
          AND c.level = 'L1'
        ORDER BY d.pct_change DESC
    """, {})


async def get_industry_detail(session: AsyncSession, industry_code: str) -> Optional[dict]:
    """行业详情：行情+成分股"""
    info = await _first(session, """
        SELECT d.ts_code AS code, c.industry_name AS name, c.level,
               d.pct_change AS pct_chg, d.close, d.vol, d.amount
        FROM index_sw_daily d
        JOIN index_sw_classify c ON d.ts_code = c.index_code
        WHERE d.ts_code = :code
          AND d.trade_date = (SELECT MAX(trade_date) FROM index_sw_daily WHERE ts_code = :code)
    """, {"code": industry_code})
    if not info:
        return None

    members = await _all(session, """
        SELECT m.ts_code, b.name,
               q.close, q.pct_chg, q.amount
        FROM index_sw_member m
        JOIN stock_basic b ON m.ts_code = b.ts_code
        LEFT JOIN stock_daily q ON q.ts_code = m.ts_code
            AND q.trade_date = (SELECT MAX(trade_date) FROM stock_daily)
        WHERE (m.l1_code = :code OR m.l2_code = :code OR m.l3_code = :code)
        ORDER BY q.pct_chg DESC NULLS LAST
        LIMIT 100
    """, {"code": industry_code})

    return {"info": info, "members": members}


async def get_industry_history(session: AsyncSession, industry_code: str, limit: int = 60) -> list:
    """行业指数历史行情"""
    return await _all(session, """
        SELECT trade_date, open, high, low, close, vol, amount, pct_change AS pct_chg
        FROM index_sw_daily
        WHERE ts_code = :code
        ORDER BY trade_date DESC
        LIMIT :lim
    """, {"code": industry_code, "lim": limit})
