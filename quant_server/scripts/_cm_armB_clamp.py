# -*- coding: utf-8 -*-
"""方案 B 对照：保留原 R² 公式，仅把负值夹到 0（不提交）。

目的：验证「代价近乎为零」的修法 —— 正 R² 逐位不变（r2_threshold=0.47 的含义不变），
      只消除负 R² 导致的符号翻转。与 A 臂（教科书 WLS R²）对比。
"""
import json
import subprocess
import sys
import time

import requests

BASE = "http://localhost:8080/quantTrade"
REL = "quant_server/modules/strategy/strategies/rotation/cross_market_momentum_strategy.py"
NAME = "跨市场-R²夹零-验证"
START, END = "2019-06-01", "2026-09-12"

OLD_R2 = """        ss_res = float(np.sum(weights * (y - y_pred) ** 2))
        ss_tot = float(np.sum(weights * (y - float(np.mean(y))) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0"""
NEW_R2 = """        ss_res = float(np.sum(weights * (y - y_pred) ** 2))
        ss_tot = float(np.sum(weights * (y - float(np.mean(y))) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        # 负 R² 在「样本内 + 带截距」的回归里物理上不可能（此处加权口径不一致所致）。
        # 而 score = 年化 × R²，负 R² 与负年化相乘得**正**分，会让下跌标的通过
        # `raw_score >= 0` 的动量门（实测 2.83% 样本）。夹到 0 即可消除该符号翻转，
        # 且**所有正 R² 逐位不变** → r2_threshold 的标定含义不受影响。
        r2 = max(0.0, r2)"""

ARMS = {"原始基线": {"total_return": 10.1382, "annual_return": 0.4100, "sharpe_ratio": 1.4219,
                     "max_drawdown": 0.2518, "num_trades": 719},
        "旧R²重跑": {"total_return": 10.2274, "annual_return": 0.4113, "sharpe_ratio": 1.4260,
                     "max_drawdown": 0.2518, "num_trades": 719},
        "A·全W口径": {"total_return": 4.6672, "annual_return": 0.2803, "sharpe_ratio": 1.0245,
                      "max_drawdown": 0.3917, "num_trades": 725}}


def main() -> None:
    code_old = subprocess.run(["git", "show", f"HEAD:{REL}"],
                              capture_output=True, cwd="..").stdout.decode("utf-8")
    assert OLD_R2 in code_old, "未在 HEAD 代码中定位到 R² 公式片段"
    code_b = code_old.replace(OLD_R2, NEW_R2)
    print(f"B 臂代码: {len(code_b)} 字符（原 {len(code_old)}，+{len(code_b) - len(code_old)}）")
    assert "r2 = max(0.0, r2)" in code_b

    r = requests.post(f"{BASE}/strategy", json={
        "name": NAME, "description": "方案B：保留原公式，仅夹零负 R²",
        "strategy_type": "rotation", "class_name": "CrossMarketMomentumStrategy",
        "code": code_b, "parameters": {}}, timeout=120)
    print(f"[1] 建实例 HTTP {r.status_code} {json.dumps(r.json(), ensure_ascii=False)[:180]}")
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

    ARMS["B·夹零"] = res
    print("\n" + "=" * 108)
    hdr = f"  {'指标':<14}" + "".join(f"{k:>17}" for k in ARMS)
    print(hdr); print("=" * 108)
    for key, lab in (("total_return", "总收益"), ("annual_return", "年化"),
                     ("sharpe_ratio", "夏普"), ("max_drawdown", "最大回撤"),
                     ("num_trades", "交易数")):
        print(f"  {lab:<14}" + "".join(
            f"{a.get(key):>17.4f}" if isinstance(a.get(key), (int, float)) else f"{'--':>17}"
            for a in ARMS.values()))
    print(f"\n  B 臂其它: {json.dumps({k: res.get(k) for k in ('win_rate','profit_factor','calmar_ratio')}, ensure_ascii=False)}")
    print(f"\n  task_id={tid}  strategy_id={sid}")


if __name__ == "__main__":
    main()
