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
    asset_type: str = "stock",
    search: Optional[str] = None,
    fund_type: Optional[str] = None,
) -> Dict[str, Any]:
    """多条件筛选器 — asset_type=stock 走 A 股多因子；asset_type=etf 走 ETF 筛选"""
    if asset_type == "etf":
        return await _screener_etf(
            session, search=search, fund_type=fund_type,
            sort_by=sort_by, sort_dir=sort_dir, page=page, limit=limit,
        )
    sort_by = sort_by if sort_by in ALLOWED_SORT else "pct_chg"
    sort_dir = sort_dir if sort_dir in ALLOWED_DIR else "desc"

    where = []
    params: Dict[str, Any] = {}

    # 市场筛选：SH → 上交所(SSE)，SZ → 深交所(SZSE)（stock_basic.exchange，修复 q.ts_code 列不存在的 500）
    if market:
        mk_conds = []
        for i, m in enumerate(market):
            if m == "SH":
                mk_conds.append("b.exchange = 'SSE'")
            elif m == "SZ":
                mk_conds.append("b.exchange = 'SZSE'")
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

    # 数值筛选（未知值一律排除：IS NOT NULL，修复 COALESCE(-1/9999) 放行空值）
    if pe_min is not None:
        where.append("d.pe IS NOT NULL AND d.pe >= :pe_min"); params["pe_min"] = pe_min
    if pe_max is not None:
        where.append("d.pe IS NOT NULL AND d.pe <= :pe_max"); params["pe_max"] = pe_max
    if pb_min is not None:
        where.append("d.pb IS NOT NULL AND d.pb >= :pb_min"); params["pb_min"] = pb_min
    if pb_max is not None:
        where.append("d.pb IS NOT NULL AND d.pb <= :pb_max"); params["pb_max"] = pb_max
    if mv_min is not None:
        where.append("COALESCE(d.total_mv, 0) >= :mv_min"); params["mv_min"] = mv_min
    if mv_max is not None:
        where.append("COALESCE(d.total_mv, 9e99) <= :mv_max"); params["mv_max"] = mv_max
    if pct_chg_min is not None:
        where.append("q.pct_chg IS NOT NULL AND q.pct_chg >= :pct_min"); params["pct_min"] = pct_chg_min
    if pct_chg_max is not None:
        where.append("q.pct_chg IS NOT NULL AND q.pct_chg <= :pct_max"); params["pct_max"] = pct_chg_max
    if turnover_min is not None:
        where.append("d.turnover_rate IS NOT NULL AND d.turnover_rate >= :to_min"); params["to_min"] = turnover_min
    if roe_min is not None:
        where.append("f.roe IS NOT NULL AND f.roe >= :roe_min"); params["roe_min"] = roe_min

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


async def list_industries(session: AsyncSession) -> List[str]:
    """去重行业列表（stock_basic.industry，东财口径，供选股器行业筛选下拉用）"""
    r = await session.execute(text("""
        SELECT DISTINCT industry FROM stock_basic
        WHERE industry IS NOT NULL AND industry != ''
        ORDER BY industry
    """))
    return [row[0] for row in r.fetchall()]


async def list_etf_types(session: AsyncSession) -> List[str]:
    """去重 ETF 类型列表（etf_basic.fund_type，供选股器 ETF 模式类型下拉用）"""
    r = await session.execute(text("""
        SELECT DISTINCT fund_type FROM etf_basic
        WHERE fund_type IS NOT NULL AND fund_type != ''
        ORDER BY fund_type
    """))
    return [row[0] for row in r.fetchall()]


_ETF_SORT = {
    "pct_chg": "q.pct_chg",
    "amount": "q.amount",
    "close": "q.close",
    "scale": "b.issue_amount",
}


async def _screener_etf(
    session: AsyncSession,
    search: Optional[str] = None,
    fund_type: Optional[str] = None,
    sort_by: str = "amount",
    sort_dir: str = "desc",
    page: int = 1,
    limit: int = 50,
) -> Dict[str, Any]:
    """ETF 筛选：类型/搜索/规模/成交额，返回上市 ETF 列表"""
    where = ["b.list_status = 'L'"]
    params: Dict[str, Any] = {}
    if search:
        where.append("(b.ts_code ILIKE :kw OR b.name ILIKE :kw)")
        params["kw"] = f"%{search}%"
    if fund_type:
        where.append("b.fund_type = :ft")
        params["ft"] = fund_type
    where_clause = " AND ".join(where)

    sort_col = _ETF_SORT.get(sort_by, "q.amount")
    sort_dir = sort_dir if sort_dir in ALLOWED_DIR else "desc"
    dir_sql = "ASC" if sort_dir == "asc" else "DESC"

    count_sql = f"""
        SELECT COUNT(*) FROM etf_basic b
        LEFT JOIN LATERAL (
            SELECT close, pct_chg, amount FROM etf_daily q2
            WHERE q2.ts_code = b.ts_code
            AND q2.trade_date = (SELECT MAX(trade_date) FROM etf_daily)
        ) q ON true
        WHERE {where_clause}
    """
    r = await session.execute(text(count_sql), params)
    total = r.fetchone()[0]

    offset = (page - 1) * limit
    query_sql = f"""
        SELECT b.ts_code, b.name, b.fund_type, b.management,
               q.close, q.pct_chg, q.amount,
               b.issue_amount AS scale_wan
        FROM etf_basic b
        LEFT JOIN LATERAL (
            SELECT close, pct_chg, amount FROM etf_daily q2
            WHERE q2.ts_code = b.ts_code
            AND q2.trade_date = (SELECT MAX(trade_date) FROM etf_daily)
        ) q ON true
        WHERE {where_clause}
        ORDER BY {sort_col} {dir_sql} NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = limit
    params["offset"] = offset
    r = await session.execute(text(query_sql), params)
    etfs = [dict(row._mapping) for row in r.fetchall()]
    for e in etfs:
        for k, v in list(e.items()):
            if isinstance(v, float) and v != v:
                e[k] = None
    return {"stocks": etfs, "total": total, "page": page}
