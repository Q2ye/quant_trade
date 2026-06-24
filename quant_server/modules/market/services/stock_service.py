# -*- coding: utf-8 -*-
"""StockDetail 全量查询 — 单股多维度数据聚合，使用原始 SQL"""
import logging
import time
from datetime import date, datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_KLINE_LIMIT = 1000


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
    """获取日/周/月 K 线 — 最新 N 条，升序排列

    子查询：DESC 取最新 N 条，外层 ASC 满足 lightweight-charts 要求
    """
    daily = await _all(session, """
        SELECT * FROM (
            SELECT trade_date, open, high, low, close, vol, amount, pct_chg
            FROM stock_daily WHERE ts_code = :ts
            ORDER BY trade_date DESC LIMIT :lim
        ) sub ORDER BY trade_date ASC
    """, {"ts": ts_code, "lim": _KLINE_LIMIT})
    weekly = await _all(session, """
        SELECT * FROM (
            SELECT trade_date, open, high, low, close, vol, amount, pct_chg
            FROM stock_weekly WHERE ts_code = :ts
            ORDER BY trade_date DESC LIMIT :lim
        ) sub ORDER BY trade_date ASC
    """, {"ts": ts_code, "lim": _KLINE_LIMIT})
    monthly = await _all(session, """
        SELECT * FROM (
            SELECT trade_date, open, high, low, close, vol, amount, pct_chg
            FROM stock_monthly WHERE ts_code = :ts
            ORDER BY trade_date DESC LIMIT :lim
        ) sub ORDER BY trade_date ASC
    """, {"ts": ts_code, "lim": _KLINE_LIMIT})
    logger.info(
        f"_fetch_quotes({ts_code}): daily={len(daily)} weekly={len(weekly)} monthly={len(monthly)}"
    )
    return {
        "daily": [_clean(r) for r in daily],
        "weekly": [_clean(r) for r in weekly],
        "monthly": [_clean(r) for r in monthly],
    }


async def _fetch_latest_data(session: AsyncSession, ts_code: str) -> tuple:
    """获取最新行情/估值/涨跌停 — 串行执行，避免 AsyncSession 单连接竞争"""
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
        await session.rollback()  # 重置 aborted 事务，避免后续查询被阻塞
        return []


async def _fetch_top_holders(session: AsyncSession, ts_code: str) -> list:
    try:
        rows = await _all(session, """
            SELECT end_date, holder_name, hold_amount AS hold_num, hold_ratio
            FROM stock_top10_holders WHERE ts_code = :ts
            ORDER BY end_date DESC, hold_ratio DESC LIMIT 20
        """, {"ts": ts_code})
        return [_clean(r) for r in rows]
    except Exception:
        await session.rollback()
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
        await session.rollback()
        return []


async def _fetch_factors(session: AsyncSession, ts_code: str) -> dict:
    """因子数据 — 从 factor_data（EAV 格式）查询并 pivot 为宽表

    factor_data 表结构: (ts_code, trade_date, factor_code, factor_value)
    输出: {"stk_factor": [{trade_date, ATR, BETA, OM, ...}, ...], "stk_factor_pro": []}
    """
    result: Dict[str, list] = {"stk_factor": [], "stk_factor_pro": []}
    try:
        # 1. 取最近 120 个有因子数据的交易日
        dates = await _all(session, """
            SELECT DISTINCT trade_date FROM factor_data
            WHERE ts_code = :ts
            ORDER BY trade_date DESC LIMIT 120
        """, {"ts": ts_code})
        if not dates:
            return result

        date_list = [d["trade_date"] for d in dates]

        # 2. 查询这些日期的所有因子值
        rows = await _all(session, """
            SELECT trade_date, factor_code, factor_value
            FROM factor_data WHERE ts_code = :ts AND trade_date = ANY(:dates)
            ORDER BY trade_date ASC
        """, {"ts": ts_code, "dates": date_list})

        # 3. Pivot: EAV → 宽表 (每行一个 trade_date，因子代码为列)
        pivot: Dict[str, dict] = {}
        for r in rows:
            td = r["trade_date"]
            if td not in pivot:
                pivot[td] = {"trade_date": td}
            pivot[td][r["factor_code"]] = r["factor_value"]

        result["stk_factor"] = [_clean(pivot[d]) for d in sorted(pivot.keys())]
    except Exception:
        await session.rollback()
    return result


async def _fetch_pledge(session: AsyncSession, ts_code: str) -> Optional[dict]:
    try:
        return _clean(await _first(session, """
            SELECT * FROM stock_pledge_stat WHERE ts_code = :ts
            ORDER BY end_date DESC LIMIT 1
        """, {"ts": ts_code}))
    except Exception:
        await session.rollback()
        return None


async def _fetch_st_risk(session: AsyncSession, ts_code: str) -> Optional[dict]:
    try:
        return _clean(await _first(session, """
            SELECT * FROM stock_st_risk WHERE ts_code = :ts LIMIT 1
        """, {"ts": ts_code}))
    except Exception:
        await session.rollback()
        return None


async def get_stock_full(session: AsyncSession, ts_code: str) -> Optional[dict]:
    t0 = time.perf_counter()

    # 串行执行所有查询 — AsyncSession 禁止并发操作（会触发 InvalidRequestError）
    basic = await _fetch_basic(session, ts_code)
    if not basic:
        logger.warning(f"Stock basic not found: {ts_code}")
        return None

    mf = await _fetch_moneyflow(session, ts_code)
    indicators = await _fetch_indicators(session, ts_code)
    holders = await _fetch_top_holders(session, ts_code)
    holdernum = await _fetch_holdernumber(session, ts_code)
    factors = await _fetch_factors(session, ts_code)
    pledge = await _fetch_pledge(session, ts_code)
    st_risk = await _fetch_st_risk(session, ts_code)

    klines = await _fetch_quotes(session, ts_code)
    latest_quote_raw, latest_basic, limit_price = await _fetch_latest_data(session, ts_code)

    latest_quote = klines["daily"][-1] if klines.get("daily") else latest_quote_raw

    result = {
        "basic": basic,
        "latest_quote": latest_quote,
        "latest_basic": latest_basic,
        "limit_price": limit_price,
        "quotes": klines,
        "moneyflow": mf,
        "financial": {"indicators": indicators},
        "shareholders": {
            "top10": holders,
            "holdernumber": holdernum,
        },
        "factors": factors,
        "risk": {
            "pledge_stat": pledge,
            "st_risk": st_risk,
        },
    }

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info(f"get_stock_full({ts_code}) 完成 ({elapsed_ms:.0f}ms)")
    return result


# 按日期范围的 K 线表名映射
_KLINE_TABLES = {
    "daily": "stock_daily",
    "weekly": "stock_weekly",
    "monthly": "stock_monthly",
}


async def get_stock_kline_range(
    session: AsyncSession,
    ts_code: str,
    period: str = "daily",
    before_date: Optional[str] = None,
    limit: int = 500,
) -> list:
    """获取指定日期之前的 K 线数据（用于动态加载更早的历史数据）

    Args:
        period: daily / weekly / monthly
        before_date: 不传则取最新数据；传入则取该日期之前的数据（不含当日）
        limit: 返回条数上限
    """
    table = _KLINE_TABLES.get(period, "stock_daily")
    cols = "trade_date, open, high, low, close, vol, amount, pct_chg"

    if before_date:
        # asyncpg 要求 date 列参数必须是 date 对象，不能是字符串
        bd = date.fromisoformat(before_date) if isinstance(before_date, str) else before_date
        rows = await _all(session, f"""
            SELECT * FROM (
                SELECT {cols} FROM {table}
                WHERE ts_code = :ts AND trade_date < :bd
                ORDER BY trade_date DESC LIMIT :lim
            ) sub ORDER BY trade_date ASC
        """, {"ts": ts_code, "bd": bd, "lim": max(1, min(limit, 2000))})
    else:
        rows = await _all(session, f"""
            SELECT * FROM (
                SELECT {cols} FROM {table}
                WHERE ts_code = :ts
                ORDER BY trade_date DESC LIMIT :lim
            ) sub ORDER BY trade_date ASC
        """, {"ts": ts_code, "lim": max(1, min(limit, 2000))})

    return [_clean(r) for r in rows]


async def get_stock_signals(session: AsyncSession, ts_code: str, recent: int = 20) -> list:
    """获取个股最近 N 条策略信号（用于K线图叠加买卖点标记）"""
    try:
        rows = await _all(session, """
            SELECT signal_time, signal_type, price, volume, strategy_name, message
            FROM signals
            WHERE ts_code = :ts
            ORDER BY signal_time DESC
            LIMIT :lim
        """, {"ts": ts_code, "lim": max(1, min(recent, 100))})
        return [_clean(r) for r in rows]
    except Exception:
        return []


async def get_stock_factor_scores(session: AsyncSession, ts_code: str) -> Optional[dict]:
    """获取个股最新因子数据及近250日分位值"""
    try:
        latest = await _first(session, """
            SELECT ts_code, trade_date, factor_code, factor_value FROM factor_data
            WHERE ts_code = :ts
            ORDER BY trade_date DESC LIMIT 1
        """, {"ts": ts_code})
        if not latest:
            return None
        meta_keys = {"id", "ts_code", "trade_date", "created_at", "updated_at", "factor_code"}
        numeric_cols = [(k, float(v)) for k, v in latest.items()
                        if k not in meta_keys and v is not None and isinstance(v, (int, float))]
        if not numeric_cols:
            return None
        # 批量拉取近 365 日因子数据，使用显式列名
        fact_cols = ", ".join([f'"{c[0]}"' for c in numeric_cols])
        hist_rows = await _all(session, f"""
            SELECT ts_code, trade_date, {fact_cols} FROM factor_data WHERE ts_code = :ts
            AND trade_date >= (SELECT MAX(trade_date) FROM factor_data WHERE ts_code = :ts) - INTERVAL '365 days'
            ORDER BY trade_date ASC
        """, {"ts": ts_code})
        factors = {}
        for col_name, current_val in numeric_cols:
            hist_vals = [float(r[col_name]) for r in hist_rows
                         if col_name in r and r[col_name] is not None]
            if not hist_vals:
                factors[col_name] = {"value": current_val, "percentile": None}
                continue
            hist_vals.sort()
            rank = sum(1 for v in hist_vals if v <= current_val)
            percentile = round(rank / len(hist_vals) * 100, 1)
            factors[col_name] = {"value": current_val, "percentile": percentile}
        return {
            "ts_code": ts_code,
            "trade_date": latest.get("trade_date"),
            "factors": factors,
        } if factors else None
    except Exception:
        return None
