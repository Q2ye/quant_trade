# -*- coding: utf-8 -*-
"""拥挤度聚合服务 (N4)

- 全市场成交额 250 日分位（stock_daily 每日成交额合计）
- 申万 L1 行业成交额 250 日分位 TOP5（index_sw_daily.amount 万元口径，
  与行业轮动柱图同名同口径，便于前端拥挤点标记）

缓存：SWR（stale-while-revalidate）300s —— 过期返回旧值并后台重算（P2）
"""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.market.services.market_temperature_service import percentile_rank
from modules.market.services._swr_cache import SwrCache

logger = logging.getLogger(__name__)

_swr = SwrCache(ttl=300.0)


async def _all(session: AsyncSession, sql: str, params: dict) -> list:
    r = await session.execute(text(sql), params)
    return [dict(row._mapping) for row in r.fetchall()]


async def get_crowding(session: AsyncSession) -> Dict[str, Any]:
    """拥挤度：全市场成交额分位 + 申万 L1 行业成交额分位 TOP5。SWR 缓存 300s。"""
    stale, need_recompute = _swr.probe("crowding")
    if stale is not None:
        if need_recompute:
            _swr.set_task("crowding", asyncio.create_task(_recompute_crowding()))
        return stale
    result = await _compute_crowding(session)
    _swr.set("crowding", result)
    return result


async def _recompute_crowding() -> None:
    from shared.database.session.session_manager import get_session_manager
    sm = get_session_manager()
    try:
        async with sm.get_session() as s:
            result = await _compute_crowding(s)
        _swr.set("crowding", result)
        logger.info("crowding 后台重算完成")
    except Exception as e:
        logger.warning("crowding 后台重算失败: %s", e)


async def _compute_crowding(session: AsyncSession) -> Dict[str, Any]:

    # 1. 全市场每日成交额（380 日历天 ≈ 250 交易日）
    rows = await _all(session, """
        SELECT trade_date, SUM(amount) AS total_amount
        FROM stock_daily
        WHERE trade_date >= (SELECT MAX(trade_date) FROM stock_daily) - INTERVAL '380 days'
        GROUP BY trade_date
        ORDER BY trade_date
    """, {})
    amounts = [float(r["total_amount"] or 0) for r in rows]
    market_pctl = percentile_rank(amounts, amounts[-1]) if amounts else None
    data_date = str(rows[-1]["trade_date"])[:10] if rows else None

    # 2. 申万 L1 行业每日成交额（与行业轮动柱图同口径：index_sw_daily + classify L1）
    rows2 = await _all(session, """
        SELECT d.trade_date, c.industry_name AS name, d.amount
        FROM index_sw_daily d
        JOIN index_sw_classify c ON d.ts_code = c.index_code
        WHERE c.level = 'L1'
          AND d.trade_date >= (SELECT MAX(trade_date) FROM index_sw_daily) - INTERVAL '380 days'
        ORDER BY d.trade_date
    """, {})
    by_ind: Dict[str, List[float]] = {}
    for r in rows2:
        if r.get("name"):
            by_ind.setdefault(r["name"], []).append(float(r["amount"] or 0))
    crowded: List[Dict[str, Any]] = []
    for name, series in by_ind.items():
        if len(series) >= 60:
            p = percentile_rank(series, series[-1])
            if p is not None:
                crowded.append({"name": name, "percentile": p})
    crowded.sort(key=lambda x: -x["percentile"])

    result = {
        "data_date": data_date,
        "market_turnover_percentile": market_pctl,
        "top_crowded_industries": crowded[:5],
    }
    return result
