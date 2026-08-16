# -*- coding: utf-8 -*-
"""市场温度计聚合服务 (N1)

四维分位合成单一温度（0~100℃）：
- 估值温度：沪深300 + 中证500 的 PE/PB 历史分位均值（样本 1000 交易日）
- 情绪温度：涨停家数分位 ×0.5 + 全市场换手率分位 ×0.5（样本 250 交易日；
  方案 B 起读 market_state_daily.limit_up_count / avg_turnover 预计算列，过渡期走原重查询）
- 资金温度：北向 20 日滚动净流入当前值分位（样本上限 750 交易日）
- 技术温度：全市场站上 MA20 比例当前值分位（样本 250 交易日；方案 A 起读
  market_state_daily.above_ma20_pct 预计算列，过渡期走 MA20 重查询 + 退路链并标记 technical_approx=True）

口径决策（2026-08 Market v5）：
- 分位 = 当前值 ≤ 历史样本的比例 ×100
- 任一维分位缺失 → sample_warning=True，温度由可用维度等权合成
- 缓存：SWR（stale-while-revalidate）300s —— 过期返回旧值并后台重算，
  轮询不再被 4~8s 的重算阻塞（P2 优化）
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.market.services._swr_cache import SwrCache

logger = logging.getLogger(__name__)

# ---- 口径常量 ----
VALUATION_CODES: Tuple[str, ...] = ("000300.SH", "000905.SH")
VALUATION_SAMPLE = 1000   # 估值分位样本（交易日）
EMOTION_SAMPLE = 250      # 情绪分位样本（交易日）
CAPITAL_SAMPLE = 750      # 资金分位样本（交易日）
CAPITAL_WINDOW = 20       # 北向滚动净流入窗口（交易日）
TECHNICAL_SAMPLE = 150    # 技术分位样本（交易日）：150 日 ≈ 230 日历天，窗口扫描耗时减半（P2）
TECHNICAL_TIMEOUT = 8.0   # MA20 重查询超时（秒）；SWR 下只约束后台重算，放宽减少降级触发（10.13）
EMOTION_MIN_SAMPLES = 20  # 情绪维预计算列最小样本数（10.15）：stock_daily_limit 数据覆盖有限（dev 32 天），
                          # 门槛设 20 保证列路径可用且分位非垃圾值；低于则走原重查询兜底
_swr = SwrCache(ttl=300.0)


# ==================== 纯函数（可单测） ====================

def percentile_rank(series: List[Optional[float]], current: Optional[float]) -> Optional[float]:
    """当前值在历史序列中的百分位（0~100）；空序列/当前值缺失返回 None"""
    clean = [float(v) for v in series if v is not None]
    if not clean or current is None:
        return None
    cur = float(current)
    le = sum(1 for v in clean if v <= cur)
    return round(le / len(clean) * 100, 1)


def rolling_sum(series: List[float], window: int) -> List[Optional[float]]:
    """滚动 window 日和（升序序列）；前 window-1 位为 None"""
    out: List[Optional[float]] = []
    for i in range(len(series)):
        if i < window - 1:
            out.append(None)
        else:
            out.append(sum(series[i - window + 1: i + 1]))
    return out


def classify_zone(temperature: float) -> str:
    """温度带：<30 低温 / 30-70 中性 / >70 高温（仓位卡 4 带见前端规则表）"""
    if temperature < 30:
        return "低温"
    if temperature <= 70:
        return "中性"
    return "高温"


def synthesize_temperature(
    valuation: Dict[str, Any],
    emotion: Dict[str, Any],
    capital: Dict[str, Any],
    technical: Dict[str, Any],
) -> Dict[str, Any]:
    """四维等权合成单一温度；任一维分位缺失 → sample_warning=True"""
    dims = [valuation, emotion, capital, technical]
    available = [float(d["percentile"]) for d in dims if d.get("percentile") is not None]
    sample_warning = len(available) < len(dims)
    if available:
        temperature = round(sum(available) / len(available), 1)
    else:
        temperature = None
    zone = classify_zone(temperature) if temperature is not None else None
    return {"temperature": temperature, "zone": zone, "sample_warning": sample_warning}


# ==================== SQL 查询 ====================

async def _all(session: AsyncSession, sql: str, params: dict) -> list:
    r = await session.execute(text(sql), params)
    return [dict(row._mapping) for row in r.fetchall()]


async def _first(session: AsyncSession, sql: str, params: dict) -> Optional[dict]:
    r = await session.execute(text(sql), params)
    row = r.fetchone()
    return dict(row._mapping) if row else None


def _dim(value, percentile, approx: bool = False) -> Dict[str, Any]:
    return {"value": value, "percentile": percentile, "approx": approx}


async def _query_valuation_dim(session: AsyncSession) -> Dict[str, Any]:
    """估值：沪深300 + 中证500 的 PE/PB 分位均值；value = 沪深300 最新 PE"""
    rows = await _all(session, """
        SELECT ts_code, pe, pb FROM (
            SELECT ts_code, pe, pb, trade_date,
                   ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) AS rn
            FROM index_dailybasic
            WHERE ts_code = ANY(:codes)
        ) t
        WHERE rn <= :n
        ORDER BY ts_code, trade_date
    """, {"codes": list(VALUATION_CODES), "n": VALUATION_SAMPLE})
    pe_by_code: Dict[str, List[float]] = {}
    pb_by_code: Dict[str, List[float]] = {}
    for r in rows:
        if r.get("pe") is not None:
            pe_by_code.setdefault(r["ts_code"], []).append(float(r["pe"]))
        if r.get("pb") is not None:
            pb_by_code.setdefault(r["ts_code"], []).append(float(r["pb"]))
    pctls: List[float] = []
    for code in VALUATION_CODES:
        for series in (pe_by_code.get(code, []), pb_by_code.get(code, [])):
            if series:
                p = percentile_rank(series, series[-1])
                if p is not None:
                    pctls.append(p)
    hs300_pe = pe_by_code.get(VALUATION_CODES[0], [])
    value = round(hs300_pe[-1], 2) if hs300_pe else None
    pctl = round(sum(pctls) / len(pctls), 1) if pctls else None
    return _dim(value, pctl)


async def _query_emotion_dim(session: AsyncSession) -> Dict[str, Any]:
    """情绪：涨停家数分位 ×0.5 + 全市场换手率分位 ×0.5；value = 最新涨停家数

    方案 B（10.15）：优先读 market_state_daily.limit_up_count / avg_turnover 预计算列（<100ms）；
    两序列**独立读取**（与旧口径一致：涨停家数受 stock_daily_limit 覆盖限制 ~32 天，
    换手率 250 天）；任一系列样本不足/列缺失（未 DDL/未回填的过渡期）→ 原两条重查询兜底。
    """
    try:
        limit_rows = await _all(session, """
            SELECT trade_date, limit_up_count FROM market_state_daily
            WHERE limit_up_count IS NOT NULL
            ORDER BY trade_date DESC
            LIMIT :n
        """, {"n": EMOTION_SAMPLE})
        limit_rows.reverse()
        limit_counts = [int(r["limit_up_count"]) for r in limit_rows if r.get("limit_up_count") is not None]
        turnover_rows = await _all(session, """
            SELECT trade_date, avg_turnover FROM market_state_daily
            WHERE avg_turnover IS NOT NULL
            ORDER BY trade_date DESC
            LIMIT :n
        """, {"n": EMOTION_SAMPLE})
        turnover_rows.reverse()
        turnovers = [float(r["avg_turnover"]) for r in turnover_rows if r.get("avg_turnover") is not None]
        if len(limit_counts) >= EMOTION_MIN_SAMPLES and len(turnovers) >= EMOTION_MIN_SAMPLES:
            limit_pctl = percentile_rank(limit_counts, limit_counts[-1])
            turn_pctl = percentile_rank(turnovers, turnovers[-1])
            parts = [p for p in (limit_pctl, turn_pctl) if p is not None]
            pctl = round(sum(parts) / len(parts), 1) if parts else None
            return _dim(limit_counts[-1], pctl, approx=False)
        logger.warning(
            "温度计情绪维预计算列样本不足(limit=%d/turnover=%d，门槛%d)，走重查询兜底",
            len(limit_counts), len(turnovers), EMOTION_MIN_SAMPLES,
        )
    except Exception as e:
        logger.warning("温度计情绪维预计算列读取失败（可能未执行 DDL）: %s，走重查询兜底", e)

    # —— 过渡期兜底：原两条重查询 ——
    limit_rows = await _all(session, """
        SELECT l.trade_date,
               COUNT(*) FILTER (WHERE sd.close >= l.up_limit) AS limit_up
        FROM stock_daily_limit l
        JOIN stock_daily sd ON sd.ts_code = l.ts_code AND sd.trade_date = l.trade_date
        WHERE l.trade_date >= (SELECT MAX(trade_date) FROM stock_daily_limit) - INTERVAL '380 days'
        GROUP BY l.trade_date
        ORDER BY l.trade_date DESC
        LIMIT :n
    """, {"n": EMOTION_SAMPLE})
    limit_rows.reverse()
    limit_counts = [int(r["limit_up"] or 0) for r in limit_rows]
    turnover_rows = await _all(session, """
        SELECT trade_date, AVG(turnover_rate) AS avg_turnover
        FROM stock_daily_basic
        WHERE trade_date >= (SELECT MAX(trade_date) FROM stock_daily_basic) - INTERVAL '380 days'
        GROUP BY trade_date
        ORDER BY trade_date DESC
        LIMIT :n
    """, {"n": EMOTION_SAMPLE})
    turnover_rows.reverse()
    turnovers = [float(r["avg_turnover"]) for r in turnover_rows if r.get("avg_turnover") is not None]
    limit_pctl = percentile_rank(limit_counts, limit_counts[-1]) if limit_counts else None
    turn_pctl = percentile_rank(turnovers, turnovers[-1]) if turnovers else None
    parts = [p for p in (limit_pctl, turn_pctl) if p is not None]
    pctl = round(sum(parts) / len(parts), 1) if parts else None
    value = limit_counts[-1] if limit_counts else None
    return _dim(value, pctl)


async def _query_capital_dim(session: AsyncSession) -> Dict[str, Any]:
    """资金：北向 20 日滚动净流入当前值分位；value = 当前 20 日滚动净流入"""
    rows = await _all(session, """
        SELECT trade_date, north_money FROM stock_moneyflow_hsgt
        ORDER BY trade_date DESC
        LIMIT :n
    """, {"n": CAPITAL_SAMPLE + CAPITAL_WINDOW})
    rows.reverse()
    flows = [float(r["north_money"]) for r in rows if r.get("north_money") is not None]
    rolls = [v for v in rolling_sum(flows, CAPITAL_WINDOW) if v is not None]
    current = rolls[-1] if rolls else None
    return _dim(
        round(current, 2) if current is not None else None,
        percentile_rank(rolls, current),
    )


async def _query_ma20_ratio_series(session: AsyncSession) -> List[float]:
    """全市场站上 MA20 比例日序列（0~100，样本 150 交易日）"""
    rows = await _all(session, """
        WITH w AS (
            SELECT trade_date, close,
                   AVG(close) OVER (PARTITION BY ts_code ORDER BY trade_date
                       ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ma20,
                   COUNT(close) OVER (PARTITION BY ts_code ORDER BY trade_date
                       ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS n
            FROM stock_daily
            WHERE trade_date >= (SELECT MAX(trade_date) FROM stock_daily) - INTERVAL '230 days'
        )
        SELECT trade_date,
               COUNT(*) FILTER (WHERE n >= 20 AND close >= ma20)::float
               / NULLIF(COUNT(*) FILTER (WHERE n >= 20), 0) * 100 AS above_ratio
        FROM w
        GROUP BY trade_date
        ORDER BY trade_date DESC
        LIMIT :n
    """, {"n": TECHNICAL_SAMPLE})
    rows.reverse()
    return [float(r["above_ratio"]) for r in rows if r.get("above_ratio") is not None]


async def _query_breadth_fallback(session: AsyncSession) -> List[float]:
    """退路1：market_state_daily.breadth_ratio（上涨家数比，近似口径）"""
    rows = await _all(session, """
        SELECT trade_date, breadth_ratio FROM market_state_daily
        ORDER BY trade_date DESC LIMIT :n
    """, {"n": TECHNICAL_SAMPLE})
    rows.reverse()
    vals = [float(r["breadth_ratio"]) for r in rows if r.get("breadth_ratio") is not None]
    if vals and max(vals) <= 1.5:  # 0~1 比例 → 转百分数，与 above_ratio 同尺度
        vals = [round(v * 100, 2) for v in vals]
    return vals


async def _query_turnover_fallback(session: AsyncSession) -> List[float]:
    """退路2：全市场涨跌家数比（上涨家数/总数×100）——stock_daily 必有数据，保证技术维永不缺失"""
    rows = await _all(session, """
        SELECT trade_date,
               COUNT(*) FILTER (WHERE pct_chg > 0)::float / NULLIF(COUNT(*), 0) * 100 AS up_ratio
        FROM stock_daily
        WHERE trade_date >= (SELECT MAX(trade_date) FROM stock_daily) - INTERVAL '230 days'
        GROUP BY trade_date
        ORDER BY trade_date
    """, {})
    return [float(r["up_ratio"]) for r in rows if r.get("up_ratio") is not None]


async def _fallback_ratios() -> List[float]:
    """退路查询：被取消/异常的查询已使当前会话事务失效 → 必须另起会话执行。
    退路1（market_state_daily 上涨比）失败时继续退路2（全市场涨跌家数比），
    两级都失败才返回空（此时技术维缺失并打日志）——保证技术维仅在 stock_daily 无数据时缺失（10.13）。"""
    from shared.database.session.session_manager import get_session_manager
    sm = get_session_manager()
    try:
        async with sm.get_session() as s2:
            vals = await _query_breadth_fallback(s2)
            if vals:
                return vals
    except Exception as e:
        logger.warning("温度计技术维退路1(market_state_daily)失败: %s", e)
    try:
        async with sm.get_session() as s3:
            return await _query_turnover_fallback(s3)
    except Exception as e:
        logger.warning("温度计技术维退路2(涨跌家数比)失败: %s", e)
        return []


async def _query_technical_dim(session: AsyncSession) -> Dict[str, Any]:
    """技术：全市场站上 MA20 比例当前值分位

    方案 A（10.14）：优先读 market_state_daily.above_ma20_pct 预计算列（<100ms）；
    列缺失/样本不足（未 DDL/未回填的过渡期）→ 原 MA20 重查询 + 退路链兜底。
    """
    try:
        rows = await _all(session, """
            SELECT trade_date, above_ma20_pct FROM market_state_daily
            WHERE above_ma20_pct IS NOT NULL
            ORDER BY trade_date DESC
            LIMIT :n
        """, {"n": TECHNICAL_SAMPLE})
        rows.reverse()
        ratios = [
            float(r["above_ma20_pct"])
            for r in rows if r.get("above_ma20_pct") is not None
        ]
        if len(ratios) >= 60:
            current = ratios[-1]
            return _dim(
                round(current, 2),
                percentile_rank(ratios, current),
                approx=False,
            )
        logger.warning("温度计技术维预计算列样本不足(%d<60)，走退路链", len(ratios))
    except Exception as e:
        logger.warning("温度计技术维预计算列读取失败（可能未执行 DDL）: %s，走退路链", e)

    # —— 过渡期兜底：原 MA20 重查询 + 退路链 ——
    try:
        ratios = await asyncio.wait_for(
            _query_ma20_ratio_series(session), timeout=TECHNICAL_TIMEOUT)
        approx = False
    except asyncio.TimeoutError:
        logger.warning("温度计技术维 MA20 比例查询超时(>%.1fs)，退化 breadth_ratio 近似", TECHNICAL_TIMEOUT)
        # 10.13b：被取消的查询使会话处于 invalid transaction → 先显式回滚修复，
        # 避免外层会话退出抛异常吞掉退路结果
        try:
            await session.rollback()
        except Exception as rb:
            logger.warning("温度计技术维会话回滚失败: %s", rb)
        ratios = await _fallback_ratios()
        approx = True
    except Exception as e:
        logger.warning("温度计技术维 MA20 比例查询异常: %s，退化 breadth_ratio 近似", e)
        try:
            await session.rollback()
        except Exception as rb:
            logger.warning("温度计技术维会话回滚失败: %s", rb)
        ratios = await _fallback_ratios()
        approx = True
    current = ratios[-1] if ratios else None
    return _dim(
        round(current, 2) if current is not None else None,
        percentile_rank(ratios, current),
        approx,
    )


# ==================== 主入口（SWR：过期返回旧值 + 后台重算） ====================

async def _compute(session: AsyncSession) -> Dict[str, Any]:
    """四维并行聚合 → 单温度（不含缓存逻辑）"""
    from shared.database.session.session_manager import get_session_manager
    sm = get_session_manager()

    async def _with_session(name: str, coro_fn):
        # 10.13b：取消/异常后的会话退出可能抛 "invalid transaction"——
        # 若结果已算出则保留结果（只记警告），避免被退出异常吞掉
        _missing = object()
        result = _missing
        try:
            async with sm.get_session() as s:
                t0 = time.perf_counter()
                result = await coro_fn(s)
                logger.info("temperature.%s 完成 (%.0fms)", name, (time.perf_counter() - t0) * 1000)
        except Exception as e:
            if result is _missing:
                logger.warning("temperature.%s 失败: %s", name, e)
                return None
            logger.warning("temperature.%s 会话退出异常（结果已计算，保留）: %s", name, e)
        return result

    t0 = time.perf_counter()
    data_date_row = await _first(session, "SELECT MAX(trade_date) AS d FROM stock_daily", {})
    valuation, emotion, capital, technical = await asyncio.gather(
        _with_session("valuation", _query_valuation_dim),
        _with_session("emotion", _query_emotion_dim),
        _with_session("capital", _query_capital_dim),
        _with_session("technical", _query_technical_dim),
    )
    valuation = valuation or _dim(None, None)
    emotion = emotion or _dim(None, None)
    capital = capital or _dim(None, None)
    technical = technical or _dim(None, None)

    core = synthesize_temperature(valuation, emotion, capital, technical)
    data_date = data_date_row.get("d") if data_date_row else None
    if data_date is not None:
        data_date = data_date.isoformat() if hasattr(data_date, "isoformat") else str(data_date)

    result = {
        "temperature": core["temperature"],
        "zone": core["zone"],
        "sample_warning": core["sample_warning"],
        "data_date": data_date,
        "updated_at": datetime.now().isoformat(),
        "dimensions": {
            "valuation": valuation,
            "emotion": emotion,
            "capital": capital,
            "technical": technical,
        },
    }
    if core["sample_warning"]:
        missing = [k for k, d in result["dimensions"].items() if d["percentile"] is None]
        logger.warning("temperature 样本不足，缺失维度: %s", missing)
    logger.info(
        "temperature 完成 → %.1f℃ (%s) 总耗时 %.0fms",
        core["temperature"] if core["temperature"] is not None else -1,
        core["zone"] or "-",
        (time.perf_counter() - t0) * 1000,
    )
    return result


async def _recompute_in_background() -> None:
    """缓存过期时的后台重算任务（独立会话，失败不影响旧值返回）"""
    from shared.database.session.session_manager import get_session_manager
    sm = get_session_manager()
    try:
        async with sm.get_session() as s:
            result = await _compute(s)
        # 样本不足 → 短 TTL 120s 快速自愈；完整结果 → 默认 300s
        _swr.set("temperature", result, ttl=120.0 if result.get("sample_warning") else None)
        logger.info("temperature 后台重算完成")
    except Exception as e:
        logger.warning("temperature 后台重算失败: %s", e)


async def get_market_temperature(session: AsyncSession) -> Dict[str, Any]:
    """市场温度计：四维并行聚合 → 单温度（0~100℃）。SWR 缓存 300s（样本不足 120s）。"""
    stale, need_recompute = _swr.probe("temperature")
    if stale is not None:
        if need_recompute:
            _swr.set_task("temperature", asyncio.create_task(_recompute_in_background()))
        return stale
    result = await _compute(session)
    _swr.set("temperature", result, ttl=120.0 if result.get("sample_warning") else None)
    return result
