# -*- coding: utf-8 -*-
"""
卫星策略实例 seed（阶段 4d 收尾）

创建两个卫星策略实例并绑定「卫星池」账户（a2fa6e3d...）：
  1. 恐慌抄底-卫星（PanicBottomStrategy，事件型）
  2. 微盘-卫星（MicrocapStrategy，进攻型）

安全约束：
  - run_mode=paper（模拟盘，SIMULATED_TRADING 约束不变）
  - status=draft（不自动运行，由人工确认后启动）
  - execution_mode=semi_auto（信号 → 人工确认 → 执行）
幂等：策略名已存在则跳过。

执行: cd quant_server && .venv/Scripts/python.exe scripts/seed_satellite_strategies.py
"""
import asyncio
import sys
import uuid
from pathlib import Path

SAT_ACCOUNT_NAME = "卫星池"


def _load_env() -> dict:
    env = {}
    p = Path(__file__).resolve().parents[1] / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def _read_strategy_code(rel_path: str) -> str:
    p = Path(__file__).resolve().parents[1] / rel_path
    return p.read_text(encoding="utf-8")


async def main() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    env = _load_env()
    user = env.get("DB_USER", "postgres")
    password = env.get("DB_PASSWORD", "")
    host = env.get("DB_HOST", "localhost")
    port = env.get("DB_PORT", "5432")
    dbname = env.get("DB_DEV_NAME", "quant_signals_dev")
    url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"
    engine = create_async_engine(url)

    strategies = [
        {
            "name": "恐慌抄底-卫星",
            "class_name": "PanicBottomStrategy",
            "module_path_key": "panicbottomstrategy",
            "strategy_type": "event",
            "code_path": "modules/strategy/strategies/panic/panic_bottom_strategy.py",
        },
        {
            "name": "微盘-卫星",
            "class_name": "MicrocapStrategy",
            "module_path_key": "microcapstrategy",
            "strategy_type": "alpha",
            "code_path": "modules/strategy/strategies/microcap/microcap_strategy.py",
        },
    ]

    async with engine.connect() as conn:
        # 卫星账户 + admin 用户
        r = await conn.execute(text(
            "SELECT id FROM accounts WHERE account_name = :n"
        ), {"n": SAT_ACCOUNT_NAME})
        acc = r.fetchone()
        if not acc:
            print("错误: 卫星池账户不存在，先执行 scripts/seed_satellite_account.py")
            await engine.dispose()
            return
        account_id = acc[0]
        r = await conn.execute(text(
            "SELECT id FROM sys_users WHERE role = 'admin' ORDER BY created_at LIMIT 1"
        ))
        urow = r.fetchone()
        if not urow:
            r = await conn.execute(text("SELECT id FROM sys_users ORDER BY created_at LIMIT 1"))
            urow = r.fetchone()
        user_id = urow[0]

        for s in strategies:
            # 幂等检查
            r = await conn.execute(text(
                "SELECT id FROM strategies WHERE name = :n"
            ), {"n": s["name"]})
            if r.fetchone():
                print(f"策略已存在，跳过: {s['name']}")
                continue

            code = _read_strategy_code(s["code_path"])
            module_path = f"strategies.user_{user_id}.{s['module_path_key']}"
            await conn.execute(text("""
                INSERT INTO strategies
                    (id, name, user_id, description, class_name, module_path, strategy_type,
                     code, status, run_mode, execution_mode, account_id, allocated_capital, created_at)
                VALUES
                    (:id, :name, :uid, :desc, :cls, :mp, :stype,
                     :code, 'draft', 'paper', 'semi_auto', :acc, 0, CURRENT_TIMESTAMP)
            """), {
                "id": str(uuid.uuid4()),
                "name": s["name"],
                "uid": user_id,
                "desc": f"卫星池子仓策略（阶段4d seed）：{s['class_name']}，绑定卫星池账户，模拟盘半自动",
                "cls": s["class_name"],
                "mp": module_path,
                "stype": s["strategy_type"],
                "code": code,
                "acc": account_id,
            })
            print(f"策略已创建: {s['name']} (account={account_id}, run_mode=paper, status=draft)")

        await conn.commit()
        # 汇总
        r = await conn.execute(text("""
            SELECT s.name, s.class_name, s.status, s.run_mode, s.account_id, a.account_name
            FROM strategies s LEFT JOIN accounts a ON a.id = s.account_id
            WHERE s.name IN ('恐慌抄底-卫星', '微盘-卫星')
        """))
        print("\n=== 卫星策略实例 ===")
        for row in r.fetchall():
            print(row)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
