# -*- coding: utf-8 -*-
"""
Sizer — 数量计算器

将策略的抽象信号（金额/权重/平仓标记）转换为具体的委托数量（股数），
实现 Strategy（what）→ Sizer（how much）→ Broker（execute）的三层分离。

参照：Backtrader Sizer / QuantConnect PortfolioConstructionModel
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from core.engines.types.entities import BarData
from modules.strategy.models import TradingSignal
from modules.strategy.constants import SignalDirection

logger = logging.getLogger(__name__)


@dataclass
class SizerConfig:
    """Sizer 通用配置"""
    lot_size: int = 100  # 1 手 = 100 股


class BaseSizer(ABC):
    """
    数量计算器基类。

    调用时机：策略产生信号后、提交 Broker 前。
    职责单一：将 signal 转换为整数股数，不做验证。
    """

    def __init__(self, config: SizerConfig = None):
        self.config = config or SizerConfig()

    @abstractmethod
    def calculate(
        self,
        signal: TradingSignal,
        bar: BarData,
        available_cash: float,
        current_position_qty: int = 0,
    ) -> int:
        """
        计算委托数量。

        Args:
            signal: 策略产生的交易信号
            bar: 当前日 BarData（用于价格参考）
            available_cash: 可用资金
            current_position_qty: 当前持仓数量（用于平仓计算）

        Returns:
            股数（整数，已按 lot_size 取整）。返回 0 表示不执行。
        """
        ...

    def _round_lot(self, qty: int) -> int:
        """向下取整到手的整数倍"""
        return (qty // self.config.lot_size) * self.config.lot_size


# =============================================================================
# 内置 Sizer
# =============================================================================


class FixedAmountSizer(BaseSizer):
    """
    固定金额模式：signal.amount → 反推股数。

    适用场景：策略指定每只股票投入固定金额（如"每只买 10 万元"）。
    """

    def calculate(
        self,
        signal: TradingSignal,
        bar: BarData,
        available_cash: float,
        current_position_qty: int = 0,
    ) -> int:
        price = signal.price if signal.price > 0 else bar.close
        amount = signal.amount if signal.amount > 0 else 0
        if price <= 0 or amount <= 0:
            return 0
        qty = int(amount / price)
        return self._round_lot(qty)


class WeightSizer(BaseSizer):
    """
    权重模式：signal 中的 weight × available_cash → 反推股数。

    适用场景：策略输出持仓权重（如 SmallCap 调仓: "002494.SZ 占 33%"）。
    signal 中可以携带 weight 属性，或通过 amount/available_cash 反推。
    """

    def calculate(
        self,
        signal: TradingSignal,
        bar: BarData,
        available_cash: float,
        current_position_qty: int = 0,
    ) -> int:
        price = signal.price if signal.price > 0 else bar.close
        if price <= 0:
            return 0

        # 权重来源：显式 weight 属性 > amount/capital 反推
        weight = getattr(signal, "weight", None)
        if weight is None and signal.amount > 0 and available_cash > 0:
            weight = signal.amount / available_cash
        if weight is None or weight <= 0:
            return 0

        # 预留 0.5% 给佣金 + 滑点 + 过户费，避免 broker 端触发自动数量缩减
        fee_buffer = 0.995
        target_value = weight * available_cash * fee_buffer
        qty = int(target_value / price)
        return self._round_lot(qty)


class CloseAllSizer(BaseSizer):
    """
    平仓模式：CLOSE_LONG → 卖出当前全部持仓。

    适用场景：策略发送 CLOSE_LONG 信号清仓。
    """

    def calculate(
        self,
        signal: TradingSignal,
        bar: BarData,
        available_cash: float,
        current_position_qty: int = 0,
    ) -> int:
        return self._round_lot(current_position_qty)


class HalfCloseSizer(BaseSizer):
    """
    半仓卖出模式：CLOSE_LONG → 卖出一半当前持仓。

    适用场景：动态再平衡时，浮盈过大的持仓强制卖半仓锁定利润。
    """

    def calculate(
        self,
        signal: TradingSignal,
        bar: BarData,
        available_cash: float,
        current_position_qty: int = 0,
    ) -> int:
        half = current_position_qty // 2
        return self._round_lot(half)


class QuantitySizer(BaseSizer):
    """
    固定数量模式：直接使用 signal.quantity（已有值则不变）。

    适用场景：策略明确计算了股数。
    """

    def calculate(
        self,
        signal: TradingSignal,
        bar: BarData,
        available_cash: float,
        current_position_qty: int = 0,
    ) -> int:
        return self._round_lot(signal.quantity)


# =============================================================================
# Sizer 自动选择
# =============================================================================


def select_sizer(signal: TradingSignal) -> BaseSizer:
    """
    根据信号特征自动选择 Sizer。

    规则：
    - CLOSE_LONG 且 quantity≤0 → CloseAllSizer（平掉全部）
    - weight 属性 > 0 → WeightSizer（等权重分配）
    - quantity > 0 → QuantitySizer（已有股数）
    - amount > 0 → FixedAmountSizer（固定金额）
    - 其他 → QuantitySizer（fallback）
    """
    direction = signal.direction
    if hasattr(direction, "value"):
        direction = direction.value

    if direction in ("CLOSE_LONG", "close_long") and signal.quantity <= 0:
        # v6.0: 支持半仓卖出（动态再平衡）
        if getattr(signal, 'half_exit', False):
            return HalfCloseSizer()
        return CloseAllSizer()

    # v2.5: weight 优先于 quantity，支持等权重仓位分配
    weight = getattr(signal, "weight", None)
    if weight is not None and weight > 0:
        return WeightSizer()

    if signal.quantity > 0:
        return QuantitySizer()

    if getattr(signal, "amount", 0) > 0:
        return FixedAmountSizer()

    return QuantitySizer()
