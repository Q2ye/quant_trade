# -*- coding: utf-8 -*-
"""变异检查：把 `_calc_momentum_score` 打回**修复前**公式，跑新测试，确认回归守卫会失败。

只在本进程内 monkeypatch，不改磁盘文件。用于证明新增测试不是空断言。
"""
import math
import sys
import traceback

import numpy as np

sys.path.insert(0, ".")


def _old_calc_momentum_score(self, closes, lookback):
    """修复前的实现（fit=W，ss_res/ss_tot 用 weights，中心化用无权 np.mean(y)）。"""
    closes = np.asarray(closes, dtype=np.float64)
    if closes.size < lookback + 1:
        return None, None, None
    recent = closes[-(lookback + 1):]
    if not np.all(np.isfinite(recent)) or np.any(recent <= 0):
        return None, None, None
    y = np.log(recent)
    x = np.arange(len(y), dtype=np.float64)
    weights = np.linspace(1.0, 2.0, len(y))
    W = weights ** 2
    W_sum = float(np.sum(W))
    if W_sum <= 0:
        return None, None, None
    x_bar = float(np.sum(W * x) / W_sum)
    y_bar = float(np.sum(W * y) / W_sum)
    dx = x - x_bar
    dy = y - y_bar
    var_x = float(np.sum(W * dx ** 2))
    if var_x <= 0:
        return 0.0, 0.0, 0.0
    slope = float(np.sum(W * dx * dy) / var_x)
    intercept = y_bar - slope * x_bar
    annualized = float(math.exp(slope * 250.0) - 1.0)
    y_pred = slope * x + intercept
    ss_res = float(np.sum(weights * (y - y_pred) ** 2))
    ss_tot = float(np.sum(weights * (y - float(np.mean(y))) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return float(annualized * r2), annualized, r2


def main() -> None:
    from modules.strategy.strategies.rotation.cross_market_momentum_strategy import (
        CrossMarketMomentumStrategy,
    )

    import tests.modules.test_strategy.test_cross_market_filters as T

    R2_TESTS = [
        "test_r2_is_one_for_perfect_log_linear_series",
        "test_r2_always_within_unit_interval",
        "test_score_sign_matches_annualized_sign",
        "test_downtrend_with_poor_fit_no_longer_scores_positive",
        "test_r2_zero_for_constant_series",
    ]

    for label, patch in (("修复后（当前代码）", False), ("修复前（旧公式）", True)):
        if patch:
            CrossMarketMomentumStrategy._calc_momentum_score = _old_calc_momentum_score
        else:
            import importlib
            importlib.reload(
                sys.modules[
                    "modules.strategy.strategies.rotation.cross_market_momentum_strategy"])
            CrossMarketMomentumStrategy = sys.modules[
                "modules.strategy.strategies.rotation.cross_market_momentum_strategy"
            ].CrossMarketMomentumStrategy
            T.CrossMarketMomentumStrategy = CrossMarketMomentumStrategy

        print("=" * 88)
        print(f"  {label}")
        print("=" * 88)
        nfail = 0
        for name in R2_TESTS:
            fn = getattr(T, name)
            try:
                fn()
                print(f"    {name:<58} PASS")
            except AssertionError as e:
                nfail += 1
                first = str(e).splitlines()[0][:80] if str(e) else "(无消息)"
                print(f"    {name:<58} ✗ FAIL  {first}")
            except Exception as e:
                nfail += 1
                print(f"    {name:<58} ✗ ERROR {type(e).__name__}: {str(e)[:60]}")
                traceback.print_exc(limit=1)
        print(f"    → 失败 {nfail}/{len(R2_TESTS)}")
        print()


if __name__ == "__main__":
    main()
