# -*- coding: utf-8 -*-
"""查 market_state_daily 剩余字段含义：breadth_ratio / volatility_pct / extra jsonb。"""
import asyncio, json
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
            "SELECT MIN(breadth_ratio), MAX(breadth_ratio), MIN(volatility_pct), MAX(volatility_pct) FROM market_state_daily"
        ))
        row = r.fetchone()
        print(f"[breadth_ratio] {row[0]} ~ {row[1]}")
        print(f"[volatility_pct] {row[2]} ~ {row[3]}")
        # 抽样看关键时点
        r = await s.execute(text(
            "SELECT trade_date, breadth_ratio, volatility_pct, extra FROM market_state_daily WHERE trade_date IN ('2015-06-12','2019-01-04','2024-09-30') ORDER BY trade_date"
        ))
        print("\n[关键时点]")
        for x in r.fetchall():
            print(f"  {x[0]} breadth={x[1]} vol={x[2]} extra={x[3]}")
    await pool.close()

asyncio.run(main())
