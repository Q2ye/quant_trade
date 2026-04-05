# -*- coding: utf-8 -*-
"""
事件类型定义

定义回测模块的事件类型
"""
from enum import Enum


class BacktestEventTypes(str, Enum):
    """
    回测事件类型
    """
    # 回测任务相关事件
    BACKTEST_START = "backtest_start"  # 回测开始
    BACKTEST_PROGRESS = "backtest_progress"  # 回测进度
    BACKTEST_COMPLETE = "backtest_complete"  # 回测完成
    BACKTEST_FAILED = "backtest_failed"  # 回测失败
    BACKTEST_CANCELLED = "backtest_cancelled"  # 回测取消
    
    # 优化任务相关事件
    OPTIMIZATION_START = "optimization_start"  # 优化开始
    OPTIMIZATION_PROGRESS = "optimization_progress"  # 优化进度
    OPTIMIZATION_COMPLETE = "optimization_complete"  # 优化完成
    OPTIMIZATION_FAILED = "optimization_failed"  # 优化失败
    OPTIMIZATION_CANCELLED = "optimization_cancelled"  # 优化取消
    
    # 交易相关事件
    TRADE_EXECUTED = "trade_executed"  # 交易执行
    ORDER_PLACED = "order_placed"  # 订单下单
    ORDER_FILLED = "order_filled"  # 订单成交
    ORDER_CANCELLED = "order_cancelled"  # 订单取消
    
    # 性能相关事件
    METRICS_CALCULATED = "metrics_calculated"  # 指标计算完成
    REPORT_GENERATED = "report_generated"  # 报告生成完成