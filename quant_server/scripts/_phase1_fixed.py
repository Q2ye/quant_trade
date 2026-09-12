# -*- coding: utf-8 -*-
"""Phase1 修正：固定先验阈值 + 滚动，涨跌家数比/波动率(2006-2026)、PE(2018-2026)。"""
import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text

STARTS = ["2008","2010","2012","2014","2016","2018","2020","2022"]

async def main():
    from shared.database.session.connection_pool import get_connection_pool
    pool = get_connection_pool()
    try: sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize(); sf = pool.get_session_factory()
    async with sf() as s:
        # 涨跌家数比（2006-2026，快）
        r = await s.execute(text(
            "SELECT trade_date, SUM(CASE WHEN pct_chg>0 THEN 1 ELSE 0 END) up, SUM(CASE WHEN pct_chg<0 THEN 1 ELSE 0 END) dn "
            "FROM stock_daily WHERE trade_date>='2006-01-01' GROUP BY trade_date ORDER BY trade_date"))
        ad = pd.DataFrame(r.fetchall(), columns=["trade_date","up","dn"])
        # 中证1000 close（2006-2026）
        r = await s.execute(text("SELECT trade_date, close FROM index_daily WHERE ts_code='000852.SH' AND trade_date>='2006-01-01' ORDER BY trade_date"))
        idx = pd.DataFrame(r.fetchall(), columns=["trade_date","close"])
    await pool.close()
    ad["trade_date"]=ad["trade_date"].astype(str); idx["trade_date"]=idx["trade_date"].astype(str)
    df = ad.merge(idx, on="trade_date").sort_values("trade_date").reset_index(drop=True)
    for c in ["up","dn","close"]: df[c]=pd.to_numeric(df[c],errors="coerce")
    df["ad_ratio"]=df["up"]/(df["up"]+df["dn"])
    df["ret"]=df["close"].pct_change()
    df["vol"]=df["ret"].rolling(20).std()*np.sqrt(250)
    n=len(df); years=n/250.0

    def ann(mask, sub, years):
        in_mkt=mask.shift(1).fillna(False).values
        rh=np.where(in_mkt, sub["ret"].values, 0.0); rh=rh[~np.isnan(rh)]
        t=(1+rh).prod()-1
        return (1+t)**(1/years)-1 if t>-1 else -1

    print(f"满仓(2006-2026) {ann(pd.Series(True,index=df.index),df,years):.1%}")
    print(f"{'信号':<18}" + "".join(f"{s:>7}" for s in STARTS) + f"{'下四分':>8}{'中位':>8}")
    print("-"*90)
    for name, mask in [("涨跌比>0.5", df["ad_ratio"]>0.5),
                       ("高波动(vol>中位)", df["vol"]>df["vol"].rolling(500).median()),
                       ("低波动(vol<中位)", df["vol"]<df["vol"].rolling(500).median())]:
        anns=[]
        for st in STARTS:
            sub=df[df["trade_date"]>=st+"-01-01"].reset_index(drop=True)
            m=mask[df["trade_date"]>=st+"-01-01"].reset_index(drop=True)
            anns.append(ann(m, sub, len(sub)/250.0))
        q25,med=np.percentile(anns,[25,50])
        print(f"{name:<18}"+"".join(f"{a:>6.1%}" for a in anns)+f"{q25:>7.1%}{med:>7.1%}")

asyncio.run(main())
