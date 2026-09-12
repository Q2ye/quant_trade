# -*- coding: utf-8 -*-
"""Phase2 样本外+bootstrap：新能源(电力设备) ma60/rs_mom 的显著性。"""
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
        r = await s.execute(text("SELECT trade_date, close FROM index_sw_daily WHERE ts_code='801730.SI' ORDER BY trade_date"))
        d = pd.DataFrame(r.fetchall(), columns=["trade_date","close"])
        r = await s.execute(text("SELECT trade_date, close FROM index_daily WHERE ts_code='000852.SH' ORDER BY trade_date"))
        mkt = pd.DataFrame(r.fetchall(), columns=["trade_date","close"])
    await pool.close()
    d["trade_date"]=d["trade_date"].astype(str); mkt["trade_date"]=mkt["trade_date"].astype(str)
    d = d.merge(mkt.rename(columns={"close":"mkt_close"}), on="trade_date").sort_values("trade_date").reset_index(drop=True)
    for c in ["close","mkt_close"]: d[c]=pd.to_numeric(d[c],errors="coerce")
    d["ret"]=d["close"].pct_change(); d["ma60"]=d["close"].rolling(60).mean()
    d["rs"]=d["close"]/d["mkt_close"]; d["rs_mom"]=d["rs"]/d["rs"].shift(60)-1

    def ann(mask, ret):
        in_mkt = mask.shift(1).fillna(False).values
        rh = np.where(in_mkt, ret.values, 0.0); rh = rh[~np.isnan(rh)]
        t=(1+rh).prod()-1; yrs=len(ret)/250.0
        return (1+t)**(1/yrs)-1 if t>-1 else -1

    # 样本外：train 2012-2019, test 2019-2026
    for sig, mask in [("ma60", d["close"]>d["ma60"]), ("rs_mom", d["rs_mom"]>0)]:
        tr = d[d["trade_date"]<"2019-01-01"].reset_index(drop=True)
        te = d[d["trade_date"]>="2019-01-01"].reset_index(drop=True)
        tr_m = mask[d["trade_date"]<"2019-01-01"].reset_index(drop=True)
        te_m = mask[d["trade_date"]>="2019-01-01"].reset_index(drop=True)
        tr_full = ann(pd.Series(True,index=tr.index), tr["ret"])
        te_full = ann(pd.Series(True,index=te.index), te["ret"])
        tr_ov = ann(tr_m, tr["ret"]) - tr_full
        te_ov = ann(te_m, te["ret"]) - te_full
        print(f"[样本外 {sig}] train超额 {tr_ov:+.1%} | test超额 {te_ov:+.1%}")

    # bootstrap：择时 vs 满仓 日收益差
    print("\n[bootstrap 显著性] 电力设备")
    rng = np.random.default_rng(42)
    for sig, mask in [("ma60", d["close"]>d["ma60"]), ("rs_mom", d["rs_mom"]>0)]:
        in_mkt = mask.shift(1).fillna(False).values
        rh_timing = np.where(in_mkt, d["ret"].values, 0.0)
        diff = rh_timing - d["ret"].values
        diff = diff[~np.isnan(diff)]
        boots = np.mean(rng.choice(diff, size=(3000, len(diff)), replace=True), axis=1)
        p = float(np.mean(boots <= 0))
        print(f"  {sig}: 日收益差均值 {np.mean(diff)*100:.3f}%  P(差<=0)={p:.4f}")

asyncio.run(main())
