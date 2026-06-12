# -*- coding: utf-8 -*-
"""资金流向查询 — 北向资金、主力净流入排行"""
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


async def get_top_moneyflow(
    session: AsyncSession,
    direction: str = "net_inflow",
    limit: int = 20,
) -> List[Dict]:
    """主力资金净流入/净流出 TOP"""
    order = "net_mf_amount DESC" if direction == "net_inflow" else "net_mf_amount ASC"
    return await _all(session, f"""
        SELECT m.ts_code, b.name, m.trade_date,
               m.net_mf_amount, m.buy_lg_amount, m.sell_lg_amount,
               m.buy_elg_amount, m.sell_elg_amount,
               m.buy_md_amount, m.sell_md_amount,
               m.buy_sm_amount, m.sell_sm_amount,
               q.close, q.pct_chg
        FROM stock_moneyflow m
        JOIN stock_basic b ON m.ts_code = b.ts_code
        LEFT JOIN stock_daily q ON q.ts_code = m.ts_code
            AND q.trade_date = m.trade_date
        WHERE m.trade_date = (SELECT MAX(trade_date) FROM stock_moneyflow)
        ORDER BY {order}
        LIMIT :lim
    """, {"lim": limit})


async def get_hsgt_history(session: AsyncSession, days: int = 60) -> List[Dict]:
    """北向资金历史"""
    return await _all(session, """
        SELECT trade_date, north_money AS net_inflow,
               hgt AS sh_inflow, sgt AS sz_inflow
        FROM stock_moneyflow_hsgt
        ORDER BY trade_date DESC
        LIMIT :lim
    """, {"lim": days})


async def get_stock_moneyflow_detail(session: AsyncSession, code: str, days: int = 60) -> List[Dict]:
    """个股资金流向"""
    return await _all(session, """
        SELECT trade_date, net_mf_amount,
               buy_lg_amount, sell_lg_amount, buy_elg_amount, sell_elg_amount,
               buy_md_amount, sell_md_amount, buy_sm_amount, sell_sm_amount
        FROM stock_moneyflow WHERE ts_code = :code
        ORDER BY trade_date DESC LIMIT :lim
    """, {"code": code, "lim": days})
