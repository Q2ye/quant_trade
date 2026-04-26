# -*- coding: utf-8 -*-
"""
策略信号事件
策略生成的交易信号相关事件
"""
from datetime import datetime
from typing import Optional

from quant_server.core.events.base import BaseEvent, EventPriority
from quant_server.modules.strategy.events.types import SignalEventType


class StrategySignalEvent(BaseEvent):
    """策略信号事件 - 策略产生交易信号时触发"""

    def __init__(
        self,
        strategy_id: str,
        strategy_name: str,
        ts_code: str,
        signal_type: str,  # BUY/SELL/HOLD
        signal_direction: str,  # LONG/SHORT/CLOSE
        price: float,
        quantity: int,
        reason: str,
        confidence: float = 1.0,
        target_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        **kwargs
    ):
        super().__init__(
            module="strategy",
            event_type=SignalEventType.ENTRY.value,
            priority=EventPriority.HIGH,  # 信号事件优先级较高
            **kwargs
        )

        self.data = {
            "strategy_id": strategy_id,
            "strategy_name": strategy_name,
            "ts_code": ts_code,
            "signal_type": signal_type,
            "signal_direction": signal_direction,
            "price": price,
            "quantity": quantity,
            "reason": reason,
            "confidence": confidence,
            "target_price": target_price,
            "stop_loss_price": stop_loss_price,
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
    """信号取消事件 - 信号被取消时触发"""

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
