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
            "SELECT tc.table_name, tc.constraint_name, kcu.column_name, tc.constraint_type "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu ON tc.constraint_name=kcu.constraint_name AND tc.table_name=kcu.table_name "
            "WHERE tc.table_name IN ('stock_moneyflow_hsgt','stock_daily_basic') AND tc.constraint_type IN ('PRIMARY KEY','UNIQUE') ORDER BY tc.table_name"))
        for x in r.fetchall(): print(x)
    await pool.close()
asyncio.run(main())
