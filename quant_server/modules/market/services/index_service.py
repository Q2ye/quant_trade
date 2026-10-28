# -*- coding: utf-8 -*-
"""指数/ETF 增强查询"""
import logging
from datetime import date
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


async def get_index_weights(session: AsyncSession, code: str, offset: int = 0, limit: int = 50) -> dict:
    """指数权重成分股 — 分页返回 {total, items}

    ⚠️ 2026-10-11：本查询**额外返回该股最新价与涨跌幅**（`close` / `pct_chg`），
    取「≤ 权重生效日」的最新一条日线（`stock_daily`），避免用到未来价格。
    此前只 `SELECT w.*` ⇒ 前端「最新价 / 涨跌幅」两列**恒为空**（IndexDetail 权重股
    与成分股两个 tab 共用本接口）。
    ⚠️ 同时把 `stock_basic` 的 **INNER JOIN 改为 LEFT JOIN** —— 成分股若不在基础表，
    原先会被**整行丢弃**，导致 items 少于 total。
    """
    total_row = await _first(session, """
        SELECT COUNT(*) AS cnt FROM index_weight
        WHERE index_code = :code
          AND trade_date = (SELECT MAX(trade_date) FROM index_weight WHERE index_code = :code)
    """, {"code": code})
    total = total_row["cnt"] if total_row else 0
    items = await _all(session, """
        SELECT w.*, b.name, b.industry, px.close, px.pct_chg
        FROM index_weight w
        LEFT JOIN stock_basic b ON w.ts_code = b.ts_code
        LEFT JOIN LATERAL (
            SELECT sd.close, sd.pct_chg
            FROM stock_daily sd
            WHERE sd.ts_code = w.ts_code AND sd.trade_date <= w.trade_date
            ORDER BY sd.trade_date DESC
            LIMIT 1
        ) px ON TRUE
        WHERE w.index_code = :code
          AND w.trade_date = (SELECT MAX(trade_date) FROM index_weight WHERE index_code = :code)
        ORDER BY w.weight DESC
        LIMIT :lim OFFSET :off
    """, {"code": code, "lim": limit, "off": offset})
    return {"total": total, "items": items}


async def get_trading_calendar(
    session: AsyncSession, start_date: date, end_date: date, exchange: str = "SSE"
) -> List[str]:
    """区间内的交易日列表（仅 is_open=True），供前端页头「交易时段」判定。

    ⚠️ 职责切分（单一职责）：
    - **本接口只答「哪天是交易日」**（需要日历表）；
    - 「**现在**是不是交易时段」由前端 `composables/useMarketSession.ts` 叠加时钟判定
      （09:30–11:30 / 13:00–15:00）。
    两者相与才是「交易中」，缺任一半都会把周末/午休误判成开市。

    返回 `["2026-10-08", "2026-10-09", ...]`（升序）。
    非交易日（周末 + 法定节假日）**不在列表内** → 前端用 `includes()` 即可判定。
    """
    from shared.database.repositories.market.reference.trade_calendar_repo import (
        TradeCalendarRepository,
    )

    repo = TradeCalendarRepository(session)
    days = await repo.get_trade_dates(exchange, start_date, end_date, only_open=True)
    return [d.isoformat() if hasattr(d, "isoformat") else str(d) for d in days]


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
    import logging
    _log = logging.getLogger(__name__)
    try:
        return await _all(session, """
            SELECT * FROM etf_shares WHERE ts_code = :code
            ORDER BY trade_date DESC LIMIT :lim
        """, {"code": code, "lim": limit})
    except Exception as e:
        _log.warning("ETF份额查询失败 code=%s: %s", code, e)
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
    """指数历史K线 — 返回最新 N 条，升序排列（lightweight-charts 要求从旧到新）

    策略：子查询先 DESC 取最新 N 条，外层 ASC 排序满足图表要求
    """
    try:
        rows = await _all(session, """
            SELECT * FROM (
                SELECT trade_date, open, high, low, close, vol, amount, pct_chg
                FROM index_daily WHERE ts_code = :code
                ORDER BY trade_date DESC LIMIT :lim
            ) sub ORDER BY trade_date ASC
        """, {"code": code, "lim": limit})
        for r in rows:
            if hasattr(r.get("trade_date"), "isoformat"):
                r["trade_date"] = r["trade_date"].isoformat()[:10]
        return rows
    except Exception as e:
        logger.warning(f"Index history query failed {code}: {e}")
        return []


async def get_index_sector_exposure(session: AsyncSession, code: str) -> list:
    """指数成分股按申万 L1 行业的权重分布（环形图用）"""
    try:
        return await _all(session, """
            SELECT b.industry AS name,
                   COALESCE(ROUND(SUM(w.weight)::numeric, 1), 0) AS weight_pct
            FROM index_weight w
            JOIN stock_basic b ON w.ts_code = b.ts_code
            WHERE w.index_code = :code
              AND w.trade_date = (SELECT MAX(trade_date) FROM index_weight WHERE index_code = :code)
              AND b.industry IS NOT NULL AND b.industry != ''
            GROUP BY b.industry
            ORDER BY SUM(w.weight) DESC
        """, {"code": code})
    except Exception as e:
        logger.warning(f"Index sector exposure query failed {code}: {e}")
        return []
