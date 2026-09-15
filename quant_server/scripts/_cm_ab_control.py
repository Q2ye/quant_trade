# -*- coding: utf-8 -*-
"""对照实验：用 HEAD（旧 R²）代码新建实例，跑与修复版**完全相同**的回测（不提交）。

用途：排除「数据变更污染基线复现性」这一混淆项。
若旧代码今日重跑 ≈ 1013.82%，则修复版 466.72% 的差异可归因于 R² 修复本身；
若不复现，则说明基线已不可比，需重新取当轮对照。
"""
import json
import subprocess
import sys
import time

import requests

BASE = "http://localhost:8080/quantTrade"
REL = "quant_server/modules/strategy/strategies/rotation/cross_market_momentum_strategy.py"
NEW = "modules/strategy/strategies/rotation/cross_market_momentum_strategy.py"
NAME = "跨市场-旧R²-对照"
START, END = "2019-06-01", "2026-09-12"
BASE_METRICS = {"total_return": 10.1382, "annual_return": 0.4100, "sharpe_ratio": 1.4219,
                "max_drawdown": 0.2518, "num_trades": 719}
# 修复版结果（task bf42496f），用于同表对比
FIXED = {"total_return": 4.6672, "annual_return": 0.2803, "sharpe_ratio": 1.0245,
         "max_drawdown": 0.3917, "num_trades": 725}


def main() -> None:
    old = subprocess.run(["git", "show", f"HEAD:{REL}"], capture_output=True, cwd="..")
    code_old = old.stdout.decode("utf-8")
    code_new = open(NEW, encoding="utf-8").read()
    print(f"HEAD 代码长度 = {len(code_old)}  含修复 = {'np.sum(W * (y - y_bar)' in code_old}")
    print(f"磁盘 代码长度 = {len(code_new)}  含修复 = {'np.sum(W * (y - y_bar)' in code_new}")
    assert "np.sum(W * (y - y_bar)" not in code_old, "HEAD 已含修复，对照无效"

    payload = {"name": NAME, "description": "R² 修复的对照臂：HEAD 旧公式",
               "strategy_type": "rotation",
               "class_name": "CrossMarketMomentumStrategy",
               "code": code_old, "parameters": {}}
    r = requests.post(f"{BASE}/strategy", json=payload, timeout=120)
    print(f"\n[1] 建对照实例 HTTP {r.status_code} {json.dumps(r.json(), ensure_ascii=False)[:200]}")
    sid = (r.json().get("data") or {}).get("id")
    if not sid:
        return
    print(f"    strategy_id = {sid}")

    bt = {"name": f"{NAME}_回测_{START}", "strategy_id": sid,
          "start_date": START, "end_date": END, "initial_capital": 1_000_000.0,
          "commission_rate": 0.0001, "slippage_rate": 0.0001, "symbols": []}
    r = requests.post(f"{BASE}/backtest/tasks", json=bt, timeout=120)
    tid = ((r.json().get("data") or {}).get("task_id"))
    print(f"[2] 提交回测 HTTP {r.status_code}  task_id = {tid}")
    if not tid:
        return

    print("[3] 轮询...")
    for i in range(240):
        time.sleep(5)
        try:
            d = (requests.get(f"{BASE}/backtest/tasks/{tid}", timeout=30).json().get("data") or {})
        except Exception:
            continue
        if i % 6 == 0:
            print(f"    [{i * 5:>4}s] status={d.get('status')} progress={d.get('progress')}")
        if d.get("status") in ("completed", "failed", "cancelled"):
            print(f"    终态: {d.get('status')}  error={d.get('error_message')}")
            break

    res = None
    try:
        j = requests.post(f"{BASE}/backtest/tasks/results/batch",
                          json={"task_ids": [tid]}, timeout=120).json()
        dd = j.get("data")
        if isinstance(dd, list) and dd:
            res = dd[0]
        elif isinstance(dd, dict):
            res = dd if "total_return" in dd else (dd.get("results") or [None])[0]
    except Exception as e:
        print("    batch 失败:", type(e).__name__)
    if not res or "total_return" not in res:
        try:
            res = requests.get(f"{BASE}/backtest/tasks/{tid}/result", timeout=60).json().get("data")
        except Exception as e:
            print("    单取失败:", type(e).__name__)
    if not res or "total_return" not in res:
        print("    取不到结果"); return

    print("\n" + "=" * 104)
    print(f"  {'指标':<16}{'原始基线':>16}{'旧R²·今日重跑':>18}{'修复版':>16}"
          f"{'旧vs原基线':>16}{'修复vs旧':>16}")
    print("=" * 104)
    for k, lab in (("total_return", "总收益"), ("annual_return", "年化"),
                   ("sharpe_ratio", "夏普"), ("max_drawdown", "最大回撤"),
                   ("num_trades", "交易数")):
        b, o, fn = BASE_METRICS[k], res.get(k), FIXED[k]
        if o is None:
            print(f"  {lab:<16}{b:>16.4f}{'--':>18}{fn:>16.4f}"); continue
        print(f"  {lab:<16}{b:>16.4f}{o:>18.4f}{fn:>16.4f}{o - b:>+16.4f}{fn - o:>+16.4f}")
    print(f"\n  旧R²今日重跑其它: "
          f"{json.dumps({k: res.get(k) for k in ('win_rate','profit_factor','calmar_ratio')}, ensure_ascii=False)}")
    print(f"\n  task_id={tid}  strategy_id={sid}")


if __name__ == "__main__":
    main()
