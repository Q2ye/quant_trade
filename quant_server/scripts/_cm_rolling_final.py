# -*- coding: utf-8 -*-
"""问题1 滚动起始日 —— 最终收集器（不提交到 git）。

按名称**前缀解析**（兼容两套历史命名），对每个「臂 × 起始日」取任一已完成结果；
真正缺失的组合在 in-flight ≤ 4 时限流补交（回测池上限 10 pending，留足余量）。

用法： python scripts/_cm_rolling_final.py [--submit]
      不带 --submit 只等+汇总，不新提交。
"""
import json
import statistics
import sys
import time

import requests

BASE = "http://localhost:8080/quantTrade"
END = "2026-09-12"
STARTS = ["2019-06-01", "2020-07-01", "2021-09-14",
          "2022-11-01", "2024-01-02", "2025-01-02"]
ARMS = {
    "A": ("A 基线", "101a0d0c-900e-4bf3-b5dc-163466631e88"),
    "B": ("B 加3日跌幅门", "1d356dc2-6439-4484-9ad9-70cbefa5bea6"),
    "C": ("C 三道门全开", "387e4227-06ac-4599-81e1-d9c2bd7fddd3"),
}
KEYS = ("total_return", "annual_return", "sharpe_ratio", "max_drawdown",
        "num_trades", "win_rate", "profit_factor")
OUT = "logs/_rolling_problem1.txt"
SUBMIT = "--submit" in sys.argv
MAX_INFLIGHT = 4
_lines: list = []


def p(m: str = "") -> None:
    print(m, flush=True)
    _lines.append(m)


def arm_of(tname: str):
    """'问题1滚动-B+3日跌幅门-2019-06-01' → ('B','2019-06-01')；不匹配返回 None。"""
    if not tname.startswith("问题1滚动-"):
        return None
    body = tname[len("问题1滚动-"):]
    for s in STARTS:
        if body.endswith("-" + s):
            tag = body[: -(len(s) + 1)]
            k = tag[0].upper()
            if k in ARMS:
                return k, s
    return None


def query():
    import asyncio
    from sqlalchemy import text
    from shared.database.session.connection_pool import get_connection_pool

    async def run():
        pool = get_connection_pool()
        try:
            sf = pool.get_session_factory()
        except RuntimeError:
            await pool.initialize()
            sf = pool.get_session_factory()
        async with sf() as s:
            r = await s.execute(text(
                "SELECT name, id::text, status, result FROM backtest_tasks "
                "WHERE name LIKE '问题1滚动%'"))
            rows = r.fetchall()
        await pool.close()
        return rows

    return asyncio.run(run())


def main() -> None:
    for it in range(400):
        rows = query()
        data, inflight, bad = {}, 0, []
        for n, i, st, res in rows:
            k = arm_of(n)
            if k is None:
                continue
            if st in ("pending", "running"):
                inflight += 1
            elif st == "completed" and res:
                if isinstance(res, str):
                    res = json.loads(res)
                if "total_return" in res:
                    data.setdefault(k, res)          # 任一已完成结果即可
        missing = [(a, s) for a in ARMS for s in STARTS if (a, s) not in data]
        if it % 2 == 0:
            p(f"  [{it * 20:>4}s] 已完成 {len(data)}/18  在途 {inflight}  缺失 {len(missing)}")
        if not missing:
            p("  ✅ 18/18 全部完成")
            break
        if SUBMIT and missing and inflight < MAX_INFLIGHT:
            a, s = missing[0]
            label, sid = ARMS[a]
            try:
                r = requests.post(f"{BASE}/backtest/tasks", json={
                    "name": f"问题1滚动-{a}-{s}", "strategy_id": sid,
                    "start_date": s, "end_date": END, "initial_capital": 1_000_000.0,
                    "commission_rate": 0.0001, "slippage_rate": 0.0001,
                    "symbols": []}, timeout=120)
                ok = r.status_code == 201
                p(f"      补交 {label}/{s} → {'✅ ' + ((r.json().get('data') or {}).get('task_id','')[:8] if ok else f'❌ HTTP {r.status_code}')}")
            except Exception as e:
                p(f"      补交 {label}/{s} 异常 {type(e).__name__}")
        time.sleep(20)

    # ---------- 汇总 ----------
    p("")
    p("=" * 104)
    p(f"  问题1 滚动起始日分布（6 个起始日，结束 {END}）")
    p("=" * 104)
    for key, lab, fmt in (("total_return", "总收益", ".2%"), ("sharpe_ratio", "夏普", ".3f"),
                          ("max_drawdown", "最大回撤", ".2%"), ("num_trades", "交易数", ".0f"),
                          ("profit_factor", "盈亏比", ".3f")):
        p("")
        p(f"  ── {lab} ──")
        p(f"  {'起始日':<14}" + "".join(f"{ARMS[a][0]:>22}" for a in ARMS))
        for s in STARTS:
            row = f"  {s:<14}"
            for a in ARMS:
                v = (data.get((a, s)) or {}).get(key)
                row += f"{format(v, fmt):>22}" if isinstance(v, (int, float)) else f"{'--':>22}"
            p(row)
        for nm, fn in (("中位数", statistics.median), ("均值", statistics.mean),
                       ("下四分位", lambda xs: statistics.quantiles(xs, n=4)[0]),
                       ("最小", min), ("最大", max)):
            row = f"  {nm:<14}"
            for a in ARMS:
                xs = [data[(a, s)][key] for s in STARTS if (a, s) in data]
                row += f"{format(fn(xs), fmt):>22}" if xs else f"{'--':>22}"
            p(row)

    p("")
    p("=" * 104)
    p("  逐组合明细")
    p("=" * 104)
    p(f"  {'起始日':<14}{'臂':<16}{'收益':>12}{'年化':>10}{'夏普':>9}"
      f"{'MDD':>10}{'笔数':>7}{'胜率':>9}{'盈亏比':>9}")
    for s in STARTS:
        for a in ARMS:
            r = data.get((a, s))
            if not r:
                p(f"  {s:<14}{ARMS[a][0]:<16}{'--':>12}"); continue
            p(f"  {s:<14}{ARMS[a][0]:<16}{r['total_return']:>12.2%}{r['annual_return']:>10.2%}"
              f"{r['sharpe_ratio']:>9.3f}{r['max_drawdown']:>10.2%}{r['num_trades']:>7.0f}"
              f"{r['win_rate']:>9.2%}{r['profit_factor']:>9.3f}")

    open(OUT, "w", encoding="utf-8").write("\n".join(_lines))
    p(f"\n[已写入 {OUT}]")


if __name__ == "__main__":
    main()
