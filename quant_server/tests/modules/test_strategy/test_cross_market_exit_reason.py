# -*- coding: utf-8 -*-
"""跨市场策略 H2（2026-10-28 独立复审）：退出信号的原因必须与事实一致。

F4 允许「已登记退出的标的即便重回目标池也强制卖出」；原实现无论哪种情形都写
「不在目标池」。若标的其实仍在目标池，这个原因是**事实错误**，会误导人工核单。
修复：`_exit_reason(code, target_codes)` 分两种情形。
"""
from modules.strategy.strategies.rotation.cross_market_momentum_strategy import (
    CrossMarketMomentumStrategy,
)


def test_reason_not_in_target_pool():
    """正常轮动：标的不在目标池。"""
    assert CrossMarketMomentumStrategy._exit_reason("510300.SH", set()) == (
        "轮动换仓: 不在目标池"
    )


def test_reason_still_in_target_pool_is_distinct():
    """F4 强制退出：标的仍在目标池 → 必须是另一种文案，不能撒谎。"""
    reason = CrossMarketMomentumStrategy._exit_reason("510300.SH", {"510300.SH"})
    assert reason != "轮动换仓: 不在目标池"
    assert "已登记退出" in reason
    assert "仍在目标池" in reason


def test_reason_source_has_both_branches():
    """源码级守卫：两条文案都必须存在，防止未来又合并回单一句。"""
    from modules.strategy.strategies.rotation import cross_market_momentum_strategy as m

    src = open(m.__file__, encoding="utf-8").read()
    assert "轮动换仓: 不在目标池" in src
    assert "轮动换仓: 已登记退出（标的仍在目标池，按 F4 强制退出）" in src
