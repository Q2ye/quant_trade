# -*- coding: utf-8 -*-
"""指数/ETF 增强查询"""
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


async def get_index_weights(session: AsyncSession, code: str) -> list:
    """指数权重成分股"""
    return await _all(session, """
        SELECT w.*, b.name
        FROM index_weight w
        JOIN stock_basic b ON w.ts_code = b.ts_code
        WHERE w.index_code = :code
          AND w.trade_date = (SELECT MAX(trade_date) FROM index_weight WHERE index_code = :code)
        ORDER BY w.weight DESC
        LIMIT 50
    """, {"code": code})


async def get_index_valuation(session: AsyncSession, code: str, limit: int = 60) -> list:
    """指数估值历史"""
    try:
        return await _all(session, """
            SELECT * FROM index_dailybasic WHERE ts_code = :code
            ORDER BY trade_date DESC LIMIT :lim
        """, {"code": code, "lim": limit})
    except Exception:
        return []


async def get_etf_shares(session: AsyncSession, code: str, limit: int = 120) -> list:
    """ETF 份额历史"""
    try:
        return await _all(session, """
            SELECT * FROM etf_shares WHERE ts_code = :code
            ORDER BY trade_date DESC LIMIT :lim
        """, {"code": code, "lim": limit})
    except Exception:
        return []


async def get_etf_benchmark(session: AsyncSession, code: str) -> Optional[dict]:
    """ETF 跟踪指数"""
    try:
        return await _first(session, """
            SELECT e.*, i.name AS index_name
            FROM etf_index e
            JOIN index_basic i ON e.benchmark_code = i.ts_code
            WHERE e.ts_code = :code LIMIT 1
        """, {"code": code})
    except Exception:
        return None
async def get_index_history(session: AsyncSession, code: str, limit: int = 60) -> list:
    try:
        return await _all(session, """
            SELECT trade_date, open, high, low, close, vol, amount, pct_chg
            FROM index_daily WHERE ts_code = :code
            ORDER BY trade_date DESC LIMIT :lim
        """, {"code": code, "lim": limit})
    except Exception as e:
        logger.warning(f"Index history query failed {code}: {e}")
        return []
