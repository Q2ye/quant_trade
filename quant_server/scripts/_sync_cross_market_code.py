# -*- coding: utf-8 -*-
"""同步 cross_market 策略磁盘代码 → 全部 4 处 DB code 副本。

副本位置：
  - strategy_templates.code_template（内置模板 2161ce9c，用户「创建实例」从这里复制）
  - strategies.code（模板镜像 abe789ce + 实例 -1/-2）

不带 --apply 只查；带 --apply 执行 UPDATE。
执行: cd quant_server && .venv/Scripts/python.exe scripts/_sync_cross_market_code.py [--apply]
"""
import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

from shared.database.session.connection_pool import get_connection_pool

DISK_PATH = Path("modules/strategy/strategies/rotation/cross_market_momentum_strategy.py")


async def main(apply: bool) -> None:
    code = DISK_PATH.read_text(encoding="utf-8")
    print(f"[磁盘] 代码长度 = {len(code)} 字符")

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    async with sf() as s:
        # 1. strategies 表（code 字段）
        rows = (await s.execute(text(
            "SELECT id, name, length(code) FROM strategies "
            "WHERE name ILIKE '%cross%' OR name ILIKE '%跨市场%' "
            "   OR name ILIKE '%动量避险%' OR code LIKE '%CrossMarketMomentumStrategy%'"
            "ORDER BY name"
        ))).fetchall()
        print(f"[strategies] {len(rows)} 条:")
        for r in rows:
            print(f"  id={r[0]}  name={r[1]}  code_len={r[2]}")
        if apply:
            for r in rows:
                await s.execute(
                    text("UPDATE strategies SET code = :c, updated_at = NOW() WHERE id = :id"),
                    {"c": code, "id": r[0]},
                )
                print(f"  [已更新] {r[1]} ({r[0]})")

        # 2. strategy_templates 表（code_template 字段）
        trows = (await s.execute(text(
            "SELECT id, template_name, length(code_template) FROM strategy_templates "
            "WHERE template_name ILIKE '%cross%' OR template_name ILIKE '%跨市场%' "
            "   OR template_name ILIKE '%动量避险%' OR code_template LIKE '%CrossMarketMomentumStrategy%'"
            "ORDER BY template_name"
        ))).fetchall()
        print(f"[strategy_templates] {len(trows)} 条:")
        for r in trows:
            print(f"  id={r[0]}  name={r[1]}  code_len={r[2]}")
        if apply:
            for r in trows:
                await s.execute(
                    text("UPDATE strategy_templates SET code_template = :c, updated_at = NOW() WHERE id = :id"),
                    {"c": code, "id": r[0]},
                )
                print(f"  [已更新模板] {r[1]} ({r[0]})")

        if apply:
            await s.commit()
            print("[完成] 已同步全部副本")
        else:
            print("[提示] 未带 --apply，仅查询。确认后加 --apply 执行更新。")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main(apply="--apply" in sys.argv))
