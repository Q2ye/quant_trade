# -*- coding: utf-8 -*-
"""
策略信号事件
策略生成的交易信号相关事件
"""
from datetime import datetime
from typing import Optional

from core.events.base import BaseEvent, EventPriority
from modules.strategy.events.types import SignalEventType


class StrategySignalEvent(BaseEvent):
    """策略信号事件 - 策略产生交易信号时触发"""

    event_type: str = SignalEventType.ENTRY.value

    def __init__(
        self,
        strategy_id: str,
        strategy_name: str,
        ts_code: str,
        signal_type: str,          # ENTRY/EXIT/STOP_LOSS/TAKE_PROFIT/REBALANCE
        signal_direction: str,     # LONG/SHORT/CLOSE_LONG/CLOSE_SHORT/NONE
        price: float,
        quantity: int,
        reason: str,
        confidence: float = 1.0,
        target_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        # v2.0 新增：价格范围
        price_limit_low: Optional[float] = None,
        price_limit_high: Optional[float] = None,
        max_slippage_pct: float = 0.02,
        order_type: str = "limit_range",
        account_id: str = "",       # v2.2: 绑定的交易账户ID
        strategy_version_id: str = "",  # v3.1: 策略版本ID，用于溯源
        parent_id: Optional[str] = None,  # v3.4: 父信号ID（候选→买入信号链路关联）
        run_mode: str = "live",
        execution_mode: str = "semi_auto",
        **kwargs
    ):
        kwargs.pop("run_mode", None)
        kwargs.pop("execution_mode", None)
        super().__init__(
            source="strategy",
            module="strategy",
            event_type=SignalEventType.ENTRY.value,
            priority=EventPriority.HIGH,
            **kwargs
        )

        # 自动计算未显式设置的价格范围
        low = price_limit_low
        high = price_limit_high
        if low is None and price > 0:
            low = round(price * (1 - max_slippage_pct), 4)
        if high is None and price > 0:
            high = round(price * (1 + max_slippage_pct), 4)

        self.data = {
            "strategy_id": strategy_id,
            "strategy_name": strategy_name,
            "strategy_version_id": strategy_version_id,  # v3.1: 溯源用
            "ts_code": ts_code,
            "signal_type": signal_type,
            "signal_direction": signal_direction,
            "price": price,
            "price_limit_low": low,
            "price_limit_high": high,
            "max_slippage_pct": max_slippage_pct,
            "order_type": order_type,
            "quantity": quantity,
            "reason": reason,
            "confidence": confidence,
            "target_price": target_price,
            "stop_loss_price": stop_loss_price,
            "account_id": account_id,
            "parent_id": parent_id,   # v3.4: 父信号ID
            "run_mode": run_mode,
            "execution_mode": execution_mode,
            "generation_time": datetime.now().isoformat()
        }


class SignalExecutedEvent(BaseEvent):
    """信号执行事件 - 信号被执行时触发"""

    def __init__(
        self,
        strategy_id: str,
        strategy_name: str,
        signal_id: str,
        ts_code: str,
        order_id: str,
        executed_price: float,
        executed_quantity: int,
        **kwargs
    ):
        super().__init__(
            source="strategy",
            module="strategy",
            event_type=SignalEventType.EXIT.value,
            priority=EventPriority.NORMAL,
            **kwargs
        )

        self.data = {
            "strategy_id": strategy_id,
            "strategy_name": strategy_name,
            "signal_id": signal_id,
            "ts_code": ts_code,
            "order_id": order_id,
            "executed_price": executed_price,
            "executed_quantity": executed_quantity,
            "execution_time": datetime.now().isoformat()
        }


class SignalCancelledEvent(BaseEvent):
    """信号取消事件 - 信号被取消时触发（含人工取消）"""

    def __init__(
        self,
        strategy_id: str,
        strategy_name: str,
        signal_id: str,
        ts_code: str,
        reason: str,
        **kwargs
    ):
        super().__init__(
            source="strategy",
            module="strategy",
            event_type=SignalEventType.STOP_LOSS.value,
            priority=EventPriority.NORMAL,
            **kwargs
        )

        self.data = {
            "strategy_id": strategy_id,
            "strategy_name": strategy_name,
            "signal_id": signal_id,
            "ts_code": ts_code,
            "reason": reason,
            "cancel_time": datetime.now().isoformat()
        }


class SignalConfirmedEvent(BaseEvent):
    """信号确认事件 - 人工确认成交时触发（v2.0 新增）"""

    def __init__(
        self,
        strategy_id: str,
        signal_id: str,
        ts_code: str,
        direction: str = "",
        fill_price: float = 0.0,
        fill_quantity: int = 0,
        fill_time: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            source="strategy",
            module="strategy",
            event_type="strategy.signal.confirmed",
            priority=EventPriority.HIGH,
            **kwargs
        )

        self.data = {
            "strategy_id": strategy_id,
            "signal_id": signal_id,
            "ts_code": ts_code,
            "direction": direction,
            "fill_price": fill_price,
            "fill_quantity": fill_quantity,
            "fill_time": fill_time or datetime.now().isoformat(),
            "confirmed_at": datetime.now().isoformat(),
        }
