# -*- coding: utf-8 -*-
"""高波动策略 · 资金流因子单测（REQ-20261114-highvol-moneyflow-select）。

覆盖：
  1. 默认关闭 → 打分与无缓存时逐位一致
  2. 缓存缺失 → fail-open，分数不变
  3. B 接法（moneyflow_min）→ 资金流 ≤ 门槛时剔除
  4. A 接法（enable_moneyflow_factor）→ score × (0.5 + w×分位)
  5. 分位缓存按日惰性计算且落在 [0,1]
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from modules.strategy.strategies.rotation.high_vol_momentum_strategy import (
    HighVolMomentumStrategy,
)

CODE = "600000.SH"
TD = "2026-11-11"


def _make_strategy(**params) -> HighVolMomentumStrategy:
    s = HighVolMomentumStrategy(name="test-hv-mf", parameters=params)
    n = 300
    closes = 10.0 * np.power(1.002, np.arange(n))          # 单调上行 → 通过趋势/新高门
    closes[-1] = closes[-2] * 1.03                          # 末端再涨，确保创新高
    vols = np.full(n, 1_000_000.0)
    vols[-5:] = 3_000_000.0                                 # 近5日均量 ≥ 20日均量×1.2
    df = pd.DataFrame({
        "trade_date": [f"2025-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(n)],
        "open": closes, "high": closes, "low": closes, "close": closes,
        "volume": vols, "amount": np.full(n, 50_000.0),      # 千元 → 5000 万元
    })
    s._data_cache[CODE] = df
    s._bar_dates[CODE] = TD
    s._last_trade_date = TD
    s._market_mom60 = 0.05
    return s


def test_disabled_equals_no_cache():
    """默认关闭：有无资金流缓存，分数逐位一致。"""
    base = _make_strategy()
    with_mf = _make_strategy()
    with_mf._mf_ratio_cache = {(CODE, TD): -0.05}
    assert base._score_candidate(CODE) == pytest.approx(with_mf._score_candidate(CODE), rel=0, abs=0)


def test_fail_open_when_missing():
    """开启因子但当日无数据 → 分数与基线一致（fail-open）。"""
    base = _make_strategy()
    s = _make_strategy(enable_moneyflow_factor=True, moneyflow_weight=1.0)
    assert s._score_candidate(CODE) == pytest.approx(base._score_candidate(CODE), rel=0, abs=0)


def test_b_gate_rejects_negative_flow():
    """B 接法：资金流 ≤ 门槛 → 返回 None。"""
    s = _make_strategy(moneyflow_min=0.0)
    s._mf_ratio_cache = {(CODE, TD): -0.001}
    assert s._score_candidate(CODE) is None

    s2 = _make_strategy(moneyflow_min=0.0)
    s2._mf_ratio_cache = {(CODE, TD): 0.001}
    assert s2._score_candidate(CODE) is not None


def test_a_factor_scales_score():
    """A 接法：score × (0.5 + w×分位)。"""
    base = _make_strategy()
    s = _make_strategy(enable_moneyflow_factor=True, moneyflow_weight=1.0)
    s._mf_ratio_cache = {(CODE, TD): 0.001}
    expected = base._score_candidate(CODE) * (0.5 + 1.0 * 1.0)   # 唯一标的 → 分位=1
    assert s._score_candidate(CODE) == pytest.approx(expected, rel=1e-9)


def test_pct_in_range_and_cached():
    s = _make_strategy(enable_moneyflow_factor=True, moneyflow_weight=1.0)
    s._mf_ratio_cache = {(f"60000{i}.SH", TD): i / 10.0 for i in range(5)}
    p = s._mf_pct_for("600000.SH", TD)
    assert 0.0 <= p <= 1.0
    assert s._mf_pct_by_date[TD]                      # 已缓存
    assert s._mf_pct_for("999999.SH", TD) is None     # 无数据 → None
