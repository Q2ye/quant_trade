# -*- coding: utf-8 -*-
"""跨市场策略 B4：重启后不得多锁 min_hold_days（重启频繁时会永不轮动）。

机制：`_held_days` 是纯内存计数，`on_start` 清空、`_restore_positions_from_db`
（每日重建 `_holdings`）也不恢复它 —— positions 表无建仓日信息。
重启后计数从 0 起算 → `min_hold_days` 守卫把持仓当「刚买入」：
  第1天 1<3 跳过、第2天 2<3 跳过、第3天才放行。
**重启间隔 < 3 个交易日时计数永远到不了 3 → 策略永不轮动**（止损仍有效，
但丧失轮动这条主要 alpha）。

修复（两条路）：
  B  框架 state_snapshot 持久化/恢复 `_held_days`（精确值）—— strategy_manager
  A  策略侧启发式兜底（快照缺失时）：有持仓但无计数 → 视为「已持有足够久」

本测试覆盖 A（纯策略逻辑，可单测）；B 用源码级回归守卫锁定。
"""
from modules.strategy.strategies.rotation.cross_market_momentum_strategy import (
    CrossMarketMomentumStrategy,
)

TD = "2026-09-10"


def _strategy(min_hold: int = 3) -> CrossMarketMomentumStrategy:
    s = CrossMarketMomentumStrategy(name="B4-测试")
    s.min_hold_days = min_hold
    return s


# ---------------- A：策略侧启发式兜底 ----------------

def test_restored_holding_gets_count_filled():
    """框架恢复的持仓（缺 fill_date）在 _held_days 无记录 → 补齐为 min_hold_days。"""
    s = _strategy(3)
    s._holdings = {"510300.SH": {"entry_price": 4.0, "shares": 100, "weight": 1.0}}
    s._held_days = {}

    s._normalize_holdings(TD)

    assert s._held_days["510300.SH"] == 3


def test_own_purchase_not_filled():
    """本策略今日买入（有 fill_date，计数已置 0）不得被补齐——应当继续锁 3 天。"""
    s = _strategy(3)
    s._holdings = {
        "510300.SH": {"entry_price": 4.0, "shares": 100, "fill_date": TD}
    }
    s._held_days = {"510300.SH": 0}

    s._normalize_holdings(TD)

    assert s._held_days["510300.SH"] == 0


def test_existing_count_not_overwritten():
    """已有计数（快照恢复或逐日累加）不被覆盖——否则重启恢复会被兜底抹平。"""
    s = _strategy(3)
    s._holdings = {"510300.SH": {"entry_price": 4.0, "shares": 100}}
    s._held_days = {"510300.SH": 7}

    s._normalize_holdings(TD)

    assert s._held_days["510300.SH"] == 7


def test_fill_date_is_never_added():
    """F2 回归守卫：绝不补 fill_date。

    该字典在实盘【每日】被 _restore_positions_from_db 清空重建且天然缺 fill_date，
    若在此补为「当日」，T+1 守卫判据 `fill_date == td` 会每天成立 → 实盘永久冻结。
    """
    s = _strategy(3)
    s._holdings = {"510300.SH": {"entry_price": 4.0}}
    s._held_days = {}

    s._normalize_holdings(TD)

    assert "fill_date" not in s._holdings["510300.SH"]
    # 其余记录性字段正常补齐
    assert s._holdings["510300.SH"]["entry_date"] == TD
    assert s._holdings["510300.SH"]["peak_high"] == 4.0


# ---------------- B：框架快照链路的源码级回归守卫 ----------------

def test_framework_snapshot_persists_and_restores_held_days():
    """B 的两端（写入 + 恢复）必须同时存在，且都带 hasattr 守卫（其他策略零影响）。"""
    from modules.strategy.engines import strategy_manager as sm_mod

    src = open(sm_mod.__file__, encoding="utf-8").read()

    assert 'snapshot["_held_days"]' in src, "写入侧缺失：快照未持久化 _held_days"
    assert 'snap.get("_held_days")' in src, "恢复侧缺失：未从快照还原 _held_days"
    assert 'hasattr(strategy, "_held_days")' in src, "写入侧缺少 hasattr 守卫"
    assert 'hasattr(strategy_obj, "_held_days")' in src, "恢复侧缺少 hasattr 守卫"
