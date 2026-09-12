# -*- coding: utf-8 -*-
"""Phase 1：现算 4 个全市场信号 + 核心择时验证。"""
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
        # 1. 涨跌家数比
        r = await s.execute(text(
            "SELECT trade_date, "
            "SUM(CASE WHEN pct_chg>0 THEN 1 ELSE 0 END) up_cnt, "
            "SUM(CASE WHEN pct_chg<0 THEN 1 ELSE 0 END) down_cnt "
            "FROM stock_daily WHERE trade_date>='2006-01-01' GROUP BY trade_date ORDER BY trade_date"
        ))
        ad = pd.DataFrame(r.fetchall(), columns=["trade_date","up_cnt","down_cnt"])
        # 2. 新高新低比（窗口函数）
        r = await s.execute(text(
            "WITH cte AS (SELECT ts_code,trade_date,close, "
            "MAX(close) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 250 PRECEDING AND 1 PRECEDING) ph, "
            "MIN(close) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 250 PRECEDING AND 1 PRECEDING) pl "
            "FROM stock_daily WHERE trade_date>='2005-01-01') "
            "SELECT trade_date, SUM(CASE WHEN close>ph THEN 1 ELSE 0 END) nh, "
            "SUM(CASE WHEN close<pl THEN 1 ELSE 0 END) nl "
            "FROM cte WHERE trade_date>='2006-01-01' GROUP BY trade_date ORDER BY trade_date"
        ))
        hl = pd.DataFrame(r.fetchall(), columns=["trade_date","new_high","new_low"])
        # 3. PE 中位数
        r = await s.execute(text(
            "SELECT trade_date, percentile_cont(0.5) WITHIN GROUP (ORDER BY pe_ttm) pe_med "
            "FROM stock_daily_basic WHERE trade_date>='2006-01-01' AND pe_ttm>0 GROUP BY trade_date ORDER BY trade_date"
        ))
        pe = pd.DataFrame(r.fetchall(), columns=["trade_date","pe_median"])
        # 4. 中证1000 close（历史波动率）
        r = await s.execute(text(
            "SELECT trade_date, close FROM index_daily WHERE ts_code='000852.SH' AND trade_date>='2006-01-01' ORDER BY trade_date"
        ))
        idx = pd.DataFrame(r.fetchall(), columns=["trade_date","close"])
    await pool.close()

    for d in [ad, hl, pe, idx]:
        d["trade_date"] = d["trade_date"].astype(str)
    df = ad.merge(hl, on="trade_date").merge(pe, on="trade_date").merge(idx, on="trade_date").sort_values("trade_date").reset_index(drop=True)
    for c in ["up_cnt","down_cnt","new_high","new_low","pe_median","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # 构造信号
    df["ad_ratio"] = df["up_cnt"] / (df["up_cnt"] + df["down_cnt"])  # 上涨占比
    df["hl_ratio"] = df["new_high"] / (df["new_high"] + df["new_low"])  # 新高占比
    df["ret"] = df["close"].pct_change()
    df["vol"] = df["ret"].rolling(20).std() * np.sqrt(250)  # 历史波动率(年化)
    df["ma250"] = df["close"].rolling(250).mean()
    n = len(df); years = n/250.0

    def ann(mask):
        in_mkt = mask.shift(1).fillna(False).values
        rh = np.where(in_mkt, df["ret"].values, 0.0); rh = rh[~np.isnan(rh)]
        t = (1+rh).prod()-1
        return (1+t)**(1/years)-1 if t>-1 else -1

    full_ann = ann(pd.Series(True, index=df.index))
    ma250_ann = ann(df["close"] > df["ma250"])
    print(f"满仓基线 {full_ann:.1%} | MA250基线 {ma250_ann:.1%}")
    print(f"{'信号':<16}{'最优规则':<22}{'年化':>8}{'vs满仓':>8}{'vsMA250':>9}")
    for sig in ["ad_ratio","hl_ratio","pe_median","vol"]:
        s = df[sig].dropna()
        if len(s) < 500: continue
        best_ann, best_q, best_dir = -1, 0, ">"
        for q in [0.2,0.3,0.4,0.5,0.6,0.7,0.8]:
            for op in [">", "<"]:
                bull = df[sig] > s.quantile(q) if op==">" else df[sig] < s.quantile(q)
                a = ann(bull)
                if a > best_ann: best_ann, best_q, best_dir = a, q, op
        print(f"{sig:<16}{best_dir}分位{best_q:.0%}{'':<14}{best_ann:>7.1%}{best_ann-full_ann:>+7.1%}{best_ann-ma250_ann:>+8.1%}")

asyncio.run(main())
