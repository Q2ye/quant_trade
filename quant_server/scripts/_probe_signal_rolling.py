# -*- coding: utf-8 -*-
"""方案⑤滚动起始日：用固定阈值（先验，非全样本最优）验证 5 个强信号的稳健性。"""
import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text

STARTS = ["2008-01-01","2010-01-01","2012-01-01","2014-01-01","2016-01-01","2018-01-01","2020-01-01","2022-01-01"]
# 固定阈值（先验，避免全样本最优过拟合）
SIGNALS = {
    "ma20>50%": lambda d: d["ma20_pct"] > 50,
    "ma60>60%": lambda d: d["ma60_pct"] > 60,
    "量比>1.5": lambda d: d["vol_ratio"] > 1.5,
    "成交额>MA60×1.2": lambda d: d["amount_ratio"] > 1.2,
    "动量>0": lambda d: d["momentum"] > 0,
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
            "SELECT trade_date, above_ma250_pct, above_ma60_pct, above_ma20_pct, volume_ratio, momentum_score "
            "FROM market_state_daily WHERE trade_date >= '2006-01-01' ORDER BY trade_date"
        ))
        ms = pd.DataFrame(r.fetchall(), columns=["trade_date","ma250_pct","ma60_pct","ma20_pct","vol_ratio","momentum"])
        r = await s.execute(text(
            "SELECT trade_date, close, amount FROM index_daily WHERE ts_code='000852.SH' AND trade_date >= '2006-01-01' ORDER BY trade_date"
        ))
        idx = pd.DataFrame(r.fetchall(), columns=["trade_date","close","amount"])
    await pool.close()

    df = ms.merge(idx, on="trade_date", how="inner").sort_values("trade_date").reset_index(drop=True)
    df["trade_date"] = df["trade_date"].astype(str)
    for c in ["ma20_pct","ma60_pct","vol_ratio","momentum","close","amount"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["ret"] = df["close"].pct_change()
    df["amount_ma60"] = df["amount"].rolling(60).mean()
    df["amount_ratio"] = df["amount"] / df["amount_ma60"]

    print(f"{'信号':<16}" + "".join(f"{s[:4]:>8}" for s in STARTS) + f"{'下四分位':>9}{'中位':>8}{'上四分位':>9}")
    print("-" * 100)
    for name, rule in SIGNALS.items():
        bull = rule(df)
        anns = []
        for st in STARTS:
            sub = df[df["trade_date"] >= st]
            b = bull[df["trade_date"] >= st]
            in_mkt = b.shift(1).fillna(False).values
            ret_hold = np.where(in_mkt, sub["ret"].values, 0.0)
            ret_hold = ret_hold[~np.isnan(ret_hold)]
            total = (1 + ret_hold).prod() - 1 if len(ret_hold) else 0
            n = len(sub); years = n / 250.0
            ann = (1 + total) ** (1/years) - 1 if total > -1 else -1
            anns.append(ann)
        q25, med, q75 = np.percentile(anns, [25,50,75])
        print(f"{name:<16}" + "".join(f"{a:>7.1%}" for a in anns) + f"{q25:>8.1%}{med:>7.1%}{q75:>8.1%}")

asyncio.run(main())
