# -*- coding: utf-8 -*-
"""新维度组合验证：涨跌家数比(价格) + 北向资金(资金流) + 两融(杠杆)，看组合是否提升 +7.5%。"""
import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text

STARTS = ["2016","2018","2020","2022","2024"]

async def main():
    from shared.database.session.connection_pool import get_connection_pool
    pool = get_connection_pool()
    try: sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize(); sf = pool.get_session_factory()
    async with sf() as s:
        r = await s.execute(text(
            "SELECT trade_date, SUM(CASE WHEN pct_chg>0 THEN 1 ELSE 0 END) up, SUM(CASE WHEN pct_chg<0 THEN 1 ELSE 0 END) dn "
            "FROM stock_daily WHERE trade_date>='2014-01-01' GROUP BY trade_date ORDER BY trade_date"))
        ad = pd.DataFrame(r.fetchall(), columns=["trade_date","up","dn"])
        r = await s.execute(text("SELECT trade_date, close FROM index_daily WHERE ts_code='000852.SH' AND trade_date>='2014-01-01' ORDER BY trade_date"))
        idx = pd.DataFrame(r.fetchall(), columns=["trade_date","close"])
        r = await s.execute(text("SELECT trade_date, north_money FROM stock_moneyflow_hsgt WHERE trade_date>='2014-01-01' ORDER BY trade_date"))
        hsgt = pd.DataFrame(r.fetchall(), columns=["trade_date","north_money"])
        r = await s.execute(text("SELECT trade_date, SUM(rzye) rzye FROM margin WHERE trade_date>='2014-01-01' GROUP BY trade_date ORDER BY trade_date"))
        mg = pd.DataFrame(r.fetchall(), columns=["trade_date","rzye"])
    await pool.close()
    for d in [ad, idx, hsgt, mg]: d["trade_date"]=d["trade_date"].astype(str)
    df = ad.merge(idx,on="trade_date").merge(hsgt,on="trade_date").merge(mg,on="trade_date").sort_values("trade_date").reset_index(drop=True)
    for c in ["up","dn","close","north_money","rzye"]: df[c]=pd.to_numeric(df[c],errors="coerce")
    df["ad_ratio"]=df["up"]/(df["up"]+df["dn"])
    df["ret"]=df["close"].pct_change()
    # 信号（相对阈值/变化）
    df["ad_med"]=df["ad_ratio"].rolling(500,min_periods=100).median()
    sig_ad = df["ad_ratio"] > df["ad_med"]
    sig_north = df["north_money"].rolling(20).mean() > 0   # 北向持续净流入
    sig_margin = df["rzye"].diff(20) > 0                     # 融资余额 20 日上升
    vote = sig_ad.astype(int) + sig_north.astype(int) + sig_margin.astype(int)

    def ann(mask, sub):
        in_mkt=mask.shift(1).fillna(False).values
        rh=np.where(in_mkt, sub["ret"].values,0.0); rh=rh[~np.isnan(rh)]
        t=(1+rh).prod()-1; yrs=len(sub)/250.0
        return (1+t)**(1/yrs)-1 if t>-1 else -1

    print(f"[新维度组合] 择时超额（数据 2014-11 起，滚动 2016 起）")
    print(f"{'规则':<20}{'各起始日超额':<40}{'下四分':>8}{'中位':>8}")
    cases = [("涨跌家数比(单一)", sig_ad), ("北向净流入(单一)", sig_north), ("两融余额升(单一)", sig_margin),
             ("组合≥2票", vote>=2), ("组合≥3票", vote>=3)]
    for label, mask in cases:
        overs=[]
        for st in STARTS:
            sub=df[df["trade_date"]>=st+"-01-01"].reset_index(drop=True)
            m=mask[df["trade_date"]>=st+"-01-01"].reset_index(drop=True)
            full=ann(pd.Series(True,index=sub.index),sub)
            overs.append(ann(m,sub)-full)
        q25,med=np.percentile(overs,[25,50])
        print(f"{label:<20}{' '.join(f'{o:+.1%}' for o in overs):<40}{q25:>+7.1%}{med:>+7.1%}")

asyncio.run(main())
