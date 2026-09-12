# -*- coding: utf-8 -*-
"""跨市场策略 — 实盘场景预演（对应验证清单 V1~V11 中可本地模拟的部分）。

与其它测试的区别：**驱动完整的 `_run_rebalance`**，构造盘前状态后断言它发出的信号。

为什么需要这一层：F2 那个「实盘永久冻结」bug **任何单测都挡不住** ——
它不是某个方法的错，而是三件事的交互：
    框架每日重建 _holdings（缺 fill_date）
  × 策略 _normalize_holdings 补 fill_date
  × T+1 守卫判据 `fill_date == td`
本文件专门覆盖这类**跨步骤交互**。

覆盖：V2 / V3 / V4 / V5 / V6 / V7 / V11
（V10 见 test_cross_market_held_days.py；V8 / V9 须真实环境）

Harness 约定：
  - `_run_rebalance` 开头有 `len(_data_cache) < 3` 早退，故每个场景都至少喂 3 个标的
  - 喂「上升序列」→ 通过全部过滤器，成为候选；喂「下降序列」→ 不是候选但价格 > 0
  - `_index_cache` 留空 → `_update_weak_period` 早退 → `_is_weak` 保持测试设定值
"""
from types import SimpleNamespace

import numpy as np
import pandas as pd

from modules.strategy.constants import RunMode, SignalDirection
from modules.strategy.strategies.rotation.cross_market_momentum_strategy import (
    CrossMarketMomentumStrategy,
)

TD = "2026-09-10"
PREV = "2026-09-09"
HELD = "510300.SH"                       # 持仓（中国池）
FILLERS = ["513100.SH", "518880.SH"]     # 仅用于满足 len(_data_cache) >= 3（均在全球池）


def _series(n: int = 40, base: float = 1.0, step: float = 0.005) -> pd.DataFrame:
    """step>0 平滑上升（动量好、R²≈1、站上 MA10、量比 1.0 → 通过全部过滤器）；
    step<0 平滑下降（动量分为负 → 不是候选，但价格恒 > 0）。"""
    closes = np.array([base * (1.0 + step) ** i for i in range(n)], dtype=np.float64)
    return pd.DataFrame({
        "trade_date": [f"2026-08-{(i % 28) + 1:02d}" for i in range(n)],
        "open": closes, "high": closes * 1.01, "low": closes * 0.99,
        "close": closes, "volume": np.full(n, 1e6), "amount": np.full(n, 1e8),
    })


def _strategy(total_assets: float = 1_000_000.0):
    s = CrossMarketMomentumStrategy(name="场景预演")
    s._is_weak = False
    s._last_trade_date = TD
    s.context = SimpleNamespace(
        positions={}, total_assets=total_assets, available_capital=total_assets
    )
    return s


def _feed(s, rising=(), falling=(), stale=()):
    """stale：有行情但 `_bar_dates` 停在昨日（模拟停牌/数据停更）。"""
    for c in rising:
        s._data_cache[c] = _series(step=0.005)
        s._bar_dates[c] = TD
    for c in falling:
        s._data_cache[c] = _series(step=-0.005)
        s._bar_dates[c] = TD
    for c in stale:
        s._data_cache[c] = _series(step=0.005)
        s._bar_dates[c] = PREV


def _hold(s, fill_date=PREV, entry_price=1.0, shares=1000):
    s._holdings[HELD] = {
        "entry_price": entry_price, "weight": 1.0, "shares": shares,
        "entry_date": PREV, "fill_date": fill_date, "peak_high": entry_price,
    }
    s._held_days[HELD] = 10


def _dirs(signals, direction):
    return [x for x in signals if x.ts_code == HELD and x.direction == direction]


EXIT = SignalDirection.CLOSE_LONG


# ---------------- V1：重启后不丢持仓 ----------------

def test_v1_live_does_not_wipe_holdings_on_empty_context_positions():
    """F1（实盘阻断项）：实盘路径**从不写** `context.positions`（恒为空 dict）。

    原 `_reconcile_holdings` 把空快照当作「broker 已无持仓」的可信证据 → 每日把
    框架 `_restore_positions_from_db` 刚恢复的 `_holdings` 全部 pop 掉 → 策略永久
    自认空仓并反复发建仓信号。修复后：有 `_active_positions`（框架注入的 DB 真相）
    可用时不整体抹除。
    """
    s = _strategy()
    s.context.run_mode = RunMode.LIVE
    s.context.positions = {}                                        # 实盘恒为空
    s._active_positions = {HELD: SimpleNamespace(quantity=1000)}    # 框架注入的 DB 真相
    _hold(s)

    s._reconcile_holdings()

    assert HELD in s._holdings, "实盘不得因 context.positions 为空而抹掉持仓"


def test_v1_backtest_empty_positions_still_cleans_ghosts():
    """对照组：回测路径下「broker 空仓」是可信证据（引擎每日注入），仍应清理幽灵。"""
    s = _strategy()
    s.context.run_mode = RunMode.BACKTEST
    s.context.positions = {}
    _hold(s)

    s._reconcile_holdings()

    assert HELD not in s._holdings, "回测下 broker 无持仓 → 幽灵持仓应被清理"


# ---------------- V2：T+1 守卫不误锁 ----------------

def test_v2_t1_locked_holding_not_sold():
    """当日成交（fill_date == td）→ 不可卖。"""
    s = _strategy()
    _feed(s, rising=FILLERS, falling=[HELD])   # 持仓不是候选 → 本应被卖
    _hold(s, fill_date=TD)                     # 但今日刚成交 → T+1 未解锁

    sigs = s._run_rebalance(TD)

    assert _dirs(sigs, EXIT) == []


def test_v2_unlocked_holding_sold():
    """对照组：非当日成交则正常卖出（证明上条不是因为别的原因没卖）。"""
    s = _strategy()
    _feed(s, rising=FILLERS, falling=[HELD])
    _hold(s, fill_date=PREV)

    sigs = s._run_rebalance(TD)

    assert len(_dirs(sigs, EXIT)) == 1


# ---------------- V3：退出信号能重发 ----------------

def _exit_pending_scenario(age: int):
    s = _strategy()
    _feed(s, rising=FILLERS, falling=[HELD])
    _hold(s)
    s._rebalance_seq = 100
    s._exit_pending[HELD] = 100 - age
    return s


def test_v3_exit_not_reissued_before_retry_interval():
    s = _exit_pending_scenario(age=0)          # 刚发过

    assert _dirs(s._run_rebalance(TD), EXIT) == []


def test_v3_exit_reissued_after_retry_interval():
    """超过 exit_retry_days 仍持有 → 必须重发，否则持仓永久冻结。"""
    s = _exit_pending_scenario(age=CrossMarketMomentumStrategy().exit_retry_days)

    assert len(_dirs(s._run_rebalance(TD), EXIT)) == 1


# ---------------- V4：止损后不被买回 ----------------

def test_v4_stopped_out_target_not_rebought():
    """止损触发时标的仍是目标：应卖出，且**不得**买回。

    用虚高 entry_price 解耦两个条件——当前价触发止损（price <= entry×0.92），
    同时价格序列上升（动量好 → 仍是唯一候选/目标）。
    """
    s = _strategy()
    _feed(s, rising=[HELD], falling=FILLERS)   # HELD 为唯一候选 → 必为目标
    _hold(s, entry_price=100.0)                # 当前价 ~1.2 << 92 → 触发止损

    sigs = s._run_rebalance(TD)

    assert len(_dirs(sigs, EXIT)) == 1, "应发出止损卖出"
    assert _dirs(sigs, SignalDirection.LONG) == [], "不得买回刚止损的标的"


# ---------------- V5：脏数据不崩 ----------------

def test_v5_nan_price_does_not_crash_and_excludes_code():
    s = _strategy()
    _feed(s, rising=FILLERS)
    bad = _series(step=0.005)
    bad.loc[bad.index[-1], "close"] = np.nan      # 模拟脏缓存
    s._data_cache[HELD] = bad
    s._bar_dates[HELD] = TD

    sigs = s._run_rebalance(TD)                   # 不得抛异常

    assert _dirs(sigs, SignalDirection.LONG) == [], "NaN 价的标的不应被选中"


def test_v5_control_clean_series_is_selected():
    """对照组：同样的上升序列但无 NaN → 应被选中（证明上条确由 NaN 造成）。"""
    s = _strategy()
    _feed(s, rising=[HELD], falling=FILLERS)

    assert len(_dirs(s._run_rebalance(TD), SignalDirection.LONG)) == 1


# ---------------- V6：停牌标的不入选 ----------------

def test_v6_no_bar_today_excludes_candidate():
    """当日无 bar（停牌/数据停更）→ 不得用陈旧数据打分入选。"""
    s = _strategy()
    _feed(s, rising=FILLERS, stale=[HELD])        # HELD 序列很好，但只有昨日 bar

    sigs = s._run_rebalance(TD)

    assert _dirs(sigs, SignalDirection.LONG) == []


def test_v6_control_with_today_bar_is_selected():
    """对照组：同样的上升序列但带当日 bar → 应被选中（证明上条确由缺当日 bar 造成）。"""
    s = _strategy()
    _feed(s, rising=[HELD], falling=FILLERS)

    assert len(_dirs(s._run_rebalance(TD), SignalDirection.LONG)) == 1


# ---------------- V7：数据缺失不动仓 ----------------

def test_v7_all_candidates_stale_skips_rebalance_entirely():
    """候选池无一带当日 bar（数据整体缺失）→ 零信号、不动仓。

    否则会误判「无候选」→ 卖出持仓切国债，数据恢复后再切回，白付两轮换手。
    """
    s = _strategy()
    _feed(s, stale=FILLERS + [HELD])              # 池内全部陈旧
    _hold(s)

    assert s._run_rebalance(TD) == [], "数据缺失时必须零信号（既不卖也不买）"


def test_v7_data_present_then_normal_rebalance():
    """对照组：数据正常时该卖就卖（证明上条不是恒定零信号）。"""
    s = _strategy()
    _feed(s, rising=FILLERS, falling=[HELD])
    _hold(s)

    assert len(_dirs(s._run_rebalance(TD), EXIT)) == 1


# ---------------- V11：卖出用 broker 实际数量 ----------------

def test_v11_exit_uses_broker_quantity_not_strategy_shares():
    """策略自维护 shares 会高估（broker 可能缩减过）→ 卖出必须以实际持仓为准，
    否则「可卖数量不足」被拒 → 资金不释放 → 后续买入死锁。"""
    s = _strategy()
    _feed(s, rising=FILLERS, falling=[HELD])
    _hold(s, shares=1000)                                       # 策略以为 1000
    s.context.positions = {HELD: SimpleNamespace(quantity=300)}  # broker 实际 300

    exits = _dirs(s._run_rebalance(TD), EXIT)

    assert len(exits) == 1
    assert exits[0].quantity == 300, "卖出数量必须取 broker 实际持仓"
