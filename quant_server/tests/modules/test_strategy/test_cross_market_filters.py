# -*- coding: utf-8 -*-
"""跨市场策略 — 选股层三因子（r2 / trend_quality / rel_strength）的单元测试。

对应 `audit-strategy.md` 第六步。三个因子都是**选股维度**的改动，
全部经 7.6 年回测 + 两段样本外 + 12 滚动起始日 + 安慰剂对照验证后采纳。

⚠️ 最关键的断言是「**只改排序、不改过滤**」：`trend_quality` 的乘子对低波动候选 >1，
   若把乘子后的分数也用于 `max_score_threshold` 判定，这些候选会被误杀 —— 与「奖励
   趋势质量」的意图完全相反。这一条必须由测试守住。
"""
from types import SimpleNamespace

import numpy as np
import pandas as pd

from modules.strategy.strategies.rotation.cross_market_momentum_strategy import (
    CrossMarketMomentumStrategy,
)

TD = "2026-12-31"


def _series(up: float, dn: float, n: int = 40) -> pd.DataFrame:
    """交替 up / dn 的收益序列（便于精确控制「上行波动 vs 下行波动」）。"""
    r = np.array([up if i % 2 == 0 else -dn for i in range(n)], dtype=np.float64)
    c = 1000.0 * np.cumprod(1.0 + r)
    return pd.DataFrame({
        "trade_date": pd.date_range("2026-01-01", periods=n).strftime("%Y-%m-%d"),
        "open": c, "high": c * 1.01, "low": c * 0.99, "close": c,
        "volume": np.full(n, 1e6), "amount": np.full(n, 1e8),
    })


def _bench(step: float, n: int = 80) -> dict:
    """构造 `_index_cache["000300.SH"]`：{date: close}。"""
    dates = pd.date_range("2026-01-01", periods=n).strftime("%Y-%m-%d").tolist()
    closes = 3000.0 * np.cumprod(1.0 + np.full(n, step))
    return {"000300.SH": dict(zip(dates, closes))}


def _strategy(bench_step: float = 0.002, bench_n: int = 80, **params):
    s = CrossMarketMomentumStrategy(name="因子自检", parameters=params)
    s.context = SimpleNamespace(positions={}, total_assets=1_000_000.0,
                                available_capital=1_000_000.0)
    s._last_trade_date = TD
    s._index_cache = _bench(bench_step, bench_n)
    return s


def _feed(s, code: str, df: pd.DataFrame) -> None:
    s._data_cache[code] = df
    s._bar_dates[code] = TD


CODE = "510300.SH"


# ============================== 默认值 ==============================

def test_defaults_of_three_layers():
    """三层默认值（2026-09-13 采纳后的基线）。"""
    s = CrossMarketMomentumStrategy(name="默认值")
    assert s.r2_threshold == 0.47
    assert s.enable_trend_quality is True
    assert s.trend_quality_power == 3.0
    assert s.enable_rel_strength is True
    # 已否决的三项必须默认关闭
    assert s.enable_entry_gain_filter is False
    assert s.entry_gain_veto is False
    assert s.momentum_efficacy_threshold <= -1.0


# ============================== trend_quality ==============================

def test_trend_quality_symmetric_gives_one():
    """上下行波动相等 → q=1（不改变排序）。"""
    s = _strategy(enable_trend_quality=True)
    q = s._trend_quality(_series(0.01, 0.01)["close"].to_numpy())
    assert q is not None and abs(q - 1.0) < 1e-9


def test_trend_quality_up_dominant_gives_above_one():
    """涨得比跌得猛 → q>1（奖励）。"""
    s = _strategy(enable_trend_quality=True)
    q = s._trend_quality(_series(0.02, 0.01)["close"].to_numpy())
    assert q is not None and q > 1.0


def test_trend_quality_down_dominant_gives_below_one():
    """跌得比涨得猛 → q<1（惩罚）。"""
    s = _strategy(enable_trend_quality=True)
    q = s._trend_quality(_series(0.01, 0.02)["close"].to_numpy())
    assert q is not None and q < 1.0


def test_trend_quality_keeps_high_vol_when_upside_dominates():
    """与「总波动惩罚」的关键区别：波动大但上行占优时**仍被奖励**。

    这是本因子与已被否决的「风险调整动量（除以总波动）」的分水岭 ——
    后者把「猛」也一起罚掉，实测三段 MDD 全部恶化。
    """
    s = _strategy(enable_trend_quality=True)
    closes = _series(0.06, 0.03)["close"].to_numpy()      # 日波动很大
    q = s._trend_quality(closes)
    assert q is not None and q > 1.0, "上行占优的高波动标的应被奖励，而非惩罚"


def test_trend_quality_returns_none_on_one_sided_sample():
    """单边样本（全涨/全跌）→ None（fail-open，不调整）。"""
    s = _strategy(enable_trend_quality=True)
    closes = 1000.0 * np.cumprod(1.0 + np.full(40, 0.01))
    assert s._trend_quality(closes) is None


def test_trend_quality_placebo_lag_uses_historical_window():
    """安慰剂 lag>0 用历史窗口（分布相同、对齐破坏）。"""
    n = 80
    rng = np.random.default_rng(7)
    r = np.concatenate([rng.normal(-0.002, 0.04, 40), rng.normal(0.006, 0.01, 40)])
    closes = 1000.0 * np.cumprod(1.0 + r)
    q0 = _strategy(enable_trend_quality=True, trend_quality_lag=0)._trend_quality(closes)
    q20 = _strategy(enable_trend_quality=True, trend_quality_lag=20)._trend_quality(closes)
    assert q0 is not None and q20 is not None and abs(q0 - q20) > 1e-6


def test_trend_quality_only_changes_ranking_not_filtering():
    """🔴 核心不变量：过滤用 `raw_score`，调整只作用于 `score`（排序）。

    `trend_quality` 的乘子对上行占优的候选 >1，会**放大**排序分 —— 若过滤也看放大后的分数，
    这些候选会被 `max_score_threshold` 误杀，与「奖励趋势质量」的意图完全相反。
    """
    s = _strategy(enable_trend_quality=True)
    # 极陡上升 → 原始动量分必然越过上限 5.0
    _feed(s, CODE, _series(0.03, 0.001, n=60))
    m = s._score_candidate(CODE)
    assert m is not None
    assert m["raw_score"] > s.max_score_threshold, "前置：原始分应越上限（否则本用例无意义）"
    assert m["passed_momentum"] is False, "过滤必须看 raw_score —— 越上限就该被过滤"
    assert m["score"] != m["raw_score"], "排序分应已被质量乘子调整（与 raw 分离）"


def test_trend_quality_disabled_keeps_score_equal_to_raw():
    """关闭时排序分等于原始动量分，且字段仍存在。"""
    s = _strategy(enable_trend_quality=False)
    _feed(s, CODE, _series(0.02, 0.005, n=60))
    m = s._score_candidate(CODE)
    assert m is not None
    assert abs(m["score"] - m["raw_score"]) < 1e-12


def test_trend_quality_enabled_makes_score_differ_from_raw():
    """开启且存在质量差异时，排序分 ≠ 原始分。"""
    s = _strategy(enable_trend_quality=True)
    _feed(s, CODE, _series(0.02, 0.005, n=60))
    m = s._score_candidate(CODE)
    assert m is not None
    assert m["raw_score"] != m["score"]


# ============================== rel_strength ==============================

def test_rel_strength_pass_when_candidate_beats_bench():
    """候选跑赢基准 → 超额 >0 → 通过。

    注意：`_series(up, dn)` 是交替序列，**净收益 ≈ (1+up)(1-dn)−1 每两日**，
    不能直接用 up 当"日收益"来估。此处取 (0.008, 0.002) → 净约 +0.3%/日，
    明显高于基准 +0.1%/日。
    """
    s = _strategy(bench_step=0.001, enable_rel_strength=True)
    exc = s._rel_strength_excess(_series(0.008, 0.002)["close"].to_numpy())
    assert exc is not None and exc > 0


def test_rel_strength_reject_when_candidate_lags_bench():
    """候选跑输基准 → 超额 <0 → 拒绝。"""
    s = _strategy(bench_step=0.004, enable_rel_strength=True)   # 基准 +0.4%/日
    exc = s._rel_strength_excess(_series(0.001, 0.001)["close"].to_numpy())
    assert exc is not None and exc < 0


def test_rel_strength_fail_open_when_bench_missing():
    """🔴 基准数据缺失 → 返回 None → 调用方 fail-open（放行），不阻断策略。"""
    s = _strategy(enable_rel_strength=True)
    s._index_cache = {}
    assert s._bench_return(TD, 25) is None
    assert s._rel_strength_excess(_series(0.003, 0.001)["close"].to_numpy()) is None
    # 且 _score_candidate 不得因此被剔除
    _feed(s, CODE, _series(0.02, 0.005, n=60))
    m = s._score_candidate(CODE)
    assert m is not None and m["passed_rel_strength"] is True


def test_rel_strength_placebo_lag_uses_historical_bench():
    """安慰剂 lag>0 用历史基准窗口。"""
    n = 80
    closes = 3000.0 * np.cumprod(
        1.0 + np.concatenate([np.full(40, -0.01), np.full(40, 0.008)]))
    dates = pd.date_range("2026-01-01", periods=n).strftime("%Y-%m-%d").tolist()
    cache = {"000300.SH": dict(zip(dates, closes))}
    s0 = _strategy(enable_rel_strength=True, rel_strength_lag=0)
    s20 = _strategy(enable_rel_strength=True, rel_strength_lag=20)
    s0._index_cache = cache
    s20._index_cache = cache
    b0, b20 = s0._bench_return(dates[-1], 25), s20._bench_return(dates[-1], 25)
    assert b0 is not None and b20 is not None and abs(b0 - b20) > 1e-9


def test_rel_strength_is_wired_into_apply_filters():
    """相对强度门确实接入 `_apply_filters`（且受开关控制）。"""
    import inspect
    src = inspect.getsource(CrossMarketMomentumStrategy._apply_filters)
    assert "passed_rel_strength" in src and "enable_rel_strength" in src


def test_rel_strength_disabled_does_not_filter():
    """关闭时该门不生效（`passed_rel_strength` 恒为 True）。"""
    s = _strategy(bench_step=0.01, enable_rel_strength=False)   # 基准远强于候选
    _feed(s, CODE, _series(0.001, 0.001, n=60))
    m = s._score_candidate(CODE)
    assert m is not None and m["passed_rel_strength"] is True
    assert m["rel_excess"] is None


# ==================== R² 口径（2026-09-13 修复：加权回归三环节须同权）====================

def _rand_path(seed: int, mu: float, sd: float = 0.04, n: int | None = None) -> np.ndarray:
    """确定性随机价格路径；n 默认 lookback_days + 1（与策略窗口同长）。"""
    n = n or (CrossMarketMomentumStrategy(name="x").lookback_days + 1)
    r = np.random.default_rng(seed).normal(mu, sd, n)
    return 1000.0 * np.cumprod(1.0 + r)


def test_r2_is_one_for_perfect_log_linear_series():
    """边界健全性（非回归守卫）：完美对数线性 → 残差为 0 → R² 必须恰为 1。

    ⚠️ 修复前后都成立，因此它**不能**用来发现本缺陷，只守住 R² 的上界。
    """
    s = CrossMarketMomentumStrategy(name="R²自检")
    closes = 1000.0 * np.exp(0.002 * np.arange(s.lookback_days + 1))
    score, annualized, r2 = s._calc_momentum_score(closes, s.lookback_days)
    assert r2 is not None and abs(r2 - 1.0) < 1e-9, "完美拟合的 R² 必须为 1"
    assert score is not None and abs(score - annualized) < 1e-9, "R²==1 时 score 应等于年化"


def test_r2_always_within_unit_interval():
    """🔴 核心不变式：R² ∈ [0, 1]。

    修复前 `ss_tot` 用**无权** `np.mean(y)` 中心化，使 `SS_tot = SS_reg + SS_res` 不成立
    → R² 可为负（实测 5.58% 样本）。样本内带截距回归的 R² 在数学上不可能为负，
    出现负值本身就是公式错的信号。

    修复方式为 `r2 = max(0.0, r2)`（夹零）：**所有正 R² 逐位不变**，故 `r2_threshold`
    的标定含义不受影响。曾评估的「全 W 同权教科书 WLS R²」修法会扰动全部正 R²，
    实测使 7.6 年收益 −556pp、MDD +14pp，已否决。
    """
    s = CrossMarketMomentumStrategy(name="R²自检")
    for seed in range(60):
        for mu in (-0.004, -0.001, 0.0, 0.002):
            _, _, r2 = s._calc_momentum_score(_rand_path(seed, mu), s.lookback_days)
            assert r2 is not None and 0.0 <= r2 <= 1.0, f"seed={seed} mu={mu} r2={r2}"


def test_score_sign_matches_annualized_sign():
    """🔴 回归守卫：`score` 与 `annualized` **同号**。

    score = 年化 × R²，R² ≥ 0 ⇒ 两者符号必然一致。修复前 R² 可为负，两个负数相乘得正，
    于是「下跌标的（年化<0）」拿到**正**得分，通过了 `raw_score >= 0` 的动量门 ——
    与「动量必须为正」的选股意图完全相反。

    ⚠️ 断言**不得**跳过 `r2 <= 0` 的样本 —— 修复前正是这些样本违例
       （实测 seed 0..299 中 9 例）。夹零后 r2 恒 ≥ 0，该条退化为「永真」，
       但仍保留：一旦有人移除夹零，它会立刻重新报错。
    """
    s = CrossMarketMomentumStrategy(name="R²自检")
    checked = 0
    for seed in range(300):
        score, annualized, r2 = s._calc_momentum_score(
            _rand_path(seed, -0.002, sd=0.05), s.lookback_days)
        if score is None or annualized is None or r2 is None:
            continue
        checked += 1
        assert score * annualized >= 0, (
            f"seed={seed} 年化={annualized:+.4f} R²={r2:.4f} 得分={score:+.4f} —— 符号翻转"
        )
    assert checked > 250, f"有效样本过少（{checked}），断言覆盖面不足"


def test_downtrend_with_poor_fit_no_longer_scores_positive():
    """🔴 回归守卫（修复前该序列的实测值）：年化 −31.07%、R² −0.0264 → 得分 **+0.0082**，通过动量门。

    修复（负 R² 夹零）后 r2 = 0、score = 0，并被 `passed_r2 = r2 > r2_threshold` 直接拦下。
    注意：拦下它的是 **R² 门**而非动量门 —— score=0 仍满足 `0.0 <= score <= 5.0`，
    夹零的语义是「让它丧失动量分并落进 R² 门」，不是「让它被动量门拒」。
    """
    s = CrossMarketMomentumStrategy(name="R²自检")
    score, annualized, r2 = s._calc_momentum_score(
        _rand_path(31, 0.0, sd=0.05), s.lookback_days)
    assert score is not None and annualized is not None and r2 is not None
    assert annualized < 0, f"前置：该序列年化应为负，实得 {annualized}"
    assert r2 >= 0.0, f"R² 不得为负（修复前为 −0.0264），实得 {r2}"
    assert score <= 0, f"下跌标的不得得正分（修复前为 +0.0082），实得 {score}"
    assert r2 < s.r2_threshold, (
        f"应被 R² 门（r2 > {s.r2_threshold}）拦下，实得 r2={r2}")


def test_r2_zero_for_constant_series():
    """边界健全性（非回归守卫）：常数序列 → ss_tot == 0 → R² 兜底为 0，无 NaN/Inf。

    ⚠️ 修复前后都成立，用于守 `ss_tot == 0` 的除零兜底与 JSONB 可序列化。
    """
    s = CrossMarketMomentumStrategy(name="R²自检")
    score, annualized, r2 = s._calc_momentum_score(
        np.full(s.lookback_days + 1, 1000.0), s.lookback_days)
    assert r2 == 0.0 and annualized == 0.0 and score == 0.0
    assert all(np.isfinite(v) for v in (score, annualized, r2))
