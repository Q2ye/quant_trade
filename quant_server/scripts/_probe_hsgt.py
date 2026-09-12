# -*- coding: utf-8 -*-
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
        # stock_hsgt 结构
        r = await s.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='stock_hsgt' ORDER BY ordinal_position"
        ))
        print(f"[stock_hsgt 列] {[x[0] for x in r.fetchall()]}")
        r = await s.execute(text("SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM stock_hsgt"))
        print(f"  行数/范围: {r.fetchone()}")
        # H50001 是什么
        r = await s.execute(text(
            "SELECT DISTINCT ts_code, name FROM index_daily WHERE ts_code LIKE 'H5000%' LIMIT 5"
        ))
        # index_daily 没有 name 列，用 index_basic
        r = await s.execute(text(
            "SELECT ts_code, name FROM index_basic WHERE ts_code LIKE 'H%' OR ts_code LIKE '%国债%' LIMIT 20"
        ))
        print(f"\n[index_basic H/国债] {[(x[0],x[1]) for x in r.fetchall()]}")
    await pool.close()

asyncio.run(main())
