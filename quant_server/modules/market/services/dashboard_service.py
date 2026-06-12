# -*- coding: utf-8 -*-
"""Dashboard 聚合查询 — 6 子查询并行，单失败不阻塞，使用原始 SQL 避免依赖 ORM 模型"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def _first(session: AsyncSession, sql: str, params: dict):
    """执行查询并返回第一行（dict），无结果返回 None"""
    r = await session.execute(text(sql), params)
    row = r.fetchone()
    return dict(row._mapping) if row else None


async def _all(session: AsyncSession, sql: str, params: dict):
    """执行查询并返回所有行（list of dict）"""
    r = await session.execute(text(sql), params)
    return [dict(row._mapping) for row in r.fetchall()]


async def _query_indices(session: AsyncSession) -> list:
    return await _all(session, """
        SELECT d.ts_code AS code, b.name,
               d.close, d.pct_chg, d.open, d.high, d.low, d.vol, d.amount
        FROM index_daily d
        JOIN index_basic b ON d.ts_code = b.ts_code
        WHERE d.trade_date = (SELECT MAX(trade_date) FROM index_daily)
          AND d.ts_code IN ('000001.SH','399001.SZ','000300.SH','000905.SH','399006.SZ','000688.SH')
    """, {})


async def _query_industry(session: AsyncSession) -> list:
    latest = await _first(session, "SELECT MAX(trade_date) AS d FROM index_sw_daily", {})
    if not latest:
        return []
    ld = latest['d']
    return await _all(session, """
        SELECT d.ts_code AS code, c.industry_name AS name,
               MAX(CASE WHEN d.trade_date = :d0 THEN d.pct_change END) AS pct_chg
        FROM index_sw_daily d
        JOIN index_sw_classify c ON d.ts_code = c.index_code
        WHERE d.trade_date = :d0 AND c.level = 'L1'
        GROUP BY d.ts_code, c.industry_name
        ORDER BY pct_chg DESC
    """, {"d0": ld})


async def _query_breadth(session: AsyncSession) -> dict:
    row = await _first(session, """
        SELECT
            MAX(trade_date) AS data_date,
            COUNT(*) FILTER (WHERE pct_chg > 0) AS up_count,
            COUNT(*) FILTER (WHERE pct_chg < 0) AS down_count,
            COUNT(*) FILTER (WHERE pct_chg = 0) AS flat_count,
            COUNT(*) FILTER (WHERE pct_chg >= 9.8) AS limit_up,
            COUNT(*) FILTER (WHERE pct_chg <= -9.8) AS limit_down,
            COUNT(*) AS total
        FROM stock_daily
        WHERE trade_date = (SELECT MAX(trade_date) FROM stock_daily)
    """, {})
    if not row:
        return {"data_date": None, "up": 0, "down": 0, "flat": 0, "total": 0, "limit_up": 0, "limit_down": 0}
    return {
        "data_date": row.get("data_date"),
        "up": row.get("up_count", 0), "down": row.get("down_count", 0),
        "flat": row.get("flat_count", 0), "total": row.get("total", 0),
        "limit_up": row.get("limit_up", 0), "limit_down": row.get("limit_down", 0),
    }


async def _query_top_volume(session: AsyncSession, limit: int = 10) -> list:
    return await _all(session, """
        SELECT q.ts_code, b.name, b.industry,
               q.close, q.pct_chg, q.amount, q.vol,
               db.pe, db.pb, db.total_mv, db.circ_mv,
               db.turnover_rate, db.volume_ratio
        FROM stock_daily q
        JOIN stock_basic b ON q.ts_code = b.ts_code
        LEFT JOIN stock_daily_basic db ON db.ts_code = q.ts_code AND db.trade_date = q.trade_date
        WHERE q.trade_date = (SELECT MAX(trade_date) FROM stock_daily)
        ORDER BY q.amount DESC
        LIMIT :lim
    """, {"lim": limit})


async def _query_top_flow(session: AsyncSession, limit: int = 10) -> list:
    return await _all(session, """
        SELECT m.ts_code, b.name, m.net_mf_amount,
               m.buy_elg_amount, m.sell_elg_amount,
               m.buy_lg_amount, m.sell_lg_amount,
               q.close, q.pct_chg
        FROM stock_moneyflow m
        JOIN stock_basic b ON m.ts_code = b.ts_code
        LEFT JOIN stock_daily q ON q.ts_code = m.ts_code AND q.trade_date = m.trade_date
        WHERE m.trade_date = (SELECT MAX(trade_date) FROM stock_moneyflow)
        ORDER BY m.net_mf_amount DESC
        LIMIT :lim
    """, {"lim": limit})


async def _query_hsgt(session: AsyncSession) -> Optional[dict]:
    return await _first(session, """
        SELECT trade_date, north_money AS net_inflow,
               hgt AS sh_inflow, sgt AS sz_inflow
        FROM stock_moneyflow_hsgt
        WHERE trade_date = (SELECT MAX(trade_date) FROM stock_moneyflow_hsgt)
    """, {})


async def get_dashboard_overview(session: AsyncSession) -> Dict[str, Any]:
    results = await asyncio.gather(
        _query_indices(session),
        _query_industry(session),
        _query_breadth(session),
        _query_top_volume(session),
        _query_top_flow(session),
        _query_hsgt(session),
        return_exceptions=True,
    )
    indices, heatmap, breadth, volume, flow, hsgt = results

    # 从 breadth 中提取 data_date，format 为 ISO 字符串
    if isinstance(breadth, dict):
        data_date = breadth.pop("data_date", None)
    else:
        data_date = None
    if data_date:
        data_date = data_date.isoformat() if hasattr(data_date, "isoformat") else str(data_date)

    return {
        "data_date": data_date,
        "indices": indices if not isinstance(indices, Exception) else [],
        "industry_heatmap": heatmap if not isinstance(heatmap, Exception) else [],
        "market_breadth": breadth if not isinstance(breadth, Exception) else {
            "up": 0, "down": 0, "flat": 0, "total": 0, "limit_up": 0, "limit_down": 0
        },
        "top_volume": volume if not isinstance(volume, Exception) else [],
        "top_moneyflow": flow if not isinstance(flow, Exception) else [],
        "hsgt_flow": hsgt if not isinstance(hsgt, Exception) else None,
    }
