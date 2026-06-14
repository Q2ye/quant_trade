# -*- coding: utf-8 -*-
"""行业分析查询 — 申万行业分类、行情、成分股"""
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


async def get_industry_tree(session: AsyncSession) -> list:
    """申万行业分类树（L1/L2/L3）"""
    return await _all(session, """
        SELECT index_code AS code, industry_name AS name, level, parent_code
        FROM index_sw_classify
        ORDER BY level, index_code
    """, {})


async def get_industry_heatmap(session: AsyncSession) -> list:
    """申万一级行业当日行情"""
    return await _all(session, """
        SELECT d.ts_code AS code, c.industry_name AS name,
               d.pct_change AS pct_chg, d.close, d.vol, d.amount
        FROM index_sw_daily d
        JOIN index_sw_classify c ON d.ts_code = c.index_code
        WHERE d.trade_date = (SELECT MAX(trade_date) FROM index_sw_daily)
          AND c.level = 'L1'
        ORDER BY d.pct_change DESC
    """, {})


async def get_industry_detail(session: AsyncSession, industry_code: str) -> Optional[dict]:
    """行业详情：行情+成分股"""
    info = await _first(session, """
        SELECT d.ts_code AS code, c.industry_name AS name, c.level,
               d.pct_change AS pct_chg, d.close, d.vol, d.amount
        FROM index_sw_daily d
        JOIN index_sw_classify c ON d.ts_code = c.index_code
        WHERE d.ts_code = :code
          AND d.trade_date = (SELECT MAX(trade_date) FROM index_sw_daily WHERE ts_code = :code)
    """, {"code": industry_code})
    if not info:
        return None

    members = await _all(session, """
        SELECT m.ts_code, b.name,
               q.close, q.pct_chg, q.amount
        FROM index_sw_member m
        JOIN stock_basic b ON m.ts_code = b.ts_code
        LEFT JOIN stock_daily q ON q.ts_code = m.ts_code
            AND q.trade_date = (SELECT MAX(trade_date) FROM stock_daily)
        WHERE (m.l1_code = :code OR m.l2_code = :code OR m.l3_code = :code)
        ORDER BY q.pct_chg DESC NULLS LAST
        LIMIT 100
    """, {"code": industry_code})

    return {"info": info, "members": members}


async def get_industry_heatmap_multi_window(
    session: AsyncSession, windows: list = None
) -> list:
    """申万一级行业多窗口涨跌幅矩阵 — 优化版：单次范围查询 + Python 计算

    避免 CTE + ROW_NUMBER 全表扫描，改为只取最近 max(windows)+1 天的数据。
    """
    if windows is None:
        windows = [1, 5, 10, 20, 30, 60]

    max_window = max(windows) + 5  # 多取几天容错

    try:
        # 一次性查询所有 L1 行业最近 max_window 天的 close 数据
        rows = await _all(session, """
            SELECT d.ts_code, d.trade_date, d.close, d.amount,
                   c.industry_name
            FROM index_sw_daily d
            JOIN index_sw_classify c ON d.ts_code = c.index_code
            WHERE c.level = 'L1'
              AND d.trade_date >= (
                SELECT MAX(trade_date) FROM index_sw_daily
              ) - CAST(:days AS INTEGER)
            ORDER BY d.ts_code, d.trade_date DESC
        """, {"days": max_window})

        # 按行业分组，closes 按 trade_date DESC 排列
        industry_data: Dict[str, dict] = {}
        for row in rows:
            code = row["ts_code"]
            if code not in industry_data:
                industry_data[code] = {
                    "code": code,
                    "name": row["industry_name"] or code,
                    "amount": row.get("amount"),
                    "closes": [],  # 按日期倒序的 close 列表
                }
            close = float(row["close"]) if row["close"] else None
            if close is not None:
                industry_data[code]["closes"].append(close)

        # 计算各窗口涨跌幅
        result = []
        for code, d in industry_data.items():
            closes = d["closes"]
            if len(closes) < 2:
                continue
            latest = closes[0]
            item: dict = {"code": code, "name": d["name"], "amount": d.get("amount")}
            for w in windows:
                if w < len(closes):
                    hist = closes[w]
                    item[f"pct_{w}d"] = round((latest / hist - 1) * 100, 2) if hist else None
                else:
                    item[f"pct_{w}d"] = None
            item["pct_chg"] = item.get("pct_1d")
            item["pct_chg_5d"] = item.get("pct_5d")
            item["pct_chg_20d"] = item.get("pct_20d")
            result.append(item)

        result.sort(key=lambda x: x.get("pct_1d") or 0, reverse=True)
        return result

    except Exception as e:
        logger.error(f"多窗口行业热力图查询失败: {e}", exc_info=True)
        return []


async def get_industry_history(session: AsyncSession, industry_code: str, limit: int = 60) -> list:
    """行业指数历史行情"""
    return await _all(session, """
        SELECT trade_date, open, high, low, close, vol, amount, pct_change AS pct_chg
        FROM index_sw_daily
        WHERE ts_code = :code
        ORDER BY trade_date DESC
        LIMIT :lim
    """, {"code": industry_code, "lim": limit})


async def get_industry_trend(session: AsyncSession, days: int = 60) -> dict:
    """28 个申万 L1 行业日度趋势数据 — 一条 SQL 返回全部系列

    Returns:
        {"dates": ["2026-01-02", ...], "series": [{"name":"银行","code":"SW801780","data":[0.5,1.2,...]}, ...]}
    """
    rows = await _all(session, """
        SELECT d.trade_date, d.pct_change, d.amount,
               c.index_code, c.industry_name
        FROM index_sw_daily d
        JOIN index_sw_classify c ON d.ts_code = c.index_code
        WHERE c.level = 'L1'
          AND d.trade_date >= (
            SELECT MAX(trade_date) FROM index_sw_daily
          ) - CAST(:days AS INTEGER)
        ORDER BY d.trade_date, c.index_code
    """, {"days": days})

    if not rows:
        return {"dates": [], "series": [], "total_industries": 0}

    # 提取排序后的日期列表
    dates: List[str] = []
    seen_dates = set()
    for r in rows:
        d = r["trade_date"]
        if hasattr(d, "isoformat"):
            d = d.isoformat()[:10]
        if d not in seen_dates:
            dates.append(d)
            seen_dates.add(d)

    # 按行业分组 pivot
    by_code: Dict[str, dict] = {}
    for r in rows:
        code = r["index_code"]
        name = r["industry_name"]
        pct = float(r["pct_change"]) if r["pct_change"] is not None else None
        if code not in by_code:
            by_code[code] = {"name": name, "code": code, "data": []}
        by_code[code]["data"].append(pct)

    series = list(by_code.values())

    return {
        "dates": dates,
        "series": series,
        "total_industries": len(series),
    }
