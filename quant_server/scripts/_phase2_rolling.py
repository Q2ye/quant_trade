# -*- coding: utf-8 -*-
"""Phase 2 滚动验证：对超额>5%的板块信号做滚动起始日，看择时超额是否稳健。"""
import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text

# 候选（Phase2 里超额>5% 的板块-信号组合）
CASES = [
    ("801730.SI","电力设备","ma60"), ("801730.SI","电力设备","rs_mom"), ("801730.SI","电力设备","ma20"),
    ("801750.SI","计算机","rs_mom"), ("801050.SI","有色","ma20"),
]
STARTS = ["2014-01-01","2016-01-01","2018-01-01","2020-01-01","2022-01-01"]

async def main():
    from shared.database.session.connection_pool import get_connection_pool
    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize(); sf = pool.get_session_factory()
    async with sf() as s:
        codes = list(set(c[0] for c in CASES))
        r = await s.execute(text(
            "SELECT ts_code, trade_date, close FROM index_sw_daily WHERE ts_code=ANY(:c) ORDER BY ts_code,trade_date"
        ), {"c": codes})
        rows = r.fetchall()
        r = await s.execute(text("SELECT trade_date, close FROM index_daily WHERE ts_code='000852.SH' ORDER BY trade_date"))
        mkt = pd.DataFrame(r.fetchall(), columns=["trade_date","close"])
    await pool.close()
    mkt["trade_date"] = mkt["trade_date"].astype(str)
    mkt = mkt.rename(columns={"close":"mkt_close"})

    print(f"{'板块-信号':<16}" + "".join(f"{s[:4]:>8}" for s in STARTS) + f"{'下四分':>8}{'中位':>8}{'上四分':>8}")
    print("-"*95)
    for code, name, sig in CASES:
        d = pd.DataFrame([(str(r[1])[:10], float(r[2])) for r in rows if r[0]==code], columns=["trade_date","close"])
        d = d.merge(mkt, on="trade_date", how="inner").sort_values("trade_date").reset_index(drop=True)
        for c in ["close","mkt_close"]: d[c] = pd.to_numeric(d[c], errors="coerce")
        d["ret"] = d["close"].pct_change()
        d["ma20"]=d["close"].rolling(20).mean(); d["ma60"]=d["close"].rolling(60).mean()
        d["rs"]=d["close"]/d["mkt_close"]; d["rs_mom"]=d["rs"]/d["rs"].shift(60)-1
        mask = {"ma60": d["close"]>d["ma60"], "ma20": d["close"]>d["ma20"], "rs_mom": d["rs_mom"]>0}[sig]
        overs = []
        for st in STARTS:
            sub = d[d["trade_date"]>=st].reset_index(drop=True)
            m = mask[d["trade_date"]>=st].reset_index(drop=True)
            def ann(mk, ret):
                in_mkt = mk.shift(1).fillna(False).values
                rh = np.where(in_mkt, ret.values, 0.0); rh = rh[~np.isnan(rh)]
                t=(1+rh).prod()-1; yrs=len(ret)/250.0
                return (1+t)**(1/yrs)-1 if t>-1 else -1
            full = ann(pd.Series(True,index=sub.index), sub["ret"])
            timing = ann(m, sub["ret"])
            overs.append(timing - full)
        q25, med, q75 = np.percentile(overs, [25,50,75])
        print(f"{name}-{sig:<12}" + "".join(f"{o:>7.1%}" for o in overs) + f"{q25:>7.1%}{med:>7.1%}{q75:>7.1%}")

asyncio.run(main())
