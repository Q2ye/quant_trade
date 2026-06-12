# -*- coding: utf-8 -*-
"""宏观经济查询 — CPI/PPI/GDP"""
import logging
from typing import List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def _all(session: AsyncSession, sql: str, params: dict) -> list:
    r = await session.execute(text(sql), params)
    return [dict(row._mapping) for row in r.fetchall()]


async def get_macro(session: AsyncSession, indicator: str, limit: int = 24) -> list:
    """查询宏观经济指标"""
    tables = {
        "cpi": ("macro_cpi", "month"),
        "ppi": ("macro_ppi", "month"),
        "gdp": ("macro_gdp", "quarter"),
    }
    entry = tables.get(indicator)
    if not entry:
        return []
    table, date_col = entry
    try:
        rows = await _all(session, f"SELECT * FROM {table} ORDER BY {date_col} DESC LIMIT :lim", {"lim": limit})
        for r in rows:
            for k, v in list(r.items()):
                if isinstance(v, float) and v != v:
                    r[k] = None
        return rows
    except Exception as e:
        logger.warning(f"Macro query failed {table}: {e}")
        return []
