# -*- coding: utf-8 -*-
"""
卫星账户 seed（阶段 4a 多账户路由）

创建「卫星池」独立账户（恐慌抄底 + 微盘策略的归属账户），主策略用主账户（默认）。
幂等：账户名已存在则跳过；重复执行安全。

执行: cd quant_server && .venv/Scripts/python.exe scripts/seed_satellite_account.py
"""
import asyncio
import sys
import uuid
from pathlib import Path

SAT_ACCOUNT_NAME = "卫星池"
SAT_ACCOUNT_TYPE = "simulation"   # 卫星池先以 simulation 类型隔离（实盘切换时改）
INITIAL_BALANCE = 0               # 资金由主账户按需划转（铁律1：主/卫星永不互通，由 M4 划转机制处理）


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

    async with engine.connect() as conn:
        # 1. 幂等检查
        r = await conn.execute(text(
            "SELECT id, account_number, account_type FROM accounts WHERE account_name = :n"
        ), {"n": SAT_ACCOUNT_NAME})
        existing = r.fetchone()
        if existing:
            print(f"卫星池账户已存在: id={existing[0]} account_number={existing[1]} type={existing[2]}（跳过）")
            await engine.dispose()
            return

        # 2. 取一个有效 user_id（优先 admin）
        r = await conn.execute(text(
            "SELECT id FROM sys_users WHERE role = 'admin' ORDER BY created_at LIMIT 1"
        ))
        row = r.fetchone()
        if not row:
            r = await conn.execute(text("SELECT id FROM sys_users ORDER BY created_at LIMIT 1"))
            row = r.fetchone()
        if not row:
            print("错误: sys_users 无用户，无法创建账户")
            await engine.dispose()
            return
        user_id = row[0]

        # 3. 创建卫星池账户（幂等防并发：唯一约束 account_name 不存在，直接插入）
        account_id = str(uuid.uuid4())
        account_number = f"SAT-{account_id[:8].upper()}"
        await conn.execute(text("""
            INSERT INTO accounts (id, account_number, account_name, user_id, account_type,
                                  status, total_balance, is_deleted, created_at)
            VALUES (:id, :num, :name, :uid, :atype, 'active', :bal, 0, CURRENT_TIMESTAMP)
        """), {
            "id": account_id, "num": account_number, "name": SAT_ACCOUNT_NAME,
            "uid": user_id, "atype": SAT_ACCOUNT_TYPE, "bal": INITIAL_BALANCE,
        })
        await conn.commit()
        print(f"卫星池账户已创建: id={account_id} account_number={account_number} "
              f"type={SAT_ACCOUNT_TYPE} user_id={user_id}")
        print("下一步：将卫星策略（恐慌抄底/微盘）的 strategies.account_id 指向该账户 ID")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
