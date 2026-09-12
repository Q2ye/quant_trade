# -*- coding: utf-8 -*-
"""北向净流入信号：样本外 + bootstrap 验证。"""
import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text

async def main():
    from shared.database.session.connection_pool import get_connection_pool
    pool = get_connection_pool()
    try: sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize(); sf = pool.get_session_factory()
    async with sf() as s:
        r = await s.execute(text("SELECT trade_date, north_money FROM stock_moneyflow_hsgt ORDER BY trade_date"))
        hsgt = pd.DataFrame(r.fetchall(), columns=["trade_date","north_money"])
        r = await s.execute(text("SELECT trade_date, close FROM index_daily WHERE ts_code='000852.SH' ORDER BY trade_date"))
        idx = pd.DataFrame(r.fetchall(), columns=["trade_date","close"])
    await pool.close()
    for d in [hsgt, idx]: d["trade_date"]=d["trade_date"].astype(str)
    df = hsgt.merge(idx,on="trade_date").sort_values("trade_date").reset_index(drop=True)
    for c in ["north_money","close"]: df[c]=pd.to_numeric(df[c],errors="coerce")
    df["ret"]=df["close"].pct_change()
    sig = df["north_money"].rolling(20).mean() > 0

    def ann(mask, sub):
        in_mkt=mask.shift(1).fillna(False).values
        rh=np.where(in_mkt, sub["ret"].values,0.0); rh=rh[~np.isnan(rh)]
        t=(1+rh).prod()-1; yrs=len(sub)/250.0
        return (1+t)**(1/yrs)-1 if t>-1 else -1

    # 样本外 train 2014-2020, test 2020-2026
    tr=df[df["trade_date"]<"2020-01-01"].reset_index(drop=True); te=df[df["trade_date"]>="2020-01-01"].reset_index(drop=True)
    tr_m=sig[df["trade_date"]<"2020-01-01"].reset_index(drop=True); te_m=sig[df["trade_date"]>="2020-01-01"].reset_index(drop=True)
    tr_ov=ann(tr_m,tr)-ann(pd.Series(True,index=tr.index),tr)
    te_ov=ann(te_m,te)-ann(pd.Series(True,index=te.index),te)
    print(f"[样本外] train(14-20)超额 {tr_ov:+.1%} | test(20-26)超额 {te_ov:+.1%}")

    # bootstrap
    in_mkt=sig.shift(1).fillna(False).values
    rh_t=np.where(in_mkt, df["ret"].values,0.0)
    diff=rh_t-df["ret"].values; diff=diff[~np.isnan(diff)]
    rng=np.random.default_rng(42)
    boots=np.mean(rng.choice(diff,size=(3000,len(diff)),replace=True),axis=1)
    p=float(np.mean(boots<=0))
    print(f"[bootstrap] 日收益差均值 {np.mean(diff)*100:.3f}% P(差<=0)={p:.4f}")

asyncio.run(main())
