# -*- coding: utf-8 -*-
"""跨市场策略 H4（2026-10-28 独立复审）：`min_hold_days` 守卫不得静默早退。

复审结论（`docs/08_实盘策略报告/独立复审记录-07651265-2026-10-28.md` H4）：
  1. 原实现直接 `return signals`、**零日志** → 走弱期翻入被拦下时无任何可追溯痕迹（假静默）。
  2. 走弱期翻入是更高优先级的换仓信号，不应被「持仓未满 3 日」拦下（与降级姿态 A 同权）。

修复：
  - 判据抽到 `_min_hold_guard`（纯函数，便于单测），拦下/豁免在 `_run_rebalance` 留 INFO 日志。
  - 新增 `weak_flip_exempt_min_hold`，**默认 False = 行为逐位不变**；打开需先过 A/B。
  - 「翻入」只认连续运行中的真实 False→True：重启首日 / 同日重跑不算（否则重启当日会被误豁免）。
"""
from modules.strategy.strategies.rotation.cross_market_momentum_strategy import (
    CrossMarketMomentumStrategy,
)

TD = "2026-10-28"
_INDEXES = ["000300.SH", "000905.SH", "399006.SZ", "399101.SZ"]


def _strategy(min_hold: int = 3, exempt: bool = False) -> CrossMarketMomentumStrategy:
    s = CrossMarketMomentumStrategy(name="H4-测试")
    s.min_hold_days = min_hold
    s.weak_flip_exempt_min_hold = exempt
    s._index_cache_ok = True
    s._holdings = {"510300.SH": {"entry_price": 4.0, "shares": 100, "weight": 1.0}}
    s._held_days = {"510300.SH": 1}
    s._weak_flipped_today = False
    return s


def _weak_index_cache():
    """构造 4 个指数全部跌破 MA10 的缓存（最后一根 9.0 < MA10 9.1）。"""
    dates = [f"2026-10-{d:02d}" for d in range(10, 21)]  # 11 个日期
    vals = [11.0] + [10.0] + [9.0] * 9                    # 最后 10 个：10 + 9×9 → MA=9.1
    return {code: dict(zip(dates, vals)) for code in _INDEXES}


# ---------------- 守卫判据 ----------------

def test_guard_blocks_under_min_hold():
    """未满 min_hold_days → 全部持仓被拦，且给出可审计的 (code, held_days)。"""
    s = _strategy()
    blocked, would, exempt = s._min_hold_guard([])
    assert blocked == [("510300.SH", 1)]
    assert would == [("510300.SH", 1)]
    assert exempt is False


def test_guard_passes_when_held_enough():
    """已满 min_hold_days → 放行。"""
    s = _strategy()
    s._held_days["510300.SH"] = 3
    assert s._min_hold_guard([]) == ([], [], False)


def test_stop_loss_takes_priority():
    """本次已有止损信号 → 守卫让路（止损优先，须继续换仓补位）。"""
    s = _strategy()
    blocked, _, _ = s._min_hold_guard([object()])
    assert blocked == []


def test_degraded_day_not_blocked():
    """降级日（_index_cache_ok=False）→ 姿态 A 要求当天切防御，守卫不得拦。"""
    s = _strategy()
    s._index_cache_ok = False
    assert s._min_hold_guard([]) == ([], [], False)


def test_min_hold_zero_means_disabled():
    s = _strategy(min_hold=0)
    assert s._min_hold_guard([]) == ([], [], False)


# ---------------- 走弱期翻入豁免（默认关闭） ----------------

def test_weak_flip_not_exempt_by_default():
    """默认关闭：即使今天翻入走弱，仍按 min_hold_days 拦下（行为与旧版一致）。"""
    s = _strategy(exempt=False)
    s._weak_flipped_today = True
    blocked, would, exempt = s._min_hold_guard([])
    assert blocked == [("510300.SH", 1)]
    assert would == [("510300.SH", 1)]
    assert exempt is False


def test_weak_flip_exempt_when_enabled():
    """打开豁免：翻入当日放行，但 would_block 仍保留（供日志审计）。"""
    s = _strategy(exempt=True)
    s._weak_flipped_today = True
    blocked, would, exempt = s._min_hold_guard([])
    assert blocked == []
    assert would == [("510300.SH", 1)]
    assert exempt is True


def test_weak_flip_exempt_only_matters_when_something_would_block():
    """已满 min_hold_days → exempt 不应置位（不做无意义的「豁免」日志）。"""
    s = _strategy(exempt=True)
    s._weak_flipped_today = True
    s._held_days["510300.SH"] = 3
    assert s._min_hold_guard([]) == ([], [], False)


# ---------------- 翻入标记：重启 / 同日重跑的边界 ----------------

def test_restart_first_day_is_not_a_flip():
    """进程重启首日（无上次评估日）即使进入走弱，也不算「翻入」。"""
    s = _strategy()
    s._index_cache = _weak_index_cache()
    s._weak_evaluated_date = None
    s._update_weak_period(TD)
    assert s._is_weak is True
    assert s._weak_flipped_today is False


def test_genuine_flip_sets_flag():
    """连续运行中的真实 False→True → 置位。"""
    s = _strategy()
    s._index_cache = _weak_index_cache()
    s._weak_evaluated_date = "2026-10-27"
    s._update_weak_period(TD)
    assert s._is_weak is True
    assert s._weak_flipped_today is True


def test_same_day_rerun_is_not_a_flip():
    """同日重跑（上次评估日 == 今天）不得重复置位。"""
    s = _strategy()
    s._index_cache = _weak_index_cache()
    s._weak_evaluated_date = TD
    s._update_weak_period(TD)
    assert s._is_weak is True
    assert s._weak_flipped_today is False


def test_continuation_does_not_set_flag():
    """已在走弱期（未翻转）→ 不置位。"""
    s = _strategy()
    s._index_cache = _weak_index_cache()
    s._is_weak = True
    s._weak_evaluated_date = "2026-10-27"
    s._update_weak_period(TD)
    assert s._is_weak is True
    assert s._weak_flipped_today is False


# ---------------- 源码级回归：不得再静默 return ----------------

def test_guard_has_info_logs():
    """锁定「拦下必有日志、豁免必有日志」——防止未来又退回静默早退。"""
    from modules.strategy.strategies.rotation import cross_market_momentum_strategy as m

    src = open(m.__file__, encoding="utf-8").read()
    assert "最小持有期守卫拦下换仓" in src
    assert "走弱期翻入 → 豁免 min_hold_days" in src
    assert "return signals" in src  # 拦截仍在（只是现在有日志）
