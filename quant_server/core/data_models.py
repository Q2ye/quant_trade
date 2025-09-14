# core/data_models.py
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Exchange(Enum):
    SSE = "SSE"  # 上交所
    SZSE = "SZSE"  # 深交所
    BSE = "BSE"  # 北交所


class Interval(Enum):
    MINUTE = "1min"
    MINUTE_5 = "5min"
    MINUTE_15 = "15min"
    MINUTE_30 = "30min"
    HOUR = "60min"
    DAILY = "D"
    WEEKLY = "W"
    MONTHLY = "M"


class Direction(Enum):
    NONE = None
    LONG = "LONG"
    SHORT = "SHORT"
    BUY = "BUY"  # 买入
    SELL = "SELL"  # 卖出


class OrderType(Enum):
    LIMIT = "LIMIT"  # 限价单
    MARKET = "MARKET"  # 市价单
    STOP = "STOP"  # 止损单


class OrderStatus(Enum):
    SUBMITTING = "SUBMITTING"  # 提交中
    SUBMITTED = "SUBMITTED"  # 已提交
    PARTIAL_FILLED = "PARTIAL_FILLED"  # 部分成交
    FILLED = "FILLED"  # 完全成交
    CANCELLED = "CANCELLED"  # 已取消
    REJECTED = "REJECTED"  # 已拒绝


@dataclass
class BarData:
    """K线数据"""
    symbol: str
    exchange: Exchange
    datetime: datetime
    interval: Interval
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    turnover: float = 0  # 成交额
    open_interest: float = 0  # 持仓量（期货）
    gateway_name: str = ""

    def __post_init__(self):
        # 确保数据类型正确
        self.open_price = float(self.open_price)
        self.high_price = float(self.high_price)
        self.low_price = float(self.low_price)
        self.close_price = float(self.close_price)
        self.volume = float(self.volume)
        self.turnover = float(self.turnover)


@dataclass
class TickData:
    """Tick数据"""
    symbol: str
    exchange: Exchange
    datetime: datetime
    last_price: float = 0
    last_volume: float = 0
    limit_up: float = 0
    limit_down: float = 0
    open_interest: float = 0
    volume: float = 0
    turnover: float = 0
    open_price: float = 0
    high_price: float = 0
    low_price: float = 0
    pre_close: float = 0

    # 买卖档位
    bid_price_1: float = 0
    bid_price_2: float = 0
    bid_price_3: float = 0
    bid_price_4: float = 0
    bid_price_5: float = 0

    bid_volume_1: float = 0
    bid_volume_2: float = 0
    bid_volume_3: float = 0
    bid_volume_4: float = 0
    bid_volume_5: float = 0

    ask_price_1: float = 0
    ask_price_2: float = 0
    ask_price_3: float = 0
    ask_price_4: float = 0
    ask_price_5: float = 0

    ask_volume_1: float = 0
    ask_volume_2: float = 0
    ask_volume_3: float = 0
    ask_volume_4: float = 0
    ask_volume_5: float = 0

    gateway_name: str = ""


@dataclass
class OrderData:
    """订单数据"""
    symbol: str
    exchange: Exchange
    orderid: str
    direction: Direction
    order_type: OrderType
    price: float
    volume: float
    traded: float = 0
    status: OrderStatus = OrderStatus.SUBMITTING
    datetime: datetime = None
    gateway_name: str = ""

    def __post_init__(self):
        if self.datetime is None:
            self.datetime = datetime.now()


@dataclass
class TradeData:
    """成交数据"""
    symbol: str
    exchange: Exchange
    tradeid: str
    orderid: str
    direction: Direction
    price: float
    volume: float
    datetime: datetime
    gateway_name: str = ""


@dataclass
class PositionData:
    """持仓数据"""
    symbol: str
    exchange: Exchange
    direction: Direction
    volume: float = 0
    frozen: float = 0  # 冻结数量
    price: float = 0  # 持仓均价
    pnl: float = 0  # 持仓盈亏
    gateway_name: str = ""


@dataclass
class SignalData:
    """信号数据"""
    strategy_id: str
    symbol: str
    signal_type: str  # BUY/SELL/HOLD
    signal_time: datetime
    price: float = 0
    strength: float = 0  # 信号强度 0-1
    reason: str = ""