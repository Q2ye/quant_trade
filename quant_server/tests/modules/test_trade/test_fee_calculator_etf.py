# -*- coding: utf-8 -*-
"""B2：实盘收费器必须对场内基金（ETF/LOF）豁免印花税与过户费（2026-10-09 修复）。

## 背景

`CostCalculator.calculate_trade_cost` 的 `ts_code` 形参**被接收却从未使用** ——
对**所有** `sell` 都计 0.05% 印花税、对全方向都计 0.01% 过户费。
而回测侧 `backtest_broker._fee_rates(order.ts_code)` 早已按 `is_etf` 正确豁免
（`stamp_tax_etf = 0.0` / `transfer_fee_rate_etf = 0.0`）。

⇒ **回测↔实盘费率口径不一致，实盘被单方面多扣。**

实测锚（生产库 `trades`，豆粕 ETF `159985.SZ` 2026-09-24 卖出 17,864.00 元）：
修复前 `tax = 8.9320`（= 0.05% 印花税）、过户费 1.7864 ⇒ `total_cost = 12.5048`；
修复后应只剩佣金 **1.7864**。对 ETF 每轮换仓模型多计 +0.07%（名义额）。

## 判据

- 场内基金（含 `.OF` 后缀、含无后缀裸码）：`stamp_duty == 0` 且 `transfer_fee == 0`
- 股票：**逐值不变**（回归保护 —— 这是"最小范围修改"的边界，回测/其他调用方不受影响）
- 未传 / 空 `ts_code`：按**股票**口径计费 + WARNING（保守方向：宁可多收，不静默免税）
"""

import logging

import pytest

from modules.trade.utils.cost_calculator import CostCalculator, calculate_fee

_FEE_LOGGER = "modules.trade.utils.cost_calculator"

#: 场内基金样本：上交所 ETF / 深交所 ETF / 科创 ETF / 行业 ETF / 商品 ETF / LOF(.OF) / 裸码
_FUND_CODES = [
    "510050.SH",
    "159915.SZ",
    "588080.SH",
    "512660.SH",
    "159985.SZ",
    "158008.OF",
    "510050",
]

#: 股票样本（须保持不变）
_STOCK_CODES = ["600519.SH", "000001.SZ"]


class TestEtfExemption:
    """场内基金免征印花税与过户费。"""

    def test_etf_buy_only_commission(self) -> None:
        """买入 ETF（10-08 实盘锚：513100.SH 7,600 股 @2.3720）。"""
        price, qty = 2.3720, 7600
        amount = price * qty
        r = calculate_fee("buy", price, qty, "513100.SH")

        assert r["transfer_fee"] == 0.0
        assert r["stamp_duty"] == 0.0
        assert r["commission"] == pytest.approx(amount * 0.0001)
        assert r["total_cost"] == pytest.approx(amount * 0.0001)

    def test_etf_sell_has_no_stamp_duty(self) -> None:
        """B2 核心断言 —— 修复前此处 `stamp_duty` = 8.9320（09-24 实盘锚）。"""
        price, qty = 2.3200, 7700
        amount = price * qty
        r = calculate_fee("sell", price, qty, "159985.SZ")

        assert r["stamp_duty"] == 0.0, "场内基金免征印花税（修复前误计 0.05%）"
        assert r["transfer_fee"] == 0.0, "场内基金免征过户费（修复前误计 0.01%）"
        assert r["commission"] == pytest.approx(amount * 0.0001)
        assert r["total_cost"] == pytest.approx(amount * 0.0001)

        # 与修复前（合计 0.07%）的差额应为 0.06%：印花 0.05% + 过户 0.01%
        fixed_total = amount * 0.0007
        assert fixed_total - r["total_cost"] == pytest.approx(amount * 0.0006)

    @pytest.mark.parametrize("code", _FUND_CODES)
    def test_fund_codes_exempt_on_both_sides(self, code: str) -> None:
        for direction in ("buy", "sell"):
            r = calculate_fee(direction, 3.0, 1000, code)
            assert r["stamp_duty"] == 0.0, f"{code} {direction}"
            assert r["transfer_fee"] == 0.0, f"{code} {direction}"

    def test_batch_entry_forwards_ts_code(self) -> None:
        """`calculate_batch_trade_cost` 必须把 `ts_code` 透传（否则豁免失效）。"""
        calc = CostCalculator()
        batch = calc.calculate_batch_trade_cost(
            [
                {"direction": "sell", "price": 2.32, "quantity": 7700, "ts_code": "159985.SZ"},
                {"direction": "buy", "price": 2.372, "quantity": 7600, "ts_code": "513100.SH"},
            ]
        )
        assert batch["total_stamp_duty"] == 0.0
        assert batch["total_transfer_fee"] == 0.0
        assert batch["total_cost"] == pytest.approx(batch["total_commission"])


class TestStockUnchanged:
    """回归保护：股票口径必须与修复前**逐值相同**。"""

    @pytest.mark.parametrize("code", _STOCK_CODES)
    def test_stock_charged_as_before(self, code: str) -> None:
        amount = 150_000.0
        for direction in ("buy", "sell"):
            r = calculate_fee(direction, 1500.0, 100, code)
            assert r["commission"] == pytest.approx(amount * 0.0001)
            assert r["transfer_fee"] == pytest.approx(amount * 0.0001)
            expected_stamp = amount * 0.0005 if direction == "sell" else 0.0
            assert r["stamp_duty"] == pytest.approx(expected_stamp)

    def test_index_code_not_exempt(self) -> None:
        """指数不在 `is_etf` 集合内 —— 保持原行为（按股票费率），不因本修复而改变。"""
        r = calculate_fee("sell", 4000.0, 10, "000300.SH")
        assert r["stamp_duty"] == pytest.approx(40_000.0 * 0.0005)
        assert r["transfer_fee"] == pytest.approx(40_000.0 * 0.0001)


class TestMissingTsCode:
    """未传代码 → 按股票口径 + WARNING（保守方向，不静默免税）。"""

    @pytest.mark.parametrize("bad_code", [None, ""])
    def test_falls_back_to_stock_and_warns(self, bad_code, caplog) -> None:
        amount = 10_000.0
        with caplog.at_level(logging.WARNING, logger=_FEE_LOGGER):
            r = calculate_fee("sell", 10.0, 1000, bad_code)

        assert r["stamp_duty"] == pytest.approx(amount * 0.0005)
        assert r["transfer_fee"] == pytest.approx(amount * 0.0001)
        assert "未传 ts_code" in caplog.text

    def test_no_warning_when_code_present(self, caplog) -> None:
        with caplog.at_level(logging.WARNING, logger=_FEE_LOGGER):
            calculate_fee("sell", 3.0, 1000, "510050.SH")
        assert caplog.text == ""
