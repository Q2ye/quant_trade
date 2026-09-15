# -*- coding: utf-8 -*-
"""Phase 4：板块级信号「可交易 ETF 落地」复验（_ 前缀，一次性研究脚本，不入 git）。

背景：`_phase2_sector.py` 在申万电力设备指数(801730.SI)上测出「趋势MA60 / 相对动量」
择时超额 +10.6% / +10.0%（2014-2026）。本脚本把**同三条规则原样搬到可交易 ETF**，
回答 P1 的收口问题：**信号在可交易标的上是否保持超额？**

与 Phase 2/3 保持一致的口径（保证可比）：
  · 市场基准 = index_daily 000852.SH（中证1000），与 801730 的 rs 口径同源
  · 择时收益 = 信号 mask.shift(1) → **T+1 执行**，无未来函数
  · 年化 = (∏(1+持有日收益))^(1/(n/250)) - 1，只在持仓日计收益、空仓日记 0
  · 信号参数不改：MA60、rs_mom>0、成交额>20日均额×1.2（Phase3 用 60 日均额）

唯一有意偏离：Phase2/3 用指数（无分红），ETF 有分红 → 额外做除息跳空检查，
并同时输出「close.pct_change()」与「pct_chg」两种收益口径的对照，避免误判。

用法：
    cd quant_server && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/_phase4_etf_verify.py
"""
import asyncio

import numpy as np
import pandas as pd
from sqlalchemy import text

MARKET = "000852.SH"

# 候选池：按库内起始日排序（仅保留历史 ≥ 4 年的）
ETFS = {
    "515700.SH": "新能车ETF",
    "515030.SH": "新能源车ETF",
    "515790.SH": "光伏ETF",
    "516160.SH": "新能源ETF",
    "516180.SH": "细分化工ETF",
    "516070.SH": "新能源(516070)",
    "159755.SZ": "电池ETF",
    "159757.SZ": "电池ETF(深)",
    "159875.SZ": "新能源ETF(深)",
    "562500.SH": "机器人ETF",
}

# 数据污染剔除：516160 有 1 天 close 口径异常（close.pct_change() 与 pct_chg 差 22.83pp），
# 全样本年化被该点污染（满仓 17.5% 虚高、MA60 超额被抹平），不纳入汇总。
EXCLUDE = {"516160.SH": "1 天 close 口径异常（偏离 2.22，两口径差 22.8pp）"}

ROLL_STARTS = ["2021-01-01", "2022-01-01", "2023-01-01", "2024-01-01"]
ERAS = [
    ("2021-01-01", "2022-12-31", "泡沫破裂+反弹"),
    ("2023-01-01", "2024-12-31", "阴跌"),
    ("2025-01-01", "2026-09-14", "反弹"),
]
MIN_DAYS = 500  # 少于 ~2 年不出结论

OUT_LINES: list = []


def p(s: str = "") -> None:
    OUT_LINES.append(s)


def ann(mask: pd.Series, ret: pd.Series) -> float:
    """择时年化：mask.shift(1) → T+1 执行；空仓日记 0 收益。与原脚本逐字一致。"""
    in_mkt = mask.shift(1).fillna(False).values
    rh = np.where(in_mkt, ret.values, 0.0)
    rh = rh[~np.isnan(rh)]
    if len(rh) == 0:
        return float("nan")
    t = (1 + rh).prod() - 1
    yrs = len(ret) / 250.0
    return (1 + t) ** (1 / yrs) - 1 if t > -1 else -1.0


def signals_of(d: pd.DataFrame) -> dict:
    """三条规则，参数与 Phase2/3 完全一致。"""
    d["ma60"] = d["close"].rolling(60).mean()
    d["rs"] = d["close"] / d["mkt_close"]
    d["rs_mom"] = d["rs"] / d["rs"].shift(60) - 1
    d["amount_ma60"] = d["amount"].rolling(60).mean()
    d["amount_ratio"] = d["amount"] / d["amount_ma60"]
    return {
        "趋势MA60": d["close"] > d["ma60"],
        "相对动量RS_mom>0": d["rs_mom"] > 0,
        "成交额放量>1.2": d["amount_ratio"] > 1.2,
    }


async def load(sf):
    async with sf() as s:
        r = await s.execute(text(
            "SELECT ts_code, trade_date, close, pre_close, pct_chg, amount "
            "FROM etf_daily WHERE ts_code = ANY(:c) ORDER BY ts_code, trade_date"
        ), {"c": list(ETFS.keys())})
        etf_rows = r.fetchall()
        r = await s.execute(text(
            "SELECT trade_date, close FROM index_daily WHERE ts_code = :m ORDER BY trade_date"
        ), {"m": MARKET})
        mkt = pd.DataFrame(r.fetchall(), columns=["trade_date", "close"])
    mkt["trade_date"] = mkt["trade_date"].astype(str).str[:10]
    mkt = mkt.rename(columns={"close": "mkt_close"})
    return etf_rows, mkt


def build(etf_rows, mkt, code: str) -> pd.DataFrame:
    d = pd.DataFrame(
        [(str(r[1])[:10], float(r[2]), float(r[3] or 0), float(r[4] or 0), float(r[5] or 0))
         for r in etf_rows if r[0] == code],
        columns=["trade_date", "close", "pre_close", "pct_chg", "amount"],
    )
    d = d.merge(mkt, on="trade_date", how="inner").sort_values("trade_date").reset_index(drop=True)
    for c in ("close", "mkt_close", "amount", "pct_chg", "pre_close"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["ret"] = d["close"].pct_change()          # 与 Phase2/3 同口径
    d["ret_pc"] = d["pct_chg"] / 100.0          # Tushare 自带涨跌幅（对照）
    return d


async def main() -> None:
    from shared.database.session.connection_pool import get_connection_pool

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    etf_rows, mkt = await load(sf)

    # ---------------------------------------------------------------- 0
    p("=" * 96)
    p("0. 数据质量：ETF 除息跳空检查（指数无分红，ETF 有 → 影响 close.pct_change() 口径）")
    p("=" * 96)
    p(f"{'ETF':<10}{'名称':<16}{'起始':<12}{'行数':>6}{'跳空日数':>9}{'最大偏离':>10}")
    frames = {}
    for code, name in list(ETFS.items()):  # 本节含被剔除项：这里就是剔除依据
        d = build(etf_rows, mkt, code)
        frames[code] = d
        if d.empty:
            p(f"{code:<10}{name:<16}{'无数据':<12}")
            continue
        # close.pct_change() 与 pct_chg 的偏离 > 0.5pp 视为疑似除息/复权跳空
        dev = (d["ret"] - d["ret_pc"]).abs()
        n_gap = int((dev > 0.005).sum())
        p(f"{code:<10}{name:<16}{d['trade_date'].iloc[0]:<12}{len(d):>6}"
          f"{n_gap:>9}{float(dev.max()):>9.4f}")

    # 汇总用：剔除数据被污染的标的
    VALID = {k: v for k, v in ETFS.items() if k not in EXCLUDE}

    # ---------------------------------------------------------------- 1
    p("")
    p("=" * 96)
    p("1. 全样本：三条规则在 ETF 上的择时超额（口径与 Phase2 一致，对照文档指数值）")
    p("=" * 96)
    p(f"{'ETF':<10}{'名称':<15}{'信号':<17}{'择时年化':>9}{'满仓ETF':>9}{'择时超额':>9}"
      f"{'起始日':>12}")
    for code, name in VALID.items():
        d = frames[code]
        if len(d) < MIN_DAYS:
            p(f"{code:<10}{name:<15}（历史 {len(d)} 日 < {MIN_DAYS}，跳过）")
            continue
        sigs = signals_of(d)
        full = ann(pd.Series(True, index=d.index), d["ret"])
        for sn, m in sigs.items():
            a = ann(m, d["ret"])
            p(f"{code:<10}{name:<15}{sn:<17}{a:>8.1%}{full:>9.1%}{a - full:>+8.1%}"
              f"{d['trade_date'].iloc[0]:>12}")
        # 三信号投票（≥2 票）
        votes = sum(m.astype(int) for m in sigs.values())
        a2 = ann(votes >= 2, d["ret"])
        p(f"{code:<10}{name:<15}{'★三信号≥2票':<17}{a2:>8.1%}{full:>9.1%}{a2 - full:>+8.1%}"
          f"{d['trade_date'].iloc[0]:>12}")
        p("")

    # ---------------------------------------------------------------- 2
    p("=" * 96)
    p("2. 滚动起始日：择时超额分布（受 ETF 起始日限制）")
    p("=" * 96)
    p(f"{'ETF':<10}{'信号':<17}" + "".join(f"{s[:4]:>8}" for s in ROLL_STARTS)
      + f"{'下四分':>9}{'中位':>9}{'上四分':>9}")
    p("-" * 96)
    for code, name in VALID.items():
        d = frames[code]
        if len(d) < MIN_DAYS:
            continue
        sigs = signals_of(d)
        sigs["★三信号≥2票"] = sum(m.astype(int) for m in sigs.values()) >= 2
        for sn, mask in sigs.items():
            overs = []
            for st in ROLL_STARTS:
                sub = d[d["trade_date"] >= st].reset_index(drop=True)
                m = mask[d["trade_date"] >= st].reset_index(drop=True)
                if len(sub) < 250:
                    continue
                overs.append(ann(m, sub["ret"]) - ann(pd.Series(True, index=sub.index), sub["ret"]))
            if not overs:
                p(f"{code:<10}{sn:<17}（各起始日样本不足）")
                continue
            q25, med, q75 = np.percentile(overs, [25, 50, 75])
            p(f"{code:<10}{sn:<17}" + "".join(f"{o:>7.1%}" for o in overs)
              + f"{q25:>8.1%}{med:>8.1%}{q75:>8.1%}")
        p("")

    # ---------------------------------------------------------------- 3
    p("=" * 96)
    p("3. 分时代：各区间择时超额（信号只在上表列出的区间内有数据）")
    p("=" * 96)
    for code, name in VALID.items():
        d = frames[code]
        if len(d) < MIN_DAYS:
            continue
        sigs = signals_of(d)
        p(f"[{code} {name}]")
        for a0, a1, label in ERAS:
            sub = d[(d["trade_date"] >= a0) & (d["trade_date"] <= a1)].reset_index(drop=True)
            if len(sub) < 120:
                p(f"   {a0[:7]}~{a1[:7]} {label:<12}（样本 {len(sub)} 日，跳过）")
                continue
            line = f"   {a0[:7]}~{a1[:7]} {label:<12} 满仓={ann(pd.Series(True, index=sub.index), sub['ret']):>7.1%}"
            for sn, mask in sigs.items():
                m = mask[(d["trade_date"] >= a0) & (d["trade_date"] <= a1)].reset_index(drop=True)
                line += f" | {sn}={ann(m, sub['ret']) - ann(pd.Series(True, index=sub.index), sub['ret']):>+6.1%}"
            p(line)
        p("")

    # ---------------------------------------------------------------- 4
    p("=" * 96)
    p("4. bootstrap 显著性（择时 vs 满仓 日收益差，seed=42，与原脚本一致）")
    p("=" * 96)
    rng = np.random.default_rng(42)
    for code, name in VALID.items():
        d = frames[code]
        if len(d) < MIN_DAYS:
            continue
        sigs = signals_of(d)
        for sn, mask in sigs.items():
            in_mkt = mask.shift(1).fillna(False).values
            rh = np.where(in_mkt, d["ret"].values, 0.0)
            diff = rh - d["ret"].values
            diff = diff[~np.isnan(diff)]
            boots = np.mean(rng.choice(diff, size=(3000, len(diff)), replace=True), axis=1)
            pv = float(np.mean(boots <= 0))
            p(f"   {code} {name:<15}{sn:<17} 日差均值={np.mean(diff) * 100:>7.3f}%  P={pv:.4f}")

    # ---------------------------------------------------------------- 5
    p("")
    p("=" * 96)
    p("5. 收益口径对照：close.pct_change() vs pct_chg（验证除息是否影响结论）")
    p("=" * 96)
    for code, name in VALID.items():
        d = frames[code]
        if len(d) < MIN_DAYS:
            continue
        sigs = signals_of(d)
        for sn, mask in sigs.items():
            a1 = ann(mask, d["ret"])
            a2 = ann(mask, d["ret_pc"])
            f1 = ann(pd.Series(True, index=d.index), d["ret"])
            f2 = ann(pd.Series(True, index=d.index), d["ret_pc"])
            p(f"   {code} {sn:<17} 超额(close口径)={a1 - f1:>+7.1%}  "
              f"超额(pct_chg口径)={a2 - f2:>+7.1%}  差={abs((a1 - f1) - (a2 - f2)) * 100:>5.2f}pp")

    # ---------------------------------------------------------------- 6
    p("")
    p("=" * 96)
    p("6. 跨 ETF 汇总（已剔除：%s）" % "、".join(EXCLUDE.keys()))
    p("=" * 96)
    sig_names = ["趋势MA60", "相对动量RS_mom>0", "成交额放量>1.2"]
    roll_by: dict = {sn: {} for sn in sig_names}
    full_by: dict = {sn: {} for sn in sig_names}
    era_by: dict = {sn: {lab: [] for _, _, lab in ERAS} for sn in sig_names}
    boot_by: dict = {sn: [] for sn in sig_names}
    rng2 = np.random.default_rng(42)

    for code, name in VALID.items():
        d = frames[code]
        if d.empty or len(d) < MIN_DAYS:
            continue
        sigs = signals_of(d)
        full = ann(pd.Series(True, index=d.index), d["ret"])
        for sn in sig_names:
            m = sigs[sn]
            full_by[sn][code] = (ann(m, d["ret"]), full, ann(m, d["ret"]) - full)
            overs = []
            for st in ROLL_STARTS:
                sub = d[d["trade_date"] >= st].reset_index(drop=True)
                mm = m[d["trade_date"] >= st].reset_index(drop=True)
                if len(sub) < 250:
                    continue
                overs.append(
                    ann(mm, sub["ret"]) - ann(pd.Series(True, index=sub.index), sub["ret"]))
            roll_by[sn][code] = overs
            for a0, a1, lab in ERAS:
                sub = d[(d["trade_date"] >= a0) & (d["trade_date"] <= a1)].reset_index(drop=True)
                if len(sub) < 120:
                    continue
                mm = m[(d["trade_date"] >= a0) & (d["trade_date"] <= a1)].reset_index(drop=True)
                era_by[sn][lab].append(
                    ann(mm, sub["ret"]) - ann(pd.Series(True, index=sub.index), sub["ret"]))
            rh = np.where(m.shift(1).fillna(False).values, d["ret"].values, 0.0)
            diff = rh - d["ret"].values
            diff = diff[~np.isnan(diff)]
            boots = np.mean(rng2.choice(diff, size=(3000, len(diff)), replace=True), axis=1)
            boot_by[sn].append(float(np.mean(boots <= 0)))

    for sn in sig_names:
        overs_all = [v for vs in roll_by[sn].values() for v in vs]
        q25, med, q75 = np.percentile(overs_all, [25, 50, 75])
        full_overs = [v[2] for v in full_by[sn].values()]
        timings = [v[0] for v in full_by[sn].values()]
        q25s = [float(np.percentile(vs, 25)) for vs in roll_by[sn].values() if vs]
        p("")
        p(f"[{sn}]  ETF 数={len(full_overs)}")
        p(f"   全样本超额: 中位 {np.median(full_overs):+.1%}  最小 {min(full_overs):+.1%}  "
          f"最大 {max(full_overs):+.1%}  为正比例 {np.mean([v > 0 for v in full_overs]):.0%}")
        p(f"   全样本择时年化: 中位 {np.median(timings):+.1%}   （立项书 P1 验收线 ≥15%）")
        p(f"   滚动超额(ETF×起始日 pooled, n={len(overs_all)}): 下四分 {q25:+.1%}  "
          f"中位 {med:+.1%}  上四分 {q75:+.1%}  |  各 ETF 下四分最小值 {min(q25s):+.1%}")
        p(f"   bootstrap P: 中位 {np.median(boot_by[sn]):.3f}  最小 {min(boot_by[sn]):.3f}")
        for _, _, lab in ERAS:
            vs = era_by[sn][lab]
            if vs:
                p(f"   分时代 {lab:<12} 超额中位 {np.median(vs):+.1%}  "
                  f"为正占比 {np.mean([v > 0 for v in vs]):.0%}  (n={len(vs)})")

    # ---------------------------------------------------------------- 7
    p("")
    p("=" * 96)
    p("7. 验收判定（超额线：滚动中位 ≥8% 且 各 ETF 下四分 >0；绝对线：择时年化中位 ≥15%）")
    p("=" * 96)
    for sn in sig_names:
        overs_all = [v for vs in roll_by[sn].values() for v in vs]
        med = float(np.median(overs_all))
        q25s = [float(np.percentile(vs, 25)) for vs in roll_by[sn].values() if vs]
        timings = [v[0] for v in full_by[sn].values()]
        ok_roll = (med >= 0.08) and (min(q25s) > 0)
        ok_abs = float(np.median(timings)) >= 0.15
        p(f"   {sn:<17} 滚动中位 {med:+.1%}(≥8%? {str(med >= 0.08):<5})  "
          f"下四分最小 {min(q25s):+.1%}(>0? {str(min(q25s) > 0):<5})  "
          f"年化中位 {np.median(timings):+.1%}(≥15%? {str(ok_abs):<5})  "
          f"→ 超额 {'通过' if ok_roll else '不通过'} / 绝对 {'通过' if ok_abs else '不通过'}")


if __name__ == "__main__":
    import os

    try:
        asyncio.run(main())
    except Exception as e:  # noqa: BLE001
        import traceback

        OUT_LINES.append("[FATAL] " + repr(e))
        OUT_LINES.append(traceback.format_exc()[:2500])
    os.makedirs("logs", exist_ok=True)
    with open("logs/_p4_etf_verify.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(OUT_LINES))
    print("OK -> logs/_p4_etf_verify.txt (%d lines)" % len(OUT_LINES))
