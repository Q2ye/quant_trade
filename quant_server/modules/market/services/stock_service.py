# -*- coding: utf-8 -*-
"""StockDetail 全量查询 — 单股多维度数据聚合，使用原始 SQL"""
import logging
from datetime import date, datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_KLINE_LIMIT = 250


async def _first(session: AsyncSession, sql: str, params: dict):
    r = await session.execute(text(sql), params)
    row = r.fetchone()
    return dict(row._mapping) if row else None


async def _all(session: AsyncSession, sql: str, params: dict):
    r = await session.execute(text(sql), params)
    return [dict(row._mapping) for row in r.fetchall()]


def _clean(row: dict) -> dict:
    """清理日期/数值类型便于 JSON 序列化"""
    for k, v in list(row.items()):
        if isinstance(v, (datetime, date)):
            row[k] = v.isoformat()
        elif isinstance(v, float) and v != v:
            row[k] = None
    return row


async def _fetch_basic(session: AsyncSession, ts_code: str) -> Optional[dict]:
    row = await _first(session, """
        SELECT b.*, COALESCE(s.st_type IS NOT NULL, FALSE) AS is_st
        FROM stock_basic b
        LEFT JOIN stock_st_list s ON b.ts_code = s.ts_code
        WHERE b.ts_code = :ts
    """, {"ts": ts_code})
    return _clean(row) if row else None


async def _fetch_quotes(session: AsyncSession, ts_code: str) -> dict:
    daily = await _all(session, """
        SELECT trade_date, open, high, low, close, vol, amount, pct_chg
        FROM stock_daily WHERE ts_code = :ts
        ORDER BY trade_date ASC LIMIT :lim
    """, {"ts": ts_code, "lim": _KLINE_LIMIT})
    weekly = await _all(session, """
        SELECT trade_date, open, high, low, close, vol, amount, pct_chg
        FROM stock_weekly WHERE ts_code = :ts
        ORDER BY trade_date ASC LIMIT :lim
    """, {"ts": ts_code, "lim": _KLINE_LIMIT})
    monthly = await _all(session, """
        SELECT trade_date, open, high, low, close, vol, amount, pct_chg
        FROM stock_monthly WHERE ts_code = :ts
        ORDER BY trade_date ASC LIMIT :lim
    """, {"ts": ts_code, "lim": _KLINE_LIMIT})
    return {
        "daily": [_clean(r) for r in daily],
        "weekly": [_clean(r) for r in weekly],
        "monthly": [_clean(r) for r in monthly],
    }


async def _fetch_latest_data(session: AsyncSession, ts_code: str) -> tuple:
    quote = await _first(session, """
        SELECT trade_date, close, pct_chg, vol, amount, open, high, low
        FROM stock_daily WHERE ts_code = :ts
        ORDER BY trade_date DESC LIMIT 1
    """, {"ts": ts_code})
    basic = await _first(session, """
        SELECT pe, pb, total_mv, circ_mv, turnover_rate, volume_ratio
        FROM stock_daily_basic WHERE ts_code = :ts
        ORDER BY trade_date DESC LIMIT 1
    """, {"ts": ts_code})
    limit = await _first(session, """
        SELECT up_limit, down_limit, pre_close
        FROM stock_daily_limit WHERE ts_code = :ts
        ORDER BY trade_date DESC LIMIT 1
    """, {"ts": ts_code})
    return _clean(quote) if quote else {}, _clean(basic) if basic else {}, _clean(limit) if limit else {}


async def _fetch_moneyflow(session: AsyncSession, ts_code: str) -> list:
    rows = await _all(session, """
        SELECT trade_date, net_mf_amount,
               buy_lg_amount, sell_lg_amount, buy_elg_amount, sell_elg_amount,
               buy_md_amount, sell_md_amount, buy_sm_amount, sell_sm_amount
        FROM stock_moneyflow WHERE ts_code = :ts
        ORDER BY trade_date DESC LIMIT 120
    """, {"ts": ts_code})
    return [_clean(r) for r in rows]


async def _fetch_indicators(session: AsyncSession, ts_code: str) -> list:
    """财务指标（不依赖完整的 ORM 财务模型）"""
    try:
        rows = await _all(session, """
            SELECT end_date, roe, roa, grossprofit_margin, netprofit_margin,
                   debt_to_assets, eps, bps, current_ratio, quick_ratio
            FROM stock_fina_indicators WHERE ts_code = :ts
            ORDER BY end_date DESC LIMIT 20
        """, {"ts": ts_code})
        return [_clean(r) for r in rows]
    except Exception:
        return []


async def _fetch_top_holders(session: AsyncSession, ts_code: str) -> list:
    try:
        rows = await _all(session, """
            SELECT end_date, holder_name, hold_num, hold_ratio
            FROM stock_top10_holders WHERE ts_code = :ts
            ORDER BY end_date DESC, hold_ratio DESC LIMIT 20
        """, {"ts": ts_code})
        return [_clean(r) for r in rows]
    except Exception:
        return []


async def _fetch_holdernumber(session: AsyncSession, ts_code: str) -> list:
    try:
        rows = await _all(session, """
            SELECT end_date, holder_num
            FROM stock_stk_holdernumber WHERE ts_code = :ts
            ORDER BY end_date DESC LIMIT 20
        """, {"ts": ts_code})
        return [_clean(r) for r in rows]
    except Exception:
        return []


async def _fetch_factors(session: AsyncSession, ts_code: str) -> dict:
    result: Dict[str, list] = {"stk_factor": [], "stk_factor_pro": []}
    for tbl in ("stock_factor_daily", "stock_factor_pro_daily"):
        try:
            rows = await _all(session, f"""
                SELECT * FROM {tbl} WHERE ts_code = :ts
                ORDER BY trade_date DESC LIMIT 120
            """, {"ts": ts_code})
            key = "stk_factor" if "pro" not in tbl else "stk_factor_pro"
            result[key] = [_clean(r) for r in rows]
        except Exception:
            pass
    return result


async def _fetch_pledge(session: AsyncSession, ts_code: str) -> Optional[dict]:
    try:
        return _clean(await _first(session, """
            SELECT * FROM stock_pledge_stat WHERE ts_code = :ts
            ORDER BY end_date DESC LIMIT 1
        """, {"ts": ts_code}))
    except Exception:
        return None


async def _fetch_st_risk(session: AsyncSession, ts_code: str) -> Optional[dict]:
    try:
        return _clean(await _first(session, """
            SELECT * FROM stock_st_risk WHERE ts_code = :ts LIMIT 1
        """, {"ts": ts_code}))
    except Exception:
        return None


async def get_stock_full(session: AsyncSession, ts_code: str) -> Optional[dict]:
    basic = await _fetch_basic(session, ts_code)
    if not basic:
        return None

    quotes, latest_basic, limit_price = await _fetch_latest_data(session, ts_code)
    klines = await _fetch_quotes(session, ts_code)
    moneyflow = await _fetch_moneyflow(session, ts_code)
    indicators = await _fetch_indicators(session, ts_code)
    top_holders = await _fetch_top_holders(session, ts_code)
    holdernumber = await _fetch_holdernumber(session, ts_code)
    factors = await _fetch_factors(session, ts_code)
    pledge = await _fetch_pledge(session, ts_code)
    st_risk = await _fetch_st_risk(session, ts_code)

    latest_quote = klines["daily"][-1] if klines["daily"] else {}

    return {
        "basic": basic,
        "latest_quote": latest_quote,
        "latest_basic": latest_basic,
        "limit_price": limit_price,
        "quotes": klines,
        "moneyflow": moneyflow,
        "financial": {"indicators": indicators},
        "shareholders": {
            "top10": top_holders,
            "holdernumber": holdernumber,
        },
        "factors": factors,
        "risk": {
            "pledge_stat": pledge,
            "st_risk": st_risk,
        },
    }
