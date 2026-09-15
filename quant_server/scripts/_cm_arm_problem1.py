# -*- coding: utf-8 -*-
"""问题1 对照实验：走弱期是否该恢复被跳过的短期风控门（不提交）。

Arm A 基线 : 现行 —— 走弱期跳过 均线/成交量/短期风控        （已测：task d8103e2a）
Arm B 最小 : 走弱期只加回「短期风控」（3 日跌幅门）
Arm C 全量 : 走弱期加回 3 道门（含 _select_targets 的 mainline 均线豁免）

⚠️ 全部 arm 走**独立 draft 实例**，绝不用实盘实例 07651265 跑回测
   （backtest_service 调的是同一个 strategy_manager.load_strategy，可能覆盖进程内实盘状态）。

用法： python scripts/_cm_arm_problem1.py B      （或 C）
"""
import difflib
import json
import sys
import time

import requests

BASE_URL = "http://localhost:8080/quantTrade"
SRC = "modules/strategy/strategies/rotation/cross_market_momentum_strategy.py"
START, END = "2019-06-01", "2026-09-12"

APPLY_GATES = '''        if not self._is_weak:
            steps += [
                ("均线", lambda m: m["passed_ma"], self.enable_ma_filter),
                ("成交量", lambda m: m["passed_volume"], self.enable_volume_check),
                ("短期风控", lambda m: m["passed_loss"], self.enable_loss_filter),
            ]'''

MAINLINE_MA = ('                and (not (self.enable_ma_filter and self._is_weak) '
               'or m["passed_ma"])')

B_APPLY = '''        # [ARM-B] 走弱期也执行「短期风控」门（均线/成交量仍只在正常期）
        steps += [("短期风控", lambda m: m["passed_loss"], self.enable_loss_filter)]
        if not self._is_weak:
            steps += [
                ("均线", lambda m: m["passed_ma"], self.enable_ma_filter),
                ("成交量", lambda m: m["passed_volume"], self.enable_volume_check),
            ]'''

C_APPLY = '''        if True:  # [ARM-C] 走弱期与正常期使用同一套门
            steps += [
                ("均线", lambda m: m["passed_ma"], self.enable_ma_filter),
                ("成交量", lambda m: m["passed_volume"], self.enable_volume_check),
                ("短期风控", lambda m: m["passed_loss"], self.enable_loss_filter),
            ]'''

C_MAINLINE = ('                and (not self.enable_ma_filter or m["passed_ma"])  '
              '# [ARM-C]')

VARIANTS = {
    "B": [(APPLY_GATES, B_APPLY)],
    "C": [(APPLY_GATES, C_APPLY), (MAINLINE_MA, C_MAINLINE)],
}
ARM_LABEL = {"B": "走弱期+3日跌幅门", "C": "走弱期+三道门全开"}


def build(arm: str) -> str:
    code = open(SRC, encoding="utf-8").read()
    for old, new in VARIANTS[arm]:
        assert code.count(old) == 1, f"[{arm}] 替换目标不唯一: {code.count(old)}"
        code = code.replace(old, new)
    compile(code, f"<arm{arm}>", "exec")

    base = open(SRC, encoding="utf-8").read().splitlines()
    diff = [l for l in difflib.unified_diff(base, code.splitlines(), lineterm="", n=1)
            if l[:1] in "+-" and l[:3] not in ("+++", "---")]
    print(f"  [{arm}] 变体长度 {len(code)}（基线 {len(base and open(SRC, encoding='utf-8').read())}）")
    print(f"  [{arm}] 变动行数 = {len(diff)}")
    for l in diff:
        print(f"        {l[:120]}")
    return code


def main() -> None:
    arm = (sys.argv[1] if len(sys.argv) > 1 else "B").upper()
    assert arm in VARIANTS, f"未知 arm: {arm}"
    print(f"构建 Arm {arm}（{ARM_LABEL[arm]}）")
    code = build(arm)

    r = requests.post(f"{BASE_URL}/strategy", json={
        "name": f"跨市场-问题1-{arm}", "description": f"问题1对照 {ARM_LABEL[arm]}",
        "strategy_type": "rotation", "class_name": "CrossMarketMomentumStrategy",
        "code": code, "parameters": {}}, timeout=120)
    print(f"[1] 建实例 HTTP {r.status_code} {json.dumps(r.json(), ensure_ascii=False)[:150]}")
    sid = (r.json().get("data") or {}).get("id")
    if not sid:
        return
    print(f"    strategy_id = {sid}")

    r = requests.post(f"{BASE_URL}/backtest/tasks", json={
        "name": f"跨市场-问题1-{arm}_回测_{START}", "strategy_id": sid,
        "start_date": START, "end_date": END, "initial_capital": 1_000_000.0,
        "commission_rate": 0.0001, "slippage_rate": 0.0001, "symbols": []}, timeout=120)
    tid = ((r.json().get("data") or {}).get("task_id"))
    print(f"[2] 提交回测 HTTP {r.status_code}  task_id = {tid}")
    if not tid:
        return

    print("[3] 轮询...")
    for i in range(150):
        time.sleep(5)
        try:
            d = (requests.get(f"{BASE_URL}/backtest/tasks/{tid}", timeout=30).json().get("data") or {})
        except Exception:
            continue
        if i % 6 == 0:
            print(f"    [{i * 5:>4}s] status={d.get('status')} progress={d.get('progress')}")
        if d.get("status") in ("completed", "failed", "cancelled"):
            print(f"    终态: {d.get('status')}  error={d.get('error_message')}")
            break

    res = None
    try:
        dd = requests.post(f"{BASE_URL}/backtest/tasks/results/batch",
                           json={"task_ids": [tid]}, timeout=120).json().get("data")
        if isinstance(dd, list) and dd:
            res = dd[0]
        elif isinstance(dd, dict):
            res = dd if "total_return" in dd else (dd.get("results") or [None])[0]
    except Exception as e:
        print("    batch 失败:", type(e).__name__)
    if not res or "total_return" not in res:
        try:
            res = requests.get(f"{BASE_URL}/backtest/tasks/{tid}/result", timeout=60).json().get("data")
        except Exception as e:
            print("    单取失败:", type(e).__name__)
    if not res or "total_return" not in res:
        print("    取不到结果"); return

    print(f"\n  Arm {arm} 结果:")
    for k in ("total_return", "annual_return", "sharpe_ratio", "max_drawdown",
              "num_trades", "win_rate", "profit_factor", "calmar_ratio", "volatility"):
        print(f"    {k:<16} = {res.get(k)}")
    print(f"\n  task_id={tid}  strategy_id={sid}")


if __name__ == "__main__":
    main()
