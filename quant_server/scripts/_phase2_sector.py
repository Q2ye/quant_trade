# -*- coding: utf-8 -*-
"""Phase 2：板块级核心 3 指标（趋势/动量/相对强度）× 8 行业，相对超额口径。"""
import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text

SECTORS = {
    "801080.SI":"电子","801750.SI":"计算机","801770.SI":"通信",
    "801120.SI":"食品饮料","801150.SI":"医药生物","801730.SI":"电力设备",
    "801780.SI":"银行","801050.SI":"有色金属",
}

async def main():
    from shared.database.session.connection_pool import get_connection_pool
    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize(); sf = pool.get_session_factory()
    async with sf() as s:
        r = await s.execute(text(
            "SELECT ts_code, trade_date, close, amount FROM index_sw_daily WHERE ts_code=ANY(:c) ORDER BY ts_code,trade_date"
        ), {"c": list(SECTORS.keys())})
        rows = r.fetchall()
        r = await s.execute(text(
            "SELECT trade_date, close FROM index_daily WHERE ts_code='000852.SH' ORDER BY trade_date"
        ))
        mkt = pd.DataFrame(r.fetchall(), columns=["trade_date","close"])
    await pool.close()
    mkt["trade_date"] = mkt["trade_date"].astype(str)
    mkt = mkt.rename(columns={"close":"mkt_close"})

    print(f"{'行业':<8}{'信号':<20}{'规则':<16}{'择时年化':>9}{'满仓板块':>9}{'择时超额':>9}")
    print("-"*80)
    for code, name in SECTORS.items():
        d = pd.DataFrame([(str(r[1])[:10], float(r[2])) for r in rows if r[0]==code], columns=["trade_date","close"])
        d = d.merge(mkt, on="trade_date", how="inner").sort_values("trade_date").reset_index(drop=True)
        for c in ["close","mkt_close"]:
            d[c] = pd.to_numeric(d[c], errors="coerce")
        d["ret"] = d["close"].pct_change()
        n = len(d); years = n/250.0
        def ann(mask):
            in_mkt = mask.shift(1).fillna(False).values
            rh = np.where(in_mkt, d["ret"].values, 0.0); rh = rh[~np.isnan(rh)]
            t = (1+rh).prod()-1
            return (1+t)**(1/years)-1 if t>-1 else -1
        full_ann = ann(pd.Series(True, index=d.index))  # 满仓板块
        # 信号
        d["ma20"]=d["close"].rolling(20).mean(); d["ma60"]=d["close"].rolling(60).mean(); d["ma250"]=d["close"].rolling(250).mean()
        d["mom60"]=d["close"]/d["close"].shift(60)-1
        d["rs"]=d["close"]/d["mkt_close"]  # 累积比值
        d["rs_mom"]=d["rs"]/d["rs"].shift(60)-1  # 相对动量
        d["excess"]=d["close"]/d["close"].shift(60)-d["mkt_close"]/d["mkt_close"].shift(60)  # 超额收益
        sigs = [
            ("趋势MA20", d["close"]>d["ma20"]),
            ("趋势MA60", d["close"]>d["ma60"]),
            ("趋势MA250", d["close"]>d["ma250"]),
            ("动量60", d["mom60"]>0),
            ("相对强度RS新高", d["rs"]>d["rs"].rolling(120).max().shift(1)),
            ("相对动量RS_mom>0", d["rs_mom"]>0),
            ("超额收益>0", d["excess"]>0),
        ]
        for sn, m in sigs:
            a = ann(m)
            print(f"{name:<8}{sn:<20}{'':<16}{a:>8.1%}{full_ann:>8.1%}{a-full_ann:>+8.1%}")

asyncio.run(main())
