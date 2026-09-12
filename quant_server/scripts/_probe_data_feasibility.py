# -*- coding: utf-8 -*-
"""数据可行性探针：查牛市信号验证所需的数据源。"""
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
        # 1. market_state_daily 表是否存在
        r = await s.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE '%market_state%'"
        ))
        tables = [x[0] for x in r.fetchall()]
        print(f"[market_state 表] {tables}")
        if tables:
            t = tables[0]
            r = await s.execute(text(
                f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='{t}' ORDER BY ordinal_position"
            ))
            cols = [(x[0], x[1]) for x in r.fetchall()]
            print(f"  列: {cols}")
            r = await s.execute(text(f"SELECT COUNT(*) FROM {t}"))
            print(f"  行数: {r.fetchone()[0]}")

        # 2. index_daily 字段
        r = await s.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='index_daily' ORDER BY ordinal_position"
        ))
        cols = [(x[0], x[1]) for x in r.fetchall()]
        print(f"\n[index_daily 列] {cols}")

        # 3. 全市场股票日线（已有，确认股票池规模）
        r = await s.execute(text(
            "SELECT COUNT(DISTINCT ts_code) FROM stock_daily WHERE trade_date >= '2020-01-01'"
        ))
        print(f"\n[stock_daily 2020后股票数] {r.fetchone()[0]}")
    await pool.close()

asyncio.run(main())
