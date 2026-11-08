# -*- coding: utf-8 -*-
"""日频底座门禁判据测试（纯函数，不连库）。"""

from __future__ import annotations

from datetime import date

from scripts.quality.check_daily_base import (
    judge_dense,
    judge_periodic,
    judge_sparse,
)


def test_dense_missing_is_fail():
    assert judge_dense(None, date(2026, 11, 6), 0, 0)[0] == "FAIL"


def test_dense_fresh_and_full_is_pass():
    status, _ = judge_dense(date(2026, 11, 6), date(2026, 11, 6), 100, 100)
    assert status == "PASS"


def test_dense_stale_is_fail():
    status, _ = judge_dense(date(2026, 11, 1), date(2026, 11, 6), 100, 100)
    assert status == "FAIL"


def test_dense_partial_load_is_fail():
    status, _ = judge_dense(date(2026, 11, 6), date(2026, 11, 6), 50, 100)
    assert status == "FAIL"


def test_sparse_no_data_is_fail():
    assert judge_sparse(0, 60, [])[0] == "FAIL"


def test_sparse_normal_is_pass():
    assert judge_sparse(30, 60, [10] * 30)[0] == "PASS"


def test_sparse_low_coverage_is_warn():
    assert judge_sparse(3, 60, [1, 1, 1])[0] == "WARN"


def test_periodic_lagging_is_fail():
    assert judge_periodic("202609", "202610")[0] == "FAIL"


def test_periodic_current_is_pass():
    assert judge_periodic("202610", "202610")[0] == "PASS"
