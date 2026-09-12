# -*- coding: utf-8 -*-
"""跨市场策略 F9：候选池当日行情整体缺失时不得调仓。

背景：F6 停牌守卫按「无当日 bar」逐只排除候选。若某日 ETF 数据整体缺失（同步故障），
候选会被全部排除 → 误判「无候选」→ `_defensive_target()` 卖出持仓切国债 →
数据恢复后再切回，白付两轮换手；期间止损判据也不可信（用的是陈旧收盘价）。

F9 守卫：候选池无一带当日 bar → `_run_rebalance` 直接返回、不动仓。

判据要点（本测试锁定）：
  1. 只要候选池有**任一**标的带当日 bar → 视为数据到位，不跳过
  2. 候选池全部为陈旧 bar / 空 → 跳过
  3. **防御标的（国债）不算数** —— 否则「只有国债有数据」会漏过
  4. 走弱期只用全球池 → 中国池有数据也不算数
"""
from modules.strategy.strategies.rotation.cross_market_momentum_strategy import (
    CrossMarketMomentumStrategy,
)

TD = "2026-09-10"
STALE = "2026-09-09"


def _strategy(weak: bool = False) -> CrossMarketMomentumStrategy:
    s = CrossMarketMomentumStrategy(name="F9-测试")
    s._is_weak = weak
    s._last_trade_date = TD
    return s


def test_any_pool_member_with_today_counts():
    s = _strategy()
    s._bar_dates = {s.china_pool[0]: TD}
    assert s._has_fresh_data(TD) is True


def test_all_stale_skips():
    s = _strategy()
    s._bar_dates = {c: STALE for c in s.global_pool + s.china_pool}
    assert s._has_fresh_data(TD) is False


def test_empty_bar_dates_skips():
    s = _strategy()
    s._bar_dates = {}
    assert s._has_fresh_data(TD) is False


def test_defensive_etf_alone_does_not_count():
    """只有国债有当日数据 = 候选全缺，仍应判为数据缺失。"""
    s = _strategy()
    s._bar_dates = {s.defensive_etf: TD}
    assert s._has_fresh_data(TD) is False


def test_weak_period_uses_global_pool_only():
    """走弱期候选池=全球池；此时仅中国池有当日数据不能算数据到位。"""
    s = _strategy(weak=True)
    s._bar_dates = {c: TD for c in s.china_pool}
    assert s._has_fresh_data(TD) is False
    # 全球池有数据则算到位
    s._bar_dates[s.global_pool[0]] = TD
    assert s._has_fresh_data(TD) is True


def test_normal_period_accepts_china_pool_only():
    """正常期候选池=全球+中国；仅中国池有数据也算到位。"""
    s = _strategy(weak=False)
    s._bar_dates = {c: TD for c in s.china_pool}
    assert s._has_fresh_data(TD) is True
