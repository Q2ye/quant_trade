# -*- coding: utf-8 -*-
"""回测券商费用模型 — 场内基金（ETF/LOF）免征印花税与过户费。

背景：`BacktestBrokerConfig` 的 `stamp_tax=0.001` / `transfer_fee_rate=0.00002`
原先是**无条件**征收的，没有标的类型判别。对 100% 交易 ETF 的策略（跨市场动量
避险轮动、ETF 底部）会错收 0.1%/笔卖出印花税——跨市场策略 5 年累计 41.0 万，
占初始资金 41.1%。实际规则：证券交易印花税仅对股票及以股票为基础的存托凭证
征收，场内基金免征；过户费为股票登记结算费用，场内基金亦不收。

本测试锁定三条不变式：
  1. `is_etf` 的代码判别（单一事实源）
  2. ETF 印花税率/过户费率为 0，股票侧保持原费率
  3. `_execute_fill` 实际结算出的费用与上述口径一致（含买入量缩减重算路径）
"""
from datetime import date

import pytest

from modules.backtest.engines.backtest_broker import (
    BacktestBroker,
    BacktestBrokerConfig,
    BrokerOrder,
    BrokerPosition,
)
from shared.utils.instrument import is_etf

# 跨市场策略实际使用的标的
ETF_CODES = ["510050.SH", "513100.SH", "518880.SH", "588080.SH", "159915.SZ"]
# 高波动动量等个股策略的标的
STOCK_CODES = ["600519.SH", "000001.SZ", "300750.SZ"]


class TestIsEtf:
    """单一事实源：ETF/LOF 代码判别。"""

    @pytest.mark.parametrize(
        "code",
        [
            *ETF_CODES,
            "561120.SH",   # 56xxxx 行业 ETF
            "159985.SZ",   # 豆粕 ETF
            "160123.SZ",   # 16xxxx LOF
            "510050",      # 无交易所后缀的裸代码
            "510050.OF",   # 场外基金后缀
        ],
    )
    def test_etf_codes(self, code: str) -> None:
        assert is_etf(code) is True

    @pytest.mark.parametrize(
        "code",
        [*STOCK_CODES, "399006.SZ", "000300.SH", "", None],
    )
    def test_non_etf_codes(self, code) -> None:
        assert is_etf(code) is False


class TestFeeRates:
    """费率选取：ETF 免征，股票按原口径。"""

    def test_etf_rates_are_zero(self) -> None:
        broker = _make_broker()
        for code in ETF_CODES:
            assert broker._fee_rates(code) == (0.0, 0.0)

    def test_stock_rates_unchanged(self) -> None:
        broker = _make_broker()
        for code in STOCK_CODES:
            assert broker._fee_rates(code) == (0.001, 0.00002)

    def test_rates_overridable(self) -> None:
        """显式覆盖后应按覆盖值生效（保留可配置性）。"""
        broker = _make_broker(stamp_tax_etf=0.0005, transfer_fee_rate_etf=0.00001)
        assert broker._fee_rates("510050.SH") == (0.0005, 0.00001)


class TestExecuteFillFees:
    """端到端：实际结算出的费用与费率口径一致。"""

    def test_etf_sell_exempt_from_stamp_tax_and_transfer_fee(self) -> None:
        broker = _make_broker()
        record = _sell(broker, "510050.SH", quantity=1000, price=2.0)

        assert record["stamp_tax"] == 0.0
        assert record["transfer_fee"] == 0.0
        # 佣金仍按万一免五正常收取
        assert record["commission"] == pytest.approx(2000.0 * 0.0001)

    def test_stock_sell_charges_stamp_tax_and_transfer_fee(self) -> None:
        broker = _make_broker()
        record = _sell(broker, "600519.SH", quantity=1000, price=2.0)

        assert record["stamp_tax"] == pytest.approx(2000.0 * 0.001)
        assert record["transfer_fee"] == pytest.approx(2000.0 * 0.00002)

    def test_etf_buy_has_no_stamp_tax_either_way(self) -> None:
        broker = _make_broker()
        record = _buy(broker, "510050.SH", quantity=1000, price=2.0)

        assert record["stamp_tax"] == 0.0
        assert record["transfer_fee"] == 0.0


# =============================================================================
# 构造工具
# =============================================================================


def _make_broker(**overrides) -> BacktestBroker:
    """构造零滑点的测试券商，便于用整数金额断言费用。"""
    config = BacktestBrokerConfig(
        initial_capital=1_000_000,
        slippage=0.0,
        **overrides,
    )
    return BacktestBroker(config=config)


def _order(ts_code: str, direction: str, quantity: int, price: float) -> BrokerOrder:
    return BrokerOrder(
        order_id="order_test",
        ts_code=ts_code,
        direction=direction,
        price=price,
        quantity=quantity,
        order_type="market",
        status="pending",
        create_date=date(2024, 1, 2),
    )


def _sell(
    broker: BacktestBroker, ts_code: str, quantity: int, price: float
) -> dict:
    """成交一笔卖出（需预置持仓，否则 _execute_fill 会作废订单）。"""
    broker.positions[ts_code] = BrokerPosition(
        ts_code=ts_code,
        quantity=quantity,
        available_quantity=quantity,
        avg_cost=price,
    )
    return broker._execute_fill(_order(ts_code, "SHORT", quantity, price), price, date(2024, 1, 3))


def _buy(
    broker: BacktestBroker, ts_code: str, quantity: int, price: float
) -> dict:
    """成交一笔买入（现金充足，不触发缩减路径）。"""
    return broker._execute_fill(_order(ts_code, "LONG", quantity, price), price, date(2024, 1, 3))
