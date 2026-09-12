# -*- coding: utf-8 -*-
"""分时代诊断：4 个时代分别测各指标的择时超额，看是否「时代平均化」抹掉了 alpha。"""
import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text

ERAS = [("时代1 2006-2010", "2006-01-01", "2010-12-31"),
        ("时代2 2011-2015", "2011-01-01", "2015-12-31"),
        ("时代3 2016-2021", "2016-01-01", "2021-12-31"),
        ("时代4 2022-2026", "2022-01-01", "2026-09-07")]

async def main():
    from shared.database.session.connection_pool import get_connection_pool
    pool = get_connection_pool()
    try: sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize(); sf = pool.get_session_factory()
    async with sf() as s:
        r = await s.execute(text(
            "SELECT trade_date, above_ma250_pct, above_ma60_pct, above_ma20_pct, volume_ratio, momentum_score, limit_up_count, avg_turnover, volatility_pct "
            "FROM market_state_daily WHERE trade_date>='2006-01-01' ORDER BY trade_date"))
        ms = pd.DataFrame(r.fetchall(), columns=["trade_date","ma250","ma60","ma20","vol_ratio","momentum","limit_up","turnover","volatility"])
        r = await s.execute(text(
            "SELECT trade_date, SUM(CASE WHEN pct_chg>0 THEN 1 ELSE 0 END) up, SUM(CASE WHEN pct_chg<0 THEN 1 ELSE 0 END) dn "
            "FROM stock_daily WHERE trade_date>='2006-01-01' GROUP BY trade_date ORDER BY trade_date"))
        ad = pd.DataFrame(r.fetchall(), columns=["trade_date","up","dn"])
        r = await s.execute(text("SELECT trade_date, close FROM index_daily WHERE ts_code='000852.SH' AND trade_date>='2006-01-01' ORDER BY trade_date"))
        idx = pd.DataFrame(r.fetchall(), columns=["trade_date","close"])
    await pool.close()
    for d in [ms, ad, idx]: d["trade_date"]=d["trade_date"].astype(str)
    df = ms.merge(ad, on="trade_date").merge(idx, on="trade_date").sort_values("trade_date").reset_index(drop=True)
    for c in ["ma250","ma60","ma20","vol_ratio","momentum","limit_up","turnover","volatility","up","dn","close"]:
        df[c]=pd.to_numeric(df[c],errors="coerce")
    df["ad_ratio"]=df["up"]/(df["up"]+df["dn"])
    df["ret"]=df["close"].pct_change()

    SIGS = ["ma250","ma60","ma20","vol_ratio","momentum","limit_up","turnover","volatility","ad_ratio"]
    print(f"{'时代':<16}{'满仓':>8}" + "".join(f"{s:>10}" for s in SIGS))
    print("-"*110)
    for era_name, s0, s1 in ERAS:
        e = df[(df["trade_date"]>=s0)&(df["trade_date"]<=s1)].reset_index(drop=True)
        if len(e) < 100: continue
        def ann(mask, sub):
            in_mkt=mask.shift(1).fillna(False).values
            rh=np.where(in_mkt, sub["ret"].values,0.0); rh=rh[~np.isnan(rh)]
            t=(1+rh).prod()-1; yrs=len(sub)/250.0
            return (1+t)**(1/yrs)-1 if t>-1 else -1
        full=ann(pd.Series(True,index=e.index), e)
        row=f"{era_name:<16}{full:>7.1%}"
        for sig in SIGS:
            s=e[sig].dropna()
            if len(s)<100: row += f"{'N/A':>10}"; continue
            med=e[sig].rolling(500,min_periods=100).median()
            ov=ann(e[sig]>med, e)-full
            row += f"{ov:>+9.1%}"
        print(row)

asyncio.run(main())
