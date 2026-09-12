import asyncio
from sqlalchemy import text
async def main():
    from shared.database.session.connection_pool import get_connection_pool
    pool = get_connection_pool()
    try: sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize(); sf = pool.get_session_factory()
    async with sf() as s:
        r = await s.execute(text("SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM stock_daily_basic"))
        print(f"[stock_daily_basic 全范围] {r.fetchone()}")
        r = await s.execute(text("SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM stock_daily_basic WHERE pe_ttm > 0"))
        print(f"[stock_daily_basic pe_ttm>0 范围] {r.fetchone()}")
        r = await s.execute(text("SELECT COUNT(DISTINCT trade_date) FROM stock_daily_basic WHERE trade_date>='2006-01-01' AND pe_ttm>0"))
        print(f"[pe_ttm>0 2006后交易日数] {r.fetchone()}")
        r = await s.execute(text("SELECT COUNT(DISTINCT trade_date) FROM index_daily WHERE ts_code='000852.SH' AND trade_date>='2006-01-01'"))
        print(f"[中证1000 2006后交易日数] {r.fetchone()}")
    await pool.close()
asyncio.run(main())
