# -*- coding: utf-8 -*-
"""市场模块事件定义"""
from typing import Any, Dict, Optional

from core.events.base import BaseEvent
from core.events.types import EventCategory, EventPriority


class MarketStatusChangedEvent(BaseEvent):
    """市场状态变更事件 — market.status.changed"""

    def __init__(self, status: str, previous: str = "", **kwargs):
        super().__init__(
            event_type="market.status.changed",
            source="market_engine",
            module="market",
            category=EventCategory.BUSINESS,
            priority=EventPriority.NORMAL,
            **kwargs,
        )
        self.data.update({"status": status, "previous": previous})


class MarketOpenedEvent(BaseEvent):
    """市场开盘事件 — market.opened"""

    def __init__(self, trade_date: str, **kwargs):
        super().__init__(
            event_type="market.opened",
            source="market_engine",
            module="market",
            category=EventCategory.BUSINESS,
            priority=EventPriority.HIGH,
            **kwargs,
        )
        self.data.update({"trade_date": trade_date})


class MarketClosedEvent(BaseEvent):
    """市场收盘事件 — market.closed"""

    def __init__(self, trade_date: str, **kwargs):
        super().__init__(
            event_type="market.closed",
            source="market_engine",
            module="market",
            category=EventCategory.BUSINESS,
            priority=EventPriority.HIGH,
            **kwargs,
        )
        self.data.update({"trade_date": trade_date})


class IndexUpdatedEvent(BaseEvent):
    """指数更新事件 — market.index.updated"""

    def __init__(self, index_code: str, value: float, change_pct: float,
                 trade_date: str = "", **kwargs):
        super().__init__(
            event_type="market.index.updated",
            source="market_engine",
            module="market",
            category=EventCategory.BUSINESS,
            priority=EventPriority.NORMAL,
            **kwargs,
        )
        self.data.update({
            "index_code": index_code,
            "value": value,
            "change_pct": change_pct,
            "trade_date": trade_date,
        })
