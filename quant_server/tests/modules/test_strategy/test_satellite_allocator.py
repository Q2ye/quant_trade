# -*- coding: utf-8 -*-
"""卫星池子仓分配器单元测试（阶段 4d）

覆盖：平时/恐慌分配、微盘门控联动、铁律2（单次上限）、铁律3（40%回流）
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from modules.strategy.engines.satellite_allocator import SatelliteAllocator


def make_allocator(**overrides):
    return SatelliteAllocator(overrides or None)


class TestAllocate:
    """子仓分配"""

    def test_idle_normal(self):
        a = make_allocator()
        w = a.allocate(micro_gate_open=True, panic_active=False)
        assert w["microcap"] == 1.0   # 平时微盘满仓
        assert w["panic"] == 0.0      # 事件空仓

    def test_idle_micro_gate_closed(self):
        a = make_allocator()
        w = a.allocate(micro_gate_open=False, panic_active=False)
        assert w["microcap"] == 0.0   # 微盘门控关 → 空仓避让
        assert w["panic"] == 0.0

    def test_panic_active(self):
        a = make_allocator()
        w = a.allocate(micro_gate_open=False, panic_active=True)
        assert w["panic"] == 1.0      # 恐慌出击全仓
        assert w["microcap"] == 0.0   # 微盘避让（联动：先避让后抄底）

    def test_panic_with_micro_open(self):
        a = make_allocator()
        w = a.allocate(micro_gate_open=True, panic_active=True)
        assert w["panic"] == 1.0
        assert w["microcap"] == 1.0   # 分配层给满，微盘策略内部再限 80% 总仓


class TestRule2:
    """铁律2：单次事件亏损上限（事前 ≤60%）"""

    def test_position_within_cap(self):
        a = make_allocator()
        r = a.check_panic_position(0.5)
        assert r["ok"] is True

    def test_position_over_cap(self):
        a = make_allocator()
        r = a.check_panic_position(0.7)
        assert r["ok"] is False
        assert "铁律2" in r["reason"]


class TestRule3:
    """铁律3：卫星池规模 > 总资金 40% → 回流主池"""

    def test_no_reflow_normal(self):
        a = make_allocator()
        r = a.check_reflow(total_assets=100_0000, satellite_assets=20_0000)  # 20%
        assert r["should_reflow"] is False

    def test_reflow_over_40pct(self):
        a = make_allocator()
        # 卫星池 50 万 / 总 100 万 = 50% > 40% → 回流 10 万
        r = a.check_reflow(total_assets=100_0000, satellite_assets=50_0000)
        assert r["should_reflow"] is True
        assert abs(r["amount"] - 10_0000) < 1

    def test_reflow_zero_protection(self):
        a = make_allocator()
        r = a.check_reflow(total_assets=0, satellite_assets=10)
        assert r["should_reflow"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header"])
