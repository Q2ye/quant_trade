# -*- coding: utf-8 -*-
"""Phase 3：板块级扩展指标（量价/创新高）× 8 行业，相对超额口径。"""
import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text

SECTORS = {"801080.SI":"电子","801750.SI":"计算机","801770.SI":"通信","801120.SI":"食品饮料",
           "801150.SI":"医药","801730.SI":"电力设备","801780.SI":"银行","801050.SI":"有色"}

async def main():
    from shared.database.session.connection_pool import get_connection_pool
    pool = get_connection_pool()
    try: sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize(); sf = pool.get_session_factory()
    async with sf() as s:
        r = await s.execute(text("SELECT ts_code, trade_date, close, amount FROM index_sw_daily WHERE ts_code=ANY(:c) ORDER BY ts_code,trade_date"), {"c": list(SECTORS.keys())})
        rows = r.fetchall()
    await pool.close()

    print(f"{'行业':<8}{'信号':<16}{'择时年化':>9}{'满仓板块':>9}{'择时超额':>9}")
    print("-"*60)
    for code, name in SECTORS.items():
        d = pd.DataFrame([(str(r[1])[:10], float(r[2]), float(r[3] or 0)) for r in rows if r[0]==code], columns=["trade_date","close","amount"])
        for c in ["close","amount"]: d[c]=pd.to_numeric(d[c],errors="coerce")
        d["ret"]=d["close"].pct_change()
        d["amount_ma60"]=d["amount"].rolling(60).mean()
        d["amount_ratio"]=d["amount"]/d["amount_ma60"]
        d["high60"]=d["close"].rolling(60).max()
        n=len(d); years=n/250.0
        def ann(mask):
            in_mkt=mask.shift(1).fillna(False).values
            rh=np.where(in_mkt,d["ret"].values,0.0); rh=rh[~np.isnan(rh)]
            t=(1+rh).prod()-1
            return (1+t)**(1/years)-1 if t>-1 else -1
        full=ann(pd.Series(True,index=d.index))
        for sn, m in [("成交额放量>1.2", d["amount_ratio"]>1.2), ("创60日新高", d["close"]>=d["high60"].shift(1))]:
            a=ann(m)
            print(f"{name:<8}{sn:<16}{a:>8.1%}{full:>8.1%}{a-full:>+8.1%}")

asyncio.run(main())
