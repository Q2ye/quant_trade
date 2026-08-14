# -*- coding: utf-8 -*-
"""
将新策略加入实盘组合 — 更新 composite_groups 的 strategy_ids + allocator_config

用法: 在 quant_server 目录下运行
    .venv/Scripts/python.exe scripts/add_strategy_to_composite.py \
        --group <组合ID> \
        --strategy <策略ID> \
        --allocator <allocator_id> \
        --w0 0.1 --w1 0.2 --w2 0.3

步骤（先手动）:
  1. 通过正常流程启动新策略（run_mode=live），account_id 设为组合的共享账户
  2. 确认策略类型/allocator_id（如 multi_asset）
  3. 决定三种 regime 下的权重（w0=熊市, w1=震荡, w2=牛市），三个权重之和加旧权重 = 1
"""
import argparse
import json
from datetime import datetime

import psycopg2

DB = dict(
    host="localhost", port=5432, user="postgres",
    password="123456", database="quant_signals_dev",
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True, help="组合分组 ID")
    ap.add_argument("--strategy", required=True, help="新策略 ID")
    ap.add_argument("--allocator", required=True, help="allocator_id（权重表的 key）")
    ap.add_argument("--w0", type=float, required=True, help="熊市(0)权重")
    ap.add_argument("--w1", type=float, required=True, help="震荡(1)权重")
    ap.add_argument("--w2", type=float, required=True, help="牛市(2)权重")
    args = ap.parse_args()

    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    cur = conn.cursor()

    # 1. 读组合
    cur.execute("SELECT strategy_ids, allocator_config FROM composite_groups WHERE id = %s", (args.group,))
    row = cur.fetchone()
    if not row:
        print(f"[错误] 组合不存在: {args.group}")
        return
    strategy_ids = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    alloc_config = json.loads(row[1]) if isinstance(row[1], str) else row[1] or {}

    # 2. 检查策略是否已在组合
    if any(c["strategy_id"] == args.strategy for c in strategy_ids):
        print(f"[警告] 策略 {args.strategy} 已在组合中，跳过添加")
        return

    # 3. 新权重（保留旧权重，归一化新权重）
    base = alloc_config.get("REGIME_BASE_ALLOCATION") or {}
    new_weights = {"0": args.w0, "1": args.w1, "2": args.w2}
    # 旧权重按比例缩放，使新旧总和 = 1
    for regime in ("0", "1", "2"):
        old_map = base.get(regime) or {}
        old_total = sum(float(v) for v in old_map.values())
        new_w = new_weights[regime]
        if old_total > 0 and (old_total + new_w) > 1.0:
            scale = (1.0 - new_w) / old_total
            base[regime] = {k: round(float(v) * scale, 4) for k, v in old_map.items()}
        base[regime][args.allocator] = new_w
    alloc_config["REGIME_BASE_ALLOCATION"] = base

    # 4. 更新组合
    strategy_ids.append({"strategy_id": args.strategy, "allocator_id": args.allocator})
    cur.execute(
        "UPDATE composite_groups SET strategy_ids = %s, allocator_config = %s, updated_at = %s WHERE id = %s",
        (json.dumps(strategy_ids), json.dumps(alloc_config), datetime.now(), args.group),
    )
    print(f"策略 {args.strategy} 已加入组合 {args.group}")
    print(f"allocator_id={args.allocator}, 权重: 熊={args.w0} 震荡={args.w1} 牛={args.w2}")
    print(f"更新后 REGIME_BASE_ALLOCATION: {json.dumps(base, ensure_ascii=False)}")

    # 5. 初始化新策略 allocated_capital（按震荡权重 × 账户余额）
    cur.execute("SELECT total_balance FROM accounts WHERE id = (SELECT account_id FROM composite_groups WHERE id = %s)", (args.group,))
    arow = cur.fetchone()
    if arow:
        account_total = float(arow[0] or 0)
        init_cap = max(10000.0, account_total * args.w1)
        cur.execute(
            "UPDATE strategies SET allocated_capital = %s, updated_at = %s WHERE id = %s",
            (init_cap, datetime.now(), args.strategy),
        )
        print(f"新策略 allocated_capital 初始化为 {init_cap:,.0f}（震荡权重×账户余额）")

    cur.close()
    conn.close()
    print("\n完成。下次组合 rebalance（每日22:42或手动触发）会按新权重重算各策略 allocated_capital。")


if __name__ == "__main__":
    main()
