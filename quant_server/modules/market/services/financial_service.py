"""财务数据查询 — 多股票指标对比、三表查询"""
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def _all(session: AsyncSession, sql: str, params: dict) -> list:
    r = await session.execute(text(sql), params)
    return [dict(row._mapping) for row in r.fetchall()]


async def get_indicators_compare(session: AsyncSession, codes: List[str], metrics=None, end_date=None) -> List[Dict]:
    if not codes: return []
    in_codes = ",".join(f":c{i}" for i in range(len(codes)))
    params = {f"c{i}": c for i, c in enumerate(codes)}
    date_filter = "AND f.end_date = :ed" if end_date else "AND f.end_date = (SELECT MAX(end_date) FROM stock_fina_indicators WHERE ts_code = f.ts_code)"
    if end_date: params["ed"] = end_date

    sql = f"""
        SELECT f.ts_code, b.name, f.end_date,
               f.roe, f.roa, f.grossprofit_margin, f.netprofit_margin,
               f.debt_to_assets, f.eps, f.current_ratio, f.quick_ratio
        FROM stock_fina_indicators f
        JOIN stock_basic b ON f.ts_code = b.ts_code
        WHERE f.ts_code IN ({in_codes}) {date_filter}
        ORDER BY f.roe DESC NULLS LAST
    """
    rows = await _all(session, sql, params)
    for r in rows:
        for k, v in list(r.items()):
            if isinstance(v, float) and v != v: r[k] = None

    # 计算行业分位值（全市场排名）
    metric_cols = ["roe", "roa", "grossprofit_margin", "netprofit_margin", "debt_to_assets", "eps", "current_ratio", "quick_ratio"]
    for r in rows:
        for col in metric_cols:
            val = r.get(col)
            if val is None:
                continue
            pct_row = await _all(session, f"""
                SELECT
                    COUNT(*) FILTER (WHERE {col} IS NOT NULL AND {col} <= :val) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE {col} IS NOT NULL), 0) AS pct
                FROM stock_fina_indicators
                WHERE end_date = (SELECT MAX(end_date) FROM stock_fina_indicators WHERE ts_code = stock_fina_indicators.ts_code)
            """, {"val": val})
            if pct_row and pct_row[0].get("pct") is not None:
                r[f"{col}_pct"] = round(pct_row[0]["pct"], 0)
    return rows


async def get_statements(session: AsyncSession, code: str, stmt_type: str, limit: int = 20) -> List[Dict]:
    """单股三表查询 — 从 financial_income/balance/cashflow 表查询"""
    table_map = {"income": "financial_income", "balance": "financial_balance", "cashflow": "financial_cashflow"}
    table = table_map.get(stmt_type, "financial_income")
    try:
        rows = await _all(session, f"""
            SELECT * FROM {table}
            WHERE ts_code = :code
            ORDER BY end_date DESC LIMIT :lim
        """, {"code": code, "lim": limit})
        for r in rows:
            for k, v in list(r.items()):
                if isinstance(v, float) and v != v: r[k] = None
        return rows
    except Exception as e:
        logger.warning(f"Statements query failed {stmt_type} {code}: {e}")
        return []


async def get_events(session: AsyncSession, code: str, event_type: str, limit: int = 10) -> List[Dict]:
    """业绩预告/快报/分红"""
    tables = {"forecast": "stock_forecasts", "express": "stock_expresses", "dividend": "stock_dividends"}
    table = tables.get(event_type)
    if not table: return []
    order_col = "end_date" if event_type != "dividend" else "div_date"
    try:
        rows = await _all(session,
            f"SELECT * FROM {table} WHERE ts_code = :code ORDER BY {order_col} DESC LIMIT :lim",
            {"code": code, "lim": limit})
        for r in rows:
            for k, v in list(r.items()):
                if isinstance(v, float) and v != v: r[k] = None
        return rows
    except Exception as e:
        logger.warning(f"Events query failed {table} {code}: {e}")
        return []
