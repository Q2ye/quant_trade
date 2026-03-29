# -*- coding: utf-8 -*-
"""
策略事件类型枚举
"""
from enum import Enum


class StrategyEventType(str, Enum):
    """策略事件类型"""

    # 生命周期事件
    CREATED = "strategy.created"
    UPDATED = "strategy.updated"
    DELETED = "strategy.deleted"
    STARTED = "strategy.started"
    STOPPED = "strategy.stopped"
    PAUSED = "strategy.paused"
    RESUMED = "strategy.resumed"
    ERROR = "strategy.error"

    # 策略执行事件
    SIGNAL_GENERATED = "strategy.signal_generated"
    SIGNAL_EXECUTED = "strategy.signal_executed"
    ORDER_SUBMITTED = "strategy.order_submitted"
    ORDER_FILLED = "strategy.order_filled"
    ORDER_CANCELLED = "strategy.order_cancelled"

    # 持仓事件
    POSITION_OPENED = "strategy.position_opened"
    POSITION_CLOSED = "strategy.position_closed"
    POSITION_UPDATED = "strategy.position_updated"

    # 绩效事件
    PERFORMANCE_UPDATED = "strategy.performance_updated"
    DRAWDOWN_ALERT = "strategy.drawdown_alert"

    # 风控事件
    RISK_REJECTED = "strategy.risk_rejected"
    RISK_WARNING = "strategy.risk_warning"

    # 回测事件
    BACKTEST_STARTED = "strategy.backtest_started"
    BACKTEST_PROGRESS = "strategy.backtest_progress"
    BACKTEST_COMPLETED = "strategy.backtest_completed"
    BACKTEST_FAILED = "strategy.backtest_failed"


class SignalEventType(str, Enum):
    """信号事件类型"""
    ENTRY = "signal.entry"
    EXIT = "signal.exit"
    STOP_LOSS = "signal.stop_loss"
    TAKE_PROFIT = "signal.take_profit"
    REBALANCE = "signal.rebalance"
