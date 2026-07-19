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

    # 轮动策略
    ROTATION = "rotation"

    # 技术指标策略
    TECHNICAL = "technical"


# ==================== 策略状态 ====================
class StrategyLifecycleStatus(str, Enum):
    """策略生命周期状态枚举

    状态流转:
        DRAFT ──start──→ RUNNING ⇄ PAUSED
                           │  ↓
                           │ ERROR（自动，handle_bar_batch 大面积异常）
                           ↓
                         STOPPED

        DRAFT ──backtest──→ BACKTESTED ──start──→ RUNNING

    v2.1: 移除 COMPILED/DEPLOYED/ARCHIVED（无实际行为差异或零实现）
    v3.5: 新增 BACKTESTED 状态（回测验证通过，可启动实盘）
    """
    # 草稿（初始态）
    DRAFT = "draft"

    # 回测验证通过（可启动实盘）
    BACKTESTED = "backtested"

    # 运行中
    RUNNING = "running"

    # 已暂停
    PAUSED = "paused"

    # 已停止（终态）
    STOPPED = "stopped"

    # 错误（自动触发，handle_bar_batch error_rate > 50%）
    ERROR = "error"

    @classmethod
    def allowed_transitions(cls, from_status: "StrategyLifecycleStatus") -> set:
        """返回 from_status 允许转换到的状态集合"""
        _map = {
            cls.DRAFT:   {cls.RUNNING, cls.BACKTESTED},
            cls.BACKTESTED: {cls.RUNNING, cls.STOPPED},
            cls.RUNNING: {cls.PAUSED, cls.STOPPED, cls.ERROR},
            cls.PAUSED:  {cls.RUNNING, cls.STOPPED, cls.ERROR},
            cls.STOPPED: {cls.RUNNING},   # STOP/ERROR 可直接启动
            cls.ERROR:   {cls.RUNNING},
        }
        return _map.get(from_status, set())

    @classmethod
    def is_terminal(cls, status: "StrategyLifecycleStatus") -> bool:
        """是否为终态（不再自动处理 bar）"""
        return status in (cls.STOPPED, cls.ERROR)


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


# ==================== 信号状态 ====================
class SignalStatus(str, Enum):
    """信号确认状态（实盘人工确认流程）"""
    PENDING_MANUAL = "pending_manual"   # 等待人工确认（实盘模式默认）
    CONFIRMED = "confirmed"             # 人工已确认成交
    PARTIAL = "partial"                 # 部分成交
    CANCELLED = "cancelled"             # 人工取消
    REJECTED = "rejected"               # 风控拒绝
    EXPIRED = "expired"                 # 过期（超过有效交易日）


# ==================== 运行模式 ====================
class RunMode(str, Enum):
    """策略运行模式"""
    # 回测模式
    BACKTEST = "backtest"

    # 实盘交易
    LIVE = "live"

    # paper trading (模拟盘，预留)
    PAPER = "paper"


# ==================== 执行模式（实盘子模式） ====================
class ExecutionMode(str, Enum):
    """实盘执行模式"""
    # 半自动：策略生成信号 → 人工在券商端买卖 → 回系统确认成交
    SEMI_AUTO = "semi_auto"

    # 全自动：策略生成信号 → 系统直接调券商接口执行
    FULL_AUTO = "full_auto"


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