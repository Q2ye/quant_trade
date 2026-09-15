# -*- coding: utf-8 -*-
"""策略实例普查（只读）：按 class × run_mode × status 统计 + live 明细。"""
import asyncio
from sqlalchemy import text
OUT = "logs/_strategy_census.txt"
B = []
async def main():
    from shared.database.session.connection_pool import get_connection_pool
    p = get_connection_pool()
    try:
        sf = p.get_session_factory()
    except RuntimeError:
        await p.initialize(); sf = p.get_session_factory()
    async with sf() as s:
        B.append("[按类 × 运行模式 统计]")
        rows = (await s.execute(text(
            "SELECT class_name, run_mode, COUNT(*) n, "
            "       STRING_AGG(DISTINCT status, '/' ORDER BY status) sts "
            "FROM strategies GROUP BY 1,2 ORDER BY 1,2"))).mappings().all()
        for r in rows:
            B.append("  %-32s %-9s n=%3d  %s" % (r["class_name"], r["run_mode"], r["n"], r["sts"]))
        B.append("\n[live / paper 实例明细]")
        rows = (await s.execute(text(
            "SELECT s.id::text, s.name, s.class_name, s.status, s.run_mode, "
            "       s.allocated_capital, s.account_id::text aid, a.account_name, "
            "       s.composite_group_id::text gid, s.updated_at::text "
            "FROM strategies s LEFT JOIN accounts a ON a.id = s.account_id "
            "WHERE s.run_mode IN ('live','paper') ORDER BY s.run_mode, s.status, s.name"
        ))).mappings().all()
        for r in rows:
            B.append("  %s %-5s %-8s alloc=%10.2f acct=%-12s grp=%-9s %s" % (
                r["id"][:8], r["run_mode"], r["status"], float(r["allocated_capital"] or 0),
                (r["account_name"] or "-"), (r["gid"] or "-")[:8], r["name"]))
        B.append("\n[各策略最近信号时间（判断是否还活着）]")
        rows = (await s.execute(text(
            "SELECT s.name, s.status, MAX(sg.signal_time)::text last_sig, COUNT(*) n "
            "FROM strategies s LEFT JOIN signals sg ON sg.strategy_id = s.id "
            "WHERE s.run_mode IN ('live','paper') GROUP BY 1,2 ORDER BY 3 DESC NULLS LAST"
        ))).mappings().all()
        for r in rows:
            B.append("  %-34s %-8s 最近=%s 共=%s" % (r["name"], r["status"], r["last_sig"], r["n"]))
if __name__ == "__main__":
    import os
    try:
        asyncio.run(main())
    except Exception as e:
        B.append("[FATAL] " + repr(e))
    os.makedirs("logs", exist_ok=True)
    open(OUT, "w", encoding="utf-8").write("\n".join(B))
    print("OK ->", OUT)
