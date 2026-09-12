# -*- coding: utf-8 -*-
"""阳性对照：用「后验完美择时」（故意用未来信息）验证框架能否识别正 alpha。"""
import asyncio
import pandas as pd
import numpy as np
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
            "SELECT trade_date, close FROM index_daily WHERE ts_code='000852.SH' AND trade_date >= '2006-01-01' ORDER BY trade_date"
        ))
        df = pd.DataFrame(r.fetchall(), columns=["trade_date","close"])
    await pool.close()
    df["trade_date"] = df["trade_date"].astype(str)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["ret"] = df["close"].pct_change()
    df["ma250"] = df["close"].rolling(250).mean()
    n = len(df); years = n/250.0

    def ann(mask):
        in_mkt = mask.shift(1).fillna(False).values
        ret_hold = np.where(in_mkt, df["ret"].values, 0.0)
        ret_hold = ret_hold[~np.isnan(ret_hold)]
        total = (1+ret_hold).prod()-1
        return (1+total)**(1/years)-1

    fwd250 = df["close"].shift(-250)
    fwd60 = df["close"].shift(-60)
    labels = {
        "未来250日上涨": df["close"] < fwd250,
        "未来60日上涨": df["close"] < fwd60,
        "未来250日涨>10%": df["close"]*1.10 < fwd250,
        "未来250日涨>20%": df["close"]*1.20 < fwd250,
    }
    print("中证1000 阳性对照（后验完美择时，故意用未来信息，应显著>9%基线）:")
    print(f"{'后验标签':<18}{'择时年化':>10}{'牛市占比':>10}")
    print(f"{'满仓(基线)':<18}{ann(pd.Series(True,index=df.index)):>9.1%}{'100%':>10}")
    print(f"{'MA250(基线)':<18}{ann(df['close']>df['ma250']):>9.1%}{(df['close']>df['ma250']).mean():>9.1%}")
    for name, mask in labels.items():
        mask = mask.fillna(False)
        print(f"{name:<18}{ann(mask):>9.1%}{mask.mean():>9.1%}")

asyncio.run(main())
