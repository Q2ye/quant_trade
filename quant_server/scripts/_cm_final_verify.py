# -*- coding: utf-8 -*-
"""终验：用**最终磁盘文件**新建实例跑正式回测，与全部对照臂对比（不提交）。

预期：与「旧R²重跑」逐位相同（因为正 R² 逐位不变，负 R² 样本从未登顶）。
"""
import json
import sys
import time

import requests

BASE = "http://localhost:8080/quantTrade"
SRC = "modules/strategy/strategies/rotation/cross_market_momentum_strategy.py"
NAME = "跨市场-R²夹零-终验"
START, END = "2019-06-01", "2026-09-12"

ARMS = {
    "原始基线": {"total_return": 10.1382, "annual_return": 0.4100, "sharpe_ratio": 1.4219,
                 "max_drawdown": 0.2518, "num_trades": 719},
    "旧R²重跑": {"total_return": 10.2274, "annual_return": 0.4113, "sharpe_ratio": 1.4260,
                 "max_drawdown": 0.2518, "num_trades": 719},
    "A·全W口径": {"total_return": 4.6672, "annual_return": 0.2803, "sharpe_ratio": 1.0245,
                  "max_drawdown": 0.3917, "num_trades": 725},
    "B·夹零(拼码)": {"total_return": 10.2274, "annual_return": 0.4113, "sharpe_ratio": 1.4260,
                     "max_drawdown": 0.2518, "num_trades": 719},
}


def main() -> None:
    code = open(SRC, encoding="utf-8").read()
    assert "r2 = max(0.0, r2)" in code, "最终文件未含夹零补丁"
    assert "np.sum(W * (y - y_bar)" not in code, "最终文件仍含 A 臂公式"
    print(f"最终文件 {SRC}\n  长度={len(code)}  夹零补丁=True  A臂公式=已移除")

    r = requests.post(f"{BASE}/strategy", json={
        "name": NAME, "description": "R² 夹零修法的终验（用最终磁盘文件）",
        "strategy_type": "rotation", "class_name": "CrossMarketMomentumStrategy",
        "code": code, "parameters": {}}, timeout=120)
    print(f"[1] 建实例 HTTP {r.status_code} {json.dumps(r.json(), ensure_ascii=False)[:170]}")
    sid = (r.json().get("data") or {}).get("id")
    if not sid:
        return
    print(f"    strategy_id = {sid}")

    r = requests.post(f"{BASE}/backtest/tasks", json={
        "name": f"{NAME}_回测_{START}", "strategy_id": sid, "start_date": START,
        "end_date": END, "initial_capital": 1_000_000.0,
        "commission_rate": 0.0001, "slippage_rate": 0.0001, "symbols": []}, timeout=120)
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
        dd = requests.post(f"{BASE}/backtest/tasks/results/batch",
                           json={"task_ids": [tid]}, timeout=120).json().get("data")
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

    ARMS["★终验"] = res
    print("\n" + "=" * 118)
    print(f"  {'指标':<14}" + "".join(f"{k:>20}" for k in ARMS))
    print("=" * 118)
    for key, lab in (("total_return", "总收益"), ("annual_return", "年化"),
                     ("sharpe_ratio", "夏普"), ("max_drawdown", "最大回撤"),
                     ("num_trades", "交易数")):
        print(f"  {lab:<14}" + "".join(
            f"{a.get(key):>20.4f}" if isinstance(a.get(key), (int, float)) else f"{'--':>20}"
            for a in ARMS.values()))
    print(f"\n  终验其它: {json.dumps({k: res.get(k) for k in ('win_rate','profit_factor','calmar_ratio')}, ensure_ascii=False)}")

    o, f = ARMS["旧R²重跑"], res
    same = all(o[k] == f.get(k) for k in o)
    print(f"\n  ★ 终验 vs 旧R²重跑 逐位相同: {same}")
    if not same:
        for k in o:
            if o[k] != f.get(k):
                print(f"     差异 {k}: 旧={o[k]}  终验={f.get(k)}")
    print(f"\n  task_id={tid}  strategy_id={sid}")


if __name__ == "__main__":
    main()
