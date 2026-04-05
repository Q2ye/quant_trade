# -*- coding: utf-8 -*-
"""
策略模块常量定义
包含策略类型、状态、参数默认值等
"""
from enum import Enum


# ==================== 策略类型 ====================
class StrategyType(str, Enum):
    """策略类型枚举"""
    # 趋势跟踪策略
    TREND_FOLLOWING = "trend_following"

    # CTA策略 (Commodity Trading Advisor)
    CTA = "cta"

    # Alpha策略
    ALPHA = "alpha"

    # 机器学习策略
    ML = "ml"

    # 深度学习策略
    DL = "dl"

    # 套利策略
    ARBITRAGE = "arbitrage"

    # 多因子策略
    MULTI_FACTOR = "multi_factor"

    # 均值回归策略
    MEAN_REVERSION = "mean_reversion"

    # 网格策略
    GRID = "grid"

    # 指数增强策略
    INDEX_ENHANCE = "index_enhance"

    # 做市商策略
    MARKET_MAKING = "market_making"

    # 自定义策略
    CUSTOM = "custom"

    # 技术指标策略
    TECHNICAL = "technical"


# ==================== 策略状态 ====================
class StrategyLifecycleStatus(str, Enum):
    """策略生命周期状态枚举"""
    # 草稿
    DRAFT = "draft"

    # 已编译
    COMPILED = "compiled"

    # 已部署
    DEPLOYED = "deployed"

    # 运行中
    RUNNING = "running"

    # 已暂停
    PAUSED = "paused"

    # 已停止
    STOPPED = "stopped"

    # 错误
    ERROR = "error"

    # 已归档
    ARCHIVED = "archived"


# ==================== 信号方向 ====================
class SignalDirection(str, Enum):
    """交易信号方向"""
    # 做多
    LONG = "long"

    # 做空
    SHORT = "short"

    # 平多
    CLOSE_LONG = "close_long"

    # 平空
    CLOSE_SHORT = "close_short"

    # 不操作
    NONE = "none"


# ==================== 信号类型 ====================
class SignalType(str, Enum):
    """信号类型"""
    # 入场信号
    ENTRY = "entry"

    # 出场信号
    EXIT = "exit"

    # 止损信号
    STOP_LOSS = "stop_loss"

    # 止盈信号
    TAKE_PROFIT = "take_profit"

    # 调仓信号
    REBALANCE = "rebalance"


# ==================== 运行模式 ====================
class RunMode(str, Enum):
    """策略运行模式"""
    # 回测模式
    BACKTEST = "backtest"

    # 模拟交易
    SIMULATION = "simulation"

    # 实盘交易
    LIVE = "live"

    # paper trading (模拟盘)
    PAPER = "paper"


# ==================== 持仓方向 ====================
class PositionSide(str, Enum):
    """持仓方向"""
    LONG = "long"
    SHORT = "short"
    NET = "net"


# ==================== 时间周期 ====================
class TimeFrame(str, Enum):
    """时间周期"""
    # 分钟级别
    MIN_1 = "1min"
    MIN_5 = "5min"
    MIN_15 = "15min"
    MIN_30 = "30min"
    MIN_60 = "60min"

    # 日级别
    DAILY = "daily"

    # 周级别
    WEEKLY = "weekly"

    # 月级别
    MONTHLY = "monthly"


# ==================== 订单类型 ====================
class OrderType(str, Enum):
    """订单类型"""
    # 市价单
    MARKET = "market"

    # 限价单
    LIMIT = "limit"

    # 止损单
    STOP = "stop"

    # 止损限价单
    STOP_LIMIT = "stop_limit"

    # 冰山订单
    ICEBERG = "iceberg"

    # 大单拆分
    TWAP = "twap"

    # 随机下单
    VWAP = "vwap"


# ==================== 缓存Key前缀 ====================
class CacheKey:
    """缓存Key前缀"""
    STRATEGY_DETAIL = "strategy:detail:{}"
    STRATEGY_STATUS = "strategy:status:{}"
    STRATEGY_SIGNALS = "strategy:signals:{}"
    STRATEGY_POSITIONS = "strategy:positions:{}"
    STRATEGY_PERFORMANCE = "strategy:performance:{}"


# ==================== 默认参数 ====================
class DefaultParams:
    """默认参数"""
    # 默认初始资金
    DEFAULT_CAPITAL = 1000000.0

    # 默认回测起始日期
    DEFAULT_START_DATE = "2020-01-01"

    # 默认回测结束日期
    DEFAULT_END_DATE = "2024-12-31"

    # 默认滑点率
    DEFAULT_SLIPPAGE = 0.001

    # 默认手续费率
    DEFAULT_COMMISSION = 0.0003

    # 默认止损比例
    DEFAULT_STOP_LOSS = 0.05

    # 默认止盈比例
    DEFAULT_TAKE_PROFIT = 0.15

    # 默认最大持仓比例
    DEFAULT_MAX_POSITION = 0.2

    # 默认最小交易金额
    MIN_TRADE_AMOUNT = 100

    # 默认数据频率
    DEFAULT_FREQUENCY = "daily"


# ==================== 错误码 ====================
class ErrorCode:
    """错误码"""
    STRATEGY_NOT_FOUND = 1001
    STRATEGY_COMPILE_ERROR = 1002
    STRATEGY_NOT_RUNNING = 1003
    STRATEGY_ALREADY_RUNNING = 1004
    STRATEGY_INSUFFICIENT_CAPITAL = 1005
    STRATEGY_INVALID_PARAMETER = 1006
    STRATEGY_NO_DATA = 1007
    STRATEGY_RISK_LIMIT_EXCEEDED = 1008


# ==================== 事件类型 ====================
class EventType:
    """策略相关事件类型"""
    STRATEGY_CREATED = "strategy.created"
    STRATEGY_UPDATED = "strategy.updated"
    STRATEGY_DELETED = "strategy.deleted"
    STRATEGY_STARTED = "strategy.started"
    STRATEGY_STOPPED = "strategy.stopped"
    STRATEGY_PAUSED = "strategy.paused"
    STRATEGY_ERROR = "strategy.error"
    SIGNAL_GENERATED = "strategy.signal"
    ORDER_SUBMITTED = "strategy.order"
    ORDER_FILLED = "strategy.filled"
    POSITION_CHANGED = "strategy.position"
    PERFORMANCE_UPDATED = "strategy.performance"