# -*- coding: utf-8 -*-
"""一次性诊断：手动 trigger 2026-09-11 加载 0 条 BarData 的根因（不提交）。

逐环节确认：交易日历 → ETF 原始日线 → 复权因子 → index_daily → 策略符号池。
"""
import asyncio
import sys

sys.path.insert(0, ".")


async def main() -> None:
    from sqlalchemy import text
    from shared.database.session.connection_pool import get_connection_pool

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    SID = "07651265-9e26-4849-89eb-6c5cdba61187"
    async with sf() as s:
        print("=" * 88)
        print("① 交易日历 2026-09-07 ~ 2026-09-14")
        print("=" * 88)
        r = await s.execute(text(
            "SELECT cal_date, is_open FROM trade_calendar "
            "WHERE cal_date BETWEEN '2026-09-07' AND '2026-09-14' ORDER BY cal_date"))
        for d, o in r.fetchall():
            print(f"  {d}  is_open={o}")

        print("\n" + "=" * 88)
        print("② 各表的日期覆盖（最近 8 个交易日）")
        print("=" * 88)
        for tbl, col in (("etf_daily", "trade_date"), ("fund_adj_factor", "trade_date"),
                         ("index_daily", "trade_date"), ("stock_daily", "trade_date"),
                         ("stock_adjusted_prices", "trade_date")):
            try:
                r = await s.execute(text(
                    f"SELECT {col}::text, count(*) FROM {tbl} "
                    f"WHERE {col} >= '2026-09-01' GROUP BY {col} ORDER BY {col} DESC LIMIT 8"))
                rows = r.fetchall()
                if not rows:
                    print(f"  {tbl:<24} 无 2026-09 数据")
                    continue
                print(f"  {tbl:<24} " + "  ".join(f"{d}:{c}" for d, c in rows))
            except Exception as e:
                print(f"  {tbl:<24} 查询失败: {type(e).__name__}: {str(e)[:80]}")

        print("\n" + "=" * 88)
        print("③ 策略实例")
        print("=" * 88)
        r = await s.execute(text(
            "SELECT id::text, name, status, run_mode, execution_mode, "
            "length(code) AS code_len, allocated_capital, "
            "updated_at::text, created_at::text "
            "FROM strategies WHERE id = :i"), {"i": SID})
        rec = r.fetchone()
        if not rec:
            print("  未找到该策略")
        else:
            sid, name, status, rmode, emode, clen, cap, upd, cre = rec
            print(f"  id={sid}\n  name={name}\n  status={status}")
            print(f"  run_mode={rmode}  execution_mode={emode}  allocated_capital={cap}")
            print(f"  code_len={clen}")
            print(f"  created={cre}  updated={upd}")
            r2 = await s.execute(text(
                "SELECT param_name, param_value::text FROM strategy_parameters "
                "WHERE strategy_id = :i ORDER BY param_name"), {"i": SID})
            prm = r2.fetchall()
            print(f"  strategy_parameters 覆盖项 {len(prm)} 条:")
            for k, v in prm[:40]:
                print(f"    {k} = {str(v)[:70]}")

        print("\n" + "=" * 88)
        print("④ 该策略代码里的 symbol 池（从 strategies.code 正则提取）")
        print("=" * 88)
        r = await s.execute(text("SELECT code FROM strategies WHERE id = :i"),
                            {"i": SID})
        code = (r.fetchone() or [""])[0] or ""
        import re
        codes = sorted(set(re.findall(r"['\"](\d{6}\.(?:SH|SZ|OF))['\"]", code)))
        print(f"  代码中出现的标的代码 {len(codes)} 个:")
        print("   " + "  ".join(codes) if codes else "   无")

        if codes:
            print("\n  这些标的在 etf_daily / index_daily 的最新日期：")
            r = await s.execute(text(
                "SELECT ts_code, max(trade_date)::text, count(*) FILTER "
                "(WHERE trade_date >= '2026-09-01') FROM etf_daily "
                "WHERE ts_code = ANY(:c) GROUP BY ts_code ORDER BY ts_code"), {"c": codes})
            etf_cov = {a: (b, c) for a, b, c in r.fetchall()}
            r = await s.execute(text(
                "SELECT ts_code, max(trade_date)::text FROM index_daily "
                "WHERE ts_code = ANY(:c) GROUP BY ts_code"), {"c": codes})
            idx_cov = {a: b for a, b in r.fetchall()}
            for c in codes:
                e = etf_cov.get(c, ("--", 0))
                i = idx_cov.get(c, "--")
                print(f"    {c:<12} etf: max={e[0]} 9月行数={e[1]:<4} index: max={i}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
