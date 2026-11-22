# -*- coding: utf-8 -*-
"""走弱期持续天数监控（`_weak_streak`）——只诊断，不参与交易判据。

## 背景（2026-10-23 实测）

`_weak_days_count` 在 `enter_cond` 成立时每日被重置为 0（见 DEFAULT_PARAMS
`max_weak_days` 注释），持续走弱时诊断恒显示 `days=0/20`。实盘当时真实已连续
走弱 **16 个交易日**，而日志显示 0 —— 监控口径失真。

新增 `_weak_streak`：回放 `_index_cache` 的 MA10 投票状态机得到真实连续走弱天数，
**与进程重启无关**，且**不参与任何交易判据**。

## 本文件守住四件事

1. 连续走弱 N 天 → streak == N，起点正确。
2. 重启（新实例、同一份缓存）→ streak 仍为 N（不依赖进程内计数器）。
3. 退出走弱期 → streak 归零。
4. 非走弱期 → (0, None)。
"""
from datetime import date, timedelta

from modules.strategy.strategies.rotation.cross_market_momentum_strategy import (
    CrossMarketMomentumStrategy,
)


def _mk():
    return CrossMarketMomentumStrategy(name="T-WEAK")


def _dates(n: int):
    start = date(2026, 1, 1)
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def _install(cache_days):
    """把同一份合成收盘价灌进 4 个弱指数（默认 weak_enter_votes=3）。

    ⚠️ 先 materialize 成 dict 再逐指数复制：`cache_days` 可能是 zip 迭代器，
    直接对每个 code 调 `dict(cache_days)` 会在第一次迭代后耗尽 → 后 3 个指数为空。
    """
    base = dict(cache_days)
    st = _mk()
    st._index_cache = {code: dict(base) for code in st.weak_indices}
    return st


def test_streak_counts_consecutive_weak_days():
    """15 天横盘 + 12 天单边下跌 → 下跌首日进入走弱，streak = 12。"""
    dates = _dates(27)
    closes = [100.0] * 15 + [100.0 - i for i in range(1, 13)]
    st = _install(zip(dates, closes))

    streak, since = st._compute_weak_streak(dates[-1])

    assert streak == 12
    assert since == dates[15]


def test_streak_is_restart_independent():
    """新实例（模拟重启）+ 同一份缓存 → 同一结果，不依赖进程内计数器。"""
    dates = _dates(27)
    closes = [100.0] * 15 + [100.0 - i for i in range(1, 13)]
    cache = list(zip(dates, closes))

    st1 = _install(cache)
    st2 = _install(cache)

    assert st1._compute_weak_streak(dates[-1]) == st2._compute_weak_streak(dates[-1])


def test_streak_resets_after_exit():
    """下跌后转为单边上涨（above >= 3）→ 退出走弱期，streak 归零。"""
    dates = _dates(35)
    # 15 平 + 10 跌（进入走弱） + 10 涨（站上 MA10 → 退出）
    closes = [100.0] * 15 + [100.0 - i for i in range(1, 11)]
    closes += [closes[-1] + i for i in range(1, 11)]
    st = _install(zip(dates, closes))

    streak, since = st._compute_weak_streak(dates[-1])

    assert streak == 0
    assert since is None


def test_streak_zero_when_never_weak():
    dates = _dates(20)
    closes = [100.0] * 20  # close == MA10 → 不投票
    st = _install(zip(dates, closes))

    assert st._compute_weak_streak(dates[-1]) == (0, None)


# ---------------------------------------------------------------- 增量维护


def _flat_then_down():
    dates = _dates(27)
    closes = [100.0] * 15 + [100.0 - i for i in range(1, 13)]
    return dates, list(zip(dates, closes))


def test_update_weak_period_increments_and_is_idempotent_per_day():
    """逐日驱动：streak 递增；同日重跑不得重复计数。"""
    dates, cache = _flat_then_down()
    st = _install(cache)

    for d in dates:
        st._update_weak_period(d)

    assert st._is_weak is True
    assert st._weak_streak == 12
    assert st._weak_start_date == dates[15]

    st._update_weak_period(dates[-1])  # 同日重跑
    assert st._weak_streak == 12, "同日重跑把 streak 多加了 1"


def test_update_weak_period_rebuilds_streak_on_restart():
    """重启后首次驱动（内存计数器为 0）也必须得到真实 streak，而不是 1。"""
    dates, cache = _flat_then_down()
    st = _install(cache)

    st._update_weak_period(dates[-1])  # 只有最后一天，模拟重启

    assert st._is_weak is True
    assert st._weak_streak == 12
    assert st._weak_start_date == dates[15]


def test_update_weak_period_resets_on_exit():
    dates = _dates(35)
    closes = [100.0] * 15 + [100.0 - i for i in range(1, 11)]
    closes += [closes[-1] + i for i in range(1, 11)]
    st = _install(zip(dates, closes))

    for d in dates:
        st._update_weak_period(d)

    assert st._is_weak is False
    assert st._weak_streak == 0
    assert st._weak_streak_date is None
