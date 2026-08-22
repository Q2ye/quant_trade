# -*- coding: utf-8 -*-
"""市场宽度服务 (N6) — 强弱榜：创20日新高 / 创20日新低 / 连涨≥5日，各 TOP10

口径（2026-08 Market v5）：
- 创20日新高：今日收盘 > 前 19 个交易日最高收盘，且前 19 日样本完整（上市满 20 日）
- 创20日新低：今日收盘 < 前 19 个交易日最低收盘，同上
- 连涨≥5日：截至今日收盘连续上涨 ≥5 个交易日
- 默认排除 ST（名称含 ST/*ST）与退市；按成交额 DESC 取 TOP10
- 缓存：模块级 dict TTL 300s
"""
import asyncio
import logging
import math
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.market.services.market_temperature_service import percentile_rank
from modules.market.services._swr_cache import SwrCache
from modules.market.services._latest_date_cache import get_latest_trade_date

logger = logging.getLogger(__name__)

_HISTORY_DAYS = 45  # 覆盖 20 个交易日的日历余量（含停牌缺口容忍）
_swr = SwrCache(ttl=300.0)  # SWR：过期返回旧值 + 后台重算（P2）

_ST_FILTER = "AND b.list_status = 'L' AND b.name NOT LIKE 'ST%' AND b.name NOT LIKE '*ST%'"


async def _all(session: AsyncSession, sql: str, params: dict) -> list:
    r = await session.execute(text(sql), params)
    return [dict(row._mapping) for row in r.fetchall()]


async def _first(session: AsyncSession, sql: str, params: dict) -> Optional[dict]:
    r = await session.execute(text(sql), params)
    row = r.fetchone()
    return dict(row._mapping) if row else None


def _fmt(row: dict) -> dict:
    out = {"ts_code": row["ts_code"], "name": row.get("name"), "industry": row.get("industry")}
    for k in ("close", "pct_chg", "amount"):
        v = row.get(k)
        out[k] = round(float(v), 2) if v is not None else None
    return out


async def _query_new_highs(session: AsyncSession, ld, start) -> list:
    rows = await _all(session, """
        WITH hist AS (
            SELECT ts_code, trade_date, close, pct_chg, amount,
                   MAX(close) OVER (PARTITION BY ts_code ORDER BY trade_date
                       ROWS BETWEEN 19 PRECEDING AND 1 PRECEDING) AS prev_max20,
                   COUNT(*) OVER (PARTITION BY ts_code ORDER BY trade_date
                       ROWS BETWEEN 19 PRECEDING AND 1 PRECEDING) AS n_prev
            FROM stock_daily
            WHERE trade_date <= :ld AND trade_date >= :start
        )
        SELECT l.ts_code, b.name, b.industry, l.close, l.pct_chg, l.amount
        FROM hist l
        JOIN stock_basic b ON l.ts_code = b.ts_code
        WHERE l.trade_date = :ld
          AND l.close > l.prev_max20 AND l.n_prev >= 19
          {st}
        ORDER BY l.amount DESC
        LIMIT 10
    """.replace("{st}", _ST_FILTER), {"ld": ld, "start": start})
    return [_fmt(r) for r in rows]


async def _query_new_lows(session: AsyncSession, ld, start) -> list:
    rows = await _all(session, """
        WITH hist AS (
            SELECT ts_code, trade_date, close, pct_chg, amount,
                   MIN(close) OVER (PARTITION BY ts_code ORDER BY trade_date
                       ROWS BETWEEN 19 PRECEDING AND 1 PRECEDING) AS prev_min20,
                   COUNT(*) OVER (PARTITION BY ts_code ORDER BY trade_date
                       ROWS BETWEEN 19 PRECEDING AND 1 PRECEDING) AS n_prev
            FROM stock_daily
            WHERE trade_date <= :ld AND trade_date >= :start
        )
        SELECT l.ts_code, b.name, b.industry, l.close, l.pct_chg, l.amount
        FROM hist l
        JOIN stock_basic b ON l.ts_code = b.ts_code
        WHERE l.trade_date = :ld
          AND l.close < l.prev_min20 AND l.n_prev >= 19
          {st}
        ORDER BY l.amount DESC
        LIMIT 10
    """.replace("{st}", _ST_FILTER), {"ld": ld, "start": start})
    return [_fmt(r) for r in rows]


async def _query_streak_up(session: AsyncSession, ld, start) -> list:
    rows = await _all(session, """
        WITH hist AS (
            SELECT ts_code, trade_date, close, pct_chg, amount
            FROM stock_daily
            WHERE trade_date <= :ld AND trade_date >= :start
        ),
        grp AS (
            SELECT *,
                   SUM(CASE WHEN pct_chg <= 0 THEN 1 ELSE 0 END)
                       OVER (PARTITION BY ts_code ORDER BY trade_date DESC
                             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS grp_id
            FROM hist
        ),
        streaks AS (
            SELECT ts_code,
                   COUNT(*) FILTER (WHERE pct_chg > 0 AND grp_id = 0) AS streak,
                   MAX(trade_date) FILTER (WHERE grp_id = 0) AS last_up_date
            FROM grp
            GROUP BY ts_code
        )
        SELECT s.ts_code, b.name, b.industry, h.close, h.pct_chg, h.amount
        FROM streaks s
        JOIN stock_basic b ON s.ts_code = b.ts_code
        JOIN hist h ON h.ts_code = s.ts_code AND h.trade_date = :ld
        WHERE s.streak >= 5 AND s.last_up_date = :ld
          {st}
        ORDER BY h.amount DESC
        LIMIT 10
    """.replace("{st}", _ST_FILTER), {"ld": ld, "start": start})
    return [_fmt(r) for r in rows]


# ==================== 主入口（SWR：过期返回旧值 + 后台重算） ====================

async def _compute_breadth_leaders(session: AsyncSession) -> Dict[str, Any]:
    # 修复 2026-08（慢查询）：压缩超表 MAX(trade_date) 全量扫描 ~3.4s，改用 TTL 缓存
    ld = await get_latest_trade_date(session, "stock_daily")
    if not ld:
        return {"data_date": None, "new_highs": [], "new_lows": [], "streak_up": []}
    start = ld - timedelta(days=_HISTORY_DAYS)

    new_highs = await _query_new_highs(session, ld, start)
    new_lows = await _query_new_lows(session, ld, start)
    streak_up = await _query_streak_up(session, ld, start)

    return {
        "data_date": ld.isoformat() if hasattr(ld, "isoformat") else str(ld),
        "new_highs": new_highs,
        "new_lows": new_lows,
        "streak_up": streak_up,
    }


async def _recompute_breadth_leaders() -> None:
    from shared.database.session.session_manager import get_session_manager
    sm = get_session_manager()
    try:
        async with sm.get_session() as s:
            result = await _compute_breadth_leaders(s)
        _swr.set("breadth", result)
        logger.info("breadth-leaders 后台重算完成")
    except Exception as e:
        logger.warning("breadth-leaders 后台重算失败: %s", e)


async def get_breadth_leaders(session: AsyncSession) -> Dict[str, Any]:
    """强弱榜：创20日新高 / 创20日新低 / 连涨≥5日 TOP10。SWR 缓存 300s。"""
    stale, need_recompute = _swr.probe("breadth")
    if stale is not None:
        if need_recompute:
            _swr.set_task("breadth", asyncio.create_task(_recompute_breadth_leaders()))
        return stale
    result = await _compute_breadth_leaders(session)
    _swr.set("breadth", result)
    return result


# ==================== N2 市场宽度补全 + N5 波动率分位（2026-08 Market v5 P1） ====================

def calc_annualized_vol(pct_list: List[float]) -> float:
    """年化波动率（%）：pct_list 为百分比涨跌幅（1.5 表示 +1.5%），样本 <2 返回 0"""
    if len(pct_list) < 2:
        return 0.0
    rets = [p / 100.0 for p in pct_list]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252) * 100


def rolling_vol(pct_list: List[float], window: int) -> List[Optional[float]]:
    """滚动 window 日年化波动率序列（升序）；前 window-1 位为 None"""
    out: List[Optional[float]] = []
    for i in range(len(pct_list)):
        if i < window - 1:
            out.append(None)
        else:
            out.append(calc_annualized_vol(pct_list[i - window + 1: i + 1]))
    return out


async def get_breadth_metrics(session: AsyncSession) -> Dict[str, Any]:
    """市场宽度补全（N2）+ 波动率分位（N5）。SWR 缓存 300s。"""
    stale, need_recompute = _swr.probe("breadth_metrics")
    if stale is not None:
        if need_recompute:
            _swr.set_task("breadth_metrics", asyncio.create_task(_recompute_breadth_metrics()))
        return stale
    result = await _compute_breadth_metrics(session)
    _swr.set("breadth_metrics", result)
    return result


async def _recompute_breadth_metrics() -> None:
    from shared.database.session.session_manager import get_session_manager
    sm = get_session_manager()
    try:
        async with sm.get_session() as s:
            result = await _compute_breadth_metrics(s)
        _swr.set("breadth_metrics", result)
        logger.info("breadth-metrics 后台重算完成")
    except Exception as e:
        logger.warning("breadth-metrics 后台重算失败: %s", e)


async def _compute_breadth_metrics(session: AsyncSession) -> Dict[str, Any]:
    """市场宽度补全（N2）+ 波动率分位（N5）计算主体（不含缓存逻辑）

    返回:
        {
            "data_date": "2026-08-14",
            "new_highs": n, "new_lows": n,            # 创20日新高/新低家数
            "above_ma20_market": 52.3, "above_ma60_market": 61.2,   # 全市场站上均线比例 %
            "above_ma20_hs300": 48.1, "above_ma60_hs300": 55.6,     # 沪深300 站上均线比例 %
            "volatility": {"value_20d": 18.3, "percentile": 42.1},  # 沪深300 20日年化波动% + 750日分位
        }
    """
    # 修复 2026-08（慢查询）：压缩超表 MAX(trade_date) 全量扫描 ~3.4s，改用 TTL 缓存
    ld = await get_latest_trade_date(session, "stock_daily")
    if not ld:
        return {
            "data_date": None, "new_highs": None, "new_lows": None,
            "above_ma20_market": None, "above_ma60_market": None,
            "above_ma20_hs300": None, "above_ma60_hs300": None,
            "volatility": {"value_20d": None, "percentile": None},
        }
    start20 = ld - timedelta(days=45)
    start60 = ld - timedelta(days=100)

    # 1. 创20日新高/新低家数（与 get_breadth_leaders 同口径）
    hl = await _first(session, """
        WITH hist AS (
            SELECT ts_code, trade_date, close,
                   MAX(close) OVER (PARTITION BY ts_code ORDER BY trade_date
                       ROWS BETWEEN 19 PRECEDING AND 1 PRECEDING) AS prev_max20,
                   MIN(close) OVER (PARTITION BY ts_code ORDER BY trade_date
                       ROWS BETWEEN 19 PRECEDING AND 1 PRECEDING) AS prev_min20,
                   COUNT(*) OVER (PARTITION BY ts_code ORDER BY trade_date
                       ROWS BETWEEN 19 PRECEDING AND 1 PRECEDING) AS n_prev
            FROM stock_daily
            WHERE trade_date <= :ld AND trade_date >= :start20
        )
        SELECT COUNT(*) FILTER (WHERE close > prev_max20 AND n_prev >= 19) AS new_highs,
               COUNT(*) FILTER (WHERE close < prev_min20 AND n_prev >= 19) AS new_lows
        FROM hist
        WHERE trade_date = :ld
    """, {"ld": ld, "start20": start20})

    # 2. 全市场站上 MA20 / MA60 比例（方案 A：优先读 market_state_daily 预计算列；
    #    列缺失/未回填的过渡期 → 原重查询兜底）
    mkt_ma20: Optional[float] = None
    mkt_ma60: Optional[float] = None
    try:
        ma_row = await _first(session, """
            SELECT above_ma20_pct, above_ma60_pct FROM market_state_daily
            WHERE above_ma20_pct IS NOT NULL OR above_ma60_pct IS NOT NULL
            ORDER BY trade_date DESC LIMIT 1
        """, {})
        if ma_row and ma_row.get("above_ma20_pct") is not None:
            mkt_ma20 = float(ma_row["above_ma20_pct"])
        if ma_row and ma_row.get("above_ma60_pct") is not None:
            mkt_ma60 = float(ma_row["above_ma60_pct"])
    except Exception as e:
        logger.warning("宽度指标读预计算列失败（可能未执行 DDL）: %s，走原查询兜底", e)
    if mkt_ma20 is None or mkt_ma60 is None:
        mkt = await _first(session, """
            WITH w AS (
                SELECT ts_code, trade_date, close,
                       AVG(close) OVER (PARTITION BY ts_code ORDER BY trade_date
                           ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ma20,
                       AVG(close) OVER (PARTITION BY ts_code ORDER BY trade_date
                           ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS ma60,
                       COUNT(close) OVER (PARTITION BY ts_code ORDER BY trade_date
                           ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS n
                FROM stock_daily
                WHERE trade_date <= :ld AND trade_date >= :start60
            )
            SELECT COUNT(*) FILTER (WHERE n >= 60 AND close >= ma20)::float
                       / NULLIF(COUNT(*) FILTER (WHERE n >= 60), 0) * 100 AS above_ma20,
                   COUNT(*) FILTER (WHERE n >= 60 AND close >= ma60)::float
                       / NULLIF(COUNT(*) FILTER (WHERE n >= 60), 0) * 100 AS above_ma60
            FROM w
            WHERE trade_date = :ld
        """, {"ld": ld, "start60": start60})
        if mkt and mkt.get("above_ma20") is not None:
            mkt_ma20 = float(mkt["above_ma20"])
        if mkt and mkt.get("above_ma60") is not None:
            mkt_ma60 = float(mkt["above_ma60"])

    # 3. 沪深300 站上 MA20 / MA60 比例（index_daily 单标的，无需分区）
    hs = await _first(session, """
        WITH w AS (
            SELECT trade_date, close,
                   AVG(close) OVER (ORDER BY trade_date
                       ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ma20,
                   AVG(close) OVER (ORDER BY trade_date
                       ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS ma60,
                   COUNT(close) OVER (ORDER BY trade_date
                       ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS n
            FROM index_daily
            WHERE ts_code = '000300.SH' AND trade_date <= :ld AND trade_date >= :start60
        )
        SELECT COUNT(*) FILTER (WHERE n >= 60 AND close >= ma20)::float
                   / NULLIF(COUNT(*) FILTER (WHERE n >= 60), 0) * 100 AS above_ma20,
               COUNT(*) FILTER (WHERE n >= 60 AND close >= ma60)::float
                   / NULLIF(COUNT(*) FILTER (WHERE n >= 60), 0) * 100 AS above_ma60
        FROM w
        WHERE trade_date = :ld
    """, {"ld": ld, "start60": start60})

    # 4. 波动率分位（N5）：沪深300 近 770 交易日 pct_chg → 滚动 20 日年化波动 → 750 分位
    rows4 = await _all(session, """
        SELECT trade_date, pct_chg FROM index_daily
        WHERE ts_code = '000300.SH' AND trade_date <= :ld
        ORDER BY trade_date DESC
        LIMIT 770
    """, {"ld": ld})
    rows4.reverse()
    pcts = [float(r["pct_chg"]) for r in rows4 if r.get("pct_chg") is not None]
    vols = rolling_vol(pcts, 20)
    cur_vol = vols[-1] if vols else None
    vol_pctl = percentile_rank([v for v in vols if v is not None], cur_vol) if vols else None

    result = {
        "data_date": ld.isoformat() if hasattr(ld, "isoformat") else str(ld),
        "new_highs": int(hl["new_highs"]) if hl and hl.get("new_highs") is not None else None,
        "new_lows": int(hl["new_lows"]) if hl and hl.get("new_lows") is not None else None,
        "above_ma20_market": round(mkt_ma20, 1) if mkt_ma20 is not None else None,
        "above_ma60_market": round(mkt_ma60, 1) if mkt_ma60 is not None else None,
        "above_ma20_hs300": round(float(hs["above_ma20"]), 1) if hs and hs.get("above_ma20") is not None else None,
        "above_ma60_hs300": round(float(hs["above_ma60"]), 1) if hs and hs.get("above_ma60") is not None else None,
        "volatility": {
            "value_20d": round(cur_vol, 1) if cur_vol is not None else None,
            "percentile": vol_pctl,
        },
    }
    return result
