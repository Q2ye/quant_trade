# -*- coding: utf-8 -*-
"""大盘状态雷达 + 风格轮动查询服务

- get_market_state: 市场状态（regime/宽度/波动率/动量/趋势）+ 涨跌停家数历史 + 年线门
- get_style_rotation: 三大指数相对强弱 + 行业强度

数据源全部现成，只读查询，不做写入。
"""
import logging
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def get_market_state(session: AsyncSession, days: int = 60) -> Dict[str, Any]:
    """大盘状态雷达数据。

    Args:
        session: 数据库会话
        days: 返回的交易日数量（默认 60）

    Returns:
        {
            "dates": [...], "regime_series": [...],
            "breadth": [...], "volatility": [...],
            "momentum": [...], "trend": [...],
            "limit_dates": [...], "limit_up": [...], "limit_down": [...],
            "latest": {"regime", "year_line_pct", "volatility_pctl",
                       "breadth", "volatility", "momentum", "trend"}
        }
    """
    # 1. market_state_daily 近 N 日
    state_rows = (await session.execute(
        text("""
            SELECT trade_date, regime, trend_strength, momentum_score,
                   breadth_ratio, volume_ratio, volatility_pct
            FROM market_state_daily
            ORDER BY trade_date DESC LIMIT :days
        """),
        {"days": days},
    )).mappings().all()
    state_rows = list(reversed(state_rows))  # 升序

    # 2. 涨跌停家数历史（沿用 market_breadth 口径：pct_chg >= 9.8 涨停 / <= -9.8 跌停）
    limit_rows = (await session.execute(
        text("""
            SELECT trade_date,
                   COUNT(*) FILTER (WHERE pct_chg >= 9.8) AS limit_up,
                   COUNT(*) FILTER (WHERE pct_chg <= -9.8) AS limit_down
            FROM stock_daily
            GROUP BY trade_date
            ORDER BY trade_date DESC LIMIT :days
        """),
        {"days": days},
    )).mappings().all()
    limit_rows = list(reversed(limit_rows))

    # 3. 年线门：中证500 close vs MA250
    close_rows = (await session.execute(
        text("""
            SELECT close FROM index_daily
            WHERE ts_code = '000905.SH'
            ORDER BY trade_date DESC LIMIT 250
        """),
        {},
    )).scalars().all()
    year_line_pct = None
    if len(close_rows) >= 250:
        closes = [float(c) for c in close_rows[:250]]
        ma250 = sum(closes) / len(closes)
        latest_close = closes[0]
        if ma250 > 0:
            year_line_pct = (latest_close - ma250) / ma250 * 100

    # 波动率分位：当前 volatility 在近 N 日序列里的分位（0-1）
    vol_list = [float(r["volatility_pct"] or 0) for r in state_rows]
    volatility_pctl = None
    if vol_list:
        cur = vol_list[-1]
        volatility_pctl = round(sum(1 for v in vol_list if v <= cur) / len(vol_list), 3)

    latest = state_rows[-1] if state_rows else {}
    return {
        "dates": [str(r["trade_date"]) for r in state_rows],
        "regime_series": [r["regime"] for r in state_rows],
        "breadth": [float(r["breadth_ratio"] or 0) for r in state_rows],
        "volatility": vol_list,
        "momentum": [float(r["momentum_score"] or 0) for r in state_rows],
        "trend": [float(r["trend_strength"] or 0) for r in state_rows],
        "limit_dates": [str(r["trade_date"]) for r in limit_rows],
        "limit_up": [int(r["limit_up"] or 0) for r in limit_rows],
        "limit_down": [int(r["limit_down"] or 0) for r in limit_rows],
        "latest": {
            "regime": latest.get("regime"),
            "year_line_pct": round(year_line_pct, 2) if year_line_pct is not None else None,
            "volatility_pctl": volatility_pctl,
            "breadth": float(latest.get("breadth_ratio") or 0) if latest else None,
            "volatility": float(latest.get("volatility_pct") or 0) if latest else None,
            "momentum": float(latest.get("momentum_score") or 0) if latest else None,
            "trend": float(latest.get("trend_strength") or 0) if latest else None,
        },
    }


async def get_style_rotation(session: AsyncSession, days: int = 60) -> Dict[str, Any]:
    """风格轮动：三大指数相对强弱（首日=1 归一化）+ 行业强度 Top。

    Args:
        session: 数据库会话
        days: 指数相对强弱回看的交易日数（默认 60）

    Returns:
        {
            "index_dates": [...],
            "index_series": {"000300.SH": [...], "000905.SH": [...], "000852.SH": [...]},
            "index_names": {"000300.SH": "沪深300", ...},
            "industry_strength": [{"name", "ret_30d"}, ...]
        }
    """
    # 1. 三大指数近 N 日收盘（首日=1 归一化）
    idx_rows = (await session.execute(
        text("""
            SELECT trade_date, ts_code, close FROM index_daily
            WHERE ts_code IN ('000300.SH', '000905.SH', '000852.SH')
            ORDER BY trade_date, ts_code
        """),
        {},
    )).mappings().all()

    index_names = {"000300.SH": "沪深300", "000905.SH": "中证500", "000852.SH": "中证1000"}
    index_series: Dict[str, List[float]] = {}
    index_dates: List[str] = []
    if idx_rows:
        # 取近 N 个交易日
        all_dates = sorted({r["trade_date"] for r in idx_rows})[-days:]
        index_dates = [str(d) for d in all_dates]
        for code in index_names:
            close_map = {r["trade_date"]: float(r["close"]) for r in idx_rows if r["ts_code"] == code}
            vals = [close_map[d] for d in all_dates if d in close_map]
            if vals and vals[0] > 0:
                base = vals[0]
                index_series[code] = [round(v / base, 4) for v in vals]
            else:
                index_series[code] = []

    # 2. 行业强度：近 30 日区间涨跌幅（L1 行业）
    ind_rows = (await session.execute(
        text("""
            SELECT c.industry_name AS name,
                   (MAX(d.close) - MIN(d.close)) / NULLIF(MIN(d.close), 0) * 100 AS ret_30d
            FROM index_sw_daily d
            JOIN index_sw_classify c ON d.ts_code = c.index_code
            WHERE c.level = 'L1'
              AND d.trade_date >= (SELECT MAX(trade_date) - INTERVAL '30 days' FROM index_sw_daily)
            GROUP BY c.industry_name
            ORDER BY ret_30d DESC
        """),
        {},
    )).mappings().all()

    industry_strength = [
        {"name": r["name"], "ret_30d": round(float(r["ret_30d"] or 0), 2)}
        for r in ind_rows if r["name"]
    ]

    return {
        "index_dates": index_dates,
        "index_series": index_series,
        "index_names": index_names,
        "industry_strength": industry_strength,
    }
