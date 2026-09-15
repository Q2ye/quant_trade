# -*- coding: utf-8 -*-
"""只读：512400/159985 真实收盘 + position 重估链路（纯 SELECT）。"""
import asyncio
from sqlalchemy import text
OUT = "logs/_probe_0914c.txt"
B = []
async def main():
    from shared.database.session.connection_pool import get_connection_pool
    p = get_connection_pool()
    try:
        sf = p.get_session_factory()
    except RuntimeError:
        await p.initialize(); sf = p.get_session_factory()
    async with sf() as s:
        for c in ("512400.SH", "159985.SZ"):
            rows = (await s.execute(text(
                "SELECT trade_date::text, close FROM etf_daily WHERE ts_code=:c "
                "ORDER BY trade_date DESC LIMIT 5"), {"c": c})).mappings().all()
            B.append(f"\n[{c}] etf_daily 近5日: " + ", ".join(
                f"{r['trade_date']}={float(r['close']):.4f}" for r in rows))
        B.append("\n[positions] 全表（含零仓）:")
        rows = (await s.execute(text("SELECT * FROM positions ORDER BY updated_at DESC"
            if False else "SELECT * FROM positions ORDER BY last_update DESC"))).mappings().all()
        for r in rows:
            B.append("  " + " | ".join(f"{k}={v}" for k, v in r.items()))
        B.append("\n[trades 列] 校验列名")
        cols = (await s.execute(text("SELECT column_name FROM information_schema.columns "
            "WHERE table_name='trades' ORDER BY ordinal_position"))).scalars().all()
        B.append("  trades: " + ", ".join(cols))
        B.append("\n[trades 全表 近10]")
        try:
            rows = (await s.execute(text("SELECT * FROM trades ORDER BY trade_time DESC LIMIT 10"
                ))).mappings().all()
            for r in rows:
                B.append("  " + " | ".join(f"{k}={v}" for k, v in r.items()))
        except Exception as e:
            await s.rollback(); B.append(f"  失败: {str(e)[:150]}")
if __name__ == "__main__":
    import os
    try:
        asyncio.run(main())
    except Exception as e:
        B.append(f"[FATAL] {type(e).__name__}: {str(e)[:200]}")
    os.makedirs("logs", exist_ok=True)
    open(OUT, "w", encoding="utf-8").write("\n".join(B))
    print("OK ->", OUT)
