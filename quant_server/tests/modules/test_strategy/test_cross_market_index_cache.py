# -*- coding: utf-8 -*-
"""跨市场策略 — regime 指数缓存的「降级 / 自愈 / 姿态 A」单元测试（2026-09-19）。

## 被修复的问题（实盘侧缺口，见 `docs/08_实盘策略报告/实盘策略验证报告-2026-09-19.md` §四 缺口 11）

`on_start` 加载 regime 指数失败时**只打 WARNING 并继续**，而 `on_start` **每进程只跑一次**
（每日驱动只调 `load_live_state`，见 `strategy_manager.py:391` / `:1743`）
→ `_index_cache` 在整个**进程生命周期内永久为空**，后果是**双重静默降级**：

  ① `_update_weak_period` 早退 → 走弱期永不成立 → **永不切防御国债**（避险腿核心功能失效）
  ② `_bench_return` 返回 None → **`rel_strength` 静默 fail-open**（等于被关掉）

## 本文件守住的六件事

1. 加载失败 → **重试 1 次**（瞬态故障可恢复）
2. 重试仍失败 → `_index_cache_ok=False` + **ERROR 日志**（不再静默）
3. `load_live_state`（每日驱动钩子）→ **自愈**
4. **姿态 A**：降级时**禁止持有/新开进攻标的**，目标强制降为防御标的
5. **「返回 0 行」不算成功**（独立复审阻断项 2：否则 `_index_cache` 成了「4 键全空」，
   `_index_cache_ok=True` 还会报假绿，而有效指数 < `weak_enter_votes` → 走弱期永不成立
   + `rel_strength` 静默 fail-open —— **与被修缺陷一字不差**）
6. **降级日不被 `min_hold_days` 拦下**（否则注释宣称的「禁止持有进攻标的」在持仓未满
   `min_hold_days` 时不成立，且全程无日志 —— 独立复审高危项）

> ⚠️ 第 4 条的**反向断言同样重要**：未降级时必须照常选出进攻标的 —— 否则守卫一旦误触发，
> 策略会永久趴在国债上（收益归零）。
"""
from types import SimpleNamespace

import numpy as np
import pandas as pd

from modules.strategy.strategies.rotation.cross_market_momentum_strategy import (
    CrossMarketMomentumStrategy,
)

TD = "2026-12-31"
_N_ROWS = 40          # 必须 ≥ `_INDEX_MIN_ROWS`(30)，否则会被行数校验判为"不可用"

#: 一个「行数达标」的指数结果集（复用同一份即可，内容不参与断言）
#: ⚠️ 结束日取 `TD`（2026-12-31）—— **未来固定值** → 被 `_index_cache_is_fresh` 判为
#:    **新鲜**，从而守住「健康 → 不重复查询」；若用真实 today 会让用例依赖运行日期（时间炸弹）。
GOOD_ROWS = [(d, 3000.0 + i) for i, d in enumerate(
    pd.date_range(end=TD, periods=_N_ROWS, freq="D").strftime("%Y-%m-%d"))]

#: 行数达标但**停在更早**的结果集 → 必须触发刷新（缺口 13：「健康即永不刷新」）。
STALE_ROWS = [(d, 3000.0 + i) for i, d in enumerate(
    pd.date_range(end="2026-01-10", periods=_N_ROWS, freq="D").strftime("%Y-%m-%d"))]


# ============================== 替身 ==============================


class _Result:
    """最小查询结果替身。"""

    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FlakySession:
    """前 `fail_times` 次 `execute` 抛异常，之后返回 `rows`。

    模拟 `InvalidCachedStatementError`：同一连接上的计划失效是瞬态的，
    换一个新事务（新 session）即可恢复。
    """

    def __init__(self, fail_times: int = 0, rows=None):
        self.fail_times = fail_times
        self.calls = 0
        self._rows = GOOD_ROWS if rows is None else rows

    async def execute(self, *_a, **_k):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("cached statement plan is invalid")
        return _Result(self._rows)


class _Ctx:
    """`async with sf() as db` 的最小上下文替身。"""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


def _factory(sessions):
    """session factory：按序弹出一个 session（第 2 次重试拿到的是**新** session）。"""
    queue = list(sessions)

    def _f():
        return _Ctx(queue.pop(0) if queue else _FlakySession(0))

    return _f


# ============================== 构造 ==============================


def _strategy(**params) -> CrossMarketMomentumStrategy:
    s = CrossMarketMomentumStrategy(name="缓存自检", parameters=params or None)
    s.context = SimpleNamespace(positions={}, total_assets=1_000_000.0,
                                available_capital=1_000_000.0)
    s._last_trade_date = TD
    return s


def _series(n: int = 40) -> pd.DataFrame:
    c = 1000.0 * np.cumprod(1.0 + np.full(n, 0.001))
    return pd.DataFrame({
        "trade_date": pd.date_range("2026-01-01", periods=n).strftime("%Y-%m-%d"),
        "open": c, "high": c * 1.01, "low": c * 0.99, "close": c,
        "volume": np.full(n, 1e6), "amount": np.full(n, 1e8),
    })


def _metric(code: str) -> dict:
    """一个「通过全部门」的候选（字段与 `_score_candidate` 返回同形）。"""
    return {
        "etf": code, "score": 5.0, "raw_score": 5.0,
        "annualized": 0.5, "r2": 0.9, "volume_ratio": 0.8,
        "passed_momentum": True, "passed_r2": True, "passed_rel_strength": True,
        "passed_ma": True, "passed_volume": True, "passed_loss": True,
        "passed_entry_gain": True, "passed_mainline": True,
        "rel_excess": 0.05, "gain_1d": 0.0, "mainline_info": {},
    }


def _rebalance_setup(**params):
    """装好 `_run_rebalance` 的最小前置：≥3 只进 `_data_cache`、候选通过全部门。"""
    s = _strategy(**params)
    cand = s.china_pool[0]
    for code in {cand, s.global_pool[0], s.defensive_etf}:
        s._data_cache[code] = _series()
        s._bar_dates[code] = TD
    s._score_candidate = lambda code: _metric(code) if code == cand else None
    return s, cand


def _hold(s, code: str) -> None:
    """给策略挂一个「未满 min_hold_days」的进攻仓位（并让 broker 对账保留它）。"""
    price = s._get_price(code)
    s._holdings[code] = {
        "entry_price": price, "weight": 0.9, "shares": 1000,
        "entry_date": TD, "fill_date": "", "peak_high": price,
    }
    s._held_days[code] = 1                       # < min_hold_days(3)
    s.context.positions = {code: SimpleNamespace(quantity=1000)}


# ====================== 1. 重试：第 2 次成功 ======================


async def test_ensure_index_cache_retries_once_then_succeeds(caplog):
    s = _strategy()
    s._db_session_factory = _factory([_FlakySession(fail_times=1), _FlakySession(fail_times=0)])

    with caplog.at_level("WARNING"):
        ok = await s._ensure_index_cache(None)

    assert ok is True, "第 2 次（新事务）应当成功"
    assert s._index_cache_ok is True
    assert set(s._index_cache) == set(s.weak_indices), "4 个 regime 指数都应加载"
    assert all(len(v) == _N_ROWS for v in s._index_cache.values())
    assert any(r.levelname == "WARNING" for r in caplog.records), "第 1 次失败要留痕"
    assert not any(r.levelname == "ERROR" for r in caplog.records), "重试成功不应报 ERROR"


async def test_ensure_index_cache_skips_query_when_already_loaded():
    """已加载**且新鲜** → 不重复查询（每日驱动不会天天打 DB）。"""
    s = _strategy()
    sess = _FlakySession(fail_times=0)
    s._db_session_factory = _factory([sess])
    await s._ensure_index_cache(None)
    first_calls = sess.calls
    await s._ensure_index_cache(None)          # 第 2 次：应直接返回
    assert sess.calls == first_calls


# ============ 1.5 缺口 13：缓存新鲜度（「健康即永不刷新」的修复） ============


async def test_stale_cache_triggers_refresh():
    """⚠️ 缺口 13：行数达标但**停在更早**的缓存必须刷新，否则 regime 在同一进程内静默冻结。

    实测命中（2026-09-21）：进程 20:22 启动、当日指数 20:43 才同步完 → 20:55 驱动用 09-18
    的指数判 regime（`above=3 below=1`；正确口径 `above=4 below=0`）。
    """
    s = _strategy()
    s._index_cache = {c: dict(STALE_ROWS) for c in s.weak_indices}
    sess = _FlakySession(fail_times=0)                 # 返回 GOOD_ROWS（新鲜）
    s._db_session_factory = _factory([sess])

    ok = await s._ensure_index_cache(None)

    assert ok is True
    # `_fetch_index_rows` 逐指数查询 → 4 个 regime 指数 = 4 次 execute
    assert sess.calls == len(s.weak_indices), "过期缓存必须触发查询 —— 这正是缺口 13 要修的行为"
    assert s._index_cache_is_fresh() is True, "刷新后应含最近交易日"
    assert max(max(v) for v in s._index_cache.values()) == TD


async def test_fresh_cache_does_not_requery():
    """新鲜缓存 → 短路（修复不得引入「每次驱动都打 DB」）。"""
    s = _strategy()
    s._index_cache = {c: dict(GOOD_ROWS) for c in s.weak_indices}
    sess = _FlakySession(fail_times=0)
    s._db_session_factory = _factory([sess])

    ok = await s._ensure_index_cache(None)

    assert ok is True
    assert sess.calls == 0, "新鲜时不得查询"


async def test_harness_with_stale_injected_cache_keeps_existing_behavior():
    """无 DB 通道（回测/harness）**注入过期缓存** → 不得刷新、不得降级、缓存逐位不变。

    这是缺口 13 修复的**回测侧安全边界**：脚本自行注入 `_index_cache` 且不接 DB 时，
    行为必须与修复前一致（否则会改变既有回测口径）。
    """
    s = _strategy()
    s._index_cache = {c: dict(STALE_ROWS) for c in s.weak_indices}
    s._db_session_factory = None

    ok = await s._ensure_index_cache(None)

    assert ok is True and s._index_cache_ok is True, "harness 路径不得降级"
    assert max(max(v) for v in s._index_cache.values()) == STALE_ROWS[-1][0], "缓存不得被改动"


# ====================== 2. 彻底失败 → 降级 + ERROR ======================


async def test_degrades_after_two_failures_with_error_log(caplog):
    s = _strategy()
    s._db_session_factory = _factory([_FlakySession(fail_times=9), _FlakySession(fail_times=9)])

    with caplog.at_level("ERROR"):
        ok = await s._ensure_index_cache(None)

    assert ok is False
    assert s._index_cache_ok is False, "必须置降级标记（姿态 A 依赖它）"
    errors = [r for r in caplog.records if r.levelname == "ERROR"]
    assert errors, "**这是本修复的核心**：失败必须 ERROR 级可见，不能再是 WARNING"
    msg = errors[0].getMessage()
    assert "降级" in msg and "姿态 A" in msg


async def test_on_start_path_degrades_when_session_creation_fails(caplog):
    """连会话都建不起来（连接池不可用）→ 同样走降级，不抛异常、不静默。"""

    def _boom():
        raise RuntimeError("pool unavailable")

    s = _strategy()
    s._db_session_factory = _boom
    with caplog.at_level("ERROR"):
        await s.on_start()
    assert s._index_cache_ok is False
    assert any(r.levelname == "ERROR" for r in caplog.records)


# ========== 2b. 复审阻断项 2：「0 行」不是成功，不得报假绿 ==========


async def test_zero_rows_is_treated_as_failure_not_success(caplog):
    """**独立复审阻断项 2 的核心用例**：查询成功但 0 行 → 必须降级 + ERROR。

    修复前：`_index_cache` 变成 `{4 键: 空}` 而 `_index_cache_ok=True` →
    `_update_weak_period` 的 `if not self._index_cache` 早退**不触发**，
    但有效指数 < `weak_enter_votes=3` → **走弱期永不可能成立**（= 被修缺陷 ①），
    且 `rel_strength` 仍静默 fail-open（= 缺陷 ②）—— 却零 ERROR、诊断还显示"4 个指数齐"。
    """
    s = _strategy()
    s._db_session_factory = _factory([_FlakySession(0, rows=[]), _FlakySession(0, rows=[])])

    with caplog.at_level("WARNING"):
        ok = await s._ensure_index_cache(None)

    assert ok is False and s._index_cache_ok is False, "0 行必须判为失败"
    assert not s._index_cache, "不得留下 `{4 键: 空}` 这种会骗过早退判据的假缓存"
    errors = [r for r in caplog.records if r.levelname == "ERROR"]
    assert errors and "走弱期" in errors[0].getMessage()


async def test_partial_rows_below_votes_is_failure(caplog):
    """4 个指数里只有 1 个行数达标（< weak_enter_votes）→ 走弱期必然失效 → 判失败。"""
    s = _strategy()
    session = _FlakySession(0, rows=GOOD_ROWS[:5])       # 5 行 < 下限 30
    s._db_session_factory = _factory([session, session])

    with caplog.at_level("ERROR"):
        ok = await s._ensure_index_cache(None)

    assert ok is False and s._index_cache_ok is False
    assert not s._index_cache, "校验失败后**不得残留半满缓存**（半投票会污染 `_is_weak`）"


async def test_empty_weak_indices_degrades_loudly(caplog):
    """`weak_indices` 被参数覆盖成 [] → 不得静默 ok=True（复审建议 3）。"""
    s = _strategy(weak_indices=[])
    with caplog.at_level("ERROR"):
        ok = await s._ensure_index_cache(None)
    assert ok is False and s._index_cache_ok is False
    assert any(r.levelname == "ERROR" for r in caplog.records)


# ====================== 3. 每日驱动自愈 ======================


async def test_load_live_state_self_heals_after_failure():
    s = _strategy()
    s._db_session_factory = _factory([_FlakySession(9), _FlakySession(9)])
    await s._ensure_index_cache(None)
    assert s._index_cache_ok is False and not s._index_cache

    # 次日驱动：DB 已恢复 → 自愈
    await s.load_live_state(_FlakySession(0), strategy_id="test-id")

    assert s._index_cache_ok is True, "每日驱动必须能自愈，否则要重启进程才恢复"
    assert set(s._index_cache) == set(s.weak_indices)


async def test_harness_without_db_keeps_existing_behavior():
    """无 DB 通道（回测/冒烟 harness）→ **不得**标记降级，行为逐位不变。"""
    s = _strategy()
    s._db_session_factory = None
    ok = await s._ensure_index_cache(None)
    assert ok is True and s._index_cache_ok is True


# ====================== 4. 姿态 A：降级 → 禁止进攻标的 ======================


def test_degraded_forces_defensive_target():
    s, cand = _rebalance_setup()
    s._index_cache_ok = False                   # ← 降级

    signals = s._run_rebalance(TD)
    codes = [sig.ts_code for sig in signals]

    assert s.defensive_etf in codes, "降级时必须切防御标的"
    assert cand not in codes, "**姿态 A：降级时禁止新开进攻仓**"


def test_not_degraded_still_picks_offensive_candidate():
    """反向断言：守卫不得误触发，否则策略会永久趴在国债上。"""
    s, cand = _rebalance_setup()
    s._index_cache_ok = True

    signals = s._run_rebalance(TD)
    codes = [sig.ts_code for sig in signals]

    assert cand in codes, "未降级时应照常选出进攻标的"
    assert s.defensive_etf not in codes


def test_degraded_day_is_not_blocked_by_min_hold_days():
    """复审高危项：降级日**不得**被 `min_hold_days` 守卫早退拦下。

    修复前：`min_hold_days` 守卫在姿态 A 守卫**之前** return →
    持仓未满 3 日时"禁止持有进攻标的"**不成立**，且**全程无日志**。
    """
    # 对照：未降级 + 持仓仅 1 日 → 被最小持有期守卫拦下（无信号）
    s_ok, cand = _rebalance_setup()
    _hold(s_ok, cand)
    assert s_ok._run_rebalance(TD) == [], "未降级时最小持有期守卫应拦下换仓（对照组）"

    # 降级 + 同样持仓仅 1 日 → 必须走到姿态 A 守卫：卖出进攻标的 + 买防御标的
    s_deg, cand = _rebalance_setup()
    _hold(s_deg, cand)
    s_deg._index_cache_ok = False

    codes = {sig.ts_code for sig in s_deg._run_rebalance(TD)}
    assert cand in codes, "降级日必须卖掉进攻持仓（不得被最小持有期拦下）"
    assert s_deg.defensive_etf in codes, "降级日必须切防御标的"


def test_degraded_signals_are_marked():
    """半自动流程下人工照单执行 → 降级信号必须可辨识（否则 DB 故障会变成真实成交）。"""
    s, cand = _rebalance_setup()
    _hold(s, cand)
    s._index_cache_ok = False

    reasons = [getattr(sig, "reason", "") or "" for sig in s._run_rebalance(TD)]
    assert any(r.startswith("[DEGRADED]") for r in reasons), "降级信号必须带 [DEGRADED] 前缀"


def test_diagnostic_exposes_degradation_state():
    """失效必须可观测，且**不得报假绿**：0 行时不能让诊断看起来"指数齐"。"""
    s = _strategy()
    diag = s.get_daily_diagnostic()
    assert diag is not None
    assert diag["index_cache_ok"] is True
    assert diag["index_cache_rows"] == {} and diag["index_cache_min_rows"] == 0

    # 模拟"4 个键但全空"（复审阻断项 2 的假绿状态）→ min_rows 必须暴露真相
    s._index_cache = {c: {} for c in s.weak_indices}
    diag = s.get_daily_diagnostic()
    assert diag["index_cache_min_rows"] == 0, "键数会骗人，**行数不会**"

    s._index_cache_ok = False
    assert s.get_daily_diagnostic()["index_cache_ok"] is False
