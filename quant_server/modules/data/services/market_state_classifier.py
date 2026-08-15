# -*- coding: utf-8 -*-
"""
市场状态分类器 (v1.0)
=====================
对每个交易日进行分类：BULL / NEUTRAL / BEAR，并计算辅助指标。
结果写入 ``market_state_daily`` 表。

分类规则（基于沪深300 + 中证500）:
  BULL   ← close > MA20 > MA60 AND MA20_slope > 0
  BEAR   ← close < MA20 < MA60 AND MA20_slope < 0
  NEUTRAL ← 其他

辅助指标:
  trend_strength = |MA20斜率| / 20日波动率
  momentum_score  = 20日涨跌幅（标准化至 [0, 1]）
  breadth_ratio   = 全市场上涨家数 / 总家数
  volume_ratio    = 当日成交额 / 20日均成交额
  volatility_pct  = std(returns, 20) × √252

使用方式:
  python -m quant_server.modules.data.services.market_state_classifier

依赖: asyncpg (数据库直连)
"""

import asyncio
import logging
import math
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any

import asyncpg
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": "localhost", "port": 5432,
    "user": "postgres", "password": "123456",
    "database": "quant_signals_dev",
}


def _get_db_config() -> dict:
    """优先从应用配置读取 DB 连接，失败时回退硬编码默认值。

    应用流水线（每日同步）调用时使用真实环境配置，独立手动运行不受影响。
    """
    try:
        from shared.config.config_manager import config
        db = config.settings.DATABASE
        return {
            "host": db.HOST, "port": int(db.PORT),
            "user": db.USER, "password": db.PASSWORD,
            "database": db.NAME,
        }
    except Exception:
        return dict(DB_CONFIG)

# 基准指数 for regime classification
BENCHMARK_INDICES = ["000300.SH", "000905.SH"]  # 沪深300 + 中证500
CLASSIFIED_BY = "v1.0_ma_regime"


async def _load_index_daily(conn: asyncpg.Connection, index_code: str) -> List[Dict]:
    """加载指数日线数据，按 trade_date 排序"""
    rows = await conn.fetch(
        "SELECT trade_date, close FROM index_daily "
        "WHERE ts_code = $1 ORDER BY trade_date",
        index_code,
    )
    return [{"trade_date": r["trade_date"], "close": float(r["close"])} for r in rows]


async def _load_breadth(conn: asyncpg.Connection) -> Dict[date, float]:
    """从 stock_daily 计算每日上涨家数占比"""
    rows = await conn.fetch("""
        SELECT trade_date,
               COUNT(*) FILTER (WHERE pct_chg > 0)::float / NULLIF(COUNT(*), 0) AS ratio
        FROM stock_daily
        WHERE trade_date >= '2019-01-01'
        GROUP BY trade_date
        ORDER BY trade_date
    """)
    return {r["trade_date"]: float(r["ratio"]) for r in rows}


def _calc_ma(closes: List[float], window: int) -> List[float]:
    """计算滚动移动平均线"""
    result = [math.nan] * len(closes)
    for i in range(window - 1, len(closes)):
        result[i] = sum(closes[i - window + 1 : i + 1]) / window
    return result


def _calc_slope(values: List[float], window: int = 5) -> List[float]:
    """计算滚动斜率（线性回归）"""
    result = [math.nan] * len(values)
    x = list(range(window))
    denom = sum((xi - (window - 1) / 2) ** 2 for xi in x)
    if denom == 0:
        return result
    for i in range(window - 1, len(values)):
        y = values[i - window + 1 : i + 1]
        if any(math.isnan(v) for v in y):
            continue
        x_mean = (window - 1) / 2
        y_mean = sum(y) / window
        num = sum((x[j] - x_mean) * (y[j] - y_mean) for j in range(window))
        result[i] = num / denom
    return result


def _calc_volatility(closes: List[float], window: int = 20) -> List[float]:
    """计算滚动波动率"""
    result = [math.nan] * len(closes)
    for i in range(window, len(closes)):
        rets = [
            (closes[j] / closes[j - 1] - 1)
            for j in range(i - window + 1, i + 1)
        ]
        result[i] = float(np.std(rets) * math.sqrt(252))
    return result


def _calc_momentum(closes: List[float], window: int = 20) -> List[float]:
    """计算滚动动量"""
    result = [math.nan] * len(closes)
    for i in range(window, len(closes)):
        result[i] = closes[i] / closes[i - window] - 1
    return result


def _calc_volume_ratio(volumes: List[float], window: int = 20) -> List[float]:
    """计算量比"""
    result = [math.nan] * len(volumes)
    for i in range(window, len(volumes)):
        ma = sum(volumes[i - window : i]) / window
        result[i] = volumes[i] / ma if ma > 0 else 1.0
    return result


async def classify_and_populate():
    """主入口：分类市场状态并写入 market_state_daily"""
    conn = await asyncpg.connect(**_get_db_config())
    try:
        # 1. 加载基准指数数据
        logger.info("加载指数日线...")
        idx_data = {}
        for ic in BENCHMARK_INDICES:
            data = await _load_index_daily(conn, ic)
            idx_data[ic] = data
            logger.info("  %s: %d 条记录", ic, len(data))

        # 2. 加载市场宽度
        logger.info("计算市场宽度...")
        breadth_map = await _load_breadth(conn)
        logger.info("  breadth: %d 个交易日", len(breadth_map))

        # 3. 对沪深300计算技术指标
        hs300 = idx_data["000300.SH"]
        dates = [d["trade_date"] for d in hs300]
        closes = [d["close"] for d in hs300]
        n = len(closes)

        ma20 = _calc_ma(closes, 20)
        ma60 = _calc_ma(closes, 60)
        slope20 = _calc_slope(ma20, 5)
        vol = _calc_volatility(closes, 20)
        mom = _calc_momentum(closes, 20)

        # 4. 加载成交量用于 volume_ratio
        vol_rows = await conn.fetch(
            "SELECT trade_date, amount FROM index_daily "
            "WHERE ts_code = '000300.SH' ORDER BY trade_date"
        )
        amounts = [float(r["amount"] or 0) for r in vol_rows]
        vr = _calc_volume_ratio(amounts, 20)

        # 5. 逐日分类并写入
        records = []
        for i in range(60, n):  # 需要至少60天 MA60
            trade_date = dates[i]
            c = closes[i]
            m20 = ma20[i]
            m60 = ma60[i]
            sl = slope20[i]

            if math.isnan(m20) or math.isnan(m60) or math.isnan(sl):
                continue

            # Regime 判定
            if c > m20 > m60 and sl > 0:
                regime = "BULL"
            elif c < m20 < m60 and sl < 0:
                regime = "BEAR"
            else:
                regime = "NEUTRAL"

            # 辅助指标
            trend_strength = abs(sl) / (vol[i] + 1e-8) if not math.isnan(vol[i]) else None
            momentum_score = mom[i] if not math.isnan(mom[i]) else None
            breadth = breadth_map.get(trade_date)
            volume_ratio_val = vr[i] if i < len(vr) and not math.isnan(vr[i]) else None
            volatility_val = vol[i] if not math.isnan(vol[i]) else None

            # 归一化趋势强度到 [0, 1]
            if trend_strength is not None:
                trend_strength = min(1.0, max(0.0, trend_strength * 100))

            records.append((
                trade_date, regime,
                round(trend_strength, 4) if trend_strength is not None else None,
                round(momentum_score, 4) if momentum_score is not None else None,
                round(breadth, 4) if breadth is not None else None,
                round(volume_ratio_val, 4) if volume_ratio_val is not None else None,
                round(volatility_val, 4) if volatility_val is not None else None,
                CLASSIFIED_BY,
                '{}',
            ))

        # 6. 批量写入
        logger.info("写入 %d 条 market_state_daily 记录...", len(records))

        # 分批写入(每批500条)
        batch_size = 500
        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            await conn.executemany("""
                INSERT INTO market_state_daily
                    (trade_date, regime, trend_strength, momentum_score,
                     breadth_ratio, volume_ratio, volatility_pct, classified_by, extra)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
                ON CONFLICT (trade_date, classified_by) DO UPDATE SET
                    regime = EXCLUDED.regime,
                    trend_strength = EXCLUDED.trend_strength,
                    momentum_score = EXCLUDED.momentum_score,
                    breadth_ratio = EXCLUDED.breadth_ratio,
                    volume_ratio = EXCLUDED.volume_ratio,
                    volatility_pct = EXCLUDED.volatility_pct
            """, batch)

        # 7. 验证
        cnt = await conn.fetchval("SELECT COUNT(*) FROM market_state_daily")
        dist = await conn.fetchrow(
            "SELECT regime, COUNT(*) n FROM market_state_daily GROUP BY regime ORDER BY n DESC"
        )
        logger.info("✅ market_state_daily 写入完成: %d 条", cnt)

        return len(records)

    finally:
        await conn.close()


async def main():
    logger.info("市场状态分类器 — 开始")
    n = await classify_and_populate()

    # 打印分布
    conn = await asyncpg.connect(**_get_db_config())
    try:
        rows = await conn.fetch(
            "SELECT regime, COUNT(*) n, "
            "ROUND(AVG(trend_strength)::numeric, 4) avg_ts, "
            "ROUND(AVG(breadth_ratio)::numeric, 4) avg_br "
            "FROM market_state_daily GROUP BY regime ORDER BY n DESC"
        )
        logger.info("Regime 分布:")
        for r in rows:
            logger.info("  %s: %d 天 (trend=%.3f, breadth=%.3f)",
                        r["regime"], r["n"], r["avg_ts"] or 0, r["avg_br"] or 0)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
