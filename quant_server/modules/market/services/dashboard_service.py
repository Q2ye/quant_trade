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
    """查询 6 大核心指数最新行情 — 使用 index_daily 自身的 MAX(trade_date)

    注意：不能用 stock_daily 的 latest_date，因为两个表的交易日可能不同步
    （如指数数据同步延迟、节假日等），导致 WHERE trade_date = :ld 返回空集。
    """
    latest = await _first(session, "SELECT MAX(trade_date) AS d FROM index_daily", {})
    if not latest or not latest.get("d"):
        logger.warning("index_daily 表无数据，请先同步指数日线数据")
        return []
    ld = latest["d"]
    logger.info(f"index_daily.latest_date = {ld}")
    return await _all(session, """
        SELECT d.ts_code AS code, b.name,
               d.close, d.pct_chg, d.open, d.high, d.low, d.vol, d.amount
        FROM index_daily d
        JOIN index_basic b ON d.ts_code = b.ts_code
        WHERE d.trade_date = :ld
          AND d.ts_code IN ('000001.SH','399001.SZ','000300.SH','000905.SH','399006.SZ','000688.SH')
    """, {"ld": ld})


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


async def _query_breadth(session: AsyncSession, latest_date=None) -> dict:
    row = await _first(session, """
        SELECT
            COUNT(*) FILTER (WHERE pct_chg > 0) AS up_count,
            COUNT(*) FILTER (WHERE pct_chg < 0) AS down_count,
            COUNT(*) FILTER (WHERE pct_chg = 0) AS flat_count,
            COUNT(*) FILTER (WHERE pct_chg >= 9.8) AS limit_up,
            COUNT(*) FILTER (WHERE pct_chg <= -9.8) AS limit_down,
            COUNT(*) AS total
        FROM stock_daily
        WHERE trade_date = :ld
    """, {"ld": latest_date})
    if not row:
        return {"data_date": None, "up": 0, "down": 0, "flat": 0, "total": 0, "limit_up": 0, "limit_down": 0}
    return {
        "data_date": row.get("data_date"),
        "up": row.get("up_count", 0), "down": row.get("down_count", 0),
        "flat": row.get("flat_count", 0), "total": row.get("total", 0),
        "limit_up": row.get("limit_up", 0), "limit_down": row.get("limit_down", 0),
    }


async def _query_top_volume(session: AsyncSession, latest_date=None, limit: int = 10) -> list:
    return await _all(session, """
        SELECT q.ts_code, b.name, b.industry,
               q.close, q.pct_chg, q.amount, q.vol,
               db.pe, db.pb, db.total_mv, db.circ_mv,
               db.turnover_rate, db.volume_ratio
        FROM stock_daily q
        JOIN stock_basic b ON q.ts_code = b.ts_code
        LEFT JOIN stock_daily_basic db ON db.ts_code = q.ts_code AND db.trade_date = :ld
        WHERE q.trade_date = :ld
        ORDER BY q.amount DESC
        LIMIT :lim
    """, {"ld": latest_date, "lim": limit})


async def _query_top_flow(session: AsyncSession, latest_date=None, limit: int = 10) -> list:
    # 修复 2026-08（A32）：moneyflow 与 stock_daily 日期基准不同，必须独立查最新日期，
    # 此前复用 stock_daily 日期导致 moneyflow 恒空
    row = await _first(session, "SELECT MAX(trade_date) AS d FROM stock_moneyflow", {})
    mf_latest = row["d"] if row else None
    return await _all(session, """
        SELECT m.ts_code, b.name, m.net_mf_amount,
               m.buy_elg_amount, m.sell_elg_amount,
               m.buy_lg_amount, m.sell_lg_amount,
               q.close, q.pct_chg
        FROM stock_moneyflow m
        JOIN stock_basic b ON m.ts_code = b.ts_code
        LEFT JOIN stock_daily q ON q.ts_code = m.ts_code AND q.trade_date = :mf_ld
        WHERE m.trade_date = :mf_ld
        ORDER BY m.net_mf_amount DESC
        LIMIT :lim
    """, {"mf_ld": mf_latest, "lim": limit})


async def _query_hsgt(session: AsyncSession) -> Optional[dict]:
    return await _first(session, """
        SELECT trade_date, north_money AS net_inflow,
               hgt AS sh_inflow, sgt AS sz_inflow
        FROM stock_moneyflow_hsgt
        WHERE trade_date = (SELECT MAX(trade_date) FROM stock_moneyflow_hsgt)
    """, {})


async def _query_sw_heatmap_multi(session: AsyncSession) -> list:
    """多窗口行业轮动热力图"""
    try:
        from modules.market.services.industry_service import get_industry_heatmap_multi_window
        return await get_industry_heatmap_multi_window(session, [1, 5, 10, 20, 30, 60])
    except Exception as e:
        logger.warning(f"行业热力图查询失败: {e}")
        return []


async def _query_macro_latest(session: AsyncSession) -> dict:
    """宏观最新值"""
    try:
        cpi = await _first(session, """
            SELECT month AS date, nt_yoy AS cpi_yoy FROM macro_cpi
            ORDER BY month DESC LIMIT 1
        """, {})
        ppi = await _first(session, """
            SELECT month AS date, ppi_yoy FROM macro_ppi
            ORDER BY month DESC LIMIT 1
        """, {})
        gdp = await _first(session, """
            SELECT quarter AS date, gdp_yoy FROM macro_gdp
            ORDER BY quarter DESC LIMIT 1
        """, {})
        return {
            "cpi": {"date": cpi["date"] if cpi and cpi.get("date") else None,
                    "cpi_yoy": float(cpi["cpi_yoy"]) if cpi and cpi.get("cpi_yoy") else None},
            "ppi": {"date": ppi["date"] if ppi and ppi.get("date") else None,
                    "ppi_yoy": float(ppi["ppi_yoy"]) if ppi and ppi.get("ppi_yoy") else None},
            "gdp": {"date": gdp["date"] if gdp and gdp.get("date") else None,
                    "gdp_yoy": float(gdp["gdp_yoy"]) if gdp and gdp.get("gdp_yoy") else None},
        }
    except Exception as e:
        logger.warning(f"宏观数据查询失败: {e}")
        return {"cpi": None, "ppi": None, "gdp": None}


async def _timed(name: str, coro):
    t0 = __import__("time").perf_counter()
    try:
        result = await coro
        ms = (__import__("time").perf_counter() - t0) * 1000
        logger.info(f"dashboard.{name} 完成 ({ms:.0f}ms)")
        return result
    except Exception as e:
        ms = (__import__("time").perf_counter() - t0) * 1000
        logger.warning(f"dashboard.{name} 失败 ({ms:.0f}ms): {e}")
        return e  # 返回异常对象而非 re-raise，避免事务级联失败


async def _get_latest_date(session):
    """预计算最新交易日，带缓存"""
    row = await _first(session, "SELECT MAX(trade_date) AS d FROM stock_daily", {})
    return row["d"] if row else None


async def get_dashboard_overview(session: AsyncSession) -> Dict[str, Any]:
    t0 = __import__("time").perf_counter()
    latest_date = await _get_latest_date(session)
    if latest_date:
        logger.info(f"dashboard.latest_date = {latest_date}")

    # v2: 每查询独立 session，实现真正并发（避免单 session 串行化）
    from shared.database.session.session_manager import get_session_manager
    sm = get_session_manager()

    async def _with_session(name, coro_fn):
        async with sm.get_session() as s:
            return await _timed(name, coro_fn(s))

    results = await asyncio.gather(
        _with_session("indices", lambda s: _query_indices(s)),
        _with_session("industry", lambda s: _query_industry(s)),
        _with_session("breadth", lambda s: _query_breadth(s, latest_date)),
        _with_session("top_volume", lambda s: _query_top_volume(s, latest_date)),
        _with_session("top_flow", lambda s: _query_top_flow(s, latest_date)),
        _with_session("hsgt", lambda s: _query_hsgt(s)),
        _with_session("sw_heatmap", lambda s: _query_sw_heatmap_multi(s)),
        _with_session("macro", lambda s: _query_macro_latest(s)),
        return_exceptions=True,
    )
    indices, heatmap, breadth, volume, flow, hsgt, sw_heatmap, macro_latest = results
    total_ms = (__import__("time").perf_counter() - t0) * 1000
    logger.info(f"dashboard.overview 完成 → 总耗时 {total_ms:.0f}ms")

    # data_date 从预查询的 latest_date 获取
    if latest_date:
        data_date = latest_date.isoformat() if hasattr(latest_date, "isoformat") else str(latest_date)
    else:
        data_date = None

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
        "sw_heatmap": sw_heatmap if not isinstance(sw_heatmap, Exception) else [],
        "macro_latest": macro_latest if not isinstance(macro_latest, Exception) else {},
    }


async def get_style_factors(session: AsyncSession) -> list:
    """风格因子日收益（动量/价值/波动/规模）"""
    try:
        rows = await _all(session, """
            SELECT fd.trade_date, fd.factor_code,
                   AVG(fd.{val}) AS factor_return
            FROM factor_data fd
            WHERE fd.trade_date >= (SELECT MAX(trade_date) FROM factor_data) - INTERVAL '5 days'
              AND fd.factor_code IN ('momentum','value','volatility','size','quality')
            GROUP BY fd.trade_date, fd.factor_code
            ORDER BY fd.trade_date DESC, fd.factor_code
        """.replace("{val}", "factor_value"), {})
        # fallback: try with generic column
        if not rows:
            rows = await _all(session, """
                SELECT trade_date, 'momentum' AS factor_code, AVG(COALESCE(macd, 0)) AS factor_return
                FROM stock_factor_daily
                WHERE trade_date >= (SELECT MAX(trade_date) FROM stock_factor_daily) - INTERVAL '5 days'
                GROUP BY trade_date
                ORDER BY trade_date DESC LIMIT 5
            """, {})
        return rows or []
    except Exception as e:
        logger.warning(f"get_style_factors failed: {e}")
        return []


async def get_sector_turnover(session: AsyncSession) -> dict:
    """行业轮动速度 — 28 行业排名的 20 日 turnover rate"""
    try:
        rows = await _all(session, """
            SELECT trade_date, ts_code,
                   RANK() OVER (PARTITION BY trade_date ORDER BY pct_change DESC) AS rnk
            FROM index_sw_daily
            WHERE trade_date >= (SELECT MAX(trade_date) FROM index_sw_daily) - INTERVAL '20 days'
            ORDER BY trade_date, ts_code
        """, {})
        if not rows:
            return {"turnover_rate": None, "description": "无行业数据"}
        # 计算最近 20 日排名变化的 turnover
        from collections import defaultdict
        ranks_by_date = defaultdict(dict)
        for r in rows:
            ranks_by_date[str(r["trade_date"])[:10]][r["ts_code"]] = r["rnk"]
        dates = sorted(ranks_by_date.keys())
        if len(dates) < 2:
            return {"turnover_rate": 0, "description": "数据不足"}
        changes = 0
        for i in range(1, len(dates)):
            prev, curr = ranks_by_date[dates[i-1]], ranks_by_date[dates[i]]
            for code in set(list(prev.keys()) + list(curr.keys())):
                if prev.get(code) != curr.get(code):
                    changes += 1
        rate = round(changes / (len(dates) - 1) / max(len(set(r["ts_code"] for r in rows)), 1), 3)
        return {"turnover_rate": rate, "description": f"基于 {len(dates)} 个交易日", "dates": len(dates)}
    except Exception as e:
        logger.warning(f"get_sector_turnover failed: {e}")
        return {"turnover_rate": None, "description": str(e)}
