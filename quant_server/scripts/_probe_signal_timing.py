# -*- coding: utf-8 -*-
"""核心验证：10 个候选牛市信号 vs 满仓/MA250 基线的择时年化 + 回撤（方案①②③+⑦）。"""
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
            "SELECT trade_date, regime, above_ma250_pct, above_ma60_pct, above_ma20_pct, "
            "limit_up_count, avg_turnover, volume_ratio, trend_strength, momentum_score "
            "FROM market_state_daily WHERE trade_date >= '2006-01-01' ORDER BY trade_date"
        ))
        ms = pd.DataFrame(r.fetchall(), columns=["trade_date","regime","ma250_pct","ma60_pct","ma20_pct",
            "limit_up","turnover","vol_ratio","trend","momentum"])
        r = await s.execute(text(
            "SELECT trade_date, close, amount FROM index_daily WHERE ts_code='000852.SH' AND trade_date >= '2006-01-01' ORDER BY trade_date"
        ))
        idx = pd.DataFrame(r.fetchall(), columns=["trade_date","close","amount"])
    await pool.close()

    df = ms.merge(idx, on="trade_date", how="inner").sort_values("trade_date").reset_index(drop=True)
    for c in ["ma250_pct","ma60_pct","ma20_pct","limit_up","turnover","vol_ratio","trend","momentum","close","amount"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["ret"] = df["close"].pct_change()
    df["ma250"] = df["close"].rolling(250).mean()
    df["amount_ma60"] = df["amount"].rolling(60).mean()
    df["amount_ratio"] = df["amount"] / df["amount_ma60"]
    n = len(df); years = n / 250.0

    def timing_ann(bull_mask):
        in_mkt = bull_mask.shift(1).fillna(False).values
        ret_hold = np.where(in_mkt, df["ret"].values, 0.0)
        total = (1 + ret_hold[~np.isnan(ret_hold)]).prod() - 1
        # 回撤：择时净值曲线
        nav = np.cumprod(1 + ret_hold)
        peak = np.maximum.accumulate(nav)
        dd = float(np.min(nav / peak - 1)) if len(nav) else 0
        ann = (1 + total) ** (1/years) - 1 if total > -1 else -1
        return ann, dd

    # 基线：满仓
    full_total = (1 + df["ret"].fillna(0)).prod() - 1
    full_ann = (1 + full_total) ** (1/years) - 1
    nav_full = np.cumprod(1 + df["ret"].fillna(0).values)
    full_dd = float(np.min(nav_full / np.maximum.accumulate(nav_full) - 1))
    # 基线：MA250
    ma250_ann, ma250_dd = timing_ann(df["close"] > df["ma250"])

    print(f"满仓基线: 年化 {full_ann:.1%}  回撤 {full_dd:.1%}")
    print(f"MA250基线: 年化 {ma250_ann:.1%}  回撤 {ma250_dd:.1%}")
    print(f"{'信号':<16}{'牛市规则':<28}{'年化':>8}{'回撤':>8}{'vs满仓':>8}{'vsMA250':>9}")
    print("-" * 90)

    # 候选信号：连续指标扫描分位数阈值
    cont_signals = ["ma250_pct","ma60_pct","ma20_pct","limit_up","turnover","vol_ratio","trend","momentum","amount_ratio"]
    for sig in cont_signals:
        s = df[sig].dropna()
        if len(s) < 500: continue
        best_ann, best_dd, best_thr = -1, 0, 0
        for q in [0.3,0.4,0.5,0.6,0.7,0.8]:
            thr = s.quantile(q)
            bull = df[sig] > thr
            ann, dd = timing_ann(bull)
            if ann > best_ann:
                best_ann, best_dd, best_thr = ann, dd, q
        tag = f">分位{best_thr:.0%}"
        print(f"{sig:<16}{tag:<28}{best_ann:>7.1%}{best_dd:>7.1%}{best_ann-full_ann:>+7.1%}{best_ann-ma250_ann:>+8.1%}")

    # 离散信号：regime
    for rv in ["BULL","BEAR"]:
        bull = df["regime"] == rv
        ann, dd = timing_ann(bull)
        tag = f"regime=={rv}"
        print(f"{'regime':<16}{tag:<28}{ann:>7.1%}{dd:>7.1%}{ann-full_ann:>+7.1%}{ann-ma250_ann:>+8.1%}")

asyncio.run(main())
