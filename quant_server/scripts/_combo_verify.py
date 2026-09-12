# -*- coding: utf-8 -*-
"""组合验证：多个相对阈值信号投票，看组合择时超额是否 > 单一信号 +7.5%。"""
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
            "SELECT trade_date, above_ma60_pct, above_ma20_pct, volume_ratio, momentum_score "
            "FROM market_state_daily WHERE trade_date>='2006-01-01' ORDER BY trade_date"))
        ms = pd.DataFrame(r.fetchall(), columns=["trade_date","ma60","ma20","vol_ratio","momentum"])
        r = await s.execute(text(
            "SELECT trade_date, SUM(CASE WHEN pct_chg>0 THEN 1 ELSE 0 END) up, SUM(CASE WHEN pct_chg<0 THEN 1 ELSE 0 END) dn "
            "FROM stock_daily WHERE trade_date>='2006-01-01' GROUP BY trade_date ORDER BY trade_date"))
        ad = pd.DataFrame(r.fetchall(), columns=["trade_date","up","dn"])
        r = await s.execute(text("SELECT trade_date, close FROM index_daily WHERE ts_code='000852.SH' AND trade_date>='2006-01-01' ORDER BY trade_date"))
        idx = pd.DataFrame(r.fetchall(), columns=["trade_date","close"])
    await pool.close()
    for d in [ms, ad, idx]: d["trade_date"]=d["trade_date"].astype(str)
    df = ms.merge(ad, on="trade_date").merge(idx, on="trade_date").sort_values("trade_date").reset_index(drop=True)
    for c in ["ma60","ma20","vol_ratio","momentum","up","dn","close"]: df[c]=pd.to_numeric(df[c],errors="coerce")
    df["ad_ratio"]=df["up"]/(df["up"]+df["dn"])
    df["ret"]=df["close"].pct_change()

    sigs = {}
    for name, col in [("涨跌家数比","ad_ratio"),("宽度20","ma20"),("宽度60","ma60"),("量比","vol_ratio"),("动量","momentum")]:
        med = df[col].rolling(500, min_periods=100).median()
        sigs[name] = (df[col] > med)
    vote = pd.Series(0, index=df.index)
    for m in sigs.values(): vote = vote + m.astype(int)

    def ann(mask, sub):
        in_mkt=mask.shift(1).fillna(False).values
        rh=np.where(in_mkt, sub["ret"].values,0.0); rh=rh[~np.isnan(rh)]
        t=(1+rh).prod()-1; yrs=len(sub)/250.0
        return (1+t)**(1/yrs)-1 if t>-1 else -1

    print("[组合投票] 择时超额（滚动中位）")
    print(f"{'规则':<16}{'各起始日超额':<52}{'下四分':>8}{'中位':>8}")
    for label, mask in [("单一:涨跌家数比", sigs["涨跌家数比"])] + [(f"组合:≥{n}票", vote>=n) for n in [2,3,4]]:
        overs=[]
        for st in STARTS:
            sub=df[df["trade_date"]>=st+"-01-01"].reset_index(drop=True)
            m=mask[df["trade_date"]>=st+"-01-01"].reset_index(drop=True)
            full=ann(pd.Series(True,index=sub.index),sub)
            overs.append(ann(m,sub)-full)
        q25,med=np.percentile(overs,[25,50])
        print(f"{label:<16}{' '.join(f'{o:+.1%}' for o in overs):<52}{q25:>+7.1%}{med:>+7.1%}")

    print("\n[样本外]")
    tr=df[df["trade_date"]<"2016-01-01"].reset_index(drop=True); te=df[df["trade_date"]>="2016-01-01"].reset_index(drop=True)
    for label, mask in [("涨跌家数比", sigs["涨跌家数比"]), ("≥3票", vote>=3)]:
        tr_m=mask[df["trade_date"]<"2016-01-01"].reset_index(drop=True); te_m=mask[df["trade_date"]>="2016-01-01"].reset_index(drop=True)
        tr_ov=ann(tr_m,tr)-ann(pd.Series(True,index=tr.index),tr)
        te_ov=ann(te_m,te)-ann(pd.Series(True,index=te.index),te)
        print(f"  {label}: train {tr_ov:+.1%} | test {te_ov:+.1%}")

asyncio.run(main())
