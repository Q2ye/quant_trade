# -*- coding: utf-8 -*-
"""修复后最终状态快照（只读）。"""
import asyncio
from sqlalchemy import text
OUT = "logs/_final_state_0914.txt"
B = []
async def main():
    from shared.database.session.connection_pool import get_connection_pool
    p = get_connection_pool()
    try:
        sf = p.get_session_factory()
    except RuntimeError:
        await p.initialize(); sf = p.get_session_factory()
    async with sf() as s:
        B.append("[positions 修复后]")
        for r in (await s.execute(text(
            "SELECT ts_code, volume, cost_price, last_price, market_value, pnl, pnl_rate "
            "FROM positions WHERE COALESCE(volume,0)<>0 ORDER BY ts_code"))).mappings().all():
            B.append("  %-11s vol=%6d 成本=%.4f 现价=%.4f 市值=%11.2f 盈亏=%9.2f (%.2f%%)" % (
                r["ts_code"], r["volume"], float(r["cost_price"]), float(r["last_price"]),
                float(r["market_value"]), float(r["pnl"]), float(r["pnl_rate"])))
        B.append("\n[live 策略 allocated_capital]")
        for r in (await s.execute(text(
            "SELECT id::text, name, status, allocated_capital, composite_group_id::text gid "
            "FROM strategies WHERE run_mode='live' ORDER BY status, name"))).mappings().all():
            B.append("  %s %-8s alloc=%11.2f group=%-9s %s" % (
                r["id"][:8], r["status"], float(r["allocated_capital"]),
                (r["gid"] or "-")[:8], r["name"]))
        B.append("\n[账户]")
        for r in (await s.execute(text(
            "SELECT account_name, total_balance, available_balance, market_value "
            "FROM accounts WHERE total_balance > 0"))).mappings().all():
            B.append("  %-12s 总=%10.2f 可用=%10.2f 市值=%10.2f" % (
                r["account_name"], float(r["total_balance"]),
                float(r["available_balance"]), float(r["market_value"])))
if __name__ == "__main__":
    import os
    try:
        asyncio.run(main())
    except Exception as e:
        B.append("[FATAL] " + repr(e))
    os.makedirs("logs", exist_ok=True)
    open(OUT, "w", encoding="utf-8").write("\n".join(B))
    print("OK ->", OUT)
