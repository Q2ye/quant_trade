# -*- coding: utf-8 -*-
"""settlement._mark_to_market 测试：持仓市值按当日收盘价重估 + 回写持仓。

  · 修复 2026-08-25：原实现仅查 stock_daily（A股），ETF 持仓（如 512400）查不到
    当日收盘 → 回退 last_price（成本价）→ 市值高估、当日盈亏虚增。
  · 修复 2026-09-17：本方法此前只把市值累加进账户/快照，**从不回写 positions** ——
    positions.market_value/last_price/pnl/pnl_rate 自成交后再不更新（实测 159985.SZ
    停在 09-14 的 17,640.70，当日收盘应为 18,272.10）。事件驱动的盯市链路从未生效，
    故改由日终结算回写。本文件同时锁定「回写」与「返回值」两件事。
"""
import asyncio
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from modules.account.tasks.settlement_tasks import SettlementTasks


class FakePos:
    """最小持仓替身：字段与 ORM Position 中被回写的列对齐。"""

    def __init__(self, ts_code, volume, last_price, cost_price):
        self.ts_code = ts_code
        self.volume = volume
        self.last_price = Decimal(last_price)
        self.cost_price = Decimal(cost_price)
        self.market_value = None
        self.pnl = None
        self.pnl_rate = None
        self.last_update = None


def _make_task(positions, stock_rows, etf_rows):
    task = SettlementTasks.__new__(SettlementTasks)
    task.position_repo = SimpleNamespace(
        get_account_positions=AsyncMock(return_value=positions))
    task.stock_daily_repo = SimpleNamespace(
        get_batch_by_date_range=AsyncMock(return_value=stock_rows))
    # _get_last_available_close 也会走同一个 session.execute —— 返回空即可
    fallback_rows = [] if etf_rows is None else etf_rows

    class FakeSession:
        flushed = 0

        async def execute(self, stmt):
            return SimpleNamespace(
                all=lambda: fallback_rows if fallback_rows else [],
                fetchall=lambda: [],
            )

        async def flush(self):
            FakeSession.flushed += 1

    task.account_repo = SimpleNamespace(session=FakeSession())
    return task


class TestMarkToMarket:
    def test_etf_uses_etf_daily_close(self):
        """ETF 持仓：stock_daily 查不到 → 用 etf_daily 收盘价重估（500×1.896=948）"""
        pos = FakePos("512400.SH", 500, "1.9730", "1.9000")
        # A股(stock_daily)不含 ETF → 返回空；ETF 收盘价由 etf_daily 分支提供
        task = _make_task([pos], [], [SimpleNamespace(ts_code="512400.SH", close=Decimal("1.8960"))])

        mv = asyncio.run(task._mark_to_market("acc-1", date(2026, 8, 25)))
        # 修复前错误回退 last_price 1.973 → 986.5
        assert mv == Decimal("948.0000")

    def test_stock_uses_stock_daily_close(self):
        """A股持仓走 stock_daily 收盘价重估（100×11.50=1150）"""
        pos = FakePos("000001.SZ", 100, "10.00", "10.00")
        task = _make_task(
            [pos], [SimpleNamespace(ts_code="000001.SZ", close=Decimal("11.50"))], None)

        mv = asyncio.run(task._mark_to_market("acc-1", date(2026, 8, 25)))
        assert mv == Decimal("1150.0000")


class TestMarkToMarketWriteBack:
    """2026-09-17 新增：结算回写持仓估值。"""

    def test_write_back_updates_position_fields(self):
        pos = FakePos("000001.SZ", 100, "10.00", "10.00")
        task = _make_task(
            [pos], [SimpleNamespace(ts_code="000001.SZ", close=Decimal("11.50"))], None)

        asyncio.run(task._mark_to_market("acc-1", date(2026, 8, 25)))

        assert pos.last_price == Decimal("11.50")
        assert pos.market_value == Decimal("1150.0000")
        assert pos.pnl == Decimal("150.0000")
        # pnl_rate 口径 = 比率（与 _upsert_position / 各接口一致），不是百分数
        assert pos.pnl_rate == Decimal("0.15")
        assert isinstance(pos.last_update, datetime)
        assert pos.last_update.tzinfo is not None

    def test_write_back_is_idempotent(self):
        """绝对赋值 → 同一交易日重复执行结果一致（日终结算幂等要求）"""
        pos = FakePos("000001.SZ", 100, "10.00", "10.00")
        task = _make_task(
            [pos], [SimpleNamespace(ts_code="000001.SZ", close=Decimal("11.50"))], None)

        first = asyncio.run(task._mark_to_market("acc-1", date(2026, 8, 25)))
        snapshot = (pos.last_price, pos.market_value, pos.pnl, pos.pnl_rate)
        second = asyncio.run(task._mark_to_market("acc-1", date(2026, 8, 25)))

        assert first == second
        assert (pos.last_price, pos.market_value, pos.pnl, pos.pnl_rate) == snapshot

    def test_zero_close_does_not_pollute_position(self):
        """坏价（收盘 0）不得写进持仓 —— 否则会出现 -100% 的假浮亏"""
        pos = FakePos("000001.SZ", 100, "10.00", "10.00")
        task = _make_task(
            [pos], [SimpleNamespace(ts_code="000001.SZ", close=Decimal("0"))], None)

        mv = asyncio.run(task._mark_to_market("acc-1", date(2026, 8, 25)))

        assert mv == Decimal("0")
        assert pos.last_price == Decimal("10.00"), "坏价不得覆盖 last_price"
        assert pos.market_value is None, "坏价不得写回市值"
        assert pos.pnl is None

    def test_zero_volume_position_is_skipped(self):
        pos = FakePos("000001.SZ", 0, "10.00", "10.00")
        task = _make_task(
            [pos], [SimpleNamespace(ts_code="000001.SZ", close=Decimal("11.50"))], None)

        mv = asyncio.run(task._mark_to_market("acc-1", date(2026, 8, 25)))
        assert mv == Decimal("0")
        assert pos.market_value is None

    def test_zero_cost_position_does_not_divide_by_zero(self):
        """成本价为 0 → pnl_rate 置 0，不得抛 ZeroDivisionError"""
        pos = FakePos("000001.SZ", 100, "10.00", "0")
        task = _make_task(
            [pos], [SimpleNamespace(ts_code="000001.SZ", close=Decimal("11.50"))], None)

        asyncio.run(task._mark_to_market("acc-1", date(2026, 8, 25)))
        assert pos.pnl_rate == Decimal("0")
        assert pos.market_value == Decimal("1150.0000")
