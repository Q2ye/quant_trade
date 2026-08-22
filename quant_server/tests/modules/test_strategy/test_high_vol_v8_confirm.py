# -*- coding: utf-8 -*-
"""高波动动量轮动 v8.0 候选确认优化测试（方向1-4 + 优化）。

方向1: max_candidates 候选入池（8.1 默认 Top2）+ 确认用 pinfo.weight 固定仓位
      （v8.1 修复：废弃 v8.0 动态仓位 min(1/slots,cap)，其持仓=1 时超配导致资金不足）
方向2: ATR 自适应确认容差（k×ATR/信号价，随波动率动态，8.1 关闭用固定 0.5%）
方向3: confirm_window_days 确认窗口 + 破位守卫 + 窗口衰减（8.1 关闭）
方向4: K 线形态过滤（排除高开低走/冲高回落/收盘软弱，8.1 关闭）

测试隔离策略：override _confirm_gap_trading_days 返回可控 gap，
使测试聚焦确认逻辑本身（交易日历由该函数真实实现覆盖，单独测试）。
"""
import os

import pandas as pd

_STRATEGY_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..",
    "modules", "strategy", "strategies", "rotation",
    "high_vol_momentum_strategy.py",
)


def _load_strategy_class():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "high_vol_momentum_v8", os.path.abspath(_STRATEGY_PATH)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.HighVolMomentumStrategy


def _seed_ohlc(strategy, code, opens, closes, highs=None, lows=None,
               start="2026-08-10"):
    """注入带 OHLC 的历史 K 线（供形态过滤与 ATR）。"""
    import datetime as _dt
    if highs is None:
        highs = [max(o, c) * 1.02 for o, c in zip(opens, closes)]
    if lows is None:
        lows = [min(o, c) * 0.98 for o, c in zip(opens, closes)]
    df = pd.DataFrame({
        "trade_date": [(_dt.date.fromisoformat(start) + _dt.timedelta(days=i)).isoformat()
                       for i in range(len(closes))],
        "open": opens, "high": highs, "low": lows, "close": closes,
        "volume": [1e6] * len(closes), "amount": [1e7] * len(closes),
    })
    strategy._data_cache[code] = df.reset_index(drop=True)
    strategy._bar_dates[code] = str(df["trade_date"].iloc[-1])[:10]


def _make_strategy(gap=1, signal_price=100.0, **param_overrides):
    """构造带单候选的策略实例，gap 可控（override 交易日历）。

    param_overrides: 覆盖 DEFAULT_PARAMS（8.1 默认 Top2/0.5%/窗口1/关形态，
    方向 2/3/4 测试需显式传 8.0 参数开启对应特性）。
    """
    s = _load_strategy_class()(name="test", parameters=param_overrides or None)
    # 21 根平 bar + 末根由调用方覆盖；此处仅保证 ATR 有效（>0）
    closes = [signal_price] * 20 + [signal_price]
    _seed_ohlc(s, "600030.SH", [signal_price] * 21, closes)
    s._last_trade_date = s._bar_dates["600030.SH"]
    s._confirm_gap_trading_days = lambda _sd, _td: gap  # 可控 gap
    s._buy_pending["600030.SH"] = {
        "signal_price": signal_price, "weight": 0.5,
        "signal_date": "2026-08-10", "signal_id": "cand-1",
    }
    s.context = type("C", (), {"initial_capital": 100000})()
    return s

# 8.0 特性测试所需的显式参数（8.1 默认已关闭这些特性）
V80_PARAMS = {
    "max_candidates": 5,
    "confirm_tolerance": 0.02,
    "confirm_atr_mult": 1.0,
    "confirm_window_days": 3,
    "confirm_break_pct": 0.05,
    "confirm_decay_step": 0.005,
    "confirm_shape_enabled": True,
}


class TestDirection1_MaxCandidates:
    """方向1：候选入池 + 动态仓位（8.1 默认 Top2）"""

    def test_default_max_candidates_is_5(self):
        """8.1 默认候选上限 = 5（Top5 扩池，解决候选信号少）"""
        s = _load_strategy_class()(name="test")
        assert s.max_candidates == 5

    def test_max_candidates_param_override(self):
        s = _load_strategy_class()(name="test", parameters={"max_candidates": 5})
        assert s.max_candidates == 5

    def test_weight_uses_pinfo_fixed(self):
        """确认用候选入池的固定 weight（pinfo.weight），非动态 slots 计算"""
        s = _make_strategy(gap=1)
        # 候选入池 weight=0.5 → 确认后 sig.weight 应为 0.5
        sigs = s._confirm_pending_buys()
        assert any(sig.ts_code == "600030.SH" for sig in sigs)
        for sig in sigs:
            if sig.ts_code == "600030.SH":
                assert sig.weight == 0.5

    def test_weight_not_doubled_when_one_slot_left(self):
        """v8.1 修复：持仓=1 时确认新候选，weight 用 pinfo.weight(0.5)，
        而非 v8.0 动态的 min(1/1,0.5)=0.5——关键是不得再叠加成超配下单。
        本测试验证已持仓时确认仍用候选固定权重，不引入动态 bug。"""
        s = _make_strategy(gap=1)
        # 模拟已持仓 1 只（000002.SZ），确认 600030 时 weight 应为 0.5（pinfo.weight）
        s._holdings["000002.SZ"] = {
            "entry_price": 10.0, "weight": 0.5, "shares": 5000,
            "entry_date": "2026-08-09", "peak_high": 10.0, "is_bear": False,
        }
        sigs = s._confirm_pending_buys()
        assert any(sig.ts_code == "600030.SH" for sig in sigs)
        for sig in sigs:
            if sig.ts_code == "600030.SH":
                assert sig.weight == 0.5  # 用固定 0.5，不用动态 1.0


class TestDirection2_ATRTolerance:
    """方向2：ATR 自适应容差"""

    def test_atr_tolerance_high_vol(self):
        """高波动（ATR 大）→ 容差大"""
        s = _make_strategy(gap=1, **V80_PARAMS)
        # 注入高波动数据：近 20 根振幅 5%
        import numpy as np
        closes = [100.0] + [100 + 5 * np.sin(i) for i in range(20)]
        highs = [c + 3 for c in closes]
        lows = [c - 3 for c in closes]
        _seed_ohlc(s, "600030.SH", [c - 1 for c in closes], closes,
                   highs=highs, lows=lows)
        tol = s._atr_confirm_tolerance("600030.SH", 100.0)
        assert tol >= 0.03, f"高波动容差应≥3%，实际 {tol:.2%}"

    def test_atr_tolerance_low_vol(self):
        """低波动（ATR 小）→ 容差收窄到下限"""
        s = _make_strategy(gap=1, **V80_PARAMS)
        # 完全平 bar（high=low=close=100）→ ATR=0 → 回退固定容差 0.02
        _seed_ohlc(s, "600030.SH",
                   opens=[100.0] * 21, closes=[100.0] * 21,
                   highs=[100.0] * 21, lows=[100.0] * 21)
        tol = s._atr_confirm_tolerance("600030.SH", 100.0)
        assert 0.01 <= tol <= 0.02  # ATR≈0 时回退固定容差

    def test_confirm_within_atr_tolerance(self):
        """收盘 ≥ 确认价（信号价-k×ATR）→ 确认买入（7.1 会拒绝）"""
        s = _make_strategy(gap=1, **V80_PARAMS)
        # 高波动 → 容差大 → close=99 应确认
        import numpy as np
        closes = [100.0] + [100 + 5 * np.sin(i) for i in range(20)]
        closes[-1] = 99.0
        highs = [c + 3 for c in closes]
        lows = [c - 3 for c in closes]
        _seed_ohlc(s, "600030.SH", [c - 1 for c in closes], closes,
                   highs=highs, lows=lows)
        tol = s._atr_confirm_tolerance("600030.SH", 100.0)
        floor = 100 * (1 - tol)
        assert 99.0 >= floor, f"close=99 应≥确认价{floor:.2f}"
        sigs = s._confirm_pending_buys()
        assert any(sig.ts_code == "600030.SH" for sig in sigs)


class TestDirection3_Window:
    """方向3：确认窗口 3 天 + 破位守卫 + 窗口衰减"""

    def test_candidate_retained_within_window(self):
        """T+1 未达标（收盘低于确认价）→ 保留候选待 T+2（窗口特性，需 8.0 参数）"""
        s = _make_strategy(gap=1, **V80_PARAMS)
        # 平 bar → ATR=0 → 回退容差 0.02 → floor=98；close=97 < 98 → 未达标保留
        _seed_ohlc(s, "600030.SH",
                   opens=[100.0] * 21, closes=[100.0] * 20 + [97.0],
                   highs=[100.0] * 21, lows=[100.0] * 21)
        sigs = s._confirm_pending_buys()
        # 窗口内：不产生买入信号，且候选被保留
        assert not any(sig.ts_code == "600030.SH" for sig in sigs)
        assert "600030.SH" in s._buy_pending

    def test_candidate_dropped_after_window(self):
        """T+3 仍未达标 → 候选被放弃（rejected）"""
        s = _make_strategy(gap=3, **V80_PARAMS)
        # gap=3 → decay=(3-1)×0.5%=1% → floor=100×(1-0.02+0.01)=99；close=97<99 → 放弃
        _seed_ohlc(s, "600030.SH",
                   opens=[100.0] * 21, closes=[100.0] * 20 + [97.0],
                   highs=[100.0] * 21, lows=[100.0] * 21)
        sigs = s._confirm_pending_buys()
        assert not any(sig.ts_code == "600030.SH" for sig in sigs)
        assert "600030.SH" not in s._buy_pending
        assert "cand-1" in s._rejected_candidate_ids

    def test_break_guard_drops_immediately(self):
        """破位守卫：窗口内收盘跌破 信号价×(1-5%) → 立即放弃（不等窗口结束）"""
        s = _make_strategy(gap=1, **V80_PARAMS)
        _seed_ohlc(s, "600030.SH",
                   opens=[100.0] * 21, closes=[100.0] * 20 + [93.0],  # 93 < 95 破位线
                   highs=[100.0] * 21, lows=[100.0] * 21)
        sigs = s._confirm_pending_buys()
        assert not any(sig.ts_code == "600030.SH" for sig in sigs)
        assert "600030.SH" not in s._buy_pending   # 破位立即移除，不等窗口
        assert "cand-1" in s._rejected_candidate_ids

    def test_window_decay_raises_bar_for_late_confirm(self):
        """窗口衰减：gap=2 时门槛上移 0.5% → 需收盘明显高于信号价才确认"""
        s = _make_strategy(gap=2, **V80_PARAMS)
        # 平 bar → 回退容差 0.02，decay=(2-1)×0.5%=0.5% → floor=100×(1-0.02+0.005)=98.5
        # close=98.5 恰好达标；用 98.4 应未达标（验证衰减确实抬升门槛）
        _seed_ohlc(s, "600030.SH",
                   opens=[100.0] * 21, closes=[100.0] * 20 + [98.4],
                   highs=[100.0] * 21, lows=[100.0] * 21)
        sigs = s._confirm_pending_buys()
        assert not any(sig.ts_code == "600030.SH" for sig in sigs)


class TestDirection4_Shape:
    """方向4：K 线形态过滤"""

    def test_high_open_low_close_rejected(self):
        """开盘涨停、收盘回落（高开低走）→ 形态拦截（需开启形态过滤）"""
        s = _make_strategy(gap=1, **V80_PARAMS)
        _seed_ohlc(s, "600030.SH",
                   opens=[100.0] * 20 + [110.0],
                   closes=[100.0] * 20 + [99.0],
                   highs=[100.0] * 20 + [110.0],
                   lows=[100.0] * 20 + [95.0])
        sigs = s._confirm_pending_buys()
        assert not any(sig.ts_code == "600030.SH" for sig in sigs)

    def test_long_upper_shadow_rejected(self):
        """长上影冲高回落 → 形态拦截（需开启形态过滤）"""
        s = _make_strategy(gap=1, **V80_PARAMS)
        _seed_ohlc(s, "600030.SH",
                   opens=[100.0] * 20 + [99.0],
                   closes=[100.0] * 20 + [99.0],
                   highs=[100.0] * 20 + [105.0],
                   lows=[100.0] * 20 + [95.0])
        sigs = s._confirm_pending_buys()
        assert not any(sig.ts_code == "600030.SH" for sig in sigs)

    def test_clean_bullish_bar_confirm(self):
        """实体阳线 + 收盘位置高 + 无长上影 → 确认买入（需开启形态过滤）"""
        s = _make_strategy(gap=1, **V80_PARAMS)
        _seed_ohlc(s, "600030.SH",
                   opens=[100.0] * 20 + [99.0],
                   closes=[100.0] * 20 + [101.0],
                   highs=[100.0] * 20 + [102.0],
                   lows=[100.0] * 20 + [98.0])
        sigs = s._confirm_pending_buys()
        assert any(sig.ts_code == "600030.SH" for sig in sigs)


class TestV81_MinimalBaseline:
    """8.1 最小干预基线：Top5 候选 + 确认后按确认数分仓 + 0.5% 容差"""

    def test_defaults_match_v81(self):
        """8.1 默认参数：Top5 + 0.5% 容差 + 窗口2 + A/B质量门 + 关闭 ATR/破位/衰减/形态"""
        s = _load_strategy_class()(name="test")
        assert s.max_candidates == 5
        assert s.confirm_tolerance == 0.005
        assert s.confirm_atr_mult == 0.0
        assert s.confirm_window_days == 2          # 方向C：窗口 2 天
        assert s.confirm_break_pct == 0.0
        assert s.confirm_decay_step == 0.0
        assert s.confirm_shape_enabled is False
        assert s.confirm_rank_sort is True          # 方向A：确认按强度排序
        assert s.confirm_score_threshold == 0.50    # 方向B：强/弱分界

    def test_tiny_tolerance_allows_micro_dip(self):
        """0.5% 容差：收盘 -0.4%（如 601886 -0.16% 量级）→ 确认买入"""
        s = _make_strategy(gap=1)  # 默认 8.1 参数
        # close=99.6（-0.4%）≥ 99.5（0.5% 容差）→ 确认
        _seed_ohlc(s, "600030.SH",
                   opens=[100.0] * 21, closes=[100.0] * 20 + [99.6],
                   highs=[100.0] * 21, lows=[100.0] * 21)
        sigs = s._confirm_pending_buys()
        assert any(sig.ts_code == "600030.SH" for sig in sigs)

    def test_tiny_tolerance_still_rejects_big_dip(self):
        """0.5% 容差：收盘 -2%（超容差）→ 拒绝（8.1 不放宽过度）"""
        # 窗口=2 时 T+1 失败保留待 T+2；用 gap=2（超窗口）验证最终放弃
        s = _make_strategy(gap=2)  # 默认 8.1 参数，窗口=2，gap=2 超期 → 放弃
        _seed_ohlc(s, "600030.SH",
                   opens=[100.0] * 21, closes=[100.0] * 20 + [98.0],
                   highs=[100.0] * 21, lows=[100.0] * 21)
        sigs = s._confirm_pending_buys()
        assert not any(sig.ts_code == "600030.SH" for sig in sigs)
        # gap=2 超窗口 → 直接放弃（不保留）
        assert "600030.SH" not in s._buy_pending

    def test_shape_filter_disabled_by_default(self):
        """8.1 默认关闭形态过滤 → 高开低走也不拦截（7.1 基线行为）"""
        s = _make_strategy(gap=1)  # 默认 8.1，confirm_shape_enabled=False
        # 高开 110 收 99（高开低走），但 99 ≥ 99.5? 否 → 应因价格拒绝而非形态
        # 用 99.6（价格达标）验证形态开关：若形态开启会拦截，关闭则确认
        _seed_ohlc(s, "600030.SH",
                   opens=[100.0] * 20 + [110.0],
                   closes=[100.0] * 20 + [99.6],
                   highs=[100.0] * 20 + [110.0],
                   lows=[100.0] * 20 + [95.0])
        sigs = s._confirm_pending_buys()
        # 99.6 ≥ 99.5（0.5% 容差）→ 确认（形态已关闭不拦截）
        assert any(sig.ts_code == "600030.SH" for sig in sigs)

    # ---- v8.1 两阶段分仓测试：确认后按确认通过的信号数平均分配 ----

    def _make_multi_candidate(self, closes_map, gap=1, scores=None, **overrides):
        """构造多候选策略：closes_map = {code: [closes...]}，末根为确认日收盘。
        scores: {code: score}，注入候选 score（v8.1-A/B 测试用）。"""
        s = _load_strategy_class()(name="test", parameters=overrides or None)
        for code, closes in closes_map.items():
            _seed_ohlc(s, code, [100.0] * 21, closes,
                       highs=[100.0] * 21, lows=[100.0] * 21)
            pinfo = {
                "signal_price": 100.0, "weight": 0.5,
                "signal_date": "2026-08-10", "signal_id": f"cand-{code[:6]}",
            }
            if scores and code in scores:
                pinfo["score"] = scores[code]
            s._buy_pending[code] = pinfo
        s._last_trade_date = s._bar_dates[list(closes_map.keys())[0]]
        s._confirm_gap_trading_days = lambda _sd, _td: gap
        s.context = type("C", (), {"initial_capital": 100000})()
        return s

    def test_two_confirm_split_50_each(self):
        """确认 2 只 → 各 50% 仓位（2×50%=100% 满仓自洽，不超配）"""
        s = self._make_multi_candidate({
            "600030.SH": [100.0] * 20 + [100.5],   # 达标
            "600031.SH": [100.0] * 20 + [100.8],   # 达标
        })
        sigs = s._confirm_pending_buys()
        assert len(sigs) == 2
        for sig in sigs:
            assert sig.weight == 0.5

    def test_one_confirm_capped_50(self):
        """只确认 1 只 → weight=min(1/1, 0.5)=0.5（单票 cap，不满仓追高）"""
        s = self._make_multi_candidate({
            "600030.SH": [100.0] * 20 + [100.5],   # 达标
            "600031.SH": [100.0] * 20 + [99.0],    # 不达标（-1% 超容差）
        })
        sigs = s._confirm_pending_buys()
        assert len(sigs) == 1
        assert sigs[0].ts_code == "600030.SH"
        assert sigs[0].weight == 0.5

    def test_existing_holding_confirms_one_no_overallocation(self):
        """v8.1 修复：已有 1 只持仓时确认 1 只新候选 → 50%，
        不出现 v8.0 动态 slots=1 → 1.0 超配（资金不足 bug 根因）"""
        s = self._make_multi_candidate({
            "600030.SH": [100.0] * 20 + [100.5],   # 达标
            "600031.SH": [100.0] * 20 + [100.8],   # 达标
        })
        # 已有 1 只持仓 → 只剩 1 空位，但两阶段确认时预占位拦截，
        # 最终只确认 1 只（600030），weight=0.5
        s._holdings["000002.SZ"] = {
            "entry_price": 10.0, "weight": 0.5, "shares": 5000,
            "entry_date": "2026-08-09", "peak_high": 10.0, "is_bear": False,
        }
        sigs = s._confirm_pending_buys()
        assert len(sigs) == 1   # 只剩 1 空位 → 只确认 1 只
        assert sigs[0].weight == 0.5  # 50%，不超配

    # ---- v8.1-A/B/C 三方向测试 ----

    def test_directionA_rank_sort_buys_strongest(self):
        """方向A：确认数超空位时，按 score 降序只买最强（过滤平庸）"""
        # 空位=2（max_positions=2），3 只确认通过 → 只买 score 最高的 2 只
        s = self._make_multi_candidate({
            "600030.SH": [100.0] * 20 + [100.5],   # 达标 score=0.3（弱）
            "600031.SH": [100.0] * 20 + [100.5],   # 达标 score=0.8（强）
            "600032.SH": [100.0] * 20 + [100.5],   # 达标 score=0.6（中）
        }, scores={"600030.SH": 0.3, "600031.SH": 0.8, "600032.SH": 0.6})
        sigs = s._confirm_pending_buys()
        # 只买 2 只（空位=2），且是 score 最高的 600031(0.8)+600032(0.6)，排除弱 600030
        assert len(sigs) == 2
        bought = {sig.ts_code for sig in sigs}
        assert "600031.SH" in bought and "600032.SH" in bought
        assert "600030.SH" not in bought  # 弱信号被过滤

    def test_directionB_weak_signal_strict_confirm(self):
        """方向B：弱信号（score<0.5）容差=0 → 收盘 99.6（-0.4%）不确认；强信号可确认"""
        # 弱信号 600030（score=0.3）：close=99.6 ≥ 99.5（0.5%容差）本应确认，
        # 但方向B容差=0 → confirm_floor=100 → 99.6<100 不确认
        s = self._make_multi_candidate({
            "600030.SH": [100.0] * 20 + [99.6],   # 弱信号
            "600031.SH": [100.0] * 20 + [99.6],   # 强信号
        }, scores={"600030.SH": 0.3, "600031.SH": 0.8})
        sigs = s._confirm_pending_buys()
        # 弱 600030 不确认（容差0）；强 600031 容差0.5% → 99.6≥99.5 确认
        bought = {sig.ts_code for sig in sigs}
        assert "600031.SH" in bought
        assert "600030.SH" not in bought

    def test_directionC_window_2_retains_for_second_day(self):
        """方向C：窗口 2 天 → T+1 失败保留待 T+2，不直接放弃"""
        s = self._make_multi_candidate({
            "600030.SH": [100.0] * 20 + [98.0],   # T+1 失败（-2%）
        }, gap=1)  # 默认窗口=2
        sigs = s._confirm_pending_buys()
        assert not any(sig.ts_code == "600030.SH" for sig in sigs)
        # 窗口内（gap=1<2）→ 保留待 T+2
        assert "600030.SH" in s._buy_pending
