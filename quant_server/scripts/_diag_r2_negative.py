# -*- coding: utf-8 -*-
"""一次性诊断：负 R² 导致「下跌标的拿到正动量分」的符号翻转有多普遍（不提交）。

用 DB 实盘版代码的 `_calc_momentum_score`，对全部 29 只池内 ETF 的历史逐日扫描，
统计 r2<0 的发生率，以及由此产生的「年化为负、得分却为正」的假阳性。
"""
import asyncio
import importlib.util
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")


def load_cls():
    spec = importlib.util.spec_from_file_location("db_cm", "logs/_db_code_0911.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.CrossMarketMomentumStrategy


async def main() -> None:
    from sqlalchemy import text
    from shared.database.session.connection_pool import get_connection_pool

    strat = load_cls()(name="r2扫描")
    etfs = list(strat.global_pool) + list(strat.china_pool)
    LB = strat.lookback_days

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()
    async with sf() as s:
        r = await s.execute(text("""
            SELECT e.ts_code, e.trade_date::text,
                   e.close * f.adj_factor / lf.latest_factor AS close
            FROM etf_daily e
            LEFT JOIN fund_adj_factor f
              ON f.ts_code = e.ts_code AND f.trade_date = e.trade_date
            LEFT JOIN (SELECT DISTINCT ON (ts_code) ts_code, adj_factor AS latest_factor
                       FROM fund_adj_factor ORDER BY ts_code, trade_date DESC) lf
              ON lf.ts_code = e.ts_code
            WHERE e.ts_code = ANY(:c) AND e.trade_date >= '2020-06-01'
            ORDER BY e.ts_code, e.trade_date"""), {"c": etfs})
        df = pd.DataFrame(r.fetchall(), columns=["code", "d", "close"])
    await pool.close()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    tot = neg = flip = neg_and_pass = 0
    worst = []
    for code, g in df.groupby("code"):
        c = g["close"].to_numpy(dtype=np.float64)
        for i in range(LB, len(c)):
            score, ann, r2 = strat._calc_momentum_score(c[: i + 1], LB)
            if score is None:
                continue
            tot += 1
            if r2 < 0:
                neg += 1
                if ann < 0 and score > 0:
                    flip += 1
                    if strat.min_score_threshold <= score <= strat.max_score_threshold:
                        neg_and_pass += 1
                worst.append((score, ann, r2, code, g["d"].iloc[i]))

    print("=" * 92)
    print(f"扫描：{len(etfs)} 只池内 ETF，2020-06 ~ 2026-09-11，共 {tot:,} 个 (标的,日) 样本")
    print("=" * 92)
    print(f"  r2 < 0 的样本            : {neg:>8,}  ({neg / tot:.2%})")
    print(f"  其中「年化为负 且 得分>0」: {flip:>8,}  ({flip / tot:.2%})  ← 符号翻转")
    print(f"  其中还通过了动量门        : {neg_and_pass:>8,}  ({neg_and_pass / tot:.2%})")
    print()
    if worst:
        worst.sort(key=lambda x: -x[0])
        print("  翻转后得分最高的 10 例（本应被排除的下跌标的）：")
        print(f"  {'标的':<11}{'日期':<13}{'得分':>10}{'年化':>12}{'R²':>10}")
        for sc, ann, r2, code, d in worst[:10]:
            print(f"  {code:<11}{str(d):<13}{sc:>10.3f}{ann:>12.2%}{r2:>10.4f}")

    # 09-11 当日全部 29 只
    print()
    print("=" * 92)
    print("  2026-09-11 当日全部 29 只池内 ETF 的 r2 / score")
    print("=" * 92)
    print(f"  {'标的':<11}{'年化':>12}{'R²':>10}{'得分':>10}   备注")
    for code, g in df.groupby("code"):
        c = g["close"].to_numpy(dtype=np.float64)
        if len(c) < LB + 1:
            continue
        score, ann, r2 = strat._calc_momentum_score(c, LB)
        note = ""
        if r2 is not None and r2 < 0:
            note = "⚠ R²<0"
            if ann < 0 and score > 0:
                note += " → 下跌却得正分"
        print(f"  {code:<11}{ann:>12.2%}{r2:>10.4f}{score:>10.3f}   {note}")


if __name__ == "__main__":
    asyncio.run(main())
