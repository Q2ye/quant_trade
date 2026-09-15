# -*- coding: utf-8 -*-
"""settlement._mark_to_market 修复测试：ETF 持仓市值按 etf_daily 收盘重估

修复 2026-08-25：原实现仅查 stock_daily（A股），ETF 持仓（如 512400）查不到
当日收盘 → 回退 last_price（成本价）→ 市值高估、当日盈亏虚增。
"""
import asyncio
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from modules.account.tasks.settlement_tasks import SettlementTasks


class TestMarkToMarket:
    def test_etf_uses_etf_daily_close(self):
        """ETF 持仓：stock_daily 查不到 → 用 etf_daily 收盘价重估（500×1.896=948）"""
        task = SettlementTasks.__new__(SettlementTasks)

        class FakePos:
            ts_code = "512400.SH"
            volume = 500
            last_price = Decimal("1.9730")

        task.position_repo = SimpleNamespace(
            get_account_positions=AsyncMock(return_value=[FakePos()]))
        # A股(stock_daily)不含 ETF → 返回空
        task.stock_daily_repo = SimpleNamespace(
            get_batch_by_date_range=AsyncMock(return_value=[]))

        class FakeSession:
            async def execute(self, stmt):
                return SimpleNamespace(all=lambda: [
                    SimpleNamespace(ts_code="512400.SH", close=Decimal("1.8960"))])

        task.account_repo = SimpleNamespace(session=FakeSession())

        mv = asyncio.run(task._mark_to_market("acc-1", date(2026, 8, 25)))
        # 修复前错误回退 last_price 1.973 → 986.5
        assert mv == Decimal("948.0000")

    def test_stock_uses_stock_daily_close(self):
        """A股持仓走 stock_daily 收盘价重估（100×11.50=1150）"""
        task = SettlementTasks.__new__(SettlementTasks)

        class FakePos:
            ts_code = "000001.SZ"
            volume = 100
            last_price = Decimal("10.00")

        task.position_repo = SimpleNamespace(
            get_account_positions=AsyncMock(return_value=[FakePos()]))
        task.stock_daily_repo = SimpleNamespace(
            get_batch_by_date_range=AsyncMock(return_value=[
                SimpleNamespace(ts_code="000001.SZ", close=Decimal("11.50"))]))

        class FakeSession:
            async def execute(self, stmt):
                return SimpleNamespace(all=lambda: [])

        task.account_repo = SimpleNamespace(session=FakeSession())

        mv = asyncio.run(task._mark_to_market("acc-1", date(2026, 8, 25)))
        assert mv == Decimal("1150.0000")
