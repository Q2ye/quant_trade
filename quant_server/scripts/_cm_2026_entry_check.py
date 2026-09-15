# -*- coding: utf-8 -*-
"""一次性诊断：2026-06~09 亏损交易的入场时点特征（不提交）。

对每笔往返：入场前一交易日（信号日）的 —— 标的自身 25 日涨幅、沪深300 同期涨幅、
相对超额、信号日单日涨幅。用于判断是「追涨」还是「选错方向」。
"""
import asyncio
import importlib.util
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
_spec = importlib.util.spec_from_file_location(
    "cmb", str(Path(__file__).resolve().parent / "_analyze_cm_backtest.py"))
cm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cm)

TASK = "9ca5b752-b6e8-444a-ba19-13d30ea211ae"
W0, W1 = "2026-06-01", "2026-09-10"


async def main() -> None:
    from sqlalchemy import text
    eq, tr, _m, _b, _op, _ap = await cm.load()
    eq = eq.sort_values("trade_date").reset_index(drop=True)
    dates = eq["trade_date"].tolist()
    pos = {d: i for i, d in enumerate(dates)}
    rt = cm.round_trips(tr)
    s = rt[(rt["entry_date"] >= W0) & (rt["entry_date"] <= W1)].copy()
    s["i"] = s["entry_date"].map(pos)
    s["sig"] = [dates[i - 1] if i and i > 0 else None for i in s["i"]]

    from shared.database.session.connection_pool import get_connection_pool
    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()
    codes = sorted(s["ts_code"].unique())
    async with sf() as sess:
        r = await sess.execute(text(
            "SELECT ts_code, trade_date, close FROM etf_daily WHERE ts_code = ANY(:c) "
            "AND trade_date BETWEEN '2026-03-01' AND '2026-09-30' ORDER BY trade_date"),
            {"c": codes})
        px = pd.DataFrame(r.fetchall(), columns=["code", "d", "close"])
        r = await sess.execute(text(
            "SELECT trade_date, close FROM index_daily WHERE ts_code='000300.SH' "
            "AND trade_date BETWEEN '2026-03-01' AND '2026-09-30' ORDER BY trade_date"))
        bm = pd.DataFrame(r.fetchall(), columns=["d", "close"])
    await pool.close()
    for x in (px, bm):
        x["d"] = pd.to_datetime(x["d"]).dt.strftime("%Y-%m-%d")
        x["close"] = x["close"].astype(float)
    bmap = bm.set_index("d")["close"]

    def ret25(code: str, end: str, n: int = 25):
        g = px[(px["code"] == code) & (px["d"] <= end)].tail(n + 1)
        if len(g) < n + 1:
            return None, None
        return g["close"].iloc[-1] / g["close"].iloc[0] - 1, g["close"].iloc[-1] / g["close"].iloc[-2] - 1

    def bret25(end: str, n: int = 25):
        g = bmap[bmap.index <= end].tail(n + 1)
        if len(g) < n + 1:
            return None
        return g.iloc[-1] / g.iloc[0] - 1

    print("=" * 104)
    print("2026-06 ~ 09 往返：入场时点特征（信号日 = 入场前一交易日）")
    print("=" * 104)
    print(f"  {'入场':<12}{'标的':<11}{'收益':>9}{'标的25日':>10}{'300的25日':>11}"
          f"{'相对超额':>10}{'信号日单日':>11}")
    rows = []
    for _, r in s.sort_values("entry_date").iterrows():
        c, sig = r["ts_code"], r["sig"]
        cand, d1 = ret25(c, sig)
        bench = bret25(sig)
        exc = (cand - bench) if (cand is not None and bench is not None) else None
        rows.append((cand, bench, exc, d1))
        f = lambda v, w=9, p=".2%": (f"{v:>{w}{p}}" if v is not None else f"{'--':>{w}}")
        print(f"  {r['entry_date']:<12}{c:<11}{r['ret']:>+9.2%}{f(cand,10)}{f(bench,11)}"
              f"{f(exc,10)}{f(d1,11)}")
    df = pd.DataFrame(rows, columns=["cand25", "bench25", "exc", "d1"]).dropna()
    print("")
    print(f"  样本 {len(df)}/{len(s)} 笔")
    print(f"  标的 25 日涨幅：均值 {df['cand25'].mean():+.2%}  中位 {df['cand25'].median():+.2%}  "
          f"为正 {(df['cand25'] > 0).mean():.0%}")
    print(f"  沪深300 25日  ：均值 {df['bench25'].mean():+.2%}  中位 {df['bench25'].median():+.2%}  "
          f"为正 {(df['bench25'] > 0).mean():.0%}")
    print(f"  **相对超额**  ：均值 {df['exc'].mean():+.2%}  中位 {df['exc'].median():+.2%}  "
          f"为正 {(df['exc'] > 0).mean():.0%}  ← 相对强度门要求 >0")
    print(f"  信号日单日涨幅：均值 {df['d1'].mean():+.2%}  中位 {df['d1'].median():+.2%}  "
          f">5% 的 {(df['d1'] > 0.05).mean():.0%}")

    # 分批对照：2026 上半年 vs 7-8 月
    print("")
    print("  对照：入场日 在 6 月前(2021-2025) vs 2026 —— 信号日特征")
    rt2 = rt.copy()
    rt2["sig"] = [dates[i - 1] if (i := pos.get(d)) and i > 0 else None
                  for d in rt2["entry_date"]]
    # 只对比 2026 内部
    print("  （仅列 2026 内部：6月前开仓 vs 7-8月开仓）")
    for lab, a, b in (("2026-01~06", "2026-01-01", "2026-06-30"), ("2026-07~09", "2026-07-01", "2026-09-10")):
        g = rt[(rt["entry_date"] >= a) & (rt["entry_date"] <= b)]
        print(f"    {lab:<14} {len(g):>2} 笔  平均单笔 {g['ret'].mean():+.2%}  胜率 {(g['ret'] > 0).mean():.0%}  "
              f"合计 {g['pnl'].sum():+,.0f}")


if __name__ == "__main__":
    asyncio.run(main())
