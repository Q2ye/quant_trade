# -*- coding: utf-8 -*-
"""方案⑥样本外 train/test + ⑧bootstrap 显著性。"""
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
        r = await s.execute(text(
            "SELECT trade_date, above_ma60_pct, above_ma20_pct, volume_ratio, momentum_score "
            "FROM market_state_daily WHERE trade_date >= '2006-01-01' ORDER BY trade_date"
        ))
        ms = pd.DataFrame(r.fetchall(), columns=["trade_date","ma60_pct","ma20_pct","vol_ratio","momentum"])
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

    def ann(mask, ret, years):
        in_mkt = mask.shift(1).fillna(False).values
        ret_hold = np.where(in_mkt, ret.values, 0.0)
        ret_hold = ret_hold[~np.isnan(ret_hold)]
        total = (1 + ret_hold).prod() - 1 if len(ret_hold) else 0
        return (1 + total) ** (1/years) - 1 if total > -1 else -1

    train = df[df["trade_date"] < "2016-01-01"].reset_index(drop=True)
    test = df[df["trade_date"] >= "2016-01-01"].reset_index(drop=True)
    print("[⑥ 样本外] train=2006-2015 定参数, test=2016-2026 验证")
    print(f"{'信号':<14}{'train最优分位':>12}{'train年化':>10}{'test年化':>10}{'衰减':>8}")
    for sig in ["ma20_pct","ma60_pct","vol_ratio","amount_ratio","momentum"]:
        s = train[sig].dropna()
        best_q, best_ann = 0, -1
        for q in [0.3,0.4,0.5,0.6,0.7,0.8]:
            thr = s.quantile(q)
            a = ann(train[sig] > thr, train["ret"], len(train)/250.0)
            if a > best_ann: best_ann, best_q = a, q
        thr = s.quantile(best_q)
        train_ann = ann(train[sig] > thr, train["ret"], len(train)/250.0)
        test_ann = ann(test[sig] > thr, test["ret"], len(test)/250.0)
        print(f"{sig:<14}{best_q:>11.0%}{train_ann:>9.1%}{test_ann:>9.1%}{test_ann-train_ann:>+7.1%}")

    print("\n[⑧ 显著性] 各信号(固定阈值)择时 vs 满仓 日收益差 bootstrap (P<=0)")
    rng = np.random.default_rng(42)
    for name, mask in [("ma20>50%", df["ma20_pct"]>50), ("量比>1.5", df["vol_ratio"]>1.5),
                       ("成交额>1.2", df["amount_ratio"]>1.2)]:
        in_mkt = mask.shift(1).fillna(False).values
        ret_timing = np.where(in_mkt, df["ret"].values, 0.0)
        diff = ret_timing - df["ret"].values
        diff = diff[~np.isnan(diff)]
        boots = np.mean(rng.choice(diff, size=(2000, len(diff)), replace=True), axis=1)
        p = float(np.mean(boots <= 0))
        print(f"  {name}: 日收益差均值 {np.mean(diff)*100:.3f}%  P(差<=0)={p:.3f}")

asyncio.run(main())
