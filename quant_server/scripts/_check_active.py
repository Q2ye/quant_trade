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
            "SELECT pid, state, wait_event_type, left(query,80), now()-query_start as dur "
            "FROM pg_stat_activity WHERE state='active' AND query NOT LIKE '%pg_stat_activity%' ORDER BY query_start"
        ))
        for x in r.fetchall():
            print(f"pid={x[0]} state={x[1]} wait={x[2]} dur={x[4]} query={x[3]}")
    await pool.close()
asyncio.run(main())
