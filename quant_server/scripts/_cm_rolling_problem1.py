# -*- coding: utf-8 -*-
"""问题1 滚动起始日验证：对 A/B/C 三臂各跑多个起始日，统计分布（不提交）。

依据项目硬性标准：路径依赖型策略禁止单起始日结论，必须看中位数 / 下四分位分布。
固定结束 2026-09-12；起始日覆盖牛/熊/震荡多段行情。

输出：控制台表格 + logs/_rolling_problem1.txt
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
    "A 基线": "101a0d0c-900e-4bf3-b5dc-163466631e88",
    "B +3日跌幅门": "1d356dc2-6439-4484-9ad9-70cbefa5bea6",
    "C 三道门全开": "387e4227-06ac-4599-81e1-d9c2bd7fddd3",
}
KEYS = ("total_return", "annual_return", "sharpe_ratio", "max_drawdown",
        "num_trades", "win_rate", "profit_factor")
OUT = "logs/_rolling_problem1.txt"
_lines: list = []


def p(m: str = "") -> None:
    print(m, flush=True)
    _lines.append(m)


def submit(sid: str, start: str, tag: str) -> str | None:
    r = requests.post(f"{BASE}/backtest/tasks", json={
        "name": f"问题1滚动-{tag}-{start}", "strategy_id": sid,
        "start_date": start, "end_date": END, "initial_capital": 1_000_000.0,
        "commission_rate": 0.0001, "slippage_rate": 0.0001, "symbols": []}, timeout=120)
    if r.status_code != 201:
        p(f"    !! 提交失败 {tag} {start}: HTTP {r.status_code} {r.text[:120]}")
        return None
    return ((r.json().get("data") or {}).get("task_id"))


def fetch(tid: str) -> dict | None:
    try:
        dd = requests.post(f"{BASE}/backtest/tasks/results/batch",
                           json={"task_ids": [tid]}, timeout=120).json().get("data")
        if isinstance(dd, list) and dd:
            return dd[0]
        if isinstance(dd, dict):
            return dd if "total_return" in dd else (dd.get("results") or [None])[0]
    except Exception:
        pass
    try:
        return requests.get(f"{BASE}/backtest/tasks/{tid}/result", timeout=60).json().get("data")
    except Exception:
        return None


def main() -> None:
    tasks = {}
    p(f"提交 {len(ARMS)} 臂 × {len(STARTS)} 起始日 = {len(ARMS) * len(STARTS)} 个回测，结束日 {END}")
    for tag, sid in ARMS.items():
        for s in STARTS:
            tid = submit(sid, s, tag.replace(" ", ""))
            if tid:
                tasks[(tag, s)] = tid
                p(f"  提交 {tag:<14} start={s}  task={tid[:8]}")
    p(f"\n共提交 {len(tasks)} 个，开始轮询（回测池 3 并发）...")

    done = {}
    for i in range(400):
        time.sleep(15)
        pend = [k for k in tasks if k not in done]
        if not pend:
            break
        for k in list(pend):
            tid = tasks[k]
            try:
                d = (requests.get(f"{BASE}/backtest/tasks/{tid}", timeout=30).json().get("data") or {})
            except Exception:
                continue
            st = d.get("status")
            if st in ("completed", "failed", "cancelled"):
                if st == "completed":
                    res = fetch(tid)
                    if res and "total_return" in res:
                        done[k] = res
                    else:
                        p(f"  !! {k} 完成但取不到结果")
                else:
                    p(f"  !! {k} 终态 {st}: {d.get('error_message')}")
                pend.remove(k) if k in pend else None
        if i % 4 == 0:
            p(f"  [{i * 15:>4}s] 已完成 {len(done)}/{len(tasks)}")

    # ---- 汇总 ----
    for key, lab, fmt in (("total_return", "总收益", ".2%"), ("sharpe_ratio", "夏普", ".3f"),
                          ("max_drawdown", "最大回撤", ".2%"), ("num_trades", "交易数", ".0f"),
                          ("profit_factor", "盈亏比", ".3f")):
        p("")
        p("=" * 96)
        p(f"  {lab}（{len(STARTS)} 个起始日，结束 {END}）")
        p("=" * 96)
        p(f"  {'起始日':<14}" + "".join(f"{t:>22}" for t in ARMS))
        for s in STARTS:
            row = f"  {s:<14}"
            for t in ARMS:
                v = (done.get((t, s)) or {}).get(key)
                row += f"{format(v, fmt):>22}" if isinstance(v, (int, float)) else f"{'--':>22}"
            p(row)
        p(f"  {'--- 统计 ---':<14}" + "".join(f"{'':>22}" for _ in ARMS))
        for name, fn in (("中位数", statistics.median), ("均值", statistics.mean),
                         ("下四分位", lambda xs: statistics.quantiles(xs, n=4)[0]),
                         ("最小", min), ("最大", max)):
            row = f"  {name:<14}"
            for t in ARMS:
                xs = [done[(t, s)][key] for s in STARTS if (t, s) in done and key in done[(t, s)]]
                row += f"{format(fn(xs), fmt):>22}" if xs else f"{'--':>22}"
            p(row)

    p("")
    p("=" * 96)
    p("  逐起始日明细")
    p("=" * 96)
    p(f"  {'起始日':<14}{'臂':<16}{'收益':>12}{'年化':>10}{'夏普':>9}{'MDD':>10}{'笔数':>7}{'胜率':>9}{'盈亏比':>9}")
    for s in STARTS:
        for t in ARMS:
            r = done.get((t, s))
            if not r:
                p(f"  {s:<14}{t:<16}{'--':>12}"); continue
            p(f"  {s:<14}{t:<16}{r['total_return']:>12.2%}{r['annual_return']:>10.2%}"
              f"{r['sharpe_ratio']:>9.3f}{r['max_drawdown']:>10.2%}{r['num_trades']:>7.0f}"
              f"{r['win_rate']:>9.2%}{r['profit_factor']:>9.3f}")

    open(OUT, "w", encoding="utf-8").write("\n".join(_lines))
    p(f"\n[已写入 {OUT}]  task ids: " + json.dumps(
        {f"{k[0]}|{k[1]}": v[:8] for k, v in tasks.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
