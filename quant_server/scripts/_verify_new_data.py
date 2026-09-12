import asyncio
from sqlalchemy import text
async def main():
    from shared.database.session.connection_pool import get_connection_pool
    pool = get_connection_pool()
    try: sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize(); sf = pool.get_session_factory()
    async with sf() as s:
        r = await s.execute(text("SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM stock_moneyflow_hsgt"))
        print(f"[北向 stock_moneyflow_hsgt] {r.fetchone()}")
        r = await s.execute(text("SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM margin"))
        print(f"[两融 margin] {r.fetchone()}")
        r = await s.execute(text("SELECT trade_date, north_money FROM stock_moneyflow_hsgt ORDER BY trade_date LIMIT 3"))
        print(f"[北向样本] {r.fetchall()}")
        r = await s.execute(text("SELECT trade_date, exchange_id, rzye FROM margin ORDER BY trade_date LIMIT 3"))
        print(f"[两融样本] {r.fetchall()}")
    await pool.close()
asyncio.run(main())
