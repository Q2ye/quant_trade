# -*- coding: utf-8 -*-
"""只读探查：2026-09-14 日终运行分析的 3 项待确认（**纯 SELECT，不写库，不提交 git**）。

对应《策略运行分析标准流程》Step 3/4 中日志无法证实的三项：

  1. 三个账户的持仓与策略归属（当日盈亏 -117.00 / -149.86 / 0.00 分别是谁）
  2. 组合 3e7c7e80 的成员清单与各自 status（为何「无运行中策略」）
  3. 跨市场动量避险轮动-实盘-2.0 的近期信号历史（0 信号是否连续 / 是否漂移）

约定：
  · 列名不确定的表一律 `SELECT *` + mappings 输出，**不猜列名**（accounts 无 name 列已踩过）
  · 结果写 UTF-8 文件（Windows 控制台 GBK 会糊中文），控制台只打印文件路径
  · 持仓按 volume<>0 过滤，与 PositionRepository 默认 include_zero=False 口径一致

用法：
    cd quant_server && .venv/Scripts/python.exe scripts/_probe_live_state_0914.py
"""
import asyncio

from sqlalchemy import text

ACCOUNTS = [
    "84d81a14-5f0f-4741-b868-92961863ac3a",
    "e3b7d893-f507-4966-aa90-534a2c93ef8b",
    "a2fa6e3d-d6b5-44e2-95b6-b47267316fce",
]
GROUP_ID = "3e7c7e80-3236-4e82-931f-c332e0bd0d42"
CM_STRATEGY = "07651265-9e26-4849-89eb-6c5cdba61187"  # 跨市场动量避险轮动-实盘-2.0
TODAY = "2026-09-14"
OUT = "logs/_probe_0914.txt"

BUF: list = []


def _h(title: str) -> None:
    BUF.append("")
    BUF.append("=" * 78)
    BUF.append(title)
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
        # ---------------------------------------------------------------- 0
        _h("0. 表结构（composite_groups / 关键表列名核对，不猜）")
        for tbl in ("strategies", "accounts", "composite_groups", "positions", "signals"):
            cols = (await s.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :t ORDER BY ordinal_position"
            ), {"t": tbl})).scalars().all()
            BUF.append(f"  {tbl}({len(cols)}): {', '.join(cols)}")

        # ---------------------------------------------------------------- 1
        _h("1. 三个账户（结算日志 -117.00 / -149.86 / 0.00）")
        rows = (await s.execute(text(
            "SELECT * FROM accounts WHERE id = ANY(:ids) ORDER BY id"
        ), {"ids": ACCOUNTS})).mappings().all()
        if not rows:
            BUF.append("  （未找到）")
        for r in rows:
            BUF.append("  " + _kv(r))

        # ---------------------------------------------------------------- 2
        _h("2. 全部策略：run_mode / status / 组合归属 / 分配资金")
        rows = (await s.execute(text(
            "SELECT id::text, name, class_name, status, run_mode, execution_mode, "
            "       account_id::text AS aid, composite_group_id::text AS gid, "
            "       allocated_capital, updated_at::text "
            "FROM strategies ORDER BY run_mode DESC, status, name"
        ))).mappings().all()
        for r in rows:
            BUF.append(
                f"  {r['id'][:8]}  {str(r['run_mode']):<9} {str(r['status']):<8} "
                f"acct={str(r['aid'] or '-')[:8]:<9} group={str(r['gid'] or '-')[:8]:<9} "
                f"alloc={float(r['allocated_capital'] or 0):>10,.2f}  "
                f"[{r['class_name']}] {r['name']}"
            )

        # ---------------------------------------------------------------- 3
        _h("3. 非零持仓（volume<>0）")
        rows = (await s.execute(text(
            "SELECT account_id::text AS aid, strategy_id::text AS sid, ts_code, volume, "
            "       available_volume, cost_price, last_price, market_value, pnl, "
            "       pnl_rate, last_update::text AS lu "
            "FROM positions WHERE COALESCE(volume, 0) <> 0 "
            "ORDER BY account_id, strategy_id, ts_code"
        ))).mappings().all()
        if not rows:
            BUF.append("  （无）")
        for r in rows:
            BUF.append(
                f"  acct={r['aid'][:8]} strat={r['sid'][:8]} {r['ts_code']:<11} "
                f"vol={r['volume']:>7} 可用={r['available_volume']:>7} "
                f"成本={float(r['cost_price'] or 0):>8.4f} "
                f"现价={float(r['last_price'] or 0):>8.4f} "
                f"市值={float(r['market_value'] or 0):>12,.2f} "
                f"盈亏={float(r['pnl'] or 0):>10,.2f} "
                f"({float(r['pnl_rate'] or 0) * 100:>6.2f}%) 更新={r['lu']}"
            )

        # ---------------------------------------------------------------- 4
        _h("4. 组合 3e7c7e80 详情")
        rows = (await s.execute(text(
            "SELECT * FROM composite_groups WHERE id = :gid"
        ), {"gid": GROUP_ID})).mappings().all()
        if not rows:
            BUF.append("  （未找到该组合）")
        for r in rows:
            for k, v in r.items():
                BUF.append(f"  {k:<20} = {v}")

        _h("4b. 全部组合（确认是否只有一个）")
        rows = (await s.execute(text(
            "SELECT id::text, name, status, account_id::text, strategy_ids, "
            "       current_regime, current_allocation, last_rebalance_at::text "
            "FROM composite_groups ORDER BY created_at"
        ))).mappings().all()
        for r in rows:
            BUF.append("  " + _kv(r))

        # ---------------------------------------------------------------- 5
        _h("5. 跨市场-实盘-2.0 近期信号（最近 20 条）")
        rows = (await s.execute(text(
            "SELECT created_at::text AS ca, signal_time::text AS st, ts_code, direction, "
            "       signal_type, price, quantity, signal_status, "
            "       LEFT(COALESCE(reason, ''), 70) AS reason "
            "FROM signals WHERE strategy_id = :sid ORDER BY created_at DESC LIMIT 20"
        ), {"sid": CM_STRATEGY})).mappings().all()
        if not rows:
            BUF.append("  （该策略无任何信号记录）")
        for r in rows:
            BUF.append(
                f"  {r['ca']} | {r['ts_code']:<11} {str(r['direction']):<10} "
                f"{str(r['signal_type']):<10} 价={float(r['price'] or 0):>8.4f} "
                f"量={r['quantity']:>6} {str(r['signal_status']):<16} {r['reason']}"
            )

        _h("6. 该策略近 60 日信号按日计数（0 信号是否连续）")
        rows = (await s.execute(text(
            "SELECT DATE(signal_time)::text AS d, COUNT(*) AS n, "
            "       COUNT(*) FILTER (WHERE signal_status = 'pending_manual') AS pend "
            "FROM signals WHERE strategy_id = :sid "
            "  AND signal_time >= now() - interval '60 days' "
            "GROUP BY 1 ORDER BY 1 DESC"
        ), {"sid": CM_STRATEGY})).mappings().all()
        if not rows:
            BUF.append("  （近 60 日无信号）")
        for r in rows:
            BUF.append(f"  {r['d']}  信号={r['n']:>3}  待确认={r['pend']:>3}")

        _h("6b. 全策略近 30 日信号按策略计数")
        rows = (await s.execute(text(
            "SELECT s.name, COUNT(*) AS n, "
            "       COUNT(*) FILTER (WHERE sg.signal_status = 'pending_manual') AS pend, "
            "       MAX(sg.signal_time)::text AS last_sig "
            "FROM signals sg JOIN strategies s ON s.id = sg.strategy_id "
            "WHERE sg.signal_time >= now() - interval '30 days' "
            "GROUP BY s.name ORDER BY n DESC"
        ))).mappings().all()
        for r in rows:
            BUF.append(f"  {r['name']:<34} 信号={r['n']:>4} 待确认={r['pend']:>4} 最近={r['last_sig']}")

        # ---------------------------------------------------------------- 7
        _h(f"7. {TODAY} 账户/策略日绩效（SELECT *）")
        for tbl in ("account_daily_performance", "strategy_daily_performance"):
            try:
                rows = (await s.execute(text(
                    f"SELECT * FROM {tbl} WHERE trade_date = :d LIMIT 20"
                ), {"d": TODAY})).mappings().all()
            except Exception as e:  # noqa: BLE001 — 表可能不存在，仅提示不外抛
                await s.rollback()  # 失败语句会污染事务，不回滚则后续全部中止
                BUF.append(f"\n  [{tbl}] 查询失败: {str(e)[:140]}")
                continue
            BUF.append(f"\n  [{tbl}] rows={len(rows)}")
            for r in rows:
                BUF.append("   " + _kv(r))

        # ---------------------------------------------------------------- 8
        _h("8. 组合净值快照（composite_account_snapshots 最近 5 条）")
        try:
            rows = (await s.execute(text(
                "SELECT * FROM composite_account_snapshots ORDER BY snap_date DESC LIMIT 5"
            ))).mappings().all()
            for r in rows:
                BUF.append("   " + _kv(r))
        except Exception as e:  # noqa: BLE001
            await s.rollback()
            BUF.append(f"  查询失败: {str(e)[:140]}")

        # ---------------------------------------------------------------- 9
        _h("9. 近期信号状态分布（全库近 30 日，核对'70% 被拒'）")
        try:
            rows = (await s.execute(text(
                "SELECT signal_status, COUNT(*) AS n FROM signals "
                "WHERE signal_time >= now() - interval '30 days' "
                "GROUP BY 1 ORDER BY n DESC"
            ))).mappings().all()
            for r in rows:
                BUF.append(f"  {str(r['signal_status']):<20} {r['n']}")
        except Exception as e:  # noqa: BLE001
            await s.rollback()
            BUF.append(f"  查询失败: {str(e)[:140]}")


if __name__ == "__main__":
    import os

    try:
        asyncio.run(main())
    except Exception as e:  # noqa: BLE001 — 异常也要落盘已采集部分
        BUF.append(f"\n[FATAL] {type(e).__name__}: {str(e)[:300]}")
    os.makedirs("logs", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(BUF))
    print(f"OK -> {OUT} ({len(BUF)} lines)")
