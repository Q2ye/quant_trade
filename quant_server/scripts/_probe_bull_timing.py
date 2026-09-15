# -*- coding: utf-8 -*-
"""确认：MA250 择时（牛市持有/熊市空仓）下指数年化，反推 40% 目标需跑赢几倍。"""
import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text

IDX = ["000852.SH", "000300.SH", "000905.SH"]  # 中证1000 / 沪深300 / 中证500

async def main():
    from shared.database.session.connection_pool import get_connection_pool
    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize(); sf = pool.get_session_factory()
    async with sf() as s:
        r = await s.execute(text(
            "SELECT ts_code, trade_date, close FROM index_daily "
            "WHERE ts_code = ANY(:c) AND trade_date >= '2006-01-01' ORDER BY ts_code, trade_date"
        ), {"c": IDX})
        rows = r.fetchall()
    await pool.close()

    data = [(str(r[0])[:10], str(r[1])[:10], float(r[2])) for r in rows]
    df = pd.DataFrame(data, columns=["code", "date", "close"])
    print(f"{'指数':<12}{'牛占比':>8}{'全期年化':>10}{'MA250择时年化':>14}{'40%需跑赢':>12}{'40%需(总倍数)':>14}")
    for code in IDX:
        sub = df[df["code"] == code].sort_values("date").reset_index(drop=True)
        sub["ma250"] = sub["close"].rolling(250).mean()
        sub["bull"] = sub["close"] > sub["ma250"]
        sub["ret"] = sub["close"].pct_change()
        sub["in_mkt"] = sub["bull"].shift(1).fillna(False)  # T+1: 前日牛→今日持有
        sub["ret_hold"] = np.where(sub["in_mkt"], sub["ret"], 0.0)
        n = len(sub); years = n / 250.0
        total = (1 + sub["ret"]).prod() - 1  # 全期满仓
        total_timing = (1 + sub["ret_hold"]).prod() - 1  # 择时
        ann = (1 + total) ** (1/years) - 1
        ann_timing = (1 + total_timing) ** (1/years) - 1 if total_timing > -1 else -1
        bull_frac = sub["bull"].mean()
        beat_ann = 0.40 / ann_timing if ann_timing > 0 else float('inf')
        beat_total = ((1.40 ** years) - 1) / total_timing if total_timing > 0 else float('inf')
        print(f"{code:<12}{bull_frac:>7.1%}{ann:>9.1%}{ann_timing:>13.1%}{beat_ann:>11.2f}x{beat_total:>13.1f}x")

asyncio.run(main())
