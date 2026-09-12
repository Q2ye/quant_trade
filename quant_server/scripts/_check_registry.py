# -*- coding: utf-8 -*-
"""诊断：CrossMarketMomentumStrategy 是否被 auto_discover 注册 + strategy_templates 表内容。"""
import asyncio
from sqlalchemy import text

async def main():
    from modules.strategy.engines.strategy_registry import StrategyRegistry
    reg = StrategyRegistry()
    reg.clear()
    count = reg.auto_discover()
    print(f"[auto_discover] 注册 {count} 个类")
    for e in reg.list_all():
        print(f"  {e['class_name']} -> type={e['strategy_type']} module={e['module']}")
    has = any(e['class_name']=='CrossMarketMomentumStrategy' for e in reg.list_all())
    print(f"\n[CrossMarketMomentumStrategy 是否在注册表] {has}")

    # strategy_templates 表
    from shared.database.session.connection_pool import get_connection_pool
    pool = get_connection_pool()
    try: sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize(); sf = pool.get_session_factory()
    async with sf() as s:
        r = await s.execute(text("SELECT template_name, template_type, is_builtin FROM strategy_templates ORDER BY template_name"))
        print("\n[strategy_templates 表内容]")
        for x in r.fetchall():
            print(f"  {x[0]} | {x[1]} | builtin={x[2]}")
    await pool.close()

asyncio.run(main())
