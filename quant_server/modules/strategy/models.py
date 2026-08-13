# -*- coding: utf-8 -*-
"""
策略模块业务模型
领域对象定义，非数据库模型
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any

from .constants import (
    StrategyType,
    StrategyLifecycleStatus,
    SignalDirection,
    SignalType,
    SignalStatus,
    PositionSide,
    TimeFrame,
    RunMode,
)


# ==================== 策略实例模型 ====================
@dataclass
class StrategyInstance:
    """策略实例 - 运行中的策略对象"""
    # 基本信息
    id: str
    name: str
    strategy_type: StrategyType
    status: StrategyLifecycleStatus
    user_id: str

    # 代码和参数
    code: str
    parameters: Dict[str, Any] = field(default_factory=dict)

    # 运行参数
    capital: float = 1000000.0
    run_mode: RunMode = RunMode.LIVE

    # 状态信息
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # 性能指标
    total_pnl: float = 0.0
    total_return: float = 0.0
    win_rate: float = 0.0

    # 创建和更新时间
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def is_running(self) -> bool:
        """判断策略是否在运行"""
        return self.status == StrategyLifecycleStatus.RUNNING

    def can_start(self) -> bool:
        """判断策略是否可以启动"""
        return self.status in [
            StrategyLifecycleStatus.DRAFT,
            StrategyLifecycleStatus.PAUSED,
            StrategyLifecycleStatus.STOPPED,
            StrategyLifecycleStatus.RUNNING,  # v2.4: 重启恢复
	            StrategyLifecycleStatus.ERROR,
        ]

    def can_stop(self) -> bool:
        """判断策略是否可以停止"""
        return self.status in [
            StrategyLifecycleStatus.RUNNING,
            StrategyLifecycleStatus.PAUSED,
            StrategyLifecycleStatus.RUNNING,  # v2.4: 重启恢复
	            StrategyLifecycleStatus.ERROR,
        ]


# ==================== 交易信号模型 ====================
@dataclass
class TradingSignal:
    """交易信号"""
    # 标识信息
    id: str
    strategy_id: str
    strategy_name: str

    # 信号信息
    ts_code: str  # 股票代码
    signal_type: SignalType
    direction: SignalDirection

    # 价格信息
    price: float                                  # 参考价格（信号触发时的收盘价）
    price_limit_low: Optional[float] = None       # 可接受最低成交价
    price_limit_high: Optional[float] = None      # 可接受最高成交价
    max_slippage_pct: float = 0.02                # 最大可接受滑点（默认 2%）
    order_type: str = "limit_range"               # limit / limit_range / market
    weight: float = 1.0                           # 仓位权重 [0, 1]，策略层→交易层仓位映射
    target_price: Optional[float] = None          # 目标价格
    stop_loss_price: Optional[float] = None       # 止损价格
    # v6.11: 执行模式
    #   "open"    — 次日开盘价成交（默认，T+1 传统撮合）
    #   "close"   — 当日收盘价成交（收盘确认买入）
    #   "trigger" — 当日触发价成交（日内止损，盘中触及 trigger_price 即成交）
    order_mode: str = "open"
    trigger_price: Optional[float] = None         # trigger 模式的触发价（如止损价）

    # 数量信息
    quantity: int = 0
    amount: float = 0.0

    # 置信度 (0-1)
    confidence: float = 1.0

    # 原因
    reason: str = ""

    # v3.4: 父信号ID（候选→买入信号链路关联，用于全链路追溯）
    parent_id: Optional[str] = None

    # 时间
    timestamp: datetime = field(default_factory=datetime.now)

    # 状态
    is_executed: bool = False
    executed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，若未显式设置价格范围则按 max_slippage_pct 自动生成"""
        low = self.price_limit_low
        high = self.price_limit_high
        if low is None and self.price > 0:
            low = round(self.price * (1 - self.max_slippage_pct), 4)
        if high is None and self.price > 0:
            high = round(self.price * (1 + self.max_slippage_pct), 4)

        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "ts_code": self.ts_code,
            "signal_type": self.signal_type.value,
            "direction": self.direction.value,
            "price": self.price,
            "price_limit_low": low,
            "price_limit_high": high,
            "max_slippage_pct": self.max_slippage_pct,
            "order_type": self.order_type,
            "target_price": self.target_price,
            "stop_loss_price": self.stop_loss_price,
            "quantity": self.quantity,
            "amount": self.amount,
            "confidence": self.confidence,
            "reason": self.reason,
            "parent_id": self.parent_id,   # v3.4: 父信号ID
            "timestamp": self.timestamp.isoformat(),
            "is_executed": self.is_executed,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
        }


# ==================== 持仓模型 ====================
@dataclass
class Position:
    """持仓"""
    # 标识
    id: str
    strategy_id: str
    ts_code: str

    # 持仓信息
    side: PositionSide
    quantity: int
    avg_cost: float  # 平均成本

    # 当前价值
    current_price: float = 0.0
    market_value: float = 0.0

    # 盈亏
    pnl: float = 0.0
    pnl_rate: float = 0.0

    # 时间
    open_date: Optional[datetime] = None
    update_time: datetime = field(default_factory=datetime.now)

    def calculate_pnl(self) -> float:
        """计算盈亏"""
        if self.side == PositionSide.LONG:
            self.pnl = (self.current_price - self.avg_cost) * self.quantity
        elif self.side == PositionSide.SHORT:
            self.pnl = (self.avg_cost - self.current_price) * self.quantity
        else:
            self.pnl = 0.0

        if self.avg_cost > 0:
            self.pnl_rate = self.pnl / (self.avg_cost * self.quantity)
        return self.pnl

    def update_price(self, price: float) -> None:
        """更新当前价格"""
        self.current_price = price
        self.market_value = price * self.quantity
        self.calculate_pnl()
        self.update_time = datetime.now()


# ==================== 绩效指标模型 ====================
@dataclass
class PerformanceMetrics:
    """绩效指标"""
    # 基础信息
    strategy_id: str
    start_date: datetime
    end_date: datetime

    # 收益指标
    total_return: float = 0.0  # 总收益率
    annual_return: float = 0.0  # 年化收益率
    benchmark_return: float = 0.0  # 基准收益
    excess_return: float = 0.0  # 超额收益

    # 风险指标
    max_drawdown: float = 0.0  # 最大回撤
    volatility: float = 0.0  # 波动率
    sharpe_ratio: float = 0.0  # 夏普比率
    sortino_ratio: float = 0.0  # 索提诺比率
    calmar_ratio: float = 0.0  # 卡玛比率

    # 交易统计
    total_trades: int = 0  # 总交易次数
    winning_trades: int = 0  # 盈利交易次数
    losing_trades: int = 0  # 亏损交易次数
    win_rate: float = 0.0  # 胜率
    avg_win: float = 0.0  # 平均盈利
    avg_loss: float = 0.0  # 平均亏损

    # 持仓统计
    max_position: float = 0.0  # 最大持仓
    avg_position: float = 0.0  # 平均持仓


# ==================== 策略配置模型 ====================
@dataclass
class StrategyConfig:
    """策略配置"""
    # 基本配置
    name: str = ""
    description: str = ""
    strategy_type: StrategyType = StrategyType.CTA
    user_id: Any = ""  # v2.3: load_strategy 用 hasattr 读取，必须存在

    # 初始资金
    initial_capital: float = 1000000.0

    # 交易配置
    commission_rate: float = 0.0003  # 手续费率
    slippage: float = 0.001  # 滑点
    min_trade_amount: float = 100  # 最小交易金额

    # 风控配置
    max_position: float = 0.2  # 最大持仓比例
    stop_loss: float = 0.05  # 止损比例
    take_profit: float = 0.15  # 止盈比例

    # 数据配置
    time_frame: TimeFrame = TimeFrame.DAILY
    start_date: str = ""
    end_date: str = ""

    # 策略特定参数
    parameters: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """验证配置"""
        errors = []
        if not self.name:
            errors.append("策略名称不能为空")
        if self.initial_capital <= 0:
            errors.append("初始资金必须大于0")
        if self.commission_rate < 0:
            errors.append("手续费率不能为负")
        if self.max_position <= 0 or self.max_position > 1:
            errors.append("最大持仓比例必须在0-1之间")
        return errors


# ==================== 回测结果模型 ====================
@dataclass
class BacktestResult:
    """回测结果"""
    # 标识
    id: str
    strategy_id: str

    # 参数
    start_date: str
    end_date: str
    initial_capital: float

    # 结果
    final_capital: float = 0.0
    metrics: Optional[PerformanceMetrics] = None

    # 交易记录
    trades: List[Dict[str, Any]] = field(default_factory=list)

    # 资金曲线
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)

    # 状态
    status: str = "running"  # running, completed, failed
    error_message: Optional[str] = None

    # 时间
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None


# ==================== 策略状态模型 ====================
@dataclass
class StrategyState:
    """策略运行状态"""
    strategy_id: str
    is_running: bool = False

    # 持仓状态
    positions: List[Position] = field(default_factory=list)

    # 信号状态
    pending_signals: List[TradingSignal] = field(default_factory=list)

    # 资金状态
    available_capital: float = 0.0
    frozen_capital: float = 0.0
    total_assets: float = 0.0

    # 统计
    today_trades: int = 0
    total_trades: int = 0

    # 中断检测
    last_run_date: Optional[datetime] = None

    # 最后更新时间
    last_update_time: datetime = field(default_factory=datetime.now)

    def get_position(self, ts_code: str) -> Optional[Position]:
        """获取持仓"""
        for pos in self.positions:
            if pos.ts_code == ts_code:
                return pos
        return None

    def has_position(self, ts_code: str) -> bool:
        """是否有持仓"""
        return self.get_position(ts_code) is not None
