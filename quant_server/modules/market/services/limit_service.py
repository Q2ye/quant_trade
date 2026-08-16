# -*- coding: utf-8 -*-
"""涨跌停分析服务"""
import asyncio
import logging
import time
from datetime import date, timedelta
from typing import Optional, List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.market.services._swr_cache import SwrCache

logger = logging.getLogger(__name__)


async def _all(session: AsyncSession, sql: str, params: dict) -> list:
    r = await session.execute(text(sql), params)
    return [dict(row._mapping) for row in r.fetchall()]


async def _first(session: AsyncSession, sql: str, params: dict) -> Optional[dict]:
    r = await session.execute(text(sql), params)
    row = r.fetchone()
    return dict(row._mapping) if row else None


def _clean(row: dict) -> dict:
    for k, v in list(row.items()):
        if isinstance(v, (date,)):
            row[k] = v.isoformat() if v else None
        elif isinstance(v, float) and v != v:
            row[k] = None
    return row


async def get_limit_stocks(
    session: AsyncSession,
    trade_date: Optional[str] = None,
    exchange: Optional[str] = None,
    board: Optional[str] = None,
) -> dict:
    """获取当日涨跌停股票列表及统计

    返回:
        {
            "trade_date": "2026-06-13",
            "stats": {"limit_up": 32, "limit_down": 8, "up_down_ratio": 4.0},
            "up_stocks": [...],
            "down_stocks": [...],
        }
    """
    # 默认最新交易日
    if not trade_date:
        latest = await _first(session, """
            SELECT MAX(trade_date) AS d FROM stock_daily
        """, {})
        trade_date = latest["d"].isoformat()[:10] if latest and latest["d"] else None
    if not trade_date:
        return {"trade_date": None, "stats": {}, "up_stocks": [], "down_stocks": []}

    # asyncpg 对 date 参数严格类型化：SQL 参数必须传 date 对象（字符串会 DataError，
    # 2026-08 Market v5 批修复，get_limit_ladder 同根因）
    td = date.fromisoformat(trade_date)

    params: dict = {"trade_date": td}
    exch_filter = ""
    if exchange:
        exch_filter = " AND b.exchange = :exchange"
        params["exchange"] = exchange
    board_filter = ""
    if board:
        board_filter = " AND b.market = :board"
        params["board"] = board

    rows = await _all(session, f"""
        SELECT d.ts_code, b.name, b.industry, b.exchange, b.market,
               d.close, d.pct_chg, d.vol, d.amount,
               dl.up_limit, dl.down_limit, dl.pre_close,
               CASE WHEN d.close >= dl.up_limit THEN 1 ELSE 0 END AS is_limit_up,
               CASE WHEN d.close <= dl.down_limit THEN 1 ELSE 0 END AS is_limit_down
        FROM stock_daily d
        JOIN stock_basic b ON d.ts_code = b.ts_code
        LEFT JOIN stock_daily_limit dl ON d.ts_code = dl.ts_code AND d.trade_date = dl.trade_date
        WHERE d.trade_date = :trade_date
          AND (d.close >= dl.up_limit OR d.close <= dl.down_limit)
          {exch_filter} {board_filter}
        ORDER BY d.pct_chg DESC
    """, params)

    up_stocks = []
    down_stocks = []
    for r in rows:
        item = _clean(r)
        if item.get("is_limit_up"):
            up_stocks.append(item)
        if item.get("is_limit_down"):
            down_stocks.append(item)

    # 计算连续天数（批量窗口函数替代逐只查询）
    all_codes = [s["ts_code"] for s in up_stocks + down_stocks]
    if all_codes:
        code_list = ",".join(f":c{i}" for i in range(len(all_codes)))
        batch_params = {f"c{i}": c for i, c in enumerate(all_codes)}
        batch_params["trade_date"] = td
        consec_rows = await _all(session, f"""
            WITH daily AS (
                SELECT d.ts_code, d.trade_date, d.close, dl.up_limit, dl.down_limit
                FROM stock_daily d
                JOIN stock_daily_limit dl ON d.ts_code = dl.ts_code AND d.trade_date = dl.trade_date
                WHERE d.ts_code IN ({code_list}) AND d.trade_date <= :trade_date
            ),
            labeled AS (
                SELECT *,
                    CASE WHEN close >= up_limit THEN 1 ELSE 0 END AS is_up,
                    CASE WHEN close <= down_limit THEN 1 ELSE 0 END AS is_down,
                    SUM(CASE WHEN close < up_limit THEN 1 ELSE 0 END)
                        OVER (PARTITION BY ts_code ORDER BY trade_date DESC) AS up_grp,
                    SUM(CASE WHEN close > down_limit THEN 1 ELSE 0 END)
                        OVER (PARTITION BY ts_code ORDER BY trade_date DESC) AS down_grp
                FROM daily
            )
            SELECT ts_code,
                   COUNT(*) FILTER (WHERE is_up = 1 AND up_grp = 0) AS consecutive_up,
                   COUNT(*) FILTER (WHERE is_down = 1 AND down_grp = 0) AS consecutive_down
            FROM labeled
            GROUP BY ts_code
        """, batch_params)
        consec_map = {r["ts_code"]: r for r in consec_rows}
        for s in up_stocks + down_stocks:
            entry = consec_map.get(s["ts_code"], {})
            s["consecutive_days"] = entry.get(
                "consecutive_up" if s.get("is_limit_up") else "consecutive_down", 0
            )

    return {
        "trade_date": trade_date,
        "stats": {
            "limit_up": len(up_stocks),
            "limit_down": len(down_stocks),
            "up_down_ratio": round(len(up_stocks) / max(len(down_stocks), 1), 1),
            "consecutive_max": max(
                [s.get("consecutive_days", 0) for s in up_stocks + down_stocks] + [0],
            ),
        },
        "up_stocks": up_stocks,
        "down_stocks": down_stocks,
    }


# ==================== N3 涨停梯队（2026-08 Market v5 概览页） ====================

# SWR：过期返回旧值 + 后台重算（P2）；按交易日分键，日频数据当天基本不变
_ladder_swr = SwrCache(ttl=300.0)


def build_ladder(consecutive_days_list: list) -> dict:
    """连板高度分布：首板 / 2连板 / 3连板 / ≥4板"""
    ladder = {"board1": 0, "board2": 0, "board3": 0, "board4plus": 0}
    for d in consecutive_days_list:
        d = int(d or 0)
        if d <= 1:
            ladder["board1"] += 1
        elif d == 2:
            ladder["board2"] += 1
        elif d == 3:
            ladder["board3"] += 1
        else:
            ladder["board4plus"] += 1
    return ladder


def calc_bust_rate(touched: int, sealed: int) -> Optional[float]:
    """炸板率 = (曾触涨停 - 收涨停) / 曾触涨停 ×100；分母 0 → None"""
    if not touched:
        return None
    return round((touched - sealed) / touched * 100, 1)


def classify_emotion_phase(
    board1: int,
    bust_rate: Optional[float],
    max_height: int,
    limit_up_count: int,
    prev_limit_up_count: Optional[int],
):
    """情绪周期（规则表，可引为因子）。返回 (phase, phase_desc)

    判定优先级：冰点 → 退潮 → 高潮 → 发酵 → 修复 → 兜底
    """
    if bust_rate is None:
        if board1 < 20:
            return "冰点", "无炸板样本，涨停梯队清淡，宜等待"
        return "修复", "无炸板样本，封板质量尚可，情绪修复初期"
    if board1 < 20 and bust_rate > 40:
        return "冰点", "涨停家数稀少且炸板率高，赚钱效应缺失，宜等待"
    if prev_limit_up_count is not None and bust_rate > 35 and limit_up_count < prev_limit_up_count:
        return "退潮", "炸板率抬升且涨停家数环比收缩，情绪由盛转衰，警惕高位股"
    if board1 > 80 or max_height >= 5:
        return "高潮", "涨停家数激增或高度打开，情绪亢奋，注意分歧风险"
    if board1 >= 40 or max_height >= 3:
        return "发酵", "涨停梯队扩张，情绪升温，主线初步成形"
    if board1 >= 20:
        return "修复", "涨停家数温和回升，情绪修复初期"
    return "冰点", "涨停清淡但封板稳定，观望为主"


async def get_limit_ladder(session: AsyncSession, trade_date: Optional[str] = None) -> dict:
    """涨停梯队：连板高度分布 + 炸板率 + 封板资金（成交额近似）+ 情绪周期

    返回:
        {
            "data_date": "2026-08-15",
            "ladder": {"board1": n, "board2": n, "board3": n, "board4plus": n},
            "max_height": 4,
            "bust_rate": 25.0 | None,
            "touched_count": 80,          # 曾触涨停家数
            "limit_up_count": 60,         # 收涨停家数
            "prev_limit_up_count": 55 | None,
            "seal_amount": 1234567.8,     # 涨停股当日成交额合计（偏差⑤a：近似口径）
            "seal_amount_approx": True,
            "emotion_phase": "发酵",
            "phase_desc": "...",
        }
    """
    if not trade_date:
        latest = await _first(session, """
            SELECT MAX(trade_date) AS d FROM stock_daily
        """, {})
        trade_date = latest["d"].isoformat()[:10] if latest and latest["d"] else None
    if not trade_date:
        return {
            "data_date": None, "ladder": build_ladder([]), "max_height": 0,
            "bust_rate": None, "touched_count": 0, "limit_up_count": 0,
            "prev_limit_up_count": None, "seal_amount": None, "seal_amount_approx": True,
            "emotion_phase": "冰点", "phase_desc": "无行情数据",
        }

    # SWR：过期返回旧值 + 后台重算（首次请求同步计算）
    cache_key = f"ladder:{trade_date}"
    stale, need_recompute = _ladder_swr.probe(cache_key)
    if stale is not None:
        if need_recompute:
            _ladder_swr.set_task(cache_key, asyncio.create_task(_recompute_limit_ladder(trade_date)))
        return stale

    result = await _compute_limit_ladder(session, trade_date)
    _ladder_swr.set(cache_key, result)
    return result


async def _recompute_limit_ladder(trade_date: str) -> None:
    from shared.database.session.session_manager import get_session_manager
    sm = get_session_manager()
    try:
        async with sm.get_session() as s:
            result = await _compute_limit_ladder(s, trade_date)
        _ladder_swr.set(f"ladder:{trade_date}", result)
        logger.info("limit-ladder 后台重算完成: %s", trade_date)
    except Exception as e:
        logger.warning("limit-ladder 后台重算失败: %s", e)


async def _compute_limit_ladder(session: AsyncSession, trade_date: str) -> dict:
    """涨停梯队计算主体（不含缓存逻辑）"""
    # asyncpg 对 date 参数严格类型化：SQL 参数必须传 date 对象（字符串会 DataError）
    td = date.fromisoformat(trade_date)

    # 1. 当日曾触涨停集合（high >= up_limit；收涨停 = close >= up_limit）
    rows = await _all(session, """
        SELECT d.ts_code, d.close, d.high, d.amount,
               CASE WHEN d.close >= dl.up_limit THEN 1 ELSE 0 END AS is_sealed
        FROM stock_daily d
        JOIN stock_daily_limit dl ON dl.ts_code = d.ts_code AND dl.trade_date = d.trade_date
        WHERE d.trade_date = :trade_date AND d.high >= dl.up_limit
    """, {"trade_date": td})

    touched = len(rows)
    sealed_codes = [r["ts_code"] for r in rows if r.get("is_sealed")]
    bust_rate = calc_bust_rate(touched, len(sealed_codes))
    seal_amount = round(sum(float(r["amount"] or 0) for r in rows if r.get("is_sealed")), 2)

    # 2. 连板高度（gap-island 批量窗口，与 get_limit_stocks 同模式）
    consec_list: List[int] = []
    if sealed_codes:
        code_list = ",".join(f":c{i}" for i in range(len(sealed_codes)))
        batch_params = {f"c{i}": c for i, c in enumerate(sealed_codes)}
        batch_params["trade_date"] = td
        consec_rows = await _all(session, f"""
            WITH daily AS (
                SELECT d.ts_code, d.trade_date, d.close, dl.up_limit, dl.down_limit
                FROM stock_daily d
                JOIN stock_daily_limit dl ON d.ts_code = dl.ts_code AND d.trade_date = dl.trade_date
                WHERE d.ts_code IN ({code_list}) AND d.trade_date <= :trade_date
            ),
            labeled AS (
                SELECT *,
                    CASE WHEN close >= up_limit THEN 1 ELSE 0 END AS is_up,
                    CASE WHEN close <= down_limit THEN 1 ELSE 0 END AS is_down,
                    SUM(CASE WHEN close < up_limit THEN 1 ELSE 0 END)
                        OVER (PARTITION BY ts_code ORDER BY trade_date DESC) AS up_grp,
                    SUM(CASE WHEN close > down_limit THEN 1 ELSE 0 END)
                        OVER (PARTITION BY ts_code ORDER BY trade_date DESC) AS down_grp
                FROM daily
            )
            SELECT ts_code,
                   COUNT(*) FILTER (WHERE is_up = 1 AND up_grp = 0) AS consecutive_up,
                   COUNT(*) FILTER (WHERE is_down = 1 AND down_grp = 0) AS consecutive_down
            FROM labeled
            GROUP BY ts_code
        """, batch_params)
        consec_map = {r["ts_code"]: r for r in consec_rows}
        consec_list = [int(consec_map.get(c, {}).get("consecutive_up", 0)) for c in sealed_codes]

    ladder = build_ladder(consec_list)
    max_height = max(consec_list) if consec_list else 0

    # 3. 前一日涨停家数（情绪周期环比，30 天有界窗口）
    start = td - timedelta(days=30)
    prev_rows = await _all(session, """
        SELECT l.trade_date,
               COUNT(*) FILTER (WHERE sd.close >= l.up_limit) AS limit_up
        FROM stock_daily_limit l
        JOIN stock_daily sd ON sd.ts_code = l.ts_code AND sd.trade_date = l.trade_date
        WHERE l.trade_date <= :trade_date AND l.trade_date >= :start
        GROUP BY l.trade_date
        ORDER BY l.trade_date DESC
        LIMIT 2
    """, {"trade_date": td, "start": start})

    limit_up_count = len(sealed_codes)
    prev_limit_up_count = None
    if len(prev_rows) >= 2:
        prev_limit_up_count = int(prev_rows[1]["limit_up"] or 0)
    phase, phase_desc = classify_emotion_phase(
        ladder["board1"], bust_rate, max_height, limit_up_count, prev_limit_up_count)

    result = {
        "data_date": trade_date,
        "ladder": ladder,
        "max_height": max_height,
        "bust_rate": bust_rate,
        "touched_count": touched,
        "limit_up_count": limit_up_count,
        "prev_limit_up_count": prev_limit_up_count,
        "seal_amount": seal_amount,
        "seal_amount_approx": True,
        "emotion_phase": phase,
        "phase_desc": phase_desc,
    }
    return result
