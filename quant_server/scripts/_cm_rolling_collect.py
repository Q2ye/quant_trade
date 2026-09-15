# -*- coding: utf-8 -*-
"""问题1 滚动起始日 —— 幂等收集器（不提交到 git）。

按「臂 × 起始日」对齐 18 个组合：DB 里已有的复用，缺的补交（回测池满则等待重试），
全部完成后输出分布表。可重复执行。
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
    "A_基线": "101a0d0c-900e-4bf3-b5dc-163466631e88",
    "B_加3日跌幅门": "1d356dc2-6439-4484-9ad9-70cbefa5bea6",
    "C_三道门全开": "387e4227-06ac-4599-81e1-d9c2bd7fddd3",
}
KEYS = ("total_return", "annual_return", "sharpe_ratio", "max_drawdown",
        "num_trades", "win_rate", "profit_factor")
OUT = "logs/_rolling_problem1.txt"
_lines: list = []


def p(m: str = "") -> None:
    print(m, flush=True)
    _lines.append(m)


def name(arm: str, s: str) -> str:
    return f"问题1滚动-{arm}-{s}"


def main() -> None:
    from sqlalchemy import text
    from shared.database.session.connection_pool import get_connection_pool
    import asyncio

    async def load():
        pool = get_connection_pool()
        try:
            sf = pool.get_session_factory()
        except RuntimeError:
            await pool.initialize()
            sf = pool.get_session_factory()
        async with sf() as s:
            r = await s.execute(text(
                "SELECT name, id::text, status, result FROM backtest_tasks "
                "WHERE name LIKE '问题1滚动-%'"))
            rows = r.fetchall()
        await pool.close()
        return rows

    def refresh():
        return asyncio.run(load())

    # ---------- 1. 对齐 + 补交 ----------
    for attempt in range(200):
        rows = refresh()
        have = {}
        for n, i, st, res in rows:
            if isinstance(res, str):
                res = json.loads(res)
            have[n] = (i, st, res)
        missing = [(a, s) for a in ARMS for s in STARTS if name(a, s) not in have]
        stuck = [(n, v[0]) for n, v in have.items()
                 if v[1] in ("failed", "cancelled")]
        pending = [n for n, v in have.items() if v[1] in ("pending", "running")]
        if not missing and not stuck:
            p(f"  全部 18 个组合就绪（等待中 {len(pending)}）")
            if not pending:
                break
        if missing:
            p(f"  [{attempt}] 缺 {len(missing)} 个，尝试补交: "
              + ", ".join(f"{a}/{s}" for a, s in missing[:6]))
            for a, s in missing:
                if s == START_SKIP:
                    pass
                try:
                    r = requests.post(f"{BASE}/backtest/tasks", json={
                        "name": name(a, s), "strategy_id": ARMS[a],
                        "start_date": s, "end_date": END, "initial_capital": 1_000_000.0,
                        "commission_rate": 0.0001, "slippage_rate": 0.0001,
                        "symbols": []}, timeout=120)
                    if r.status_code == 201:
                        p(f"      ✅ 补交 {a}/{s} → {(r.json().get('data') or {}).get('task_id','')[:8]}")
                    else:
                        p(f"      ⏳ {a}/{s} 暂不可提交（{r.status_code}）")
                        break
                except Exception as e:
                    p(f"      !! {a}/{s} {type(e).__name__}"); break
        for n, tid in stuck:
            try:
                requests.post(f"{BASE}/backtest/tasks/{tid}/cancel", timeout=30)
                p(f"      取消异常任务 {n}")
            except Exception:
                pass
        time.sleep(20)

    # ---------- 2. 汇总 ----------
    rows = refresh()
    data = {}
    for n, i, st, res in rows:
        if st != "completed" or not res:
            continue
        if isinstance(res, str):
            res = json.loads(res)
        for a in ARMS:
            for s in STARTS:
                if n == name(a, s):
                    data[(a, s)] = res

    p("")
    p(f"已完成组合: {len(data)}/18")
    for key, lab, fmt in (("total_return", "总收益", ".2%"), ("annual_return", "年化", ".2%"),
                          ("sharpe_ratio", "夏普", ".3f"),
                          ("max_drawdown", "最大回撤", ".2%"),
                          ("num_trades", "交易数", ".0f"),
                          ("profit_factor", "盈亏比", ".3f")):
        p("")
        p("=" * 100)
        p(f"  {lab}（{len(STARTS)} 起始日，结束 {END}）")
        p("=" * 100)
        p(f"  {'起始日':<14}" + "".join(f"{a:>24}" for a in ARMS))
        for s in STARTS:
            row = f"  {s:<14}"
            for a in ARMS:
                v = (data.get((a, s)) or {}).get(key)
                row += f"{format(v, fmt):>24}" if isinstance(v, (int, float)) else f"{'--':>24}"
            p(row)
        p(f"  {'── 统计 ──':<14}" + "".join(f"{'':>24}" for _ in ARMS))
        for nm, fn in (("中位数", statistics.median), ("均值", statistics.mean),
                       ("下四分位", lambda xs: statistics.quantiles(xs, n=4)[0]),
                       ("最小", min), ("最大", max)):
            row = f"  {nm:<14}"
            for a in ARMS:
                xs = [data[(a, s)][key] for s in STARTS if (a, s) in data]
                row += f"{format(fn(xs), fmt):>24}" if xs else f"{'--':>24}"
            p(row)

    p("")
    p("=" * 100)
    p("  逐组合明细")
    p("=" * 100)
    p(f"  {'起始日':<14}{'臂':<16}{'收益':>12}{'年化':>10}{'夏普':>9}"
      f"{'MDD':>10}{'笔数':>7}{'胜率':>9}{'盈亏比':>9}")
    for s in STARTS:
        for a in ARMS:
            r = data.get((a, s))
            if not r:
                p(f"  {s:<14}{a:<16}{'--':>12}"); continue
            p(f"  {s:<14}{a:<16}{r['total_return']:>12.2%}{r['annual_return']:>10.2%}"
              f"{r['sharpe_ratio']:>9.3f}{r['max_drawdown']:>10.2%}{r['num_trades']:>7.0f}"
              f"{r['win_rate']:>9.2%}{r['profit_factor']:>9.3f}")

    open(OUT, "w", encoding="utf-8").write("\n".join(_lines))
    p(f"\n[已写入 {OUT}]")


START_SKIP = "__none__"

if __name__ == "__main__":
    main()
