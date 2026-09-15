# -*- coding: utf-8 -*-
"""Phase 4c：同窗口基准对照（回答「板块择时到底有没有跑赢简单基准」）。

Phase 4 得到的两个数来自不同窗口，不可直接比：
  · 新能源 ETF 择时年化中位 +9.9%  → 窗口 2020-02 ~ 2026-09（ETF 各自起点）
  · 中证1000 满仓 11.5% / MA250 择时 9.0% → 窗口 2006-2026（P0 表）
本脚本把**所有口径压到同一窗口**（2020-02-10 ~ 2026-09-14，最长 ETF 的区间）后重算。

口径与 Phase2/3/4 一致：mask.shift(1) T+1 执行，年化 = (∏(1+持有日收益))^(1/(n/250))-1。
"""
import asyncio

import numpy as np
import pandas as pd
from sqlalchemy import text

W_START = "2020-02-10"
W_END = "2026-09-14"
MARKET = "000852.SH"
ETFS = ["515700.SH", "515030.SH", "515790.SH", "516180.SH", "516070.SH",
        "159755.SZ", "159757.SZ", "159875.SZ", "562500.SH"]  # 已剔除 516160
OUT = "logs/_p4c_benchmark.txt"
B: list = []


def ann(mask: pd.Series, ret: pd.Series) -> float:
    in_mkt = mask.shift(1).fillna(False).values
    rh = np.where(in_mkt, ret.values, 0.0)
    rh = rh[~np.isnan(rh)]
    if len(rh) == 0:
        return float("nan")
    t = (1 + rh).prod() - 1
    return (1 + t) ** (1 / (len(ret) / 250.0)) - 1 if t > -1 else -1.0


def mdd(mask: pd.Series, ret: pd.Series) -> float:
    """择时净值最大回撤（空仓日收益 0 → 曲线走平）。"""
    in_mkt = mask.shift(1).fillna(False).values
    rh = np.where(in_mkt, ret.values, 0.0)
    rh = np.nan_to_num(rh, nan=0.0)
    eq = np.cumprod(1 + rh)
    peak = np.maximum.accumulate(eq)
    return float((eq / peak - 1).min())


async def main() -> None:
    from shared.database.session.connection_pool import get_connection_pool

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    async with sf() as s:
        r = await s.execute(text(
            "SELECT trade_date, close FROM index_daily WHERE ts_code = :m ORDER BY trade_date"
        ), {"m": MARKET})
        mkt = pd.DataFrame(r.fetchall(), columns=["trade_date", "close"])
        r = await s.execute(text(
            "SELECT ts_code, trade_date, close FROM etf_daily WHERE ts_code = ANY(:c) "
            "ORDER BY ts_code, trade_date"
        ), {"c": ETFS})
        etf = r.fetchall()

    mkt["trade_date"] = mkt["trade_date"].astype(str).str[:10]
    mkt["close"] = pd.to_numeric(mkt["close"], errors="coerce")
    m = mkt[(mkt["trade_date"] >= W_START) & (mkt["trade_date"] <= W_END)].reset_index(drop=True)
    m["ret"] = m["close"].pct_change()
    m["ma250"] = m["close"].rolling(250).mean()
    # 250 日均线预热：额外取窗口前 250 行用于算 MA250
    mkt_all = mkt.reset_index(drop=True)
    mkt_all["ma250"] = mkt_all["close"].rolling(250).mean()
    m2 = mkt_all[(mkt_all["trade_date"] >= W_START) & (mkt_all["trade_date"] <= W_END)].reset_index(drop=True)
    m2["ret"] = m2["close"].pct_change()

    B.append("=" * 88)
    B.append("同窗口基准对照：%s ~ %s" % (W_START, W_END))
    B.append("=" * 88)
    yrs = len(m2) / 250.0
    full_ann = ann(pd.Series(True, index=m2.index), m2["ret"])
    ma250_ann = ann(m2["close"] > m2["ma250"], m2["ret"])
    B.append("")
    B.append("[基准] 中证1000 (000852.SH)")
    B.append("   满仓年化                  = %+.1f%%   （%d 个交易日 / %.1f 年）"
             % (full_ann * 100, len(m2), yrs))
    B.append("   MA250 择时年化（P0 基线）  = %+.1f%%" % (ma250_ann * 100))

    B.append("")
    B.append("[新能源系 ETF] 三条规则（同窗口、各自起始日对齐）")
    B.append("   %-11s %-10s %8s %8s %8s %8s" % ("ETF", "起始", "满仓", "MA60择时", "rs_mom", "成交额"))
    ma60_list, full_list = [], []
    for code in ETFS:
        d = pd.DataFrame([(str(r[1])[:10], float(r[2])) for r in etf if r[0] == code],
                         columns=["trade_date", "close"])
        if d.empty:
            continue
        d["close"] = pd.to_numeric(d["close"], errors="coerce")
        d = d[(d["trade_date"] >= W_START) & (d["trade_date"] <= W_END)].reset_index(drop=True)
        if len(d) < 250:
            continue
        d["ret"] = d["close"].pct_change()
        d["ma60"] = d["close"].rolling(60).mean()
        r_ma60 = ann(d["close"] > d["ma60"], d["ret"])
        r_full = ann(pd.Series(True, index=d.index), d["ret"])
        ma60_list.append(r_ma60)
        full_list.append(r_full)
        B.append("   %-11s %-10s %7.1f%% %7.1f%%" % (
            code, d["trade_date"].iloc[0], r_full * 100, r_ma60 * 100))
    B.append("")
    B.append("   ETF MA60 择时年化: 中位 %+.1f%%   满仓 ETF 中位 %+.1f%%"
             % (np.median(ma60_list) * 100, np.median(full_list) * 100))
    B.append("")
    B.append("[回撤对照] 立项书 P1 验收含「回撤 < 满仓回撤」")
    B.append("   %-11s %12s %12s" % ("ETF", "满仓MDD", "MA60择时MDD"))
    mdd_full, mdd_tim = [], []
    for code in ETFS:
        d = pd.DataFrame([(str(r[1])[:10], float(r[2])) for r in etf if r[0] == code],
                         columns=["trade_date", "close"])
        if d.empty:
            continue
        d["close"] = pd.to_numeric(d["close"], errors="coerce")
        d = d[(d["trade_date"] >= W_START) & (d["trade_date"] <= W_END)].reset_index(drop=True)
        if len(d) < 250:
            continue
        d["ret"] = d["close"].pct_change()
        d["ma60"] = d["close"].rolling(60).mean()
        mf = mdd(pd.Series(True, index=d.index), d["ret"])
        mt = mdd(d["close"] > d["ma60"], d["ret"])
        mdd_full.append(mf)
        mdd_tim.append(mt)
        B.append("   %-11s %11.1f%% %11.1f%%" % (code, mf * 100, mt * 100))
    B.append("   %-11s %11.1f%% %11.1f%%" % ("【中位】", np.median(mdd_full) * 100,
                                             np.median(mdd_tim) * 100))
    B.append("   → 择时回撤中位 %.1f%% vs 满仓中位 %.1f%%（改善 %.1fpp）"
             % (np.median(mdd_tim) * 100, np.median(mdd_full) * 100,
                (np.median(mdd_tim) - np.median(mdd_full)) * 100))
    B.append("   → 同期中证1000 满仓 %+.1f%% ／ MA250 择时 %+.1f%%"
             % (full_ann * 100, ma250_ann * 100))
    B.append("")
    delta_idx = np.median(ma60_list) - full_ann
    delta_base = np.median(ma60_list) - ma250_ann
    B.append("[结论计算]")
    B.append("   新能源ETF MA60 择时 − 中证1000 满仓      = %+.1fpp" % (delta_idx * 100))
    B.append("   新能源ETF MA60 择时 − 中证1000 MA250择时 = %+.1fpp" % (delta_base * 100))


if __name__ == "__main__":
    import os

    try:
        asyncio.run(main())
    except Exception as e:  # noqa: BLE001
        import traceback
        B.append("[FATAL] " + repr(e))
        B.append(traceback.format_exc()[:1500])
    os.makedirs("logs", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(B))
    print("OK ->", OUT)
