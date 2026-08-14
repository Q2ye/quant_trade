# -*- coding: utf-8 -*-
"""
补齐 ETF 底部策略 — 估值因子 + 市场状态因子
===========================================
将此前缺失的 valuation 和 market_regime 子集因子写入 factor_data。

估值因子来源: index_dailybasic (6大指数 PE/PB) + etf_shares + etf_basic
市场状态来源: market_state_daily (已填充5166天) → 映射到每只ETF
执行: cd quant_server && .venv/Scripts/python.exe scripts/backfill_valuation_factors.py
"""
import asyncio, logging, math, uuid
from datetime import date, datetime
from typing import Dict, Optional

import asyncpg
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB = {"host":"localhost","port":5432,"user":"postgres","password":"123456","database":"quant_signals_dev"}

# ── ETF → 跟踪指数 映射 ──
ETF_IDX = {
    "510050.SH":"000016.SH","510300.SH":"000300.SH","159919.SZ":"000300.SH",
    "510310.SH":"000300.SH","510500.SH":"000905.SH","512100.SH":"000852.SH",
    "159915.SZ":"399006.SZ","159949.SZ":"399006.SZ","159781.SZ":"000688.SH",
    "510880.SH":"000015.SH","512880.SH":"399975.SZ","512660.SH":"399967.SZ",
    "512800.SH":"399986.SZ","512170.SH":"399989.SZ","159806.SZ":"399976.SZ",
    "512690.SH":"000932.SH","512400.SH":"000819.SH",
    # 以下无 index_dailybasic 覆盖, 跳过估值因子
    "513100.SH":None,"513050.SH":None,"518880.SH":None,"511010.SH":None,"511260.SH":None,
    "159825.SZ":None,"159865.SZ":None,"159766.SZ":None,"159840.SZ":None,"516510.SH":None,
}

ETF_POOL = list(ETF_IDX.keys())


async def load_index_dailybasic(conn):
    """加载所有指数的每日 PE/PB/total_mv"""
    rows = await conn.fetch("""
        SELECT ts_code, trade_date, pe_ttm, pb, total_mv, turnover_rate
        FROM index_dailybasic ORDER BY ts_code, trade_date
    """)
    data = {}
    for r in rows:
        key = r["ts_code"]
        if key not in data: data[key] = []
        data[key].append({
            "trade_date": r["trade_date"],
            "pe_ttm": float(r["pe_ttm"]) if r["pe_ttm"] else None,
            "pb": float(r["pb"]) if r["pb"] else None,
            "total_mv": float(r["total_mv"]) if r["total_mv"] else None,
            "turnover_rate": float(r["turnover_rate"]) if r["turnover_rate"] else None,
        })
    logger.info("加载 %d 个指数估值数据", len(data))
    return data


def calc_percentile(values, window):
    """滚动分位计算"""
    result = [None]*len(values)
    for i in range(window-1, len(values)):
        window_vals = [v for v in values[i-window+1:i+1] if v is not None]
        if len(window_vals) < window//2: continue
        cur = values[i]
        if cur is None: continue
        result[i] = sum(1 for v in window_vals if v <= cur) / len(window_vals)
    return result


async def backfill_valuation(conn):
    """估值因子: PE/PB分位、ERP、市值等"""
    logger.info("="*56)
    logger.info("回填估值因子")

    idx_data = await load_index_dailybasic(conn)
    etf_static = {}
    rows = await conn.fetch("SELECT ts_code, m_fee, list_date FROM etf_basic")
    for r in rows:
        etf_static[r["ts_code"]] = {
            "m_fee": float(r["m_fee"]) if r["m_fee"] else None,
            "list_date": r["list_date"],
        }

    total = 0
    for etf_code, idx_code in ETF_IDX.items():
        if idx_code is None or idx_code not in idx_data:
            continue
        idx_rows = idx_data[idx_code]
        dates = [r["trade_date"] for r in idx_rows]
        pe_vals = [r["pe_ttm"] for r in idx_rows]
        pb_vals = [r["pb"] for r in idx_rows]
        mv_vals = [r["total_mv"] for r in idx_rows]
        tr_vals = [r["turnover_rate"] for r in idx_rows]

        pe_p5 = calc_percentile(pe_vals, 1260)
        pb_p5 = calc_percentile(pb_vals, 1260)
        pe_p1 = calc_percentile(pe_vals, 252)
        pb_p1 = calc_percentile(pb_vals, 252)

        records = []
        for i, td in enumerate(dates):
            out = {}
            if pe_vals[i] is not None: out["pe_ttm"] = pe_vals[i]
            if pb_vals[i] is not None: out["pb"] = pb_vals[i]
            if pe_p5[i] is not None: out["pe_percentile_5y"] = round(pe_p5[i],6)
            if pb_p5[i] is not None: out["pb_percentile_5y"] = round(pb_p5[i],6)
            if pe_p1[i] is not None: out["pe_percentile_1y"] = round(pe_p1[i],6)
            if pb_p1[i] is not None: out["pb_percentile_1y"] = round(pb_p1[i],6)
            if mv_vals[i] is not None: out["total_mv_log"] = round(math.log(mv_vals[i]+1),6)
            if tr_vals[i] is not None: out["turnover_rate_idx"] = tr_vals[i]
            # ERP = 1/PE - 无风险利率(简化为2.5%)
            if pe_vals[i] is not None and pe_vals[i] > 0:
                out["erp"] = round(1.0/pe_vals[i] - 0.025, 6)

            if out:
                # PE/PB区域编码
                if pe_p5[i] is not None:
                    for boundary in [0.1,0.3,0.5,0.7,0.9]:
                        if pe_p5[i] <= boundary: out["pe_region"] = round(boundary,1); break
                if pb_p5[i] is not None:
                    for boundary in [0.1,0.3,0.5,0.7,0.9]:
                        if pb_p5[i] <= boundary: out["pb_region"] = round(boundary,1); break

            for fcode, fval in out.items():
                records.append((str(uuid.uuid4()), fcode, etf_code, td, fval))

        if records:
            # Batch insert
            for start in range(0, len(records), 500):
                batch = records[start:start+500]
                await conn.executemany("""
                    INSERT INTO factor_data (id, factor_code, ts_code, trade_date, factor_value)
                    VALUES ($1,$2,$3,$4,$5)
                    ON CONFLICT (ts_code, factor_code, trade_date) DO UPDATE SET factor_value=EXCLUDED.factor_value
                """, batch)
            total += len(records)
            logger.info("  %s ← %s: %d 条估值记录", etf_code, idx_code, len(records))

    # ETF 静态因子 (m_fee, fund_age_days)
    logger.info("写入 ETF 静态因子...")
    static_records = []
    etf_daily_dates = await conn.fetch("SELECT ts_code, MIN(trade_date) as d FROM etf_daily GROUP BY ts_code")
    date_map = {r["ts_code"]: r["d"] for r in etf_daily_dates}
    for etf_code in ETF_POOL:
        s = etf_static.get(etf_code, {})
        if s.get("m_fee") is not None:
            td = date_map.get(etf_code, date(2020,1,1))
            static_records.append((str(uuid.uuid4()), "m_fee", etf_code, td, s["m_fee"]))
        if s.get("list_date"):
            td = date_map.get(etf_code, date(2020,1,1))
            age = (td - s["list_date"].date()).days if hasattr(s["list_date"],'date') else 0
            static_records.append((str(uuid.uuid4()), "fund_age_days", etf_code, td, float(age)))
    for start in range(0, len(static_records), 500):
        batch = static_records[start:start+500]
        await conn.executemany("""
            INSERT INTO factor_data (id, factor_code, ts_code, trade_date, factor_value)
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT (ts_code, factor_code, trade_date) DO UPDATE SET factor_value=EXCLUDED.factor_value
        """, batch)
    total += len(static_records)

    logger.info("估值因子回填完成: %d 条", total)
    return total


async def backfill_market_regime(conn):
    """市场状态因子: 从 market_state_daily 映射到每只ETF"""
    logger.info("="*56)
    logger.info("回填市场状态因子")

    rows = await conn.fetch("""
        SELECT trade_date, regime, trend_strength, momentum_score,
               breadth_ratio, volume_ratio, volatility_pct
        FROM market_state_daily WHERE classified_by='v1.0_ma_regime'
        ORDER BY trade_date
    """)
    logger.info("market_state_daily: %d 天", len(rows))

    regime_map = {"BULL":2.0,"NEUTRAL":1.0,"BEAR":0.0}
    factor_map = {
        "market_regime": lambda r: regime_map.get(r["regime"],1.0),
        "trend_strength": lambda r: float(r["trend_strength"]) if r["trend_strength"] else None,
        "momentum_score": lambda r: float(r["momentum_score"]) if r["momentum_score"] else None,
        "breadth_ratio": lambda r: float(r["breadth_ratio"]) if r["breadth_ratio"] else None,
        "volatility_pct": lambda r: float(r["volatility_pct"]) if r["volatility_pct"] else None,
    }

    total = 0
    for etf_code in ETF_POOL:
        records = []
        for r in rows:
            td = r["trade_date"]
            for fcode, fn in factor_map.items():
                val = fn(r)
                if val is not None:
                    records.append((str(uuid.uuid4()), fcode, etf_code, td, val))
        for start in range(0, len(records), 500):
            batch = records[start:start+500]
            await conn.executemany("""
                INSERT INTO factor_data (id, factor_code, ts_code, trade_date, factor_value)
                VALUES ($1,$2,$3,$4,$5)
                ON CONFLICT (ts_code, factor_code, trade_date) DO UPDATE SET factor_value=EXCLUDED.factor_value
            """, batch)
        total += len(records)
    logger.info("市场状态因子回填完成: %d 条 (27ETF × %d天 × 5因子)", total, len(rows))
    return total


async def main():
    conn = await asyncpg.connect(**DB)
    try:
        n1 = await backfill_valuation(conn)
        n2 = await backfill_market_regime(conn)

        # 验证
        cnt = await conn.fetchval("SELECT COUNT(*) FROM factor_data")
        fcs = await conn.fetch("""
            SELECT factor_code, COUNT(DISTINCT ts_code) etfs, COUNT(*) n
            FROM factor_data GROUP BY factor_code
            ORDER BY factor_code
        """)
        logger.info("="*56)
        logger.info("factor_data 总记录: %d", cnt)
        logger.info("新增因子覆盖:")
        for r in fcs:
            logger.info("  %-30s %3d ETFs %8d rows", r["factor_code"], r["etfs"], r["n"])
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
