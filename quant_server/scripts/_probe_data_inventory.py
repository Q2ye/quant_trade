# -*- coding: utf-8 -*-
"""数据盘点：查遗漏清单里的数据源是否在 DB。"""
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
        # 1. 全表清单（找相关表）
        r = await s.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
        ))
        tables = [x[0] for x in r.fetchall()]
        print(f"[全部表 {len(tables)} 个]")
        # 关键词匹配
        kw = ["moneyflow","hsgt","margin","opt","vix","volatil","yield","bond","treasury","member","basic","valuation","index_option"]
        for k in kw:
            hits = [t for t in tables if k in t]
            print(f"  '{k}': {hits}")

        # 2. index_sw_member 结构（成分股时间戳？）
        try:
            r = await s.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='index_sw_member' ORDER BY ordinal_position"
            ))
            cols = [x[0] for x in r.fetchall()]
            print(f"\n[index_sw_member 列] {cols}")
            r = await s.execute(text("SELECT * FROM index_sw_member LIMIT 3"))
            print(f"  样本: {r.fetchall()}")
        except Exception as e:
            print(f"\n[index_sw_member 查询失败] {e}")

        # 3. index_daily 是否有估值列（PE）
        r = await s.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='index_daily' ORDER BY ordinal_position"
        ))
        print(f"\n[index_daily 列] {[x[0] for x in r.fetchall()]}")

        # 4. 国债指数是否在 index_daily
        r = await s.execute(text(
            "SELECT DISTINCT ts_code FROM index_daily WHERE ts_code LIKE '%000012%' OR ts_code LIKE '%国债%' OR ts_code LIKE 'H%' LIMIT 20"
        ))
        print(f"\n[index_daily 国债相关] {[x[0] for x in r.fetchall()]}")

        # 5. stock_daily_basic 估值列
        try:
            r = await s.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='stock_daily_basic' ORDER BY ordinal_position"
            ))
            print(f"\n[stock_daily_basic 列] {[x[0] for x in r.fetchall()]}")
        except Exception as e:
            print(f"\n[stock_daily_basic 查询失败] {e}")
    await pool.close()

asyncio.run(main())
