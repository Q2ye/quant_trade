# -*- coding: utf-8 -*-
"""
策略生命周期事件
策略启动、停止、暂停、恢复等生命周期相关事件

v2.0: StrategyStartedEvent 新增 run_mode / execution_mode 字段，
      支持半自动(semi_auto)和全自动(full_auto)两种实盘执行模式。
      strategy_name 改为可选（ExecutionService 可不传）。
"""
from datetime import datetime
from typing import Dict, Any, Optional

from core.events.base import BaseEvent, EventPriority
from modules.strategy.events.types import StrategyEventType


class StrategyStartedEvent(BaseEvent):
    """策略启动事件 — v2.0"""

    def __init__(
        self,
        strategy_id: str,
        user_id: str,
        strategy_name: str = "",
        initial_capital: float = 0.0,
        parameters: Optional[Dict[str, Any]] = None,
        run_mode: str = "live",
        execution_mode: str = "semi_auto",
        source: str = "execution_service",
        account_id: str = "",
        **kwargs
    ):
        super().__init__(
            source=source,
            module="strategy",
            event_type=StrategyEventType.STARTED.value,
            priority=EventPriority.NORMAL,
            **kwargs
        )

        self.data = {
            "strategy_id": strategy_id,
            "strategy_name": strategy_name or "",
            "user_id": user_id,
            "initial_capital": initial_capital,
            "parameters": parameters or {},
            "run_mode": run_mode,
            "execution_mode": execution_mode,
            "account_id": account_id,
            "start_time": datetime.now().isoformat(),
        }


class StrategyStoppedEvent(BaseEvent):
    """策略停止事件"""

    def __init__(
        self,
        strategy_id: str,
        user_id: str,
        strategy_name: str = "",
        reason: str = "manual",
        performance_summary: Optional[Dict[str, Any]] = None,
        source: str = "execution_service",
        **kwargs
    ):
        super().__init__(
            source=source,
            module="strategy",
            event_type=StrategyEventType.STOPPED.value,
            priority=EventPriority.NORMAL,
            **kwargs
        )

        self.data = {
            "strategy_id": strategy_id,
            "strategy_name": strategy_name or "",
            "user_id": user_id,
            "reason": reason,
            "performance_summary": performance_summary or {},
            "stop_time": datetime.now().isoformat(),
        }


class StrategyPausedEvent(BaseEvent):
    """策略暂停事件"""

    def __init__(
        self,
        strategy_id: str,
        user_id: str,
        strategy_name: str = "",
        reason: str = "manual",
        source: str = "execution_service",
        **kwargs
    ):
        super().__init__(
            source=source,
            module="strategy",
            event_type=StrategyEventType.PAUSED.value,
            priority=EventPriority.NORMAL,
            **kwargs
        )

        self.data = {
            "strategy_id": strategy_id,
            "strategy_name": strategy_name or "",
            "user_id": user_id,
            "reason": reason,
            "pause_time": datetime.now().isoformat(),
        }


class StrategyResumedEvent(BaseEvent):
    """策略恢复事件"""

    def __init__(
        self,
        strategy_id: str,
        user_id: str,
        strategy_name: str = "",
        source: str = "execution_service",
        **kwargs
    ):
        super().__init__(
            source=source,
            module="strategy",
            event_type=StrategyEventType.RESUMED.value,
            priority=EventPriority.NORMAL,
            **kwargs
        )

        self.data = {
            "strategy_id": strategy_id,
            "strategy_name": strategy_name or "",
            "user_id": user_id,
            "resume_time": datetime.now().isoformat(),
        }
