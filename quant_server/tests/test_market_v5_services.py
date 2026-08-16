# -*- coding: utf-8 -*-
"""Market 概览页 v5 新增服务纯函数测试（温度计 / 涨停梯队口径）

覆盖：
- N1 温度计：percentile_rank / rolling_sum / classify_zone / synthesize_temperature
- N3 涨停梯队：build_ladder / calc_bust_rate / classify_emotion_phase
"""
from modules.market.services.market_temperature_service import (
    percentile_rank,
    rolling_sum,
    classify_zone,
    synthesize_temperature,
)
from modules.market.services.limit_service import (
    build_ladder,
    calc_bust_rate,
    classify_emotion_phase,
)
from modules.market.services.breadth_service import (
    calc_annualized_vol,
    rolling_vol,
)
from modules.market.services._swr_cache import SwrCache


class TestPercentileRank:
    def test_empty_series_returns_none(self):
        assert percentile_rank([], 1.0) is None

    def test_current_is_max(self):
        assert percentile_rank([1.0, 2.0, 3.0], 3.0) == 100.0

    def test_current_is_min(self):
        assert percentile_rank([1.0, 2.0, 3.0], 1.0) == 33.3

    def test_ties_count_towards_current(self):
        assert percentile_rank([1.0, 2.0, 2.0, 3.0], 2.0) == 75.0

    def test_none_values_ignored(self):
        assert percentile_rank([1.0, None, 3.0], 2.0) == 50.0

    def test_current_none_returns_none(self):
        assert percentile_rank([1.0, 2.0], None) is None


class TestRollingSum:
    def test_prefix_none(self):
        assert rolling_sum([1, 2, 3, 4], 3) == [None, None, 6, 9]

    def test_window_larger_than_series(self):
        assert rolling_sum([1, 2], 3) == [None, None]

    def test_window_one(self):
        assert rolling_sum([1, 2, 3], 1) == [1, 2, 3]


class TestClassifyZone:
    def test_boundaries(self):
        assert classify_zone(29.9) == "低温"
        assert classify_zone(30.0) == "中性"
        assert classify_zone(70.0) == "中性"
        assert classify_zone(70.1) == "高温"


class TestSynthesizeTemperature:
    @staticmethod
    def _dim(value, pctl):
        return {"value": value, "percentile": pctl}

    def test_equal_weight(self):
        out = synthesize_temperature(
            self._dim(10, 10), self._dim(20, 20), self._dim(30, 30), self._dim(40, 40))
        assert out["temperature"] == 25.0
        assert out["zone"] == "低温"
        assert out["sample_warning"] is False

    def test_missing_dim_raises_warning(self):
        out = synthesize_temperature(
            self._dim(10, 10), self._dim(20, 20), self._dim(None, None), self._dim(40, 40))
        assert out["temperature"] == 23.3  # (10+20+40)/3
        assert out["sample_warning"] is True

    def test_all_missing(self):
        out = synthesize_temperature(
            self._dim(None, None), self._dim(None, None),
            self._dim(None, None), self._dim(None, None))
        assert out["temperature"] is None
        assert out["zone"] is None
        assert out["sample_warning"] is True


class TestBuildLadder:
    def test_buckets(self):
        assert build_ladder([1, 1, 2, 3, 4, 5]) == {
            "board1": 2, "board2": 1, "board3": 1, "board4plus": 2}

    def test_empty(self):
        assert build_ladder([]) == {"board1": 0, "board2": 0, "board3": 0, "board4plus": 0}

    def test_none_treated_as_first_board(self):
        assert build_ladder([None, 0, 1]) == {"board1": 3, "board2": 0, "board3": 0, "board4plus": 0}


class TestCalcBustRate:
    def test_normal(self):
        assert calc_bust_rate(100, 70) == 30.0

    def test_zero_denominator(self):
        assert calc_bust_rate(0, 0) is None


class TestClassifyEmotionPhase:
    def test_cold_no_bust_sample(self):
        assert classify_emotion_phase(10, None, 1, 10, 15)[0] == "冰点"

    def test_recovery_no_bust_sample(self):
        assert classify_emotion_phase(25, None, 1, 25, 20)[0] == "修复"

    def test_cold_high_bust(self):
        assert classify_emotion_phase(10, 45.0, 1, 10, 15)[0] == "冰点"

    def test_retreat(self):
        assert classify_emotion_phase(50, 40.0, 2, 50, 80)[0] == "退潮"

    def test_climax_height(self):
        assert classify_emotion_phase(30, 20.0, 5, 30, 25)[0] == "高潮"

    def test_climax_count(self):
        assert classify_emotion_phase(90, 20.0, 2, 90, 40)[0] == "高潮"

    def test_ferment(self):
        assert classify_emotion_phase(50, 20.0, 2, 50, 40)[0] == "发酵"

    def test_recovery(self):
        assert classify_emotion_phase(25, 20.0, 1, 25, 20)[0] == "修复"

    def test_fallback_stable_cold(self):
        assert classify_emotion_phase(10, 20.0, 1, 10, 12)[0] == "冰点"

    def test_retreat_requires_prev(self):
        # 无前一日数据时不判退潮，落入发酵
        assert classify_emotion_phase(50, 40.0, 2, 50, None)[0] == "发酵"


class TestCalcAnnualizedVol:
    def test_flat_series_zero(self):
        assert calc_annualized_vol([0.0, 0.0, 0.0]) == 0.0

    def test_volatile_series_positive(self):
        v = calc_annualized_vol([1.0, -1.0, 1.0, -1.0])
        assert v > 0

    def test_single_point_zero(self):
        assert calc_annualized_vol([1.0]) == 0.0

    def test_empty_zero(self):
        assert calc_annualized_vol([]) == 0.0


class TestRollingVol:
    def test_prefix_none(self):
        r = rolling_vol([1.0, -1.0, 1.0], 2)
        assert r[0] is None
        assert all(v is not None and v >= 0 for v in r[1:])

    def test_window_larger_than_series(self):
        r = rolling_vol([1.0, 2.0], 3)
        assert r == [None, None]


class TestSwrCache:
    """SWR 缓存：过期返回旧值 + 后台重算标记（P2）"""

    def test_miss_then_fresh(self):
        c = SwrCache(ttl=300)
        assert c.probe("k") == (None, False)
        c.set("k", {"v": 1})
        assert c.probe("k") == ({"v": 1}, False)

    def test_expired_returns_stale_and_needs_recompute(self):
        c = SwrCache(ttl=300)
        c.set("k", 42)
        c._entries["k"]["ts"] -= 999  # 模拟过期
        assert c.probe("k") == (42, True)

    def test_expired_with_pending_task_no_recompute(self):
        c = SwrCache(ttl=300)
        c.set("k", 42)
        c._entries["k"]["ts"] -= 999

        class _FakePendingTask:
            def done(self):
                return False

        c.set_task("k", _FakePendingTask())  # type: ignore
        assert c.probe("k") == (42, False)

    def test_expired_with_done_task_needs_recompute(self):
        c = SwrCache(ttl=300)
        c.set("k", 42)
        c._entries["k"]["ts"] -= 999

        class _DoneTask:
            def done(self):
                return True

        c.set_task("k", _DoneTask())  # type: ignore
        assert c.probe("k") == (42, True)

    def test_overwrite_updates_timestamp(self):
        c = SwrCache(ttl=300)
        c.set("k", 1)
        c._entries["k"]["ts"] -= 999
        c.set("k", 2)  # 后台重算完成回写 → 重新变新鲜
        assert c.probe("k") == (2, False)

    def test_custom_ttl_override(self):
        c = SwrCache(ttl=300)
        c.set("k", 42, ttl=50)  # 样本不足短 TTL
        assert c.probe("k") == (42, False)
        c._entries["k"]["ts"] -= 60  # 超过 50s → 过期
        assert c.probe("k") == (42, True)
