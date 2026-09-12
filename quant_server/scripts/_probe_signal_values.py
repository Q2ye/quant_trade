# -*- coding: utf-8 -*-
"""查 regime 取值 + 指标值域，确定牛市判定规则。"""
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
        r = await s.execute(text(
            "SELECT regime, COUNT(*), MIN(trade_date), MAX(trade_date) FROM market_state_daily GROUP BY regime ORDER BY regime"
        ))
        print("[regime 取值分布]")
        for x in r.fetchall():
            print(f"  {x[0]!r}: {x[1]} 行, {x[2]} ~ {x[3]}")
        r = await s.execute(text(
            "SELECT MIN(above_ma250_pct), MAX(above_ma250_pct), MIN(limit_up_count), MAX(limit_up_count), MIN(avg_turnover), MAX(avg_turnover), MIN(volume_ratio), MAX(volume_ratio), MIN(trend_strength), MAX(trend_strength), MIN(momentum_score), MAX(momentum_score) FROM market_state_daily"
        ))
        row = r.fetchone()
        print(f"\n[above_ma250_pct] {row[0]} ~ {row[1]}")
        print(f"[limit_up_count] {row[2]} ~ {row[3]}")
        print(f"[avg_turnover] {row[4]} ~ {row[5]}")
        print(f"[volume_ratio] {row[6]} ~ {row[7]}")
        print(f"[trend_strength] {row[8]} ~ {row[9]}")
        print(f"[momentum_score] {row[10]} ~ {row[11]}")
        # 抽样看几个牛市/熊市时点的指标值
        r = await s.execute(text(
            "SELECT trade_date, regime, above_ma250_pct, limit_up_count, volume_ratio FROM market_state_daily WHERE trade_date IN ('2015-06-12','2019-01-04','2021-02-18','2024-09-30') ORDER BY trade_date"
        ))
        print("\n[关键时点抽样] (2015牛市顶/2019熊市底/2021顶/2024牛起)")
        for x in r.fetchall():
            print(f"  {x[0]} regime={x[1]!r} 宽度={x[2]} 涨停={x[3]} 量比={x[4]}")
    await pool.close()

asyncio.run(main())
