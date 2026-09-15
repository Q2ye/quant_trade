# -*- coding: utf-8 -*-
"""验证 2026-09-14 三处修复（`_` 前缀，不提交 git）。

A. 修复#1 盯市：走 on_data_sync_completed(sync_type="etf_daily") 全链路
   —— 守卫是否放行 + ETF 是否取到价 + positions 是否被重估
B. 修复#3 落库：sync_standalone_strategy_capital() 后回读 strategies.allocated_capital
C. 修复#2 兜底：_get_last_available_close() 是否返回「最近已入库收盘价」

**会写库**（dev 库 quant_signals_dev），写入内容即修复后的期望值。

用法：
    cd quant_server && .venv/Scripts/python.exe scripts/_verify_fixes_0914.py
"""
import asyncio
from datetime import date
from types import SimpleNamespace

from sqlalchemy import text

CM_SID = "07651265-9e26-4849-89eb-6c5cdba61187"  # 跨市场-实盘-2.0（独立策略，running）
GROUP_SIDS = ["dc862847-8197-48f4-82e5-9233a0b134dd",
              "cebe247d-2778-472c-afb7-eb18a11502ab"]  # 组合内（paused，不应被 #3 触碰）
TRADE_DATE = date(2026, 9, 14)
OUT = "logs/_verify_fixes_0914.txt"

BUF: list = []


def _h(t: str) -> None:
    BUF.append("")
    BUF.append("=" * 78)
    BUF.append(t)
    BUF.append("=" * 78)


async def _dump_positions(s) -> None:
    rows = (await s.execute(text(
        "SELECT ts_code, volume, cost_price, last_price, market_value, pnl, pnl_rate "
        "FROM positions WHERE COALESCE(volume,0) <> 0 ORDER BY ts_code"
    ))).mappings().all()
    for r in rows:
        BUF.append(
            f"   {r['ts_code']:<11} vol={r['volume']:>6} 成本={float(r['cost_price']):.4f} "
            f"现价={float(r['last_price']):.4f} 市值={float(r['market_value']):>11,.2f} "
            f"盈亏={float(r['pnl']):>9,.2f} ({float(r['pnl_rate']):.2f}%)"
        )


async def _dump_alloc(s, ids) -> None:
    rows = (await s.execute(text(
        "SELECT id::text, name, status, allocated_capital FROM strategies "
        "WHERE id = ANY(:ids) ORDER BY name"
    ), {"ids": ids})).mappings().all()
    for r in rows:
        BUF.append(
            f"   {r['id'][:8]} {r['status']:<8} alloc={float(r['allocated_capital']):>12,.2f}  {r['name']}"
        )


async def main() -> None:
    from shared.database.session.connection_pool import get_connection_pool

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    # =================================================================== A
    _h("A. 修复#1 盯市：修复前后 positions 对比")
    async with sf() as s:
        BUF.append("  [修复前 / 未触发盯市]")
        await _dump_positions(s)

    from modules.trade.services.mark_to_market import on_data_sync_completed

    # 1) 无关 sync_type 应被守卫拦掉（回归保护）
    await on_data_sync_completed(SimpleNamespace(sync_type="moneyflow"), sf)
    BUF.append("\n  ▶ sync_type='moneyflow' 已调用（应被守卫拦截，不改数据）")

    # 2) 日终真实 sync_type 应放行并完成重估
    await on_data_sync_completed(SimpleNamespace(sync_type="etf_daily"), sf)
    BUF.append("  ▶ sync_type='etf_daily' 已调用（应放行 + 取到 ETF 价）")

    async with sf() as s:
        BUF.append("\n  [修复后]")
        await _dump_positions(s)
        BUF.append(f"  期望: 159985.SZ 现价=2.2910 市值=17640.70 盈亏=-146.30 / "
                   f"512400.SH 现价=1.7390 市值=869.50 盈亏=-117.00")

    # =================================================================== B
    _h("B. 修复#3 allocated_capital 落库")
    from modules.strategy.engines.strategy_manager import StrategyManager

    mgr = StrategyManager.__new__(StrategyManager)  # 跳过 __init__，避免事件订阅等副作用
    ctx = SimpleNamespace(total_assets=0.0, available_capital=0.0)
    mgr._contexts = {CM_SID: ctx}
    mgr.session_factory = sf

    async with sf() as s:
        BUF.append("  [落库前]")
        await _dump_alloc(s, [CM_SID] + GROUP_SIDS)

    synced = await mgr.sync_standalone_strategy_capital()
    BUF.append(f"\n  ▶ sync_standalone_strategy_capital() → synced={synced}")
    BUF.append(f"  ▶ context: total_assets={ctx.total_assets:,.2f} "
               f"available_capital={ctx.available_capital:,.2f}")

    async with sf() as s:
        BUF.append("\n  [落库后]（跨市场-2.0 应与 context 一致；组合内两腿必须不变）")
        await _dump_alloc(s, [CM_SID] + GROUP_SIDS)

    # =================================================================== C
    _h("C. 修复#2 兜底源：_get_last_available_close()")
    from modules.account.tasks.settlement_tasks import SettlementTasks

    st = SettlementTasks.__new__(SettlementTasks)
    async with sf() as s:
        st.account_repo = SimpleNamespace(session=s)
        fb = await st._get_last_available_close(
            ["159985.SZ", "512400.SH", "000001.SZ"], TRADE_DATE,
        )
    for k, v in fb.items():
        BUF.append(f"   {k:<11} 最近已入库收盘价 = {v}")
    BUF.append("   期望: 159985.SZ=2.3250(09-11)、512400.SH=1.7540(09-11)、"
               "000001.SZ=前一日收盘（证明兜底不再是成本价）")

    _h("D. 结算兜底路径对照（修复前 vs 修复后 市值）")
    async with sf() as s:
        st.account_repo = SimpleNamespace(session=s)
        for syms in (["512400.SH"], ["159985.SZ"]):
            fb2 = await st._get_last_available_close(syms, TRADE_DATE)
            BUF.append(f"   {syms[0]} 当日缺价时：旧兜底=last_price(成本) "
                       f"→ 新兜底={fb2.get(syms[0])}")


if __name__ == "__main__":
    import os

    try:
        asyncio.run(main())
    except Exception as e:  # noqa: BLE001 — 异常也落盘
        import traceback

        BUF.append("[FATAL] " + repr(e))
        BUF.append(traceback.format_exc()[:2000])
    os.makedirs("logs", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(BUF))
    print(f"OK -> {OUT} ({len(BUF)} lines)")
