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
        r = await s.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='stock_daily' ORDER BY ordinal_position"
        ))
        print(f"[stock_daily 列] {[x[0] for x in r.fetchall()]}")
        r = await s.execute(text(
            "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM stock_daily WHERE trade_date >= '2006-01-01'"
        ))
        print(f"[stock_daily 2006后 行数/范围] {r.fetchone()}")
    await pool.close()

asyncio.run(main())
