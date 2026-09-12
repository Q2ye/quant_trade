# -*- coding: utf-8 -*-
"""查板块级数据：申万行业指数 + 行业ETF。"""
import asyncio
from sqlalchemy import text

async def main():
    from shared.database.session.connection_pool import get_connection_pool
    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize(); sf = pool.get_session_factory()
    async with sf() as s:
        # 申万行业指数
        r = await s.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_name LIKE '%sw%' OR table_name LIKE '%index%' ORDER BY table_name"
        ))
        print("[指数相关表]", [x[0] for x in r.fetchall()])
        try:
            r = await s.execute(text(
                "SELECT ts_code, name, COUNT(*), MIN(trade_date), MAX(trade_date) FROM index_sw_daily GROUP BY ts_code, name ORDER BY ts_code LIMIT 40"
            ))
            print("\n[index_sw_daily 申万行业指数]")
            for x in r.fetchall():
                print(f"  {x[0]} {x[1]}: {x[2]}行 {x[3]}~{x[4]}")
        except Exception as e:
            print(f"\n[index_sw_daily 查询失败] {e}")
        # 行业ETF
        r = await s.execute(text(
            "SELECT DISTINCT ts_code FROM etf_daily WHERE ts_code LIKE '515%' OR ts_code LIKE '512%' OR ts_code LIKE '516%' OR ts_code LIKE '159%' ORDER BY ts_code LIMIT 60"
        ))
        print("\n[etf_daily 行业/主题ETF]", [x[0] for x in r.fetchall()])
    await pool.close()

asyncio.run(main())
