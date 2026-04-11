# models.py                 # 交易业务模型

# 本地枚举定义（enums.py 中没有的枚举）
import enum
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Boolean, Text
from sqlalchemy.orm import relationship

from quant_server.core.engines.types.enums import (
	OrderStatus, OrderType, OrderDirection as Direction,
	TimeInForce, RiskLevel
)
from quant_server.shared.database.models import Base


class SignalStatus(str, enum.Enum):
	"""信号状态枚举"""
	GENERATED = "generated"  # 已生成
	PROCESSED = "processed"  # 已处理
	EXECUTED = "executed"  # 已执行
	FAILED = "failed"  # 失败
	CANCELLED = "cancelled"  # 已取消


# 基础模型类
class TradeBase(Base):
	"""交易基础模型"""
	__abstract__ = True

	id = Column(Integer, primary_key=True, index=True)
	created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
	updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# 订单模型
class Order(TradeBase):
	"""订单模型"""
	__tablename__ = "orders"

	order_id = Column(String(100), unique=True, index=True, nullable=False)
	client_order_id = Column(String(100), nullable=True, index=True)
	ts_code = Column(String(20), index=True, nullable=False)
	direction = Column(Enum(Direction), nullable=False)
	price = Column(Float, nullable=False)
	quantity = Column(Integer, nullable=False)
	filled_price = Column(Float, nullable=True)
	filled_quantity = Column(Integer, nullable=True, default=0)
	status = Column(Enum(OrderStatus), default=OrderStatus.PENDING, index=True)
	order_type = Column(Enum(OrderType), default=OrderType.LIMIT)
	time_in_force = Column(Enum(TimeInForce), default=TimeInForce.DAY)
	strategy_id = Column(String(100), nullable=True, index=True)
	signal_id = Column(String(100), nullable=True, index=True)
	error_message = Column(Text, nullable=True)

	# 关系
	trades = relationship("Trade", back_populates="order", cascade="all, delete-orphan")


# 交易模型
class Trade(TradeBase):
	"""交易模型"""
	__tablename__ = "trades"

	trade_id = Column(String(100), unique=True, index=True, nullable=False)
	order_id = Column(String(100), ForeignKey("orders.order_id"), nullable=False, index=True)
	ts_code = Column(String(20), index=True, nullable=False)
	direction = Column(Enum(Direction), nullable=False)
	price = Column(Float, nullable=False)
	quantity = Column(Integer, nullable=False)
	trade_time = Column(DateTime, nullable=False, index=True)
	commission = Column(Float, default=0.0)
	stamp_duty = Column(Float, default=0.0)
	transfer_fee = Column(Float, default=0.0)

	# 关系
	order = relationship("Order", back_populates="trades")


# 持仓模型
class Position(TradeBase):
	"""持仓模型"""
	__tablename__ = "positions"

	ts_code = Column(String(20), unique=True, index=True, nullable=False)
	quantity = Column(Integer, default=0)
	available_quantity = Column(Integer, default=0)
	average_cost = Column(Float, default=0.0)
	current_price = Column(Float, default=0.0)
	market_value = Column(Float, default=0.0)
	profit_loss = Column(Float, default=0.0)
	profit_loss_ratio = Column(Float, default=0.0)
	last_update = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# 账户模型
class Account(TradeBase):
	"""账户模型"""
	__tablename__ = "accounts"

	account_id = Column(String(100), unique=True, index=True, nullable=False)
	total_asset = Column(Float, default=0.0)
	available_cash = Column(Float, default=0.0)
	frozen_cash = Column(Float, default=0.0)
	market_value = Column(Float, default=0.0)
	total_profit_loss = Column(Float, default=0.0)
	total_profit_loss_ratio = Column(Float, default=0.0)
	last_update = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# 信号模型
class Signal(TradeBase):
	"""信号模型"""
	__tablename__ = "signals"

	signal_id = Column(String(100), unique=True, index=True, nullable=False)
	strategy_id = Column(String(100), nullable=False, index=True)
	ts_code = Column(String(20), index=True, nullable=False)
	direction = Column(Enum(Direction), nullable=False)
	price = Column(Float, nullable=False)
	quantity = Column(Integer, nullable=False)
	status = Column(Enum(SignalStatus), default=SignalStatus.GENERATED, index=True)
	order_id = Column(String(100), nullable=True, index=True)
	error_message = Column(Text, nullable=True)
	extra_data = Column(Text, nullable=True)  # 存储额外的信号数据


# 风险事件模型
class RiskEvent(TradeBase):
	"""风险事件模型"""
	__tablename__ = "risk_events"

	event_id = Column(String(100), unique=True, index=True, nullable=False)
	risk_type = Column(String(100), index=True, nullable=False)
	risk_level = Column(Enum(RiskLevel), nullable=False)
	message = Column(Text, nullable=False)
	ts_code = Column(String(20), nullable=True, index=True)
	account_id = Column(String(100), nullable=True, index=True)
	order_id = Column(String(100), nullable=True, index=True)
	signal_id = Column(String(100), nullable=True, index=True)
	handled = Column(Boolean, default=False)
	handled_time = Column(DateTime, nullable=True)
	handled_by = Column(String(100), nullable=True)