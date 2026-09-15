# -*- coding: utf-8 -*-
"""一次性诊断：「逆风建仓」是否系统性更差（不提交）。

对全部往返，按信号日为止的 —— 沪深300 近 25 日收益（bench25）与标的自身近 25 日收益
（cand25）做二维切分。用于判断「在市场下跌时买逆势强势标的」是不是真正的亏损来源。

⚠️ 这是**条件统计**，不是因果。设计干预前必须先确认它足够稳健（逐年一致）。
"""
import asyncio
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
_spec = importlib.util.spec_from_file_location(
    "cmb", str(Path(__file__).resolve().parent / "_analyze_cm_backtest.py"))
cm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cm)

TASK = sys.argv[1] if len(sys.argv) > 1 else "9ca5b752-b6e8-444a-ba19-13d30ea211ae"
WINDOW = 25


async def main() -> None:
    from sqlalchemy import text
    eq, tr, _m, _b, _op, _ap = await cm.load()
    eq = eq.sort_values("trade_date").reset_index(drop=True)
    dates = eq["trade_date"].tolist()
    pos = {d: i for i, d in enumerate(dates)}
    rt = cm.round_trips(tr)
    rt = rt[rt["entry_date"].isin(pos)].copy()
    rt["i"] = rt["entry_date"].map(pos)
    rt["sig"] = [dates[i - 1] if i > 0 else None for i in rt["i"]]
    rt = rt[rt["sig"].notna()]

    from shared.database.session.connection_pool import get_connection_pool
    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()
    codes = sorted(rt["ts_code"].unique())
    async with sf() as s:
        r = await s.execute(text(
            "SELECT ts_code, trade_date, close FROM etf_daily WHERE ts_code = ANY(:c) "
            "AND trade_date >= '2018-06-01' ORDER BY trade_date"), {"c": codes})
        px = pd.DataFrame(r.fetchall(), columns=["code", "d", "close"])
        r = await s.execute(text(
            "SELECT trade_date, close FROM index_daily WHERE ts_code='000300.SH' "
            "AND trade_date >= '2018-06-01' ORDER BY trade_date"))
        bm = pd.DataFrame(r.fetchall(), columns=["d", "close"])
    await pool.close()
    for x in (px, bm):
        x["d"] = pd.to_datetime(x["d"]).dt.strftime("%Y-%m-%d")
        x["close"] = x["close"].astype(float)
    bmap = bm.set_index("d")["close"]

    def ret_n(series_map, end, n=WINDOW, col=None):
        g = series_map[series_map.index <= end].tail(n + 1)
        if len(g) < n + 1:
            return None
        return g.iloc[-1] / g.iloc[0] - 1

    pmap = {c: g.set_index("d")["close"] for c, g in px.groupby("code")}
    rt["cand25"] = [ret_n(pmap[c], sig) if c in pmap else None
                    for c, sig in zip(rt["ts_code"], rt["sig"])]
    rt["bench25"] = [ret_n(bmap, sig) for sig in rt["sig"]]
    d = rt.dropna(subset=["cand25", "bench25"]).copy()
    d["逆风"] = np.where(d["bench25"] < 0, "大盘25日为负(逆风)", "大盘25日为正(顺风)")

    print("=" * 92)
    print(f"「逆风建仓」检验  task={TASK}   window={WINDOW}日   样本 {len(d)}/{len(rt)} 笔")
    print("=" * 92)
    print(f"  {'组':<22}{'笔数':>6}{'平均单笔':>11}{'中位':>10}{'胜率':>8}{'合计盈亏':>15}")
    for k, g in d.groupby("逆风"):
        print(f"  {k:<22}{len(g):>6}{g['ret'].mean():>+11.2%}{g['ret'].median():>+10.2%}"
              f"{(g['ret'] > 0).mean():>8.1%}{g['pnl'].sum():>+15,.0f}")
    hi = d[d["bench25"] < 0]["ret"]
    lo = d[d["bench25"] >= 0]["ret"]
    if len(hi) and len(lo):
        gap = lo.mean() - hi.mean()
        se = np.sqrt(hi.var() / len(hi) + lo.var() / len(lo))
        print(f"\n  差（顺风 − 逆风）= {gap:+.2%}   t ≈ {gap / se:.2f}")

    print("\n  【逐年一致性】")
    d["y"] = d["entry_date"].str[:4]
    print(f"  {'年':<6}{'顺风笔':>7}{'顺风均值':>11}{'逆风笔':>7}{'逆风均值':>11}{'差':>10}")
    ok = tot = 0
    for y, g in d.groupby("y"):
        a = g[g["bench25"] >= 0]["ret"]
        b = g[g["bench25"] < 0]["ret"]
        if len(a) < 5 or len(b) < 5:
            continue
        tot += 1
        diff = a.mean() - b.mean()
        if diff > 0:
            ok += 1
        print(f"  {y:<6}{len(a):>7}{a.mean():>+11.2%}{len(b):>7}{b.mean():>+11.2%}{diff:>+10.2%}")
    print(f"  → 「顺风均值 > 逆风均值」的年份：{ok}/{tot}")

    print("\n  【四象限（含标的自身强度）】")
    d["标的强"] = np.where(d["cand25"] > 0, "标的25日为正", "标的25日为负")
    print(f"  {'大盘':<20}{'标的':<16}{'笔数':>6}{'平均单笔':>11}{'胜率':>8}{'合计盈亏':>15}")
    for a in ("大盘25日为正(顺风)", "大盘25日为负(逆风)"):
        for b in ("标的25日为正", "标的25日为负"):
            g = d[(d["逆风"] == a) & (d["标的强"] == b)]
            if not len(g):
                continue
            print(f"  {a:<20}{b:<16}{len(g):>6}{g['ret'].mean():>+11.2%}"
                  f"{(g['ret'] > 0).mean():>8.1%}{g['pnl'].sum():>+15,.0f}")

    print("\n  【相对超额分档】")
    d["exc"] = d["cand25"] - d["bench25"]
    q = pd.qcut(d["exc"], 4, labels=["超额最低25%", "次低", "次高", "超额最高25%"])
    print(f"  {'档':<14}{'笔数':>6}{'平均单笔':>11}{'胜率':>8}{'其中逆风占比':>14}")
    for lv in ["超额最低25%", "次低", "次高", "超额最高25%"]:
        g = d[q == lv]
        print(f"  {lv:<14}{len(g):>6}{g['ret'].mean():>+11.2%}{(g['ret'] > 0).mean():>8.1%}"
              f"{(g['bench25'] < 0).mean():>14.1%}")


if __name__ == "__main__":
    asyncio.run(main())
