# -*- coding: utf-8 -*-
"""高波动 · 突破确认（站稳 vs 追涨）单测（维度一第1步）。

覆盖：
  1. 默认关闭 → 与追涨确认（现状）逐位一致
  2. 开启后：连续 N 日站稳才通过；中途跌破 buffer 归零重计
  3. 候选入池初始化 retest_streak=0
"""

import numpy as np
import pandas as pd

from modules.strategy.strategies.rotation.high_vol_momentum_strategy import (
    HighVolMomentumStrategy,
)

CODE = "600000.SH"
TD = "2026-11-11"


def _make_strategy(**params) -> HighVolMomentumStrategy:
    s = HighVolMomentumStrategy(name="test-hv-retest", parameters=params)
    n = 300
    closes = 10.0 * np.power(1.002, np.arange(n))
    closes[-1] = closes[-2] * 1.03
    vols = np.full(n, 1_000_000.0)
    vols[-5:] = 3_000_000.0
    df = pd.DataFrame({
        "trade_date": [f"2025-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(n)],
        "open": closes, "high": closes, "low": closes, "close": closes,
        "volume": vols, "amount": np.full(n, 50_000.0),
    })
    s._data_cache[CODE] = df
    s._bar_dates[CODE] = TD
    s._last_trade_date = TD
    s._market_mom60 = 0.05
    return s


def _cand(s, price=10.5):
    s._buy_pending = {CODE: {"signal_price": price, "weight": 0.5,
                             "signal_date": "2026-11-10", "signal_id": "sig1",
                             "retest_streak": 0}}


def test_default_off_chases():
    """默认关闭 → 追涨确认：收盘 > 信号价才通过。"""
    s = _make_strategy()
    # 追涨通过：数据最后一根收盘 > 信号价
    _cand(s, price=s._data_cache[CODE]["close"].iloc[-1] * 0.9)
    sigs = s._confirm_pending_buys()
    assert len(sigs) == 1


def test_default_off_rejects_flat():
    """默认关闭 → 收盘 ≤ 信号价 → 拒绝。"""
    s = _make_strategy()
    _cand(s, price=s._data_cache[CODE]["close"].iloc[-1] * 1.1)  # 信号价高于收盘
    sigs = s._confirm_pending_buys()
    assert len(sigs) == 0


def test_retest_requires_consecutive_days():
    """开启 retest，days=2：首日站稳不通过（streak=1），次日站稳才通过。"""
    s = _make_strategy(enable_confirm_retest=True, confirm_retest_days=2, confirm_retest_buffer=0.03)
    base = s._data_cache[CODE]["close"].iloc[-1]
    _cand(s, price=base * 0.9)  # 信号价 90% 收盘 → 站稳
    # 首日：streak 0→1，未到 2，保留
    sigs = s._confirm_pending_buys()
    assert len(sigs) == 0
    assert CODE in s._buy_pending
    assert s._buy_pending[CODE]["retest_streak"] == 1
    # 次日：streak 1→2，通过
    sigs = s._confirm_pending_buys()
    assert len(sigs) == 1


def test_retest_resets_on_break():
    """开启 retest：中途跌破 buffer → streak 归零重计。"""
    s = _make_strategy(enable_confirm_retest=True, confirm_retest_days=2, confirm_retest_buffer=0.03)
    base = s._data_cache[CODE]["close"].iloc[-1]
    # 信号价设得很高（> 收盘），首日不站稳 → streak 归零
    _cand(s, price=base * 1.2)
    sigs = s._confirm_pending_buys()
    assert len(sigs) == 0
    assert s._buy_pending[CODE]["retest_streak"] == 0


def test_retest_streak_missing_defaults_zero():
    """pinfo 缺 retest_streak 字段（如重启恢复的候选）→ 兜底 0，不 KeyError。"""
    s = _make_strategy(enable_confirm_retest=True, confirm_retest_days=2)
    base = s._data_cache[CODE]["close"].iloc[-1]
    # 缺 retest_streak 字段（模拟重启恢复，_restore_candidates_from_db 不落该字段）
    s._buy_pending = {CODE: {"signal_price": base * 0.9, "weight": 0.5,
                             "signal_date": "2026-11-10", "signal_id": "sig1"}}
    sigs = s._confirm_pending_buys()
    assert len(sigs) == 0          # 首日站稳，streak 兜底 0→1，未到 2
    assert s._buy_pending[CODE]["retest_streak"] == 1
