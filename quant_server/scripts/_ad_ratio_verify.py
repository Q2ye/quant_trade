# -*- coding: utf-8 -*-
"""验证 ad_ratio(涨跌家数比>滚动中位数) 是否跨时代稳健：滚动 + 样本外 + bootstrap。"""
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
        r = await s.execute(text(
            "SELECT trade_date, SUM(CASE WHEN pct_chg>0 THEN 1 ELSE 0 END) up, SUM(CASE WHEN pct_chg<0 THEN 1 ELSE 0 END) dn "
            "FROM stock_daily WHERE trade_date>='2006-01-01' GROUP BY trade_date ORDER BY trade_date"))
        ad = pd.DataFrame(r.fetchall(), columns=["trade_date","up","dn"])
        r = await s.execute(text("SELECT trade_date, close FROM index_daily WHERE ts_code='000852.SH' AND trade_date>='2006-01-01' ORDER BY trade_date"))
        idx = pd.DataFrame(r.fetchall(), columns=["trade_date","close"])
    await pool.close()
    for d in [ad, idx]: d["trade_date"]=d["trade_date"].astype(str)
    df = ad.merge(idx, on="trade_date").sort_values("trade_date").reset_index(drop=True)
    for c in ["up","dn","close"]: df[c]=pd.to_numeric(df[c],errors="coerce")
    df["ad_ratio"]=df["up"]/(df["up"]+df["dn"])
    df["ret"]=df["close"].pct_change()
    df["ad_med"]=df["ad_ratio"].rolling(500,min_periods=100).median()
    sig = df["ad_ratio"] > df["ad_med"]  # 相对阈值

    def ann(mask, sub):
        in_mkt=mask.shift(1).fillna(False).values
        rh=np.where(in_mkt, sub["ret"].values,0.0); rh=rh[~np.isnan(rh)]
        t=(1+rh).prod()-1; yrs=len(sub)/250.0
        return (1+t)**(1/yrs)-1 if t>-1 else -1

    # 滚动
    print("[滚动] ad_ratio>滚动中位数 的择时超额（vs 满仓）")
    overs=[]
    for st in STARTS:
        sub=df[df["trade_date"]>=st+"-01-01"].reset_index(drop=True)
        m=sig[df["trade_date"]>=st+"-01-01"].reset_index(drop=True)
        full=ann(pd.Series(True,index=sub.index),sub)
        ov=ann(m,sub)-full
        overs.append(ov)
    print("  " + " ".join(f"{o:+.1%}" for o in overs))
    print(f"  下四分 {np.percentile(overs,25):+.1%} | 中位 {np.percentile(overs,50):+.1%} | 上四分 {np.percentile(overs,75):+.1%}")

    # 样本外
    tr=df[df["trade_date"]<"2016-01-01"].reset_index(drop=True); te=df[df["trade_date"]>="2016-01-01"].reset_index(drop=True)
    tr_m=sig[df["trade_date"]<"2016-01-01"].reset_index(drop=True); te_m=sig[df["trade_date"]>="2016-01-01"].reset_index(drop=True)
    tr_ov=ann(tr_m,tr)-ann(pd.Series(True,index=tr.index),tr)
    te_ov=ann(te_m,te)-ann(pd.Series(True,index=te.index),te)
    print(f"[样本外] train(06-15)超额 {tr_ov:+.1%} | test(16-26)超额 {te_ov:+.1%}")

    # bootstrap
    in_mkt=sig.shift(1).fillna(False).values
    rh_t=np.where(in_mkt, df["ret"].values,0.0)
    diff=rh_t-df["ret"].values; diff=diff[~np.isnan(diff)]
    rng=np.random.default_rng(42)
    boots=np.mean(rng.choice(diff,size=(3000,len(diff)),replace=True),axis=1)
    p=float(np.mean(boots<=0))
    print(f"[bootstrap] 日收益差均值 {np.mean(diff)*100:.3f}% P(差<=0)={p:.4f}")

asyncio.run(main())
