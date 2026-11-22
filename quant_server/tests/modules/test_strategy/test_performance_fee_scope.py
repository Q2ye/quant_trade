# -*- coding: utf-8 -*-
"""B1：策略净值台账的费用口径必须取 `trade_fees` 明细（含过户费）（2026-10-09 修复）。

## 背景

`PerformanceService._get_strategy_trade_cash_flow` 原先按
`trades.commission + trades.tax` 求和 —— 而 `trades` 表**根本没有过户费列**
（`docs/sql/create_table.sql` 只有 `commission` / `tax`），过户费只落在
`trade_fees` 明细里（`trade_record_service._resolve_fees` 三项分别写行）。

⇒ **策略虚拟现金台账永远看不到过户费** ⇒ 净值被系统性**高估**。

实测（`strategy_daily_performance` − `account_daily_performance`，随成交笔数阶梯累加）：

| 区间 | 差 |
|:---|---:|
| 09-15 ~ 09-23 | 1.7774 |
| 09-24 ~ 09-30 | 3.5622 |
| 10-08 | 5.3676 |

即每笔台阶 = 该笔名义额 × 0.0001（= 过户费率）。修本项后两者应**归零**
（已用生产库 3 笔实测验证：虚拟现金 2,030.1324 ≡ `accounts.available_balance`）。

## 判据

- 明细存在 → 取三项之和（**含过户费**）
- 明细为空 / 读取失败 → 回退 `commission + tax` 并 **WARNING**（不静默按 0 计费）
- 读取失败**不得抛出** —— 否则 21:00 结算任务整体中断，产出"无绩效行"的第二类缺口

详见 `docs/08_实盘策略报告/实盘执行监控-2026-09-22起.md` §四 10-09 附记 B1 与 B2 专条。
"""

import logging
from decimal import Decimal

from modules.strategy.services.performance_service import PerformanceService

_SVC = PerformanceService  # 静态方法，无需 session
_LOGGER = "modules.strategy.services.performance_service"


class _Fee:
    """`TradeFee` 的最小替身。"""

    def __init__(self, amount: float) -> None:
        self.fee_amount = amount


class _Trade:
    """`Trade` 的最小替身（默认不带 `fees` 属性 = 明细未预加载）。"""

    def __init__(self, commission: float = 0.0, tax: float = 0.0, fees=None, trade_id: str = "T") -> None:
        self.commission, self.tax, self.trade_id = commission, tax, trade_id
        if fees is not None:
            self.fees = fees


class TestTradeFeesSum:
    def test_sums_all_three_fee_types(self) -> None:
        """09-24 卖单实盘值：佣金 1.7864 + 印花税 8.9320 + 过户费 1.7864 = 12.5048。"""
        t = _Trade(
            commission=1.7864,
            tax=8.9320,
            fees=[_Fee(1.7864), _Fee(8.9320), _Fee(1.7864)],
        )
        assert _SVC._trade_fees_sum(t) == Decimal("12.5048")

    def test_old_scope_would_have_undercounted(self) -> None:
        """口径对照：旧实现（commission + tax）恒 ≤ 新实现，差额 = 过户费。"""
        transfer = 1.7864
        t = _Trade(commission=1.7864, tax=8.9320, fees=[_Fee(1.7864), _Fee(8.9320), _Fee(transfer)])
        old_scope = Decimal(str(t.commission)) + Decimal(str(t.tax))
        assert _SVC._trade_fees_sum(t) - old_scope == Decimal(str(transfer))

    def test_etf_trade_after_b2_has_only_commission(self) -> None:
        """B2 修复后 ETF 成交明细只剩佣金一行 → 合计不得为 0。"""
        t = _Trade(commission=1.8027, tax=0.0, fees=[_Fee(1.8027)])
        assert _SVC._trade_fees_sum(t) == Decimal("1.8027")

    def test_zero_fee_trade_returns_zero(self) -> None:
        """确实零费用（无明细行）时返回 0，不误判。"""
        assert _SVC._trade_fees_sum(_Trade()) == Decimal("0")


class TestFallbacks:
    """明细缺失时的兜底 —— 必须告警且**不得抛出**。"""

    def test_empty_detail_list_warns_and_falls_back(self, caplog) -> None:
        t = _Trade(commission=1.7864, tax=8.9320, fees=[])
        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            got = _SVC._trade_fees_sum(t)

        assert got == Decimal("10.7184")  # 少扣过户费 1.7864 —— 兜底口径的已知代价
        assert "不含过户费" in caplog.text
        assert "为空" in caplog.text

    def test_missing_attribute_warns_and_falls_back(self, caplog) -> None:
        """`fees` 属性不存在（未预加载）→ 告警 + 回退。"""
        t = _Trade(commission=1.0, tax=2.0)
        assert not hasattr(t, "fees")
        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            assert _SVC._trade_fees_sum(t) == Decimal("3")
        assert "不含过户费" in caplog.text

    def test_load_failure_does_not_propagate(self, caplog) -> None:
        """async 惰性访问抛异常（MissingGreenlet 类）→ 兜底告警，**不得让结算中断**。"""

        class _Boom:
            trade_id = "T"
            commission = 1.0
            tax = 2.0

            @property
            def fees(self):
                raise RuntimeError("MissingGreenlet: greenlet_spawn has not been called")

        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            got = _SVC._trade_fees_sum(_Boom())

        assert got == Decimal("3")
        assert "读取失败" in caplog.text
