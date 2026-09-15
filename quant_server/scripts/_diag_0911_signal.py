# -*- coding: utf-8 -*-
"""一次性诊断：手动触发 09-11 产生的信号是否自洽（不提交）。

检查：已有信号/持仓 → 是否重复下单 → 09-11 价格是否正确 → 走弱期切换是否该有卖出。
"""
import asyncio
import sys

sys.path.insert(0, ".")

SID = "07651265-9e26-4849-89eb-6c5cdba61187"


async def main() -> None:
    from sqlalchemy import text
    from shared.database.session.connection_pool import get_connection_pool

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    async with sf() as s:
        print("=" * 96)
        print("① 该策略最近 15 条信号")
        print("=" * 96)
        r = await s.execute(text(
            "SELECT id::text, ts_code, signal_type, signal_time::text, price, signal_status, "
            "quantity, strength, order_type, created_at::text, reason "
            "FROM signals WHERE strategy_id = :i ORDER BY created_at DESC LIMIT 15"),
            {"i": SID})
        rows = r.fetchall()
        if not rows:
            print("  无信号")
        for x in rows:
            sid, code, st, stime, price, status, qty, streng, otype, cre, reason = x
            print(f"  {str(sid)[:8]} {code:<11}{str(st):<6}{str(status):<17}"
                  f"px={price} qty={qty} str={streng} {otype} {stime[:19]} created={cre[:19]}")
            print(f"            reason={str(reason)[:150]}")

        print("\n" + "=" * 96)
        print("② 该策略当前持仓")
        print("=" * 96)
        try:
            r = await s.execute(text(
                "SELECT ts_code, volume, available_volume, cost_price, market_value, "
                "last_price, last_update::text "
                "FROM positions WHERE strategy_id = :i ORDER BY last_update DESC"),
                {"i": SID})
            pr = r.fetchall()
            if not pr:
                print("  无持仓")
            for x in pr:
                print("  " + "  ".join(str(v) for v in x))
        except Exception as e:
            print(f"  positions 查询失败: {type(e).__name__}: {str(e)[:150]}")

        print("\n" + "=" * 96)
        print("③ 159985.SZ（豆粕ETF）最近 6 个交易日 etf_daily")
        print("=" * 96)
        r = await s.execute(text(
            "SELECT trade_date::text, open, high, low, close, vol FROM etf_daily "
            "WHERE ts_code='159985.SZ' ORDER BY trade_date DESC LIMIT 6"))
        for x in r.fetchall():
            print(f"  {x[0]}  O={x[1]} H={x[2]} L={x[3]} C={x[4]}  vol={x[5]}")

        print("\n" + "=" * 96)
        print("④ 4 个 regime 指数 09-11 的 MA10 复算（验证 above=0 below=4）")
        print("=" * 96)
        for code in ("000300.SH", "000905.SH", "399006.SZ", "399101.SZ"):
            r = await s.execute(text(
                "SELECT trade_date::text, close FROM index_daily WHERE ts_code=:c "
                "AND trade_date <= '2026-09-11' ORDER BY trade_date DESC LIMIT 10"), {"c": code})
            g = r.fetchall()
            if len(g) < 10:
                print(f"  {code}: 数据不足 ({len(g)} 行)")
                continue
            closes = [float(v) for _, v in g]
            cur, ma = closes[0], sum(closes) / len(closes)
            tag = "BELOW" if cur < ma else "ABOVE"
            print(f"  {code}  {g[0][0]}  close={cur:.2f}  MA10={ma:.2f}  "
                  f"({cur / ma - 1:+.2%})  → {tag}")

        print("\n" + "=" * 96)
        print("⑤ 09-11 数据完整性：etf_daily / index_daily / fund_adj_factor")
        print("=" * 96)
        for tbl in ("etf_daily", "index_daily", "fund_adj_factor"):
            r = await s.execute(text(
                f"SELECT count(*) FROM {tbl} WHERE trade_date='2026-09-11'"))
            print(f"  {tbl:<20} 09-11 行数 = {r.fetchone()[0]}")

        print("\n" + "=" * 96)
        print("⑥ 策略实例状态")
        print("=" * 96)
        r = await s.execute(text(
            "SELECT status, run_mode, execution_mode, allocated_capital, updated_at::text "
            "FROM strategies WHERE id = :i"), {"i": SID})
        print("  ", r.fetchone())

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
