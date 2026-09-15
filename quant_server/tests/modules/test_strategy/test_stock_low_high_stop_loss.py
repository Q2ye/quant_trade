# -*- coding: utf-8 -*-
"""低吸轮动（StockLowHigh）止损判据回归 —— 2026-09-15 符号统一。

**为什么补这个文件**：`stock_low_high_strategy.py` 此前**无任何测试文件**，
而 2026-09-15 的「止损符号统一」动了它最危险的一处 ——
判据由 `x < stop_loss`（stop_loss = **-0.04**，负值域）改为 `x < -stop_loss_pct`（**正数**阈值）。
若符号翻转写错，止损会变成「涨 4% 才卖」，属灾难性回归，故必须锁死。

锁定三件事：
1. 参数键已改名且为**正数**（`stop_loss_pct` / `sideways_stop_loss_pct` / `bear_stop_loss_pct`）；
2. 触发边界 = `entry × (1 − stop_loss_pct)`，**严格小于**才触发（边界内侧不触发）；
3. **日内止损语义**：收盘价未破但当日 `low` 破了也触发（v6.11 行为，且信号带 `trigger_price`）。
"""
import datetime as _dt
import importlib.util
import os
from types import SimpleNamespace

import pandas as pd
import pytest

_STRATEGY_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..",
    "modules", "strategy", "strategies", "reference", "stock_low_high_strategy.py",
)


def _load_strategy_class():
    """按既有测试模式从文件加载策略类（避免包级副作用）。"""
    spec = importlib.util.spec_from_file_location(
        "stock_low_high_strategy", os.path.abspath(_STRATEGY_PATH)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.StockLowHighStrategy


class TestStopLossSignUnification:
    """止损符号统一（负值域 → 正数跌幅阈值）回归。"""

    CODE = "600000.SH"
    ENTRY = 10.0
    #: 与 DEFAULT_PARAMS 的三档一致（2026-09-15 统一为正数）
    BASE = {"stop_loss_pct": 0.04, "sideways_stop_loss_pct": 0.04, "bear_stop_loss_pct": 0.04}

    @classmethod
    def _make(cls, pct=0.04, close=None, low=None, entry=None):
        """构造一个「已持仓 + 有当日行情」的最小状态。"""
        s = _load_strategy_class()(name="止损回归测试")
        entry = entry or cls.ENTRY
        low = low if low is not None else (close if close is not None else entry)
        s._holdings[cls.CODE] = {"entry_price": entry, "entry_date": "2026-08-10", "shares": 1000}
        s._data_cache[cls.CODE] = pd.DataFrame({
            "trade_date": ["2026-08-14"],
            "close": [close if close is not None else entry],
            "low": [low],
            "high": [entry],
        })
        s._track_high[cls.CODE] = entry
        # 与 entry_date 不同日 → 不触发「同日买入」跳过分支
        s._last_trade_date = "2026-08-14"
        return s

    def test_param_keys_renamed_and_positive(self):
        """三个止损参数键已改名且全为正数（原为 stop_loss/bear_/sideways_ = -0.04）"""
        s = _load_strategy_class()(name="参数校验")
        for key, expect in self.BASE.items():
            assert key in s.parameters, f"应存在正数键 {key}"
            assert abs(float(s.parameters[key]) - expect) < 1e-12, \
                f"{key} 应为 {expect}（正数跌幅阈值），实际 {s.parameters[key]}"
        for legacy in ("stop_loss", "sideways_stop_loss", "bear_stop_loss"):
            assert legacy not in s.parameters, f"旧负值键 {legacy} 不应残留"

    @pytest.mark.parametrize("pct", [0.03, 0.04, 0.05, 0.08])
    def test_boundary_inside_not_triggered(self, pct):
        """边界内侧（ε）不触发 —— 判据为严格小于"""
        eps = 1e-6
        s = self._make(pct=pct, close=self.ENTRY * (1 - pct + eps),
                       low=self.ENTRY * (1 - pct + eps))
        sigs = s._check_all_stop_profit(today_pool={self.CODE}, stop_loss_pct=pct)
        assert sigs == [], f"边界内侧不应触发（pct={pct}）"

    @pytest.mark.parametrize("pct", [0.03, 0.04, 0.05, 0.08])
    def test_boundary_outside_triggered(self, pct):
        """边界外侧（ε）触发止损，且 trigger_price = entry×(1−pct)"""
        eps = 1e-6
        s = self._make(pct=pct, close=self.ENTRY * (1 - pct - eps),
                       low=self.ENTRY * (1 - pct - eps))
        sigs = s._check_all_stop_profit(today_pool={self.CODE}, stop_loss_pct=pct)
        assert len(sigs) == 1, f"边界外侧应触发止损（pct={pct}）"
        from modules.strategy.constants import SignalType
        assert sigs[0].signal_type == SignalType.STOP_LOSS
        assert abs(float(sigs[0].trigger_price) - self.ENTRY * (1 - pct)) < 1e-9, \
            "trigger_price 应为 entry×(1−pct)"

    def test_intraday_low_triggers_even_if_close_ok(self):
        """日内止损语义：收盘未破但当日 low 破了 → 仍触发（v6.11 行为）

        这是符号统一最易被误伤的语义 —— 若把判据写成 `low_pnl < stop_loss`（旧负值域）
        而阈值已改正数，则跌破永不触发（漏止损）。
        """
        pct = 0.04
        s = self._make(pct=pct,
                       close=self.ENTRY * 1.01,          # 收盘 +1%，未破
                       low=self.ENTRY * (1 - pct) * 0.995)  # 盘中破 4%
        sigs = s._check_all_stop_profit(today_pool={self.CODE}, stop_loss_pct=pct)
        assert len(sigs) == 1, "日内 low 破位应触发止损（收盘价正常也不例外）"

    def test_no_trigger_when_profitable(self):
        """盈利时不触发止损（防符号写反导致『涨了才卖』）"""
        s = self._make(close=self.ENTRY * 1.10, low=self.ENTRY * 1.05)
        sigs = s._check_all_stop_profit(today_pool={self.CODE}, stop_loss_pct=0.04)
        assert sigs == [], "浮盈 +10% 绝不应触发止损"
