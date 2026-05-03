# -*- coding: utf-8 -*-
"""
策略组合事件
策略组合相关的事件定义
"""
from datetime import datetime
from typing import Dict, List, Optional

from core.events.base import BaseEvent, EventPriority
from modules.strategy.events.types import StrategyEventType


class PortfolioCreatedEvent(BaseEvent):
    """策略组合创建事件 - 当创建新的策略组合时触发"""

    def __init__(
        self,
        portfolio_id: str,
        portfolio_name: str,
        strategies: List[Dict[str, str]],  # [{'strategy_id': '...', 'weight': '...'}]
        initial_capital: float,
        description: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            module="strategy",
            event_type=StrategyEventType.PORTFOLIO_CREATED.value,
            priority=EventPriority.NORMAL,
            **kwargs
        )

        self.data = {
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio_name,
            "strategies": strategies,
            "initial_capital": initial_capital,
            "description": description,
            "created_time": datetime.now().isoformat()
        }


class PortfolioUpdatedEvent(BaseEvent):
    """策略组合更新事件 - 当更新策略组合时触发"""

    def __init__(
        self,
        portfolio_id: str,
        portfolio_name: str,
        strategies: List[Dict[str, str]],
        description: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            module="strategy",
            event_type=StrategyEventType.PORTFOLIO_UPDATED.value,
            priority=EventPriority.NORMAL,
            **kwargs
        )

        self.data = {
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio_name,
            "strategies": strategies,
            "description": description,
            "updated_time": datetime.now().isoformat()
        }


class PortfolioDeletedEvent(BaseEvent):
    """策略组合删除事件 - 当删除策略组合时触发"""

    def __init__(
        self,
        portfolio_id: str,
        portfolio_name: str,
        reason: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            module="strategy",
            event_type=StrategyEventType.PORTFOLIO_DELETED.value,
            priority=EventPriority.NORMAL,
            **kwargs
        )

        self.data = {
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio_name,
            "reason": reason,
            "deleted_time": datetime.now().isoformat()
        }


class PortfolioRebalancedEvent(BaseEvent):
    """策略组合调仓事件 - 当策略组合进行调仓时触发"""

    def __init__(
        self,
        portfolio_id: str,
        portfolio_name: str,
        old_weights: Dict[str, float],  # {strategy_id: weight}
        new_weights: Dict[str, float],  # {strategy_id: weight}
        rebalance_reason: str,
        **kwargs
    ):
        super().__init__(
            module="strategy",
            event_type=StrategyEventType.PORTFOLIO_REBALANCED.value,
            priority=EventPriority.HIGH,
            **kwargs
        )

        self.data = {
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio_name,
            "old_weights": old_weights,
            "new_weights": new_weights,
            "rebalance_reason": rebalance_reason,
            "rebalance_time": datetime.now().isoformat()
        }


class PortfolioPerformanceUpdatedEvent(BaseEvent):
    """策略组合绩效更新事件 - 当策略组合绩效更新时触发"""

    def __init__(
        self,
        portfolio_id: str,
        portfolio_name: str,
        total_assets: float,
        pnl: float,
        pnl_ratio: float,
        sharpe_ratio: float,
        max_drawdown: float,
        update_time: Optional[datetime] = None,
        **kwargs
    ):
        super().__init__(
            module="strategy",
            event_type=StrategyEventType.PORTFOLIO_PERFORMANCE_UPDATED.value,
            priority=EventPriority.NORMAL,
            **kwargs
        )

        self.data = {
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio_name,
            "total_assets": total_assets,
            "pnl": pnl,
            "pnl_ratio": pnl_ratio,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "update_time": (update_time or datetime.now()).isoformat()
        }


class PortfolioRiskEvent(BaseEvent):
    """策略组合风险事件 - 当策略组合触发风险预警时触发"""

    def __init__(
        self,
        portfolio_id: str,
        portfolio_name: str,
        risk_type: str,
        risk_value: float,
        threshold: float,
        message: str,
        **kwargs
    ):
        super().__init__(
            module="strategy",
            event_type=StrategyEventType.PORTFOLIO_RISK_WARNING.value,
            priority=EventPriority.HIGH,
            **kwargs
        )

        self.data = {
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio_name,
            "risk_type": risk_type,
            "risk_value": risk_value,
            "threshold": threshold,
            "message": message,
            "event_time": datetime.now().isoformat()
        }


class PortfolioStrategyAddedEvent(BaseEvent):
    """策略组合添加策略事件 - 当向策略组合添加策略时触发"""

    def __init__(
        self,
        portfolio_id: str,
        portfolio_name: str,
        strategy_id: str,
        strategy_name: str,
        weight: float,
        **kwargs
    ):
        super().__init__(
            module="strategy",
            event_type=StrategyEventType.PORTFOLIO_STRATEGY_ADDED.value,
            priority=EventPriority.NORMAL,
            **kwargs
        )

        self.data = {
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio_name,
            "strategy_id": strategy_id,
            "strategy_name": strategy_name,
            "weight": weight,
            "added_time": datetime.now().isoformat()
        }


class PortfolioStrategyRemovedEvent(BaseEvent):
    """策略组合移除策略事件 - 当从策略组合移除策略时触发"""

    def __init__(
        self,
        portfolio_id: str,
        portfolio_name: str,
        strategy_id: str,
        strategy_name: str,
        reason: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            module="strategy",
            event_type=StrategyEventType.PORTFOLIO_STRATEGY_REMOVED.value,
            priority=EventPriority.NORMAL,
            **kwargs
        )

        self.data = {
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio_name,
            "strategy_id": strategy_id,
            "strategy_name": strategy_name,
            "reason": reason,
            "removed_time": datetime.now().isoformat()
        }