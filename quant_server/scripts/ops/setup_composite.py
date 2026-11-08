# -*- coding: utf-8 -*-
"""
实盘组合初始化脚本 — 创建 composite_groups + 绑定共享账户

用法: 在 quant_server 目录下运行
    .venv/Scripts/python.exe scripts/ops/setup_composite.py

功能:
  1. 将 ETF底部 + 低吸 两个策略绑定到共享账户（SHARED_ACCOUNT_ID）
  2. 创建 composite_groups 记录（REGIME_BASE_ALLOCATION + 组合名称）
  3. 初始化各策略 allocated_capital = 账户余额 × 权重
"""
import argparse
import json
import uuid
from datetime import datetime

import psycopg2


def _parse_env_args() -> str:
    ap = argparse.ArgumentParser(description="实盘组合初始化")
    ap.add_argument("--env", choices=("dev", "prod"), default="dev",
                    help="目标环境（默认 dev；prod 需 --yes-i-mean-prod）")
    ap.add_argument("--yes-i-mean-prod", action="store_true",
                    help="确认对生产环境执行组合/账户变更")
    args = ap.parse_args()
    if args.env == "prod" and not args.yes_i_mean_prod:
        raise SystemExit("拒绝：--env prod 需同时传 --yes-i-mean-prod")
    return args.env


def _db_config(env: str) -> dict:
    from shared.config.config_manager import DatabaseSettings, resolve_database_env
    base = DatabaseSettings().model_dump()
    values, missing = resolve_database_env(
        "development" if env == "dev" else "production", base
    )
    if env == "prod" and missing:
        raise SystemExit(f"拒绝：生产 DB 配置缺失 {missing}")
    return {
        "host": values["HOST"], "port": values["PORT"],
        "user": values["USER"], "password": values["PASSWORD"],
        "database": values["NAME"],
    }


def _assert_role(cur, env: str) -> None:
    expected = "quant_dev" if env == "dev" else "quant_prod"
    cur.execute("SELECT current_user, current_setting('search_path')")
    user, path = cur.fetchone()
    if user != expected:
        raise SystemExit(f"拒绝：{env} 环境应以 {expected} 连接，实际 {user}")
    compact = (path or "").replace(" ", "")
    if env == "dev" and not compact.startswith("dev"):
        raise SystemExit(f"拒绝：dev 的 search_path 为 {path!r}")
    if env == "prod" and not compact.startswith("public"):
        raise SystemExit(f"拒绝：prod 的 search_path 为 {path!r}")

# 组合配置
COMPOSITE_NAME = "进攻防御组合"
STRATEGIES = [
    {"strategy_id": "5277a1fc-a747-4f33-bb95-8056d1e56e24", "allocator_id": "etf_bottom"},
    {"strategy_id": "1b6b57a8-d58c-499f-a5fe-7d8c0c91f5a7", "allocator_id": "stock_low_high"},
]
# 共享账户（资金池）。当前用低吸账户 84d81a14（余额 ~10044）。
# 若想用新账户/合并资金，改这里并在账户层面合并余额。
SHARED_ACCOUNT_ID = "84d81a14-5f0f-4741-b868-92961863ac3a"

REGIME_BASE_ALLOCATION = {
    "0": {"etf_bottom": 0.8, "stock_low_high": 0.2},  # 熊市防御
    "1": {"etf_bottom": 0.5, "stock_low_high": 0.5},  # 震荡均衡
    "2": {"etf_bottom": 0.2, "stock_low_high": 0.8},  # 牛市进攻
}


def main() -> None:
    env = _parse_env_args()
    conn = psycopg2.connect(**_db_config(env))
    conn.autocommit = True
    cur = conn.cursor()
    _assert_role(cur, env)

    # 1. 获取共享账户余额
    cur.execute("SELECT total_balance FROM accounts WHERE id = %s", (SHARED_ACCOUNT_ID,))
    row = cur.fetchone()
    if not row:
        print(f"[错误] 共享账户不存在: {SHARED_ACCOUNT_ID}")
        return
    account_total = float(row[0] or 0)
    print(f"共享账户余额: {account_total:,.0f}")

    # 2. 将两策略绑定到共享账户
    for cfg in STRATEGIES:
        cur.execute(
            "UPDATE strategies SET account_id = %s, updated_at = %s WHERE id = %s",
            (SHARED_ACCOUNT_ID, datetime.now(), cfg["strategy_id"]),
        )
        print(f"策略 {cfg['strategy_id'][:8]} → account {SHARED_ACCOUNT_ID[:8]}")

    # 3. 创建组合分组（幂等：若已存在同名组合则跳过）
    cur.execute("SELECT id FROM composite_groups WHERE name = %s", (COMPOSITE_NAME,))
    existing = cur.fetchone()
    if existing:
        print(f"组合已存在: {existing[0]}, 跳过创建")
        gid = existing[0]
    else:
        gid = str(uuid.uuid4())
        alloc_config = {
            "REGIME_BASE_ALLOCATION": REGIME_BASE_ALLOCATION,
            "risk_parity_enabled": False,
            "rp_blend_strength": 0.3,
            "rp_rebalance_freq": "monthly",
        }
        cur.execute(
            """
            INSERT INTO composite_groups
            (id, name, account_id, strategy_ids, allocator_config,
             current_regime, current_allocation, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', %s, %s)
            """,
            (
                gid, COMPOSITE_NAME, SHARED_ACCOUNT_ID,
                json.dumps(STRATEGIES), json.dumps(alloc_config),
                1,  # 初始 RANGE
                json.dumps(REGIME_BASE_ALLOCATION["1"]),
                datetime.now(), datetime.now(),
            ),
        )
        print(f"组合已创建: {gid} ({COMPOSITE_NAME})")

    # 4. 初始化各策略 allocated_capital = 账户余额 × 权重 + 设置 composite_group_id 反向引用
    for cfg in STRATEGIES:
        weight = float(REGIME_BASE_ALLOCATION["1"][cfg["allocator_id"]])
        target = max(10000.0, account_total * weight)
        cur.execute(
            "UPDATE strategies SET allocated_capital = %s, composite_group_id = %s, updated_at = %s WHERE id = %s",
            (target, gid, datetime.now(), cfg["strategy_id"]),
        )
        print(f"策略 {cfg['strategy_id'][:8]} allocated_capital = {target:,.0f} (权重 {weight:.0%})")

    cur.close()
    conn.close()
    print("\n组合初始化完成。重启服务后，每日数据同步(20:00)将自动执行组合 rebalance。")


if __name__ == "__main__":
    main()
