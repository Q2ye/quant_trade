# -*- coding: utf-8 -*-
"""一次性脚本：新建实例（含 R² 修复代码）→ 跑与基线同配置的回测 → 对比（不提交）。

基线：task 020611da（实例 07651265，HEAD 代码），start=2019-06-01 end=2026-09-12
      1013.82% / 夏普 1.4219 / MDD 25.18% / 719 笔

⚠️ 绝不触碰已有实例（实盘 07651265 / 4eab20a9 / draft c297dd4a / f6aa073f），只新建。
"""
import json
import sys
import time

import requests

BASE = "http://localhost:8080/quantTrade"
SRC = "modules/strategy/strategies/rotation/cross_market_momentum_strategy.py"
NAME = "跨市场-R²修复-验证"
START, END = "2019-06-01", "2026-09-12"

BASE_METRICS = {"total_return": 10.1382, "annual_return": 0.4100, "sharpe_ratio": 1.4219,
                "max_drawdown": 0.2518, "num_trades": 719}


def main() -> None:
    code = open(SRC, encoding="utf-8").read()
    has_fix = "np.sum(W * (y - y_bar) ** 2)" in code
    print(f"源码 {SRC}\n 长度={len(code)}  R²修复存在={has_fix}")
    assert has_fix, "源码未包含 R² 修复，终止"

    # ---------- 1. 新建实例 ----------
    payload = {
        "name": NAME,
        "description": "验证 2026-09-13 R² 口径修复；不触碰任何已有实例",
        "strategy_type": "rotation",
        "class_name": "CrossMarketMomentumStrategy",
        "code": code,
        "parameters": {},
    }
    r = requests.post(f"{BASE}/strategy", json=payload, timeout=120)
    print(f"\n[1] 建实例 HTTP {r.status_code}")
    body = r.json()
    print("    ", json.dumps(body, ensure_ascii=False)[:400])
    data = body.get("data") or {}
    sid = data.get("id") or data.get("strategy_id")
    print(f"    新实例 id = {sid}")
    if not sid:
        print("    拿不到 id，终止"); return

    # ---------- 2. 提交回测 ----------
    bt = {"name": f"{NAME}_回测_{START}", "strategy_id": sid,
          "start_date": START, "end_date": END,
          "initial_capital": 1_000_000.0,
          "commission_rate": 0.0001, "slippage_rate": 0.0001, "symbols": []}
    r = requests.post(f"{BASE}/backtest/tasks", json=bt, timeout=120)
    print(f"\n[2] 提交回测 HTTP {r.status_code}")
    b2 = r.json()
    print("    ", json.dumps(b2, ensure_ascii=False)[:300])
    d2 = b2.get("data") or b2
    tid = d2.get("task_id") or d2.get("id")
    print(f"    task_id = {tid}")
    if not tid:
        return

    # ---------- 3. 轮询 ----------
    print("\n[3] 轮询...")
    st = None
    for i in range(200):
        time.sleep(5)
        try:
            r = requests.get(f"{BASE}/backtest/tasks/{tid}", timeout=30)
            if r.status_code != 200:
                continue
            d = (r.json().get("data") or {})
        except Exception as e:
            print(f"    轮询异常: {type(e).__name__}"); continue
        st = d.get("status")
        if i % 6 == 0:
            print(f"    [{i * 5:>4}s] status={st} progress={d.get('progress')}")
        if st in ("completed", "failed", "cancelled"):
            print(f"    终态: {st}  error={d.get('error_message')}")
            break

    # ---------- 4. 取结果 ----------
    res = None
    try:
        r = requests.post(f"{BASE}/backtest/tasks/results/batch",
                          json={"task_ids": [tid]}, timeout=120)
        if r.status_code == 200:
            j = r.json()
            d = j.get("data")
            if isinstance(d, list) and d:
                res = d[0]
            elif isinstance(d, dict):
                res = d.get("results") or d
                if isinstance(res, list) and res:
                    res = res[0]
    except Exception as e:
        print(f"    batch 取结果失败: {type(e).__name__}")
    if not res or not isinstance(res, dict) or "total_return" not in res:
        try:
            r = requests.get(f"{BASE}/backtest/tasks/{tid}/result", timeout=60)
            if r.status_code == 200:
                res = (r.json().get("data") or {})
        except Exception as e:
            print(f"    单取结果失败: {type(e).__name__}")
    if not res or "total_return" not in res:
        print("    取不到结果 —— 用 DB 直查兜底")
        return

    print("\n" + "=" * 96)
    print(f"  {'指标':<16}{'基线(旧R²)':>20}{'修复后':>20}{'变化':>20}")
    print("=" * 96)
    for k, lab in (("total_return", "总收益"), ("annual_return", "年化"),
                   ("sharpe_ratio", "夏普"), ("max_drawdown", "最大回撤"),
                   ("num_trades", "交易数")):
        b, n = BASE_METRICS[k], res.get(k)
        if n is None:
            print(f"  {lab:<16}{b:>20.4f}{'--':>20}{'--':>20}"); continue
        print(f"  {lab:<16}{b:>20.4f}{n:>20.4f}{n - b:>+20.4f}")
    extra = {k: res.get(k) for k in ("win_rate", "profit_factor", "calmar_ratio", "volatility")}
    print(f"\n  其它: {json.dumps(extra, ensure_ascii=False)}")
    n = res.get("total_return")
    if n is not None and abs(n - BASE_METRICS["total_return"]) < 1e-9:
        print("\n  ⚠️ 与基线逐位相同 —— 高度可疑（可能跑到了旧代码，需排查）")
    print(f"\n  task_id={tid}  strategy_id={sid}")


if __name__ == "__main__":
    main()
