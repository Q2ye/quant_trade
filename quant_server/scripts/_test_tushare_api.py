# -*- coding: utf-8 -*-
"""测试 Tushare 三类数据的 API 返回 + 查目标表 schema。"""
import asyncio
from sqlalchemy import text

async def main():
    # noop
    from shared.sources.tushare_source import TushareSource
    from shared.database.session.connection_pool import get_connection_pool
    # 1. Tushare API 测试
    src = TushareSource()
    try:
        # 北向资金全历史
        df = src.get_moneyflow_hsgt(start_date="20141117", end_date="20260907")
        print(f"[moneyflow_hsgt 北向] {len(df)} 行, 列 {list(df.columns)[:12] if not df.empty else '空'}")
        # 更早 PE
        df2 = src.get_daily_basic(trade_date="20100101")
        print(f"[daily_basic 20100101] {len(df2)} 行, 列 {list(df2.columns)[:8] if not df2.empty else '空'}")
        # 两融
        try:
            df3 = src.pro.margin(start_date="20100331", end_date="20260907")
            print(f"[margin 两融] {len(df3)} 行, 列 {list(df3.columns)[:12] if not df3.empty else '空'}")
        except Exception as e:
            print(f"[margin 两融] 失败: {str(e)[:120]}")
    except Exception as e:
        print(f"[Tushare 初始化失败] {str(e)[:120]}")

    # 2. 目标表 schema
    pool = get_connection_pool()
    try: sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize(); sf = pool.get_session_factory()
    async with sf() as s:
        for t in ["stock_moneyflow_hsgt", "stock_daily_basic"]:
            r = await s.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name=:t ORDER BY ordinal_position"), {"t": t})
            print(f"[{t} 列] {[x[0] for x in r.fetchall()]}")
        r = await s.execute(text("SELECT table_name FROM information_schema.tables WHERE table_name LIKE '%margin%'"))
        print(f"[margin 表] {[x[0] for x in r.fetchall()]}")
    await pool.close()

asyncio.run(main())
