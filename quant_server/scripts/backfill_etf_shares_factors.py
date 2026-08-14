# -*- coding: utf-8 -*-
"""
回填 ETF 份额/规模因子: share_change_5d, share_change_20d, fund_size_change_20d
从 etf_shares 表计算 → 写入 factor_data

执行: cd quant_server && .venv/Scripts/python.exe scripts/backfill_etf_shares_factors.py
"""
import asyncio, logging, uuid
from datetime import date

import asyncpg
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB = {"host": "localhost", "port": 5432, "user": "postgres", "password": "123456", "database": "quant_signals_dev"}

ETF_POOL = [
    "510050.SH", "510300.SH", "510500.SH", "159919.SZ", "510880.SH",
    "512880.SH", "512660.SH", "512690.SH", "512800.SH", "512100.SH",
    "159915.SZ", "159949.SZ", "518880.SH", "513100.SH", "513050.SH",
    "511010.SH", "511260.SH", "510310.SH", "159865.SZ", "159825.SZ",
    "159766.SZ", "159781.SZ", "512170.SH", "159806.SZ", "516510.SH",
    "159840.SZ", "512400.SH",
]

FACTOR_NAMES = ["share_change_5d", "share_change_20d", "fund_size_change_20d"]


async def main():
    conn = await asyncpg.connect(**DB)
    try:
        # 加载 etf_shares
        etf_list = "','".join(ETF_POOL)
        rows = await conn.fetch(f"""
            SELECT ts_code, trade_date, fund_vol, fund_size
            FROM etf_shares
            WHERE ts_code = ANY(ARRAY['{etf_list}']::varchar[])
              AND trade_date >= '2019-01-01'
            ORDER BY ts_code, trade_date
        """)
        logger.info("加载 etf_shares: %d rows", len(rows))

        # 组织数据 per ETF
        data = {}
        for r in rows:
            etf = r["ts_code"]
            if etf not in data:
                data[etf] = {"dates": [], "fund_vol": [], "fund_size": []}
            td = r["trade_date"]
            if hasattr(td, 'date'):
                td = td.date()
            data[etf]["dates"].append(td)
            data[etf]["fund_vol"].append(float(r["fund_vol"]) if r["fund_vol"] else None)
            data[etf]["fund_size"].append(float(r["fund_size"]) if r["fund_size"] else None)

        total = 0
        for etf, d in data.items():
            dates = d["dates"]
            fv = np.array(d["fund_vol"], dtype=np.float64)
            fs = np.array(d["fund_size"], dtype=np.float64)
            n = len(dates)

            # share_change_5d
            sc5 = np.full(n, np.nan)
            for i in range(5, n):
                if fv[i - 5] and fv[i - 5] > 0:
                    sc5[i] = (fv[i] - fv[i - 5]) / fv[i - 5]

            # share_change_20d
            sc20 = np.full(n, np.nan)
            for i in range(20, n):
                if fv[i - 20] and fv[i - 20] > 0:
                    sc20[i] = (fv[i] - fv[i - 20]) / fv[i - 20]

            # fund_size_change_20d
            fsc20 = np.full(n, np.nan)
            for i in range(20, n):
                if fs[i - 20] and fs[i - 20] > 0:
                    fsc20[i] = (fs[i] - fs[i - 20]) / fs[i - 20]

            maps = {
                "share_change_5d": sc5,
                "share_change_20d": sc20,
                "fund_size_change_20d": fsc20,
            }

            records = []
            for fcode, values in maps.items():
                for i in range(n):
                    if np.isnan(values[i]):
                        continue
                    records.append((
                        str(uuid.uuid4()), fcode, etf, dates[i], float(values[i]),
                    ))

            # 批量写入
            for start in range(0, len(records), 500):
                batch = records[start:start + 500]
                await conn.executemany("""
                    INSERT INTO factor_data (id, factor_code, ts_code, trade_date, factor_value)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (ts_code, factor_code, trade_date) DO UPDATE
                    SET factor_value = EXCLUDED.factor_value
                """, batch)
            total += len(records)
            if len(records) > 0:
                logger.info("  %s: %d records", etf, len(records))

        logger.info("=" * 50)
        logger.info("etf_shares 因子回填完成: %d 条", total)
        for fc in FACTOR_NAMES:
            n = await conn.fetchval(
                "SELECT COUNT(*) FROM factor_data WHERE factor_code = $1", fc)
            logger.info("  %-25s %8d", fc, n)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
