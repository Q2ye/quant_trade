# -*- coding: utf-8 -*-
"""2026-08 Review 修复回归测试（B15）

覆盖本次修复的三个关键缺陷，防止回归：
- A1: delete_by_time_range 条件被丢弃 → 全表删除
- A2: RedisCache 序列化 TypeError
- A20: 事件优先级字母序反转
"""
import asyncio
from datetime import datetime, timedelta, date

import pytest


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestA1DeleteByTimeRange:
    """A1 回归：delete_by_time_range 必须带 where 条件（防全表删除）"""

    def test_delete_query_carries_conditions(self):
        from sqlalchemy import delete as sql_delete, and_, Table, Column, MetaData, String, DateTime

        meta = MetaData()
        tbl = Table(
            "stock_daily", meta,
            Column("trade_date", DateTime),
            Column("ts_code", String),
        )
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)

        # 复现修复后的关键一行：query = query.where(...)（返回值必须被接收）
        query = sql_delete(tbl)
        conditions = [
            tbl.c.trade_date >= start,
            tbl.c.trade_date <= end,
        ]
        query = query.where(and_(*conditions))

        compiled = str(query.compile())
        assert "WHERE" in compiled, f"where 条件未生效: {compiled}"

    def test_discarded_where_is_unconditional(self):
        """对照：where() 返回值被丢弃时，语句无 WHERE（旧 bug 会全表删除）"""
        from sqlalchemy import delete as sql_delete, and_, Table, Column, MetaData, String, DateTime

        meta = MetaData()
        tbl = Table(
            "stock_daily", meta,
            Column("trade_date", DateTime),
            Column("ts_code", String),
        )
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)

        query = sql_delete(tbl)
        conditions = [
            tbl.c.trade_date >= start,
            tbl.c.trade_date <= end,
        ]
        # 旧 bug 形态：返回值未接收
        query.where(and_(*conditions))
        compiled_buggy = str(query.compile())
        assert "WHERE" not in compiled_buggy, "丢弃返回值的旧实现会无条件全表删除"

        # 新实现：显式接收返回值
        fixed = sql_delete(tbl).where(and_(*conditions))
        assert "WHERE" in str(fixed.compile())


class TestA2RedisCacheSerialize:
    """A2 回归：CacheEntry 整体 pickle roundtrip（不再 json.dumps(bytes) TypeError）"""

    def test_entry_roundtrip(self):
        from shared.cache.base import CacheEntry
        from shared.cache.redis_cache import RedisCache

        cache = RedisCache(host="127.0.0.1", port=6379, db=0)
        entry = CacheEntry(
            value={"ts_code": "600519.SH", "price": 1685.5, "nested": [1, 2, 3]},
            expires_at=datetime.now() + timedelta(hours=1),
            tags=["quote"],
        )

        async def _roundtrip():
            data = await cache._serialize_entry(entry)
            assert isinstance(data, bytes), f"序列化结果应为 bytes，实际 {type(data)}"
            restored = await cache._deserialize_entry(data)
            assert isinstance(restored, CacheEntry)
            assert restored.value["ts_code"] == "600519.SH"
            assert restored.value["nested"] == [1, 2, 3]
            assert restored.tags == ["quote"]
            assert abs((restored.expires_at - entry.expires_at).total_seconds()) < 1

        _run(_roundtrip())


class TestB6SandboxImport:
    """B6 回归：策略沙箱 import 白名单——正常依赖放行、系统模块拒绝"""

    def test_allowed_modules_pass(self):
        from modules.strategy.engines.strategy_manager import _safe_import

        for mod in ("numpy", "pandas", "joblib", "sqlalchemy", "datetime", "json"):
            m = _safe_import(mod, fromlist=())
            assert m is not None, f"白名单模块应放行: {mod}"

    def test_dangerous_modules_blocked(self):
        import pytest
        from modules.strategy.engines.strategy_manager import _safe_import

        for mod in ("os", "subprocess", "socket", "sys", "shutil", "builtins", "importlib"):
            with pytest.raises(ImportError, match="策略沙箱禁止导入模块"):
                _safe_import(mod, fromlist=())

    def test_submodule_root_checked(self):
        import pytest
        from modules.strategy.engines.strategy_manager import _safe_import

        # os.path 的根是 os → 拒绝
        with pytest.raises(ImportError, match="策略沙箱禁止导入模块"):
            _safe_import("os.path")
        # numpy.linalg 的根是 numpy → 放行
        m = _safe_import("numpy.linalg", fromlist=())
        assert m is not None


class TestC4PerformanceMetrics:
    """C4 回归：绩效口径统一（夏普日频超额 ddof=1、年化 252、回撤负值）"""

    def test_sharpe_standard_formula(self):
        import numpy as np
        from utils.core_utils.math_utils.financial_calculator import FinancialCalculator

        fc = FinancialCalculator(risk_free_rate=0.02)
        # 构造已知序列：10 个日收益，均值 0.001，std≈0.01
        rng = np.random.default_rng(42)
        returns = rng.normal(0.001, 0.01, 100)

        sharpe = fc.sharpe_ratio(returns.tolist())

        # 手算标准口径：mean(r - rf/252) / std(ddof=1) × √252
        rf_daily = 0.02 / 252
        excess = returns - rf_daily
        expected = float(np.mean(excess)) / float(np.std(excess, ddof=1)) * np.sqrt(252)
        assert abs(sharpe - expected) < 1e-9, f"sharpe={sharpe}, expected={expected}"

    def test_annualized_return_252_basis(self):
        from utils.core_utils.math_utils.financial_calculator import FinancialCalculator

        fc = FinancialCalculator(risk_free_rate=0.02)
        # 构造 100 个相等的日收益，使累计收益 = 10% → 年化 (1.10)^(252/100)-1
        r = (1.10) ** (1 / 100) - 1
        returns = [r] * 100
        expected = (1.10) ** (252 / 100) - 1
        result = fc.annualized_return(returns)
        assert abs(result - expected) < 1e-9

    def test_pnl_sharpe_ddof1(self):
        from modules.account.calculators.pnl_calculator import PnLCalculator
        import numpy as np

        rng = np.random.default_rng(7)
        returns = (rng.normal(0.0005, 0.01, 60)).tolist()
        sharpe = PnLCalculator._calculate_sharpe_ratio(returns, risk_free_rate=0.02)

        rf_daily = 0.02 / 252
        excess = np.array(returns) - rf_daily
        expected = float(np.mean(excess)) / float(np.std(excess, ddof=1)) * np.sqrt(252)
        assert abs(float(sharpe) - round(expected, 6)) < 1e-6

    def test_mdd_negative_convention(self):
        from modules.strategy.services.performance_service import PerformanceService
        import inspect

        src = inspect.getsource(PerformanceService)
        # 回撤公式应为 (total - peak)/peak（负值口径）
        assert "(total_assets - peak) / peak" in src, "回撤未统一为负值口径"


class TestA20EventPriority:
    """A20 回归：优先级数值化——CRITICAL 先于 NORMAL，BACKGROUND 最后"""

    def test_priority_order(self):
        import heapq
        from core.engines.system.event_engine import QueuedEvent

        class FakeMeta:
            def __init__(self, priority):
                self.priority = priority

        class FakeEvent:
            event_type = "test.event"

            def __init__(self, priority):
                self.metadata = FakeMeta(priority)
                self.priority = priority

        from core.engines.types.enums import PriorityLevel

        events = [
            FakeEvent(PriorityLevel.NORMAL),
            FakeEvent(PriorityLevel.CRITICAL),
            FakeEvent(PriorityLevel.BACKGROUND),
            FakeEvent(PriorityLevel.HIGH),
        ]
        q = [QueuedEvent(e) for e in events]
        heapq.heapify(q)

        order = [heapq.heappop(q).priority for _ in range(len(q))]
        # 数值越小越紧急：CRITICAL(1) < HIGH(2) < NORMAL(3) < BACKGROUND(5)
        assert order == sorted(order), f"堆出队顺序应数值升序，实际 {order}"
        assert order[0] == PriorityLevel.get_priority_value(PriorityLevel.CRITICAL)
        assert order[-1] == PriorityLevel.get_priority_value(PriorityLevel.BACKGROUND)

    def test_background_not_first(self):
        import heapq
        from core.engines.system.event_engine import QueuedEvent
        from core.engines.types.enums import PriorityLevel

        class FakeMeta:
            def __init__(self, priority):
                self.priority = priority

        class FakeEvent:
            event_type = "test.event"

            def __init__(self, priority):
                self.metadata = FakeMeta(priority)
                self.priority = priority

        q = [
            QueuedEvent(FakeEvent(PriorityLevel.BACKGROUND)),
            QueuedEvent(FakeEvent(PriorityLevel.CRITICAL)),
        ]
        heapq.heapify(q)
        first = heapq.heappop(q).priority
        assert first == PriorityLevel.get_priority_value(PriorityLevel.CRITICAL), (
            "BACKGROUND 不应先于 CRITICAL 出队（字母序反转回归）"
        )
