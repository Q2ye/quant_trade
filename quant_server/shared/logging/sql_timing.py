# -*- coding: utf-8 -*-
"""SQL 查询计时辅助函数 — 开发环境 DEBUG 级别记录每条 SQL 耗时"""
import time
import logging
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("sql.timing")


async def _first_timed(
    session: AsyncSession, sql: str, params: dict, tag: str = ""
) -> Optional[dict]:
    """执行查询并返回第一行（带 debug 耗时）"""
    t0 = time.perf_counter()
    r = await session.execute(text(sql), params)
    row = r.fetchone()
    ms = (time.perf_counter() - t0) * 1000
    label = f" [{tag}]" if tag else ""
    logger.debug(f"SQL{label} ({ms:.0f}ms): {sql.strip()[:80]}...")
    return dict(row._mapping) if row else None


async def _all_timed(
    session: AsyncSession, sql: str, params: dict, tag: str = ""
) -> list:
    """执行查询并返回所有行（带 debug 耗时）"""
    t0 = time.perf_counter()
    r = await session.execute(text(sql), params)
    rows = [dict(row._mapping) for row in r.fetchall()]
    ms = (time.perf_counter() - t0) * 1000
    label = f" [{tag}]" if tag else ""
    logger.debug(f"SQL{label} ({ms:.0f}ms, {len(rows)} rows): {sql.strip()[:80]}...")
    return rows
