# -*- coding: utf-8 -*-
"""可行性探查（只读）：新能源 ETF + 申万板块指数的数据覆盖。

决定「申万板块指数信号 → 可交易 ETF 落地」能否执行的关键事实。
"""
import asyncio

from sqlalchemy import text

OUT = "logs/_probe_bull_data.txt"
B: list = []

# 候选：新能源/光伏/电池/半导体设备 相关 ETF
ETF_CANDIDATES = [
    "515790.SH",  # 光伏ETF
    "516160.SH",  # 新能源ETF
    "515700.SH",  # 新能车ETF
    "515030.SH",  # 新能源车ETF
    "159875.SZ",  # 新能源ETF(深)
    "159824.SZ",  # 新能车ETF(深)
    "159516.SZ",  # 半导体设备ETF
    "562500.SH",  # 机器人ETF
    "516180.SH",  # 细分化工
    "159757.SZ",  # 电池ETF
    "159755.SZ",  # 电池ETF
    "159611.SZ",  # 电力ETF
    "516070.SH",  # 新能源
]


async def main() -> None:
    from shared.database.session.connection_pool import get_connection_pool

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    async with sf() as s:
        B.append("[1] 候选新能源系 ETF 在 etf_daily 的覆盖（n=行数）")
        rows = (await s.execute(text(
            "SELECT ts_code, COUNT(*) n, MIN(trade_date)::text mn, MAX(trade_date)::text mx "
            "FROM etf_daily WHERE ts_code = ANY(:c) GROUP BY 1 ORDER BY n DESC"
        ), {"c": ETF_CANDIDATES})).mappings().all()
        if not rows:
            B.append("   （无任何行）")
        for r in rows:
            B.append("   %-11s n=%5d   %s ~ %s" % (r["ts_code"], r["n"], r["mn"], r["mx"]))

        B.append("\n[2] etf_daily 表整体规模（判断 ETF 池广度）")
        r = (await s.execute(text(
            "SELECT COUNT(DISTINCT ts_code) codes, COUNT(*) n, "
            "       MIN(trade_date)::text mn, MAX(trade_date)::text mx FROM etf_daily"
        ))).mappings().one()
        B.append("   标的数=%s 行数=%s  %s ~ %s" % (r["codes"], r["n"], r["mn"], r["mx"]))

        B.append("\n[3] index_sw_daily（申万行业指数）覆盖")
        try:
            r = (await s.execute(text(
                "SELECT COUNT(DISTINCT ts_code) codes, COUNT(*) n, "
                "       MIN(trade_date)::text mn, MAX(trade_date)::text mx FROM index_sw_daily"
            ))).mappings().one()
            B.append("   标的数=%s 行数=%s  %s ~ %s" % (r["codes"], r["n"], r["mn"], r["mx"]))
            rows = (await s.execute(text(
                "SELECT ts_code, COUNT(*) n, MIN(trade_date)::text mn, MAX(trade_date)::text mx "
                "FROM index_sw_daily GROUP BY 1 ORDER BY n DESC LIMIT 45"
            ))).mappings().all()
            B.append("   [明细]")
            for x in rows:
                B.append("    %-14s n=%5d  %s ~ %s" % (x["ts_code"], x["n"], x["mn"], x["mx"]))
        except Exception as e:  # noqa: BLE001 — 表可能不存在
            await s.rollback()
            B.append("   查询失败: %s" % str(e)[:160])

        B.append("\n[4] 申万指数是否也落在 index_daily（可能以 .SI 后缀存这里）")
        try:
            rows = (await s.execute(text(
                "SELECT ts_code, COUNT(*) n, MIN(trade_date)::text mn, MAX(trade_date)::text mx "
                "FROM index_daily WHERE ts_code LIKE '8%' OR ts_code LIKE '%.SI' "
                "GROUP BY 1 ORDER BY n DESC LIMIT 20"
            ))).mappings().all()
            if not rows:
                B.append("   （index_daily 无 8xxxxx/.SI 指数）")
            for x in rows:
                B.append("    %-14s n=%5d  %s ~ %s" % (x["ts_code"], x["n"], x["mn"], x["mx"]))
        except Exception as e:  # noqa: BLE001
            await s.rollback()
            B.append("   查询失败: %s" % str(e)[:160])


if __name__ == "__main__":
    import os

    try:
        asyncio.run(main())
    except Exception as e:  # noqa: BLE001
        B.append("[FATAL] " + repr(e))
    os.makedirs("logs", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(B))
    print("OK ->", OUT)
