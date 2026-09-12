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
        # moneyflow_hsgt 范围
        r = await s.execute(text(
            "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM stock_moneyflow_hsgt"
        ))
        print(f"[stock_moneyflow_hsgt 行数/范围] {r.fetchone()}")
        # index_basic 里 H 开头/国债
        r = await s.execute(text(
            "SELECT ts_code, name FROM index_basic WHERE ts_code LIKE 'H%' OR name LIKE '%国债%' OR name LIKE '%债%' LIMIT 30"
        ))
        print(f"\n[index_basic H/债] {[(x[0],x[1]) for x in r.fetchall()]}")
        # index_daily 里 H50001 是什么指数（查 index_basic 匹配）
        r = await s.execute(text(
            "SELECT ts_code, name FROM index_basic WHERE ts_code IN ('H50001.SH','H50010.SH') OR ts_code LIKE '000012%' LIMIT 10"
        ))
        print(f"\n[H50001/000012 匹配] {[(x[0],x[1]) for x in r.fetchall()]}")
    await pool.close()

asyncio.run(main())
