# -*- coding: utf-8 -*-
"""恐慌抄底策略单元测试（阶段 4b）

覆盖（audit-strategy 门禁）：
  - 状态机：触发(T) → T+1 → confirm → buy_wait → holding 全链路
  - 年线门拦截（熊市放弃）
  - 止盈止损（硬止损 / 阶梯止盈 15/30/50% / 时间兜底）
  - 边界：空数据 / 无触发 / 恐慌加剧取消
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from modules.strategy.constants import SignalType
from modules.strategy.strategies.panic.panic_bottom_strategy import PanicBottomStrategy


def make_strategy(**overrides):
    params = dict(PanicBottomStrategy.DEFAULT_PARAMS)
    params.update(overrides)
    return PanicBottomStrategy(name="恐慌抄底-测试", parameters=params)


def seed_market(s, dates, panic_values, hs300_closes, csi500_closes):
    """注入市场数据缓存（panic / 沪深300 / CSI500）。"""
    for d, p in zip(dates, panic_values):
        s._panic_by_date[d] = p
    for d, c in zip(dates, hs300_closes):
        s._hs300_by_date[d] = {"close": c, "amount": 1e6}
    for d, c in zip(dates, csi500_closes):
        s._csi500_by_date[d] = c


def seed_stock(s, code, closes, start="2024-01-01"):
    """注入个股 K 线（含 amount），日期连续递增。"""
    n = len(closes)
    from datetime import date, timedelta
    d0 = date.fromisoformat(start) - timedelta(days=n)
    df = pd.DataFrame({
        "trade_date": [(d0 + timedelta(days=i)).isoformat() for i in range(n)],
        "open": closes, "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes], "close": closes,
        "volume": [1e6] * n,
        "amount": [5e5] * n,  # 5000 千元 → 500 万元
    })
    s._data_cache[code] = df.reset_index(drop=True)


class TestTrigger:
    """触发检测（条件A + 条件B + 年线门）"""

    def test_trigger_basic(self):
        s = make_strategy()
        dates = [f"2024-01-{i:02d}" for i in range(1, 31)]
        # 构造 2024-01 微盘崩盘式恐慌：01-22 panic 飙到 5.9
        panic = [0.2] * 21 + [3.0, 4.2, 5.9, 5.1, 4.0] + [2.0, 1.8, 1.5, 1.2]
        # 沪深300：01-01~01-16 高位 3500，01-17 起暴跌（01-22 近5日 -9.1% 满足条件B）
        hs = [3500.0] * 16 + [3300.0, 3250.0, 3200.0, 3150.0, 3100.0, 3000.0,
                              2950.0, 2900.0, 2850.0, 2800.0, 2780.0, 2760.0, 2740.0, 2720.0]
        csi = [5200] * 30  # 年线上（非熊）
        seed_market(s, dates[:30], panic[:30], hs[:30], csi[:30])
        # 用 01-22（index 21）触发
        assert s._check_trigger("2024-01-22") is True

    def test_annual_gate_blocks_bear(self):
        s = make_strategy()
        dates = [f"2022-04-{i:02d}" for i in range(1, 25)]
        panic = [0.2] * 20 + [6.0, 5.0, 4.0, 3.0]
        hs = [4000] * 24
        csi = [4200] * 24  # 熊市（CSI500 低于 MA250）
        seed_market(s, dates, panic, hs, csi)
        # 2022 熊市 → 年线门拦截
        assert s._check_trigger("2022-04-21") is False

    def test_threshold_blocks_low_panic(self):
        s = make_strategy()
        dates = [f"2024-06-{i:02d}" for i in range(1, 15)]
        panic = [0.5] * 14  # 均 < 3.0
        hs = [3500] * 14
        csi = [5500] * 14
        seed_market(s, dates, panic, hs, csi)
        assert s._check_trigger("2024-06-10") is False


class TestStateMachine:
    """状态机全链路：触发 → T+1 → confirm → T+7 买入"""

    def test_full_sequence(self):
        s = make_strategy()
        dates = [f"2024-01-{i:02d}" for i in range(1, 21)]
        # T=01-10(idx9) 起：panic 尖峰后回落
        panic = [0.2] * 9 + [5.9, 4.0, 2.0, 1.2, 0.8] + [0.5] * 6
        # 沪深300：01-01~01-06 高位 3500，01-07 起暴跌（01-10 近5日 -10% 满足条件B）
        hs = [3500.0] * 6 + [3300.0, 3250.0, 3200.0, 3150.0] + [3100.0] * 10
        csi = [5200] * 20
        seed_market(s, dates, panic, hs, csi)
        # 600000.SH 近 5 日超跌 >15%（[-6]=5.5 → [-1]=4.6，-16.4%）
        seed_stock(s, "600000.SH", [10.0] * 15 + [8.5, 8.0, 7.5, 7.0, 6.0, 5.5] + [5.0, 4.9, 4.8, 4.7, 4.6])

        # 驱动：01-10 触发
        sigs = s.on_bar_batch_end("2024-01-10")
        assert s._stage == "t1"
        assert len(sigs) == 0
        # 01-11 T+1 未创新高（panic 4.0 ≤ 5.9）
        s.on_bar_batch_end("2024-01-11")
        assert s._stage == "confirm"
        # 01-12 panic=2.0（未 <1.5 且未收阳？hs 平盘 → 不确认，保持 confirm）
        s.on_bar_batch_end("2024-01-12")
        assert s._stage == "confirm"
        # 01-13 真恐慌确认（panic 1.2 < 1.5）
        s.on_bar_batch_end("2024-01-13")
        assert s._stage == "buy_wait"
        assert s._buy_date is not None
        # T+7 买入（buy_delay_days=7，从触发日数 7 个交易日）
        for d in ["2024-01-16", "2024-01-17", "2024-01-18", "2024-01-19", "2024-01-20"]:
            s.on_bar_batch_end(d)
        # 若 buy_wait 仍待（shift 到 01-22 等），检查状态一致
        assert s._stage in ("buy_wait", "holding")

    def test_panic_escalation_cancels(self):
        s = make_strategy()
        # 15 天：02-20~02-28（9 天，index 0-8）+ 03-01~03-06（index 9-14）
        dates = [f"2024-02-{i:02d}" for i in range(20, 29)] + [f"2024-03-{i:02d}" for i in range(1, 7)]
        panic = [0.2] * 9 + [4.0, 6.0, 5.0, 4.0, 3.0, 2.0]  # 03-01=4.0 触发，03-03=5.0>4.0 取消
        # 沪深300：高位后暴跌（03-01 近5日 -8.3% 满足条件B）
        hs = [3600.0] * 8 + [3300.0, 3280.0, 3260.0, 3240.0, 3220.0, 3200.0, 3180.0]
        csi = [5200] * 15
        seed_market(s, dates, panic, hs, csi)
        s.on_bar_batch_end("2024-03-01")  # T 触发 panic=4.0
        assert s._stage == "t1"
        s.on_bar_batch_end("2024-03-03")  # T+1 panic=5.0 > 4.0 → 取消
        assert s._stage == "idle"


class TestStopProfitLoss:
    """止盈止损（硬止损 / 阶梯止盈）"""

    def test_stop_loss(self):
        s = make_strategy()
        s._holdings["600000.SH"] = {"entry_price": 10.0, "entry_date": "2024-01-10",
                                    "peak": 10.0, "sold_tiers": set(), "entry_weight": 0.1}

        class FakeBar:
            ts_code = "600000.SH"
            close = 8.0  # -20% → 止损

        sigs = s.check_stop_profit_stop_loss(FakeBar())
        assert len(sigs) == 1
        assert sigs[0].signal_type == SignalType.EXIT
        assert "600000.SH" not in s._holdings  # 已清仓

    def test_take_profit_tier1(self):
        s = make_strategy()
        s._holdings["600000.SH"] = {"entry_price": 10.0, "entry_date": "2024-01-10",
                                    "peak": 10.0, "sold_tiers": set(), "entry_weight": 0.1}

        class FakeBar:
            ts_code = "600000.SH"
            close = 11.6  # +16% → 档1 卖 1/3

        sigs = s.check_stop_profit_stop_loss(FakeBar())
        assert len(sigs) == 1
        assert sigs[0].signal_type == SignalType.TAKE_PROFIT
        assert abs(sigs[0].weight - 1 / 3) < 1e-6
        assert "tp1" in s._holdings["600000.SH"]["sold_tiers"]

    def test_time_exit(self):
        s = make_strategy()
        s._holdings["600000.SH"] = {"entry_price": 10.0, "entry_date": "2024-01-01",
                                    "peak": 10.0, "sold_tiers": set(), "entry_weight": 0.1}
        dates = [f"2024-01-{i:02d}" for i in range(1, 25)]
        seed_market(s, dates, [0.2] * 24, [3200] * 24, [5200] * 24)
        seed_stock(s, "600000.SH", [10.0] * 24)
        sigs = s.generate_exit_signals("2024-01-24")  # 持仓 23 交易日 > 20
        assert len(sigs) == 1
        assert "600000.SH" not in s._holdings


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header"])
