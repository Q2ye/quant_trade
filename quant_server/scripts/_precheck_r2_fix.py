# -*- coding: utf-8 -*-
"""只读预检：R² 三种口径的差异（不提交、不改策略文件）。

现状     : fit=W, ss_res=weights, ss_tot 中心化=np.mean(y)
方案A(全W): fit=W, ss_res=W,       ss_tot 中心化=y_bar(加权均值)   ← 教科书 WLS R²，保证 ∈[0,1]
方案B(半修): fit=W, ss_res=weights, ss_tot 中心化=y_bar            ← 只改中心化

对池内全部 ETF 全历史逐日计算三者的 r2 与 score=annualized*r2，
统计负值率、翻转率、与现状的偏离幅度、以及对 2026-09-11 选股的影响。
"""
import asyncio
import math
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

POOL = [
    "518880.SH", "513100.SH", "513500.SH", "513030.SH", "513520.SH",
    "159920.SZ", "513050.SH", "513330.SZ", "513180.SH", "159980.SZ", "159985.SZ",
    "510050.SH", "510300.SH", "510500.SH", "512100.SH", "159915.SZ", "159949.SZ",
    "588080.SH", "512880.SH", "515880.SH", "512480.SH", "512400.SH", "512660.SH",
    "512800.SH", "512690.SH", "512170.SH", "512010.SH", "515030.SH",
]
LB = 25

ETF_SQL = """
    SELECT e.ts_code, e.trade_date::text,
           e.close * COALESCE(f.adj_factor,1) / lf.latest_factor AS close
    FROM etf_daily e
    LEFT JOIN fund_adj_factor f ON f.ts_code=e.ts_code AND f.trade_date=e.trade_date
    LEFT JOIN (SELECT DISTINCT ON (ts_code) ts_code, adj_factor AS latest_factor
               FROM fund_adj_factor ORDER BY ts_code, trade_date DESC) lf
      ON lf.ts_code=e.ts_code
    WHERE e.ts_code = ANY(:c) AND e.trade_date >= '2020-06-01'
    ORDER BY e.ts_code, e.trade_date
"""


def three_variants(recent: np.ndarray):
    """返回 (annualized, r2_cur, r2_A, r2_B)。口径与策略文件逐行对齐。"""
    y = np.log(recent)
    x = np.arange(len(y), dtype=np.float64)
    weights = np.linspace(1.0, 2.0, len(y))
    W = weights ** 2
    W_sum = float(np.sum(W))
    if W_sum <= 0:
        return None
    x_bar = float(np.sum(W * x) / W_sum)
    y_bar = float(np.sum(W * y) / W_sum)
    dx, dy = x - x_bar, y - y_bar
    var_x = float(np.sum(W * dx ** 2))
    if var_x <= 0:
        return 0.0, 0.0, 0.0, 0.0
    slope = float(np.sum(W * dx * dy) / var_x)
    intercept = y_bar - slope * x_bar
    annualized = float(math.exp(slope * 250.0) - 1.0)
    y_pred = slope * x + intercept

    ss_res_w = float(np.sum(weights * (y - y_pred) ** 2))   # 现状/方案B 用
    ss_res_W = float(np.sum(W * (y - y_pred) ** 2))         # 方案A 用
    ss_tot_np = float(np.sum(weights * (y - float(np.mean(y))) ** 2))   # 现状
    ss_tot_bar = float(np.sum(W * (y - y_bar) ** 2))                    # 方案A/B

    r2_cur = 1.0 - ss_res_w / ss_tot_np if ss_tot_np > 0 else 0.0
    r2_A = 1.0 - ss_res_W / ss_tot_bar if ss_tot_bar > 0 else 0.0
    r2_B = 1.0 - ss_res_w / ss_tot_bar if ss_tot_bar > 0 else 0.0
    return annualized, r2_cur, r2_A, r2_B


async def main() -> None:
    from sqlalchemy import text
    from shared.database.session.connection_pool import get_connection_pool

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()
    async with sf() as s:
        r = await s.execute(text(ETF_SQL), {"c": POOL})
        df = pd.DataFrame(r.fetchall(), columns=["code", "d", "close"])
    await pool.close()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    rec = []
    for code, g in df.groupby("code"):
        c = g["close"].to_numpy(dtype=np.float64)
        ds = g["d"].tolist()
        for i in range(LB, len(c)):
            v = three_variants(c[i - LB: i + 1])
            if v is None:
                continue
            ann, cur, a, b = v
            rec.append((ann, cur, a, b, code, ds[i]))
    t = pd.DataFrame(rec, columns=["ann", "cur", "A", "B", "code", "d"])
    n = len(t)
    print("=" * 104)
    print(f"样本 {n:,}（28 只池内 ETF，2020-06 ~ 2026-09-11，lookback={LB}）")
    print("=" * 104)
    print(f"  {'口径':<22}{'r2<0 占比':>12}{'r2<-0.001':>12}{'r2 最小':>11}"
          f"{'r2>1':>9}{'r2 最大':>10}")
    for lab, col in (("现状（fit W / 无权均值）", "cur"),
                     ("方案A（三者同用 W）", "A"),
                     ("方案B（只改中心化）", "B")):
        s = t[col]
        print(f"  {lab:<22}{(s < 0).mean():>12.2%}{(s < -0.001).mean():>12.2%}"
              f"{s.min():>11.4f}{(s > 1).mean():>9.2%}{s.max():>10.4f}")

    print()
    print("  与现状的偏离（只在两者都 ≥0 的样本上比，看对正常样本的扰动）：")
    for lab, col in (("方案A", "A"), ("方案B", "B")):
        m = (t["cur"] >= 0) & (t[col] >= 0)
        d = (t.loc[m, col] - t.loc[m, "cur"]).abs()
        print(f"    {lab}: 样本 {m.sum():>7,}   |Δr2| 均值={d.mean():.5f}  "
              f"p95={d.quantile(0.95):.5f}  最大={d.max():.5f}")
        # 对通过 r2>0.47 门槛的候选集合的影响
        cur_pass = set(t.loc[(t["cur"] > 0.47), "code"] + "|" + t.loc[(t["cur"] > 0.47), "d"])
        new_pass = set(t.loc[(t[col] > 0.47), "code"] + "|" + t.loc[(t[col] > 0.47), "d"])
        print(f"           r2>0.47 命中：现状 {len(cur_pass):,} → {lab} {len(new_pass):,}  "
              f"新增 {len(new_pass - cur_pass):,}  丢失 {len(cur_pass - new_pass):,}")

    print()
    print("=" * 104)
    print("  对 2026-09-11 选股的影响（走弱期池 11 只）")
    print("=" * 104)
    g11 = ["518880.SH", "513100.SH", "513500.SH", "513030.SH", "513520.SH",
           "159920.SZ", "513050.SH", "513330.SZ", "513180.SH", "159980.SZ", "159985.SZ"]
    sub = t[(t["d"] == "2026-09-11") & (t["code"].isin(g11))].sort_values("cur", ascending=False)
    print(f"  {'标的':<11}{'年化':>10}{'现状r2':>10}{'现状score':>12}"
          f"{'A_r2':>9}{'A_score':>11}{'B_r2':>9}{'B_score':>11}   变化")
    for _, x in sub.iterrows():
        ch = ""
        if (x["cur"] < 0) and (x["A"] >= 0):
            ch = "★A 修复负值"
        if (x["cur"] < 0) and (x["B"] < 0):
            ch += "  B 仍为负"
        print(f"  {x['code']:<11}{x['ann']:>10.2%}{x['cur']:>10.4f}"
              f"{x['ann'] * x['cur']:>12.4f}{x['A']:>9.4f}{x['ann'] * x['A']:>11.4f}"
              f"{x['B']:>9.4f}{x['ann'] * x['B']:>11.4f}   {ch}")


if __name__ == "__main__":
    asyncio.run(main())
