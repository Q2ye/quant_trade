import asyncio
from sqlalchemy import text
async def main():
    from shared.database.session.connection_pool import get_connection_pool
    pool = get_connection_pool()
    try: sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize(); sf = pool.get_session_factory()
    async with sf() as s:
        r = await s.execute(text(
            "SELECT column_name, data_type, column_default, is_nullable FROM information_schema.columns WHERE table_name='stock_moneyflow_hsgt' AND column_name='id'"))
        print(r.fetchall())
    await pool.close()
asyncio.run(main())
