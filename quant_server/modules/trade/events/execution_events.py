# 订单执行事件

from typing import Dict, Any, Optional
from dataclasses import dataclass
from core.events.base import BaseEvent

@dataclass
class OrderCreateEvent(BaseEvent):
    """订单创建事件"""
    event_type: str = "order_create"
    order_data: Dict[str, Any] = None
    user_id: Optional[str] = None


@dataclass
class OrderSubmitEvent(BaseEvent):
    """订单提交事件"""
    event_type: str = "order_submit"
    order_id: str = None
    order_data: Dict[str, Any] = None


@dataclass
class OrderCancelEvent(BaseEvent):
    """订单取消事件"""
    event_type: str = "order_cancel"
    order_id: str = None
    reason: Optional[str] = None


@dataclass
class OrderFillEvent(BaseEvent):
    """订单成交事件"""
    event_type: str = "order_fill"
    order_id: str = None
    fill_price: float = 0.0
    fill_quantity: float = 0.0
    fill_time: str = None


@dataclass
class OrderRejectEvent(BaseEvent):
    """订单拒绝事件"""
    event_type: str = "order_reject"
    order_id: str = None
    reason: str = None
    order_data: Dict[str, Any] = None


@dataclass
class ExecutionErrorEvent(BaseEvent):
    """执行错误事件"""
    event_type: str = "execution_error"
    error_message: str = None
    order_data: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionSuccessEvent(BaseEvent):
    """执行成功事件"""
    event_type: str = "execution_success"
    order_id: str = None
    order_data: Dict[str, Any] = None