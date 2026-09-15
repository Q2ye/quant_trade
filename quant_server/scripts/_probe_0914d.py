# -*- coding: utf-8 -*-
"""只读：etf_daily/stock_daily 行写入时刻 vs 结算时刻（验证'兜底'触发条件）。"""
import asyncio
from sqlalchemy import text
OUT = "logs/_probe_0914d.txt"
B = []
async def main():
    from shared.database.session.connection_pool import get_connection_pool
    p = get_connection_pool()
    try:
        sf = p.get_session_factory()
    except RuntimeError:
        await p.initialize(); sf = p.get_session_factory()
    async with sf() as s:
        for tbl in ("etf_daily", "stock_daily", "account_daily_performance"):
            cols = (await s.execute(text("SELECT column_name FROM information_schema.columns "
                "WHERE table_name=:t ORDER BY ordinal_position"), {"t": tbl})).scalars().all()
            B.append(f"\n[{tbl}] cols: {', '.join(cols)}")
        B.append("\n[etf_daily 512400 写入时刻]")
        rows = (await s.execute(text(
            "SELECT trade_date::text, close, created_at::text, updated_at::text "
            "FROM etf_daily WHERE ts_code='512400.SH' AND trade_date >= DATE '2026-09-01' "
            "ORDER BY trade_date DESC"))).mappings().all()
        for r in rows:
            B.append("  " + " | ".join(f"{k}={v}" for k, v in r.items()))
        B.append("\n[84d81a14 结算记录写入时刻 vs 市值]")
        rows = (await s.execute(text(
            "SELECT trade_date::text, total_asset, market_value, created_at::text "
            "FROM account_daily_performance WHERE account_id='84d81a14-5f0f-4741-b868-92961863ac3a' "
            "AND trade_date >= DATE '2026-09-01' ORDER BY trade_date DESC"))).mappings().all()
        for r in rows:
            B.append("  " + " | ".join(f"{k}={v}" for k, v in r.items()))
        B.append("\n[etf_daily 全表最近写入 10 行]")
        rows = (await s.execute(text(
            "SELECT ts_code, trade_date::text, close, created_at::text FROM etf_daily "
            "ORDER BY created_at DESC LIMIT 10"))).mappings().all()
        for r in rows:
            B.append("  " + " | ".join(f"{k}={v}" for k, v in r.items()))
if __name__ == "__main__":
    import os
    try:
        asyncio.run(main())
    except Exception as e:
        B.append(f"[FATAL] {type(e).__name__}: {str(e)[:200]}")
    os.makedirs("logs", exist_ok=True)
    open(OUT, "w", encoding="utf-8").write("\n".join(B))
    print("OK ->", OUT)
