# -*- coding: utf-8 -*-
"""一次性诊断：① 牛/熊/震荡三态表现 ② 2026-07/08 亏损归因（不提交）。

regime 判定与项目后端/前端同源：CSI500(000905.SH) close vs MA250 ±3% 带
（bull: >MA×1.03 ｜ bear: <MA×0.97 ｜ range: 其余）。
"""
import asyncio
from datetime import date
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
_out: list[str] = []


def p(m: str = "") -> None:
    print(m, flush=True)
    _out.append(m)


async def main() -> None:
    from sqlalchemy import text
    eq, tr, meta, _bm, open_pos, allpos = await cm.load()
    eq = eq.sort_values("trade_date").reset_index(drop=True)
    eq["ret"] = eq["equity"].pct_change().fillna(0.0)

    # ---- CSI500 regime（与 shared.market_regime 同源）----
    from shared.database.session.connection_pool import get_connection_pool
    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()
    async with sf() as s:
        r = await s.execute(text(
            "SELECT trade_date, close FROM index_daily WHERE ts_code='000905.SH' "
            "AND trade_date BETWEEN :a AND :b ORDER BY trade_date"),
            {"a": date.fromisoformat(eq["trade_date"].iloc[0]),
             "b": date.fromisoformat(eq["trade_date"].iloc[-1])})
        idx = pd.DataFrame(r.fetchall(), columns=["d", "close"])
    await pool.close()
    idx["d"] = pd.to_datetime(idx["d"]).dt.strftime("%Y-%m-%d")
    idx["close"] = idx["close"].astype(float)
    idx["ma250"] = idx["close"].rolling(250).mean()
    idx["bm_ret"] = idx["close"].pct_change().fillna(0.0)

    def _reg(v: pd.Series) -> str:
        if pd.isna(v["ma250"]):
            return "range"
        if v["close"] > v["ma250"] * 1.03:
            return "bull"
        if v["close"] < v["ma250"] * 0.97:
            return "bear"
        return "range"

    idx["regime"] = idx.apply(_reg, axis=1)
    d = eq.merge(idx[["d", "regime", "bm_ret"]].rename(columns={"d": "trade_date"}),
                 on="trade_date", how="left")

    p("=" * 86)
    p(f"① 三态市况下的策略表现   task={TASK}")
    p(f"   regime 判定：CSI500 vs MA250 ±3%（与后端 shared.market_regime 同源）")
    p("=" * 86)
    p(f"  {'市况':<8}{'天数':>6}{'占比':>8}{'策略日均':>10}{'策略胜率':>10}"
      f"{'基准日均':>10}{'日均超额':>10}{'策略累计':>12}{'基准累计':>11}")
    for reg, lab in (("bull", "牛市"), ("range", "震荡"), ("bear", "熊市")):
        g = d[d["regime"] == reg]
        if not len(g):
            continue
        cum = float((1 + g["ret"]).prod() - 1)
        bcum = float((1 + g["bm_ret"]).prod() - 1)
        p(f"  {lab:<8}{len(g):>6}{len(g) / len(d):>8.1%}{g['ret'].mean() * 100:>9.3f}%"
          f"{(g['ret'] > 0).mean():>10.1%}{g['bm_ret'].mean() * 100:>9.3f}%"
          f"{(g['ret'].mean() - g['bm_ret'].mean()) * 100:>9.3f}%"
          f"{cum:>12.1%}{bcum:>11.1%}")
    p(f"  {'全区间':<8}{len(d):>6}{'100%':>8}{d['ret'].mean() * 100:>9.3f}%"
      f"{(d['ret'] > 0).mean():>10.1%}{d['bm_ret'].mean() * 100:>9.3f}%"
      f"{(d['ret'].mean() - d['bm_ret'].mean()) * 100:>9.3f}%"
      f"{(1 + d['ret']).prod() - 1:>12.1%}{(1 + d['bm_ret']).prod() - 1:>11.1%}")
    p("")
    p("  逐年 × 市况 拆解：")
    d["y"] = d["trade_date"].str[:4]
    p(f"  {'年':<6}{'牛':>7}{'震荡':>8}{'熊':>7}{'策略年收益':>13}{'基准年收益':>13}")
    for y, g in d.groupby("y"):
        nb = (g["regime"] == "bull").sum()
        nr = (g["regime"] == "range").sum()
        nbe = (g["regime"] == "bear").sum()
        p(f"  {y:<6}{nb:>7}{nr:>8}{nbe:>7}"
          f"{(1 + g['ret']).prod() - 1:>13.1%}{(1 + g['bm_ret']).prod() - 1:>13.1%}")

    # ---- ② 2026-07/08 ----
    p("")
    p("=" * 86)
    p("② 2026-07-01 ~ 2026-08-31 亏损归因")
    p("=" * 86)
    W = d[(d["trade_date"] >= "2026-07-01") & (d["trade_date"] <= "2026-08-31")]
    seg = float((1 + W["ret"]).prod() - 1)
    segb = float((1 + W["bm_ret"]).prod() - 1)
    p(f"  区间：{len(W)} 个交易日   策略 {seg:+.2%}   基准 {segb:+.2%}   超额 {seg - segb:+.2%}")
    p(f"  市况分布：" + "  ".join(f"{k}={int((W['regime'] == k).sum())}天" for k in ("bull", "range", "bear")))
    p(f"  日胜率 {((W['ret'] > 0).mean()):.1%}   日均 {W['ret'].mean():+.3%}   日波动 {W['ret'].std():.2%}")

    p("")
    p("  逐日明细（组合当日 / 基准当日 / 持有标的自身当日）：")
    mv = allpos.pivot_table(index="trade_date", columns="ts_code", values="market_value", aggfunc="last")
    vol = allpos.pivot_table(index="trade_date", columns="ts_code", values="volume", aggfunc="last").replace(0, np.nan)
    px = (mv / vol).sort_index()
    hold = mv.idxmax(axis=1)
    p(f"  {'日期':<12}{'市况':<7}{'持有':<12}{'标的当日':>10}{'组合当日':>10}{'基准当日':>10}")
    for _, r in W.iterrows():
        dt = r["trade_date"]
        c = hold.get(dt)
        ar = np.nan
        if c is not None and c in px.columns and dt in px.index:
            i = px.index.get_loc(dt)
            if i > 0 and pd.notna(px[c].iloc[i]) and pd.notna(px[c].iloc[i - 1]):
                ar = px[c].iloc[i] / px[c].iloc[i - 1] - 1
        lab = {"bull": "牛", "range": "震荡", "bear": "熊"}.get(r["regime"], "?")
        p(f"  {dt:<12}{lab:<7}{str(c):<12}{ar:>10.2%}{r['ret']:>10.2%}{r['bm_ret']:>10.2%}")

    rt = cm.round_trips(tr)
    s = rt[(rt["entry_date"] >= "2026-06-01") & (rt["entry_date"] <= "2026-09-10")].copy()
    s["days"] = (pd.to_datetime(s["exit_date"]) - pd.to_datetime(s["entry_date"])).dt.days
    p("")
    p("  2026-06 起的完整往返（含 7/8 月）：")
    p(f"  {'入场':<12}{'出场':<12}{'标的':<12}{'收益':>9}{'天':>5}{'盈亏':>13}")
    for _, r in s.sort_values("entry_date").iterrows():
        p(f"  {r['entry_date']:<12}{r['exit_date']:<12}{r['ts_code']:<12}"
          f"{r['ret']:>+9.2%}{int(r['days']):>5}{r['pnl']:>+13,.0f}")
    p(f"  合计 {s['pnl'].sum():+,.0f}   胜率 {(s['ret'] > 0).mean():.1%}   {len(s)} 笔")
    p(f"  其中 7/1~8/31 开仓的：{len(s[(s['entry_date'] >= '2026-07-01') & (s['entry_date'] <= '2026-08-31')])} 笔，"
      f"盈亏 {s[(s['entry_date'] >= '2026-07-01') & (s['entry_date'] <= '2026-08-31')]['pnl'].sum():+,.0f}")

    # 对照：2026 上半年 / 历史同期
    p("")
    p("  对照：")
    for lab, a, b in (("2026 上半年", "2026-01-01", "2026-06-30"),
                      ("2026-07~08", "2026-07-01", "2026-08-31"),
                      ("2026-09 至末", "2026-09-01", "2026-12-31")):
        g = d[(d["trade_date"] >= a) & (d["trade_date"] <= b)]
        if not len(g):
            continue
        p(f"    {lab:<14} {len(g):>3} 天  策略 {(1 + g['ret']).prod() - 1:>+8.2%}  "
          f"基准 {(1 + g['bm_ret']).prod() - 1:>+8.2%}  "
          f"超额 {((1 + g['ret']).prod() - (1 + g['bm_ret']).prod()):>+8.2%}")

    out = Path("logs/_cm_regime_2026.txt")
    out.write_text("\n".join(_out), encoding="utf-8")
    print(f"\n[已写入 {out}]")


if __name__ == "__main__":
    asyncio.run(main())
