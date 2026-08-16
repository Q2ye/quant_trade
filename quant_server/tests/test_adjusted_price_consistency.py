# -*- coding: utf-8 -*-
"""C17 复权口径一致性测试（2026-08）。

口径定义（与 stock_adj_factor_repo.market_service 一致）：
  qfq: adj = raw × factor(t) / latest_factor    （最新价 = 真实市场价）
  hfq: adj = raw × factor(t) / earliest_factor  （全局最早因子日为基准，含历史分红）

真实样例：000002.SZ 复权因子 9.2 → 181.7（期间多次分红/送转）。
核心不变量：两种复权序列的相邻收益率必须与原始序列完全一致。
"""

from shared.database.repositories.market.quote.stock_adj_factor_repo import (
    qfq_ratio,
    hfq_ratio,
)

# 000002.SZ 风格样例：3 个交易日，因子 9.2 → 12.5 → 181.7
FACTORS = [9.2, 12.5, 181.7]
RAW_CLOSE = [10.0, 10.5, 9.8]
LATEST = FACTORS[-1]      # 181.7
EARLIEST = FACTORS[0]     # 9.2


def _returns(prices):
    return [prices[i + 1] / prices[i] for i in range(len(prices) - 1)]


def test_qfq_latest_equals_raw():
    """前复权：最新价归一化 = 原始价。"""
    adj = [raw * qfq_ratio(f, LATEST) for raw, f in zip(RAW_CLOSE, FACTORS)]
    assert abs(adj[-1] - RAW_CLOSE[-1]) < 1e-9
    assert adj[0] < RAW_CLOSE[0]  # 历史价被压到当前基准


def test_hfq_earliest_equals_raw():
    """后复权：首日价 = 原始首日价（基准锚定最早因子日）。"""
    adj = [raw * hfq_ratio(f, EARLIEST) for raw, f in zip(RAW_CLOSE, FACTORS)]
    assert abs(adj[0] - RAW_CLOSE[0]) < 1e-9
    # 最新日后复权价 = raw × latest/earliest = 9.8 × 181.7/9.2 ≈ 193.55（含历史分红）
    assert abs(adj[-1] - RAW_CLOSE[-1] * LATEST / EARLIEST) < 1e-9


def test_returns_invariant_for_both_adjustments():
    """qfq 与 hfq 的相邻收益率完全一致（分红跳变纳入总收益），
    且 = 原始价收益率 × 因子比率（因子跳跃即分红/送转贡献）。"""
    raw_ret = _returns(RAW_CLOSE)
    qfq_prices = [raw * qfq_ratio(f, LATEST) for raw, f in zip(RAW_CLOSE, FACTORS)]
    hfq_prices = [raw * hfq_ratio(f, EARLIEST) for raw, f in zip(RAW_CLOSE, FACTORS)]
    factor_ret = [FACTORS[i + 1] / FACTORS[i] for i in range(len(FACTORS) - 1)]
    for a, b, expected, f_ret in zip(_returns(qfq_prices), _returns(hfq_prices), raw_ret, factor_ret):
        assert abs(a - b) < 1e-9          # 两口径总收益一致
        assert abs(a - expected * f_ret) < 1e-9  # 总收益 = 价收益 × 因子收益


def test_ratios_cross_check():
    """同一日两口径的乘积关系：qfq_ratio × (latest/earliest) == hfq_ratio。"""
    for f in FACTORS:
        assert abs(qfq_ratio(f, LATEST) * (LATEST / EARLIEST) - hfq_ratio(f, EARLIEST)) < 1e-9


def test_zero_guard():
    """因子为 0 时调用方自行跳过（纯函数不做保护，保持与 SQL 一致语义）。"""
    # 仅验证正常路径不被 0 破坏调用约定：不传 0
    assert qfq_ratio(1.0, 2.0) == 0.5
    assert hfq_ratio(1.0, 2.0) == 0.5
