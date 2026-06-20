# -*- coding: utf-8 -*-
"""股票筛选器 — 多条件组合查询"""
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

ALLOWED_SORT = {"pct_chg", "pe", "pb", "total_mv", "turnover_rate", "roe", "amount", "close"}
ALLOWED_DIR = {"asc", "desc"}


async def screener(
    session: AsyncSession,
    market: Optional[List[str]] = None,
    industry: Optional[List[str]] = None,
    pe_min: Optional[float] = None,
    pe_max: Optional[float] = None,
    pb_min: Optional[float] = None,
    pb_max: Optional[float] = None,
    mv_min: Optional[float] = None,
    mv_max: Optional[float] = None,
    roe_min: Optional[float] = None,
    pct_chg_min: Optional[float] = None,
    pct_chg_max: Optional[float] = None,
    turnover_min: Optional[float] = None,
    sort_by: str = "pct_chg",
    sort_dir: str = "desc",
    page: int = 1,
    limit: int = 50,
) -> Dict[str, Any]:
    """多条件股票筛选"""
    sort_by = sort_by if sort_by in ALLOWED_SORT else "pct_chg"
    sort_dir = sort_dir if sort_dir in ALLOWED_DIR else "desc"

    where = []
    params: Dict[str, Any] = {}

    # 市场筛选：SH → 6xxxx, SZ → 0xxxx/3xxxx
    if market:
        mk_conds = []
        for i, m in enumerate(market):
            if m == "SH":
                mk_conds.append(f"q.ts_code LIKE '6%'")
            elif m == "SZ":
                mk_conds.append(f"(q.ts_code LIKE '0%' OR q.ts_code LIKE '3%')")
        if mk_conds:
            where.append(f"({' OR '.join(mk_conds)})")

    # 行业筛选
    if industry:
        in_clause = ",".join(f":ind_{i}" for i in range(len(industry)))
        for i, ind in enumerate(industry):
            params[f"ind_{i}"] = ind
        where.append(
            f"b.ts_code IN (SELECT DISTINCT m.ts_code FROM index_sw_member m "
            f"WHERE m.l1_code IN (SELECT index_code FROM index_sw_classify WHERE industry_name IN ({in_clause}))"
            f" OR m.l2_code IN (SELECT index_code FROM index_sw_classify WHERE industry_name IN ({in_clause}))"
            f" OR m.l3_code IN (SELECT index_code FROM index_sw_classify WHERE industry_name IN ({in_clause})))"
            f" OR b.industry IN ({in_clause})"
        )

    # 数值筛选
    if pe_min is not None:
        where.append("COALESCE(d.pe, 9999) >= :pe_min"); params["pe_min"] = pe_min
    if pe_max is not None:
        where.append("COALESCE(d.pe, -1) <= :pe_max"); params["pe_max"] = pe_max
    if pb_min is not None:
        where.append("COALESCE(d.pb, 9999) >= :pb_min"); params["pb_min"] = pb_min
    if pb_max is not None:
        where.append("COALESCE(d.pb, -1) <= :pb_max"); params["pb_max"] = pb_max
    if mv_min is not None:
        where.append("COALESCE(d.total_mv, 0) >= :mv_min"); params["mv_min"] = mv_min
    if mv_max is not None:
        where.append("COALESCE(d.total_mv, 9e99) <= :mv_max"); params["mv_max"] = mv_max
    if pct_chg_min is not None:
        where.append("COALESCE(q.pct_chg, -999) >= :pct_min"); params["pct_min"] = pct_chg_min
    if pct_chg_max is not None:
        where.append("COALESCE(q.pct_chg, 999) <= :pct_max"); params["pct_max"] = pct_chg_max
    if turnover_min is not None:
        where.append("COALESCE(d.turnover_rate, 0) >= :to_min"); params["to_min"] = turnover_min
    if roe_min is not None:
        where.append("COALESCE(f.roe, -999) >= :roe_min"); params["roe_min"] = roe_min

    where_clause = " AND ".join(where) if where else "1=1"

    # 将 MAX(trade_date) 提到 CTE 中避免 LATERAL 内重复求值
    cte_prefix = """
        WITH latest_daily AS (SELECT MAX(trade_date) AS dt FROM stock_daily),
             latest_basic AS (SELECT MAX(trade_date) AS dt FROM stock_daily_basic)
    """

    # 计数
    count_sql = cte_prefix + f"""
        SELECT COUNT(*) FROM stock_basic b
        LEFT JOIN LATERAL (
            SELECT close, pct_chg, amount, vol FROM stock_daily q2
            WHERE q2.ts_code = b.ts_code
            AND q2.trade_date = (SELECT dt FROM latest_daily)
        ) q ON true
        LEFT JOIN LATERAL (
            SELECT pe, pb, total_mv, turnover_rate FROM stock_daily_basic d2
            WHERE d2.ts_code = b.ts_code
            AND d2.trade_date = (SELECT dt FROM latest_basic)
        ) d ON true
        LEFT JOIN LATERAL (
            SELECT roe, roa FROM stock_fina_indicators f2
            WHERE f2.ts_code = b.ts_code
            ORDER BY f2.end_date DESC LIMIT 1
        ) f ON true
        WHERE {where_clause}
    """
    r = await session.execute(text(count_sql), params)
    total = r.fetchone()[0]

    # 分页查询
    offset = (page - 1) * limit
    query_sql = cte_prefix + f"""
        SELECT b.ts_code, b.name, b.industry, b.list_date,
               q.close, q.pct_chg, q.amount, q.vol,
               d.pe, d.pb, d.total_mv, d.turnover_rate,
               COALESCE(f.roe, NULL) AS roe
        FROM stock_basic b
        LEFT JOIN LATERAL (
            SELECT close, pct_chg, amount, vol FROM stock_daily q2
            WHERE q2.ts_code = b.ts_code
            AND q2.trade_date = (SELECT dt FROM latest_daily)
        ) q ON true
        LEFT JOIN LATERAL (
            SELECT pe, pb, total_mv, turnover_rate FROM stock_daily_basic d2
            WHERE d2.ts_code = b.ts_code
            AND d2.trade_date = (SELECT dt FROM latest_basic)
        ) d ON true
        LEFT JOIN LATERAL (
            SELECT roe, roa FROM stock_fina_indicators f2
            WHERE f2.ts_code = b.ts_code
            ORDER BY f2.end_date DESC LIMIT 1
        ) f ON true
        WHERE {where_clause}
        ORDER BY {sort_by} {sort_dir} NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = limit
    params["offset"] = offset
    r = await session.execute(text(query_sql), params)
    stocks = [dict(row._mapping) for row in r.fetchall()]

    # float 清理
    for s in stocks:
        for k, v in list(s.items()):
            if isinstance(v, float) and v != v:
                s[k] = None

    return {"stocks": stocks, "total": total, "page": page}
