# -*- coding: utf-8 -*-
"""只读探查第二轮：核实第一轮暴露的 4 个疑点（**纯 SELECT，不写库，不提交 git**）。

第一轮结论与疑点：
  · positions(159985.SZ) cost=last=2.3100、market_value=17,787.00、pnl=0  ← 疑似未重估
  · accounts(跨市场避险) market_value=17,640.70 → 隐含价 2.2910            ← 两处市值口径分叉
  · 信号 created 2026-09-13 21:26（周一前一日）需确认 signal_time 与交易日
  · 当日盈亏 -149.86 的构成未知

本轮查：交易日/周几、159985 真实收盘、成交记录、持仓快照、日绩效、结算明细。

用法：
    cd quant_server && .venv/Scripts/python.exe scripts/_probe_live_state_0914b.py
"""
import asyncio

from sqlalchemy import text

ACC_CM = "e3b7d893-f507-4966-aa90-534a2c93ef8b"   # 跨市场避险
ACC_MAIN = "84d81a14-5f0f-4741-b868-92961863ac3a"  # 银河实盘账户
STRAT_CM = "07651265-9e26-4849-89eb-6c5cdba61187"  # 跨市场-实盘-2.0
STRAT_HV = "dc862847-8197-48f4-82e5-9233a0b134dd"  # 高波动-7.1-实盘
STRAT_DF = "cebe247d-2778-472c-afb7-eb18a11502ab"  # 熊市防守-01-实盘
TS = "159985.SZ"
OUT = "logs/_probe_0914b.txt"

BUF: list = []


def _h(t: str) -> None:
    BUF.append("")
    BUF.append("=" * 78)
    BUF.append(t)
    BUF.append("=" * 78)


def _kv(r) -> str:
    return " | ".join(f"{k}={v}" for k, v in r.items())


async def main() -> None:
    from shared.database.session.connection_pool import get_connection_pool

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    async with sf() as s:
        _h("0. 日历：2026-09-14 是周几 + 最近 8 个交易日")
        r = (await s.execute(text(
            "SELECT EXTRACT(ISODOW FROM DATE '2026-09-14') AS dow, "
            "       TO_CHAR(DATE '2026-09-14', 'Day') AS dow_name"
        ))).mappings().one()
        BUF.append(f"  2026-09-14 ISODOW={r['dow']} ({r['dow_name']})  ← 1=Mon..7=Sun")
        rows = (await s.execute(text(
            "SELECT trade_date::text FROM index_daily WHERE ts_code = '000300.SH' "
            "ORDER BY trade_date DESC LIMIT 8"
        ))).scalars().all()
        BUF.append(f"  沪深300 最近 8 交易日: {rows}")

        _h(f"1. {TS} 真实行情（判断 2.3100 vs 2.2910 谁对）")
        for tbl, col in (("etf_daily", "close"), ("stock_adjusted_prices", "close")):
            try:
                rows = (await s.execute(text(
                    f"SELECT trade_date::text, open, high, low, close, vol FROM {tbl} "
                    f"WHERE ts_code = :c ORDER BY trade_date DESC LIMIT 6"
                ), {"c": TS})).mappings().all()
                BUF.append(f"\n  [{tbl}] rows={len(rows)}")
                for x in rows:
                    BUF.append(
                        f"   {x['trade_date']}  O={float(x['open'] or 0):.4f} "
                        f"H={float(x['high'] or 0):.4f} L={float(x['low'] or 0):.4f} "
                        f"C={float(x['close'] or 0):.4f} vol={x['vol']}"
                    )
            except Exception as e:  # noqa: BLE001
                await s.rollback()
                BUF.append(f"\n  [{tbl}] 查询失败: {str(e)[:130]}")

        _h("2. 持仓快照（看 last_price/market_value 是否在刷新）")
        try:
            rows = (await s.execute(text(
                "SELECT * FROM position_snapshots ORDER BY created_at DESC LIMIT 6"
            ))).mappings().all()
            for x in rows:
                BUF.append("   " + _kv(x))
        except Exception as e:  # noqa: BLE001
            await s.rollback()
            BUF.append(f"  查询失败: {str(e)[:130]}")

        _h("3. 成交/订单（跨市场避险账户，最近 10 条）")
        for tbl in ("trades", "orders"):
            try:
                rows = (await s.execute(text(
                    f"SELECT * FROM {tbl} WHERE account_id = :a "
                    f"ORDER BY created_at DESC LIMIT 10"
                ), {"a": ACC_CM})).mappings().all()
                BUF.append(f"\n  [{tbl}] rows={len(rows)}")
                for x in rows:
                    BUF.append("   " + _kv(x))
            except Exception as e:  # noqa: BLE001
                await s.rollback()
                BUF.append(f"\n  [{tbl}] 查询失败: {str(e)[:130]}")

        _h("4. 跨市场-实盘-2.0 全部信号（含 signal_time / is_executed）")
        rows = (await s.execute(text(
            "SELECT created_at::text AS ca, signal_time::text AS st, ts_code, direction, "
            "       signal_type, price, quantity, signal_status, is_executed, "
            "       price_limit_low, price_limit_high, parent_id::text AS pid, "
            "       LEFT(COALESCE(reason,''), 70) AS reason "
            "FROM signals WHERE strategy_id = :sid ORDER BY created_at"
        ), {"sid": STRAT_CM})).mappings().all()
        for x in rows:
            BUF.append("   " + _kv(x))

        _h("5. 2026-09-14 日绩效（SELECT *，正确 date cast）")
        for tbl in ("account_daily_performance", "strategy_daily_performance"):
            try:
                rows = (await s.execute(text(
                    f"SELECT * FROM {tbl} WHERE trade_date = DATE :d LIMIT 20"
                ), {"d": "2026-09-14"})).mappings().all()
                BUF.append(f"\n  [{tbl}] rows={len(rows)}")
                for x in rows:
                    BUF.append("   " + _kv(x))
            except Exception as e:  # noqa: BLE001
                await s.rollback()
                BUF.append(f"\n  [{tbl}] 查询失败: {str(e)[:130]}")

        _h("6. 结算明细（account_statements / account_transactions，近 3 日）")
        for tbl in ("account_statements", "account_transactions"):
            try:
                rows = (await s.execute(text(
                    f"SELECT * FROM {tbl} WHERE account_id = ANY(:a) "
                    f"ORDER BY created_at DESC LIMIT 10"
                ), {"a": [ACC_CM, ACC_MAIN]})).mappings().all()
                BUF.append(f"\n  [{tbl}] rows={len(rows)}")
                for x in rows:
                    BUF.append("   " + _kv(x))
            except Exception as e:  # noqa: BLE001
                await s.rollback()
                BUF.append(f"\n  [{tbl}] 查询失败: {str(e)[:130]}")

        _h("7. 组合两腿被拒信号明细（近 5 条，核对 7-3 信号价冻结）")
        for name, sid in (("高波动-7.1", STRAT_HV), ("熊市防守", STRAT_DF)):
            rows = (await s.execute(text(
                "SELECT created_at::text AS ca, ts_code, direction, signal_type, price, "
                "       signal_status, LEFT(COALESCE(reason,''), 80) AS reason "
                "FROM signals WHERE strategy_id = :sid ORDER BY created_at DESC LIMIT 5"
            ), {"sid": sid})).mappings().all()
            BUF.append(f"\n  [{name}] {sid[:8]}")
            for x in rows:
                BUF.append(
                    f"   {x['ca']} {x['ts_code']:<11} {x['direction']:<10} "
                    f"{x['signal_type']:<10} 价={float(x['price'] or 0):>8.4f} "
                    f"{x['signal_status']:<16} {x['reason']}"
                )


if __name__ == "__main__":
    import os

    try:
        asyncio.run(main())
    except Exception as e:  # noqa: BLE001 — 异常也落盘
        BUF.append(f"\n[FATAL] {type(e).__name__}: {str(e)[:300]}")
    os.makedirs("logs", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(BUF))
    print(f"OK -> {OUT} ({len(BUF)} lines)")
