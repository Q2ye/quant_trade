# -*- coding: utf-8 -*-
"""修复#1 端到端验证（真实事件对象）—— `_` 前缀，不提交 git。

背景：第一轮验证我用的是 SimpleNamespace(sync_type=...) 伪造事件，掩盖了真正的
根因：`DataSyncCompletedEvent` 把 sync_type 放在 `event.data`，没有 `.sync_type`
属性。本脚本改用**真实事件对象**，并按「先回退到修复前陈旧状态 → 再触发」验证。

步骤：
  0. 把 positions 回退到修复前状态（last_price=成本、market_value=成本×量、pnl=0）
  1. 发 DataType.MONEYFLOW 事件（日终真会发的类型）→ 应被守卫拦截，数据不变
  2. 发 DataType.ETF_DAILY 事件（枚举成员，与日终 _task_sync_daily 传参一致）
     → 应放行并把两只 ETF 重估到 09-14 真实收盘
  3. 再发字符串 "batch" → 兼容性检查

会写库（dev 库 quant_signals_dev），写入内容即修复后的期望值。
"""
import asyncio
from datetime import date
from decimal import Decimal

from sqlalchemy import text

DTO = date(2026, 9, 14)
OUT = "logs/_verify_mtm_0914.txt"
BUF: list = []


def _h(t: str) -> None:
    BUF.append("")
    BUF.append("=" * 78)
    BUF.append(t)
    BUF.append("=" * 78)


async def _dump(s, tag: str) -> None:
    rows = (await s.execute(text(
        "SELECT ts_code, cost_price, last_price, market_value, pnl FROM positions "
        "WHERE COALESCE(volume,0) <> 0 ORDER BY ts_code"
    ))).mappings().all()
    BUF.append(f"  [{tag}]")
    for r in rows:
        BUF.append(
            f"   {r['ts_code']:<11} 成本={float(r['cost_price']):.4f} "
            f"现价={float(r['last_price']):.4f} "
            f"市值={float(r['market_value']):>11,.2f} 盈亏={float(r['pnl']):>9,.2f}"
        )


async def main() -> None:
    from shared.database.session.connection_pool import get_connection_pool

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    from modules.data.constants import DataType
    from modules.data.events.sync_events import DataSyncCompletedEvent
    from modules.trade.services.mark_to_market import on_data_sync_completed

    def _evt(sync_type):
        return DataSyncCompletedEvent(
            sync_type=sync_type, record_count=0, duration_seconds=0.0,
            success=True, summary={}, task_id="verify-0914", user_id="verify",
        )

    # ---- 0. 回退到修复前状态 ----
    _h("0. 前置：把 positions 回退到修复前状态（last_price=成本 / pnl=0）")
    async with sf() as s:
        await s.execute(text(
            "UPDATE positions SET last_price = cost_price, "
            "       market_value = cost_price * volume, pnl = 0, pnl_rate = 0 "
            "WHERE COALESCE(volume,0) <> 0"
        ))
        await s.commit()
        await _dump(s, "回退后（=修复前现场）")

    # ---- 1. 无关 sync_type 必须被拦 ----
    _h("1. 发真实事件 sync_type=DataType.MONEYFLOW → 应被守卫拦截")
    e = _evt(DataType.MONEYFLOW)
    BUF.append(f"   event.data['sync_type'] = {e.data.get('sync_type')!r}  "
               f"has .sync_type attr = {hasattr(e, 'sync_type')}")
    await on_data_sync_completed(e, sf)
    async with sf() as s:
        await _dump(s, "拦截后（应与回退后完全一致）")

    # ---- 2. 真实日终类型必须放行并重估 ----
    _h("2. 发真实事件 sync_type=DataType.ETF_DAILY → 应放行并重估 ETF")
    e2 = _evt(DataType.ETF_DAILY)
    BUF.append(f"   event.data['sync_type'] = {e2.data.get('sync_type')!r}  "
               f"in WATCHED = {e2.data.get('sync_type') in {'daily','batch','daily_quotes','etf_daily'}}")
    await on_data_sync_completed(e2, sf)
    async with sf() as s:
        await _dump(s, "放行后")
    BUF.append("   期望: 159985.SZ 现价=2.2910 市值=17640.70 盈亏=-146.30")
    BUF.append("         512400.SH 现价=1.7390 市值=869.50  盈亏=-117.00")

    # ---- 3. 字符串 batch 兼容 ----
    _h("3. 发真实事件 sync_type='batch'（字符串路径）→ 应放行")
    async with sf() as s:
        await s.execute(text(
            "UPDATE positions SET last_price = cost_price, "
            "       market_value = cost_price * volume, pnl = 0 "
            "WHERE COALESCE(volume,0) <> 0"
        ))
        await s.commit()
    await on_data_sync_completed(_evt("batch"), sf)
    async with sf() as s:
        await _dump(s, "batch 路径后（应与步骤 2 结果一致）")


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
