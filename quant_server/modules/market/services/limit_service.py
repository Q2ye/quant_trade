# -*- coding: utf-8 -*-
"""涨跌停分析服务"""
import logging
from datetime import date
from typing import Optional, List
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

    params: dict = {"trade_date": trade_date}
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
        batch_params["trade_date"] = trade_date
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


async def _count_consecutive(
    session: AsyncSession, ts_code: str, from_date: str, direction: str,
) -> int:
    """统计连续涨停/跌停天数"""
    op = ">=" if direction == "up" else "<="
    rows = await _all(session, f"""
        SELECT d.trade_date, d.close, dl.up_limit, dl.down_limit
        FROM stock_daily d
        JOIN stock_daily_limit dl ON d.ts_code = dl.ts_code AND d.trade_date = dl.trade_date
        WHERE d.ts_code = :ts AND d.trade_date <= :from_date
        ORDER BY d.trade_date DESC
        LIMIT 20
    """, {"ts": ts_code, "from_date": from_date})

    count = 0
    for r in rows:
        if direction == "up" and r["close"] >= (r["up_limit"] or 0):
            count += 1
        elif direction == "down" and r["close"] <= (r["down_limit"] or 999999):
            count += 1
        else:
            break
    return count
