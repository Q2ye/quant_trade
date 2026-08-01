# -*- coding: utf-8 -*-
"""
CapitalAllocator 单元测试

覆盖:
  - P0: Regime 基准权重（BEAR / RANGE / BULL）
  - P0: 信号权重缩放
  - 边界: 未知 Regime、空策略列表、缺失 strategy_id
"""
import pytest
from collections import deque
from datetime import date

from modules.strategy.engines.capital_allocator import CapitalAllocator


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def allocator_bear():
    """BEAR 市场分配器"""
    return CapitalAllocator(
        strategy_ids=["etf_bottom", "stock_low_high"],
        force_regime=0,
    )


@pytest.fixture
def allocator_range():
    """RANGE 市场分配器"""
    return CapitalAllocator(
        strategy_ids=["etf_bottom", "stock_low_high"],
        force_regime=1,
    )


@pytest.fixture
def allocator_bull():
    """BULL 市场分配器"""
    return CapitalAllocator(
        strategy_ids=["etf_bottom", "stock_low_high"],
        force_regime=2,
    )


@pytest.fixture
def allocator_default():
    """默认 RANGE（无 force_regime）"""
    return CapitalAllocator(
        strategy_ids=["etf_bottom", "stock_low_high"],
    )


# =============================================================================
# P0: Regime 基准权重
# =============================================================================

class TestRegimeAllocation:
    """验证 Regime → 基准权重映射"""

    def test_bear_allocation(self, allocator_bear):
        allocator_bear.rebalance(date(2024, 1, 15), {})
        w = allocator_bear.allocation
        assert w["etf_bottom"] == pytest.approx(0.8, abs=0.01)
        assert w["stock_low_high"] == pytest.approx(0.2, abs=0.01)
        assert sum(w.values()) == pytest.approx(1.0, abs=0.001)

    def test_range_allocation(self, allocator_range):
        allocator_range.rebalance(date(2024, 1, 15), {})
        w = allocator_range.allocation
        assert w["etf_bottom"] == pytest.approx(0.5, abs=0.01)
        assert w["stock_low_high"] == pytest.approx(0.5, abs=0.01)
        assert sum(w.values()) == pytest.approx(1.0, abs=0.001)

    def test_bull_allocation(self, allocator_bull):
        allocator_bull.rebalance(date(2024, 1, 15), {})
        w = allocator_bull.allocation
        assert w["etf_bottom"] == pytest.approx(0.2, abs=0.01)
        assert w["stock_low_high"] == pytest.approx(0.8, abs=0.01)
        assert sum(w.values()) == pytest.approx(1.0, abs=0.001)

    def test_default_regime_is_range(self, allocator_default):
        allocator_default.rebalance(date(2024, 1, 15), {})
        w = allocator_default.allocation
        assert w["etf_bottom"] == pytest.approx(0.5, abs=0.01)
        assert w["stock_low_high"] == pytest.approx(0.5, abs=0.01)

    def test_regime_readonly_property(self, allocator_bear):
        assert allocator_bear.regime == 0
        allocator_bear.rebalance(date(2024, 1, 15), {})
        assert allocator_bear.regime == 0


# =============================================================================
# P0: 信号权重缩放
# =============================================================================

class TestSignalScaling:
    """验证信号 weight × alloc_ratio 缩放"""

    def test_scale_etf_signal_in_bear(self, allocator_bear):
        """BEAR 下 ETF 信号权重 × 0.8"""
        allocator_bear.rebalance(date(2024, 1, 20), {})
        w = allocator_bear.get_weight("etf_bottom")
        assert w == pytest.approx(0.8, abs=0.01)

    def test_scale_stock_signal_in_bear(self, allocator_bear):
        """BEAR 下股票信号权重 × 0.2"""
        allocator_bear.rebalance(date(2024, 1, 20), {})
        w = allocator_bear.get_weight("stock_low_high")
        assert w == pytest.approx(0.2, abs=0.01)

    def test_scale_stock_signal_in_bull(self, allocator_bull):
        """BULL 下股票信号权重 × 0.8"""
        allocator_bull.rebalance(date(2024, 6, 15), {})
        w = allocator_bull.get_weight("stock_low_high")
        assert w == pytest.approx(0.8, abs=0.01)

    def test_unknown_strategy_returns_zero(self, allocator_range):
        allocator_range.rebalance(date(2024, 1, 1), {})
        w = allocator_range.get_weight("nonexistent_strategy")
        assert w == 0.0


# =============================================================================
# 边界场景
# =============================================================================

class TestEdgeCases:
    """边界和异常场景"""

    def test_empty_strategy_ids(self):
        """空策略列表：不崩溃"""
        a = CapitalAllocator(strategy_ids=[], force_regime=1)
        a.rebalance(date(2024, 1, 1), {})
        assert a.allocation == {}

    def test_force_regime_out_of_range(self):
        """超出 0-2 的 Regime：均分"""
        a = CapitalAllocator(
            strategy_ids=["etf_bottom", "stock_low_high"],
            force_regime=99,
        )
        a.rebalance(date(2024, 1, 1), {})
        w = a.allocation
        assert w["etf_bottom"] == pytest.approx(0.5, abs=0.01)
        assert w["stock_low_high"] == pytest.approx(0.5, abs=0.01)
        assert sum(w.values()) == pytest.approx(1.0, abs=0.001)

    def test_repr(self, allocator_range):
        allocator_range.rebalance(date(2024, 1, 1), {})
        r = repr(allocator_range)
        assert "CapitalAllocator" in r
        assert "regime=1" in r

    def test_rebalance_only_on_regime_change(self, allocator_bear):
        """Regime 不变时不重复计算"""
        allocator_bear.rebalance(date(2024, 1, 10), {})
        w1 = dict(allocator_bear.allocation)
        # Same regime, same date — allocation should stay cached
        allocator_bear.rebalance(date(2024, 1, 11), {})
        w2 = dict(allocator_bear.allocation)
        assert w1 == w2

    def test_vol_buffers_created(self):
        """P0 也预创建波动率缓冲区（为 P1 准备）"""
        a = CapitalAllocator(
            strategy_ids=["etf_bottom", "stock_low_high"],
            force_regime=1,
        )
        assert "etf_bottom" in a._vol_buffers
        assert "stock_low_high" in a._vol_buffers
        assert isinstance(a._vol_buffers["etf_bottom"], deque)
        assert a._vol_buffers["etf_bottom"].maxlen == 60

    def test_normalize_all_zeros(self):
        """全部权重为 0 时均分"""
        a = CapitalAllocator(
            strategy_ids=["s1", "s2", "s3"],
            force_regime=1,
        )
        result = a._normalize_and_clamp({"s1": 0.0, "s2": 0.0, "s3": 0.0})
        assert result["s1"] == pytest.approx(1 / 3, abs=0.01)
        assert result["s2"] == pytest.approx(1 / 3, abs=0.01)
        assert sum(result.values()) == pytest.approx(1.0, abs=0.001)

    def test_clamp_bounds(self):
        """钳制到 [5%, 95%]"""
        a = CapitalAllocator(strategy_ids=["s1", "s2"], force_regime=1)
        # 极端权重: 0.99 / 0.01
        result = a._normalize_and_clamp({"s1": 0.99, "s2": 0.01})
        assert result["s1"] <= 0.95
        assert result["s2"] >= 0.05
        assert sum(result.values()) == pytest.approx(1.0, abs=0.001)
