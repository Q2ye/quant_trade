# -*- coding: utf-8 -*-
"""只读：确认当前连接的库名 / 环境（写入验证前必须确认）。"""
import asyncio
from sqlalchemy import text
async def main():
    from shared.database.session.connection_pool import get_connection_pool
    p = get_connection_pool()
    try:
        sf = p.get_session_factory()
    except RuntimeError:
        await p.initialize(); sf = p.get_session_factory()
    async with sf() as s:
        r = (await s.execute(text(
            "SELECT current_database() AS db, current_user AS usr, "
            "       inet_server_addr()::text AS host, inet_server_port() AS port"
        ))).mappings().one()
        print("DB=%s USER=%s HOST=%s PORT=%s" % (r["db"], r["usr"], r["host"], r["port"]))
if __name__ == "__main__":
    asyncio.run(main())
