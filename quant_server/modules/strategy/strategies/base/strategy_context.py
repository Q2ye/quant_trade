# -*- coding: utf-8 -*-
"""
策略上下文
提供策略运行时所需的数据和服务
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Callable

import pandas as pd

from modules.strategy.constants import RunMode, TimeFrame
from modules.strategy.models import Position


@dataclass
class StrategyContext:
	"""
	策略上下文

	在策略运行时提供必要的环境信息和服务
	"""

	# 策略标识
	strategy_id: str
	strategy_name: str
	user_id: str

	# 运行参数
	run_mode: RunMode = RunMode.SIMULATION
	time_frame: TimeFrame = TimeFrame.DAILY
	initial_capital: float = 1000000.0

	# 资金状态
	available_capital: float = 1000000.0
	frozen_capital: float = 0.0
	total_assets: float = 1000000.0

	# 持仓
	positions: Dict[str, Position] = field(default_factory=dict)

	# 配置参数
	commission_rate: float = 0.0003  # 手续费率
	slippage: float = 0.001  # 滑点
	max_position: float = 0.2  # 最大持仓比例
	stop_loss: float = 0.05  # 止损比例
	take_profit: float = 0.15  # 止盈比例

	# 数据回调
	get_data_func: Optional[Callable] = None  # 获取数据函数
	get_real_time_price_func: Optional[Callable] = None  # 获取实时价格函数
	submit_order_func: Optional[Callable] = None  # 提交订单函数
	cancel_order_func: Optional[Callable] = None  # 取消订单函数

	# 事件回调
	on_signal_callback: Optional[Callable] = None  # 信号回调
	on_order_callback: Optional[Callable] = None  # 订单回调
	on_position_callback: Optional[Callable] = None  # 持仓变更回调

	# 状态
	is_initialized: bool = False
	is_running: bool = False

	# 时间
	current_date: Optional[datetime] = None
	current_time: Optional[datetime] = None

	# 缓存
	_data_cache: Dict[str, pd.DataFrame] = field(default_factory=dict)

	def initialize (self) -> None:
		"""初始化上下文"""
		self.is_initialized = True

	def update_capital (
			self,
			available: Optional[float] = None,
			frozen: Optional[float] = None
	) -> None:
		"""更新资金"""
		if available is not None:
			self.available_capital = available
		if frozen is not None:
			self.frozen_capital = frozen
		self.total_assets = self.available_capital + self.frozen_capital

	def update_position (self, position: Position) -> None:
		"""更新持仓"""
		self.positions[position.ts_code] = position

	def remove_position (self, ts_code: str) -> None:
		"""移除持仓"""
		if ts_code in self.positions:
			del self.positions[ts_code]

	def get_position (self, ts_code: str) -> Optional[Position]:
		"""获取持仓"""
		return self.positions.get(ts_code)

	def has_position (self, ts_code: str) -> bool:
		"""是否有持仓"""
		return ts_code in self.positions

	def get_all_positions (self) -> List[Position]:
		"""获取所有持仓"""
		return list(self.positions.values())

	def get_total_position_value (self) -> float:
		"""获取总持仓市值"""
		return sum(pos.market_value for pos in self.positions.values())

	def get_total_pnl (self) -> float:
		"""获取总盈亏"""
		return sum(pos.pnl for pos in self.positions.values())

	# ==================== 数据获取方法 ====================

	def get_historical_data (
			self,
			ts_code: str,
			start_date: str,
			end_date: str,
			frequency: str = "daily"
	) -> Optional[pd.DataFrame]:
		"""
		获取历史数据

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期
			frequency: 频率 (daily, 1min, 5min, etc.)

		Returns:
			DataFrame
		"""
		if self.get_data_func:
			return self.get_data_func(
				ts_code=ts_code,
				start_date=start_date,
				end_date=end_date,
				frequency=frequency
			)
		return None

	def get_realtime_price (self, ts_code: str) -> Optional[float]:
		"""
		获取实时价格

		Args:
			ts_code: 股票代码

		Returns:
			当前价格
		"""
		if self.get_real_time_price_func:
			return self.get_real_time_price_func(ts_code)
		return None

	def get_price_history (self, ts_code: str, period: int) -> List[float]:
		"""
		获取历史价格数据

		Args:
			ts_code: 股票代码
			period: 周期

		Returns:
			价格列表
		"""
		# 从缓存中获取数据
		cache_key = f"{ts_code}_price_history"
		data = self.get_cached_data(cache_key)
		if data is not None:
			return data['close'].tail(period).tolist()
		return []

	# ==================== 订单操作方法 ====================

	def submit_order (
			self,
			ts_code: str,
			direction: str,
			quantity: int,
			order_type: str = "market",
			price: Optional[float] = None
	) -> Optional[str]:
		"""
		提交订单

		Args:
			ts_code: 股票代码
			direction: 方向 (long, short, close_long, close_short)
			quantity: 数量
			order_type: 订单类型 (market, limit)
			price: 价格 (限价单)

		Returns:
			订单ID
		"""
		if self.submit_order_func:
			return self.submit_order_func(
				strategy_id=self.strategy_id,
				ts_code=ts_code,
				direction=direction,
				quantity=quantity,
				order_type=order_type,
				price=price
			)
		return None

	def cancel_order (self, order_id: str) -> bool:
		"""
		取消订单

		Args:
			order_id: 订单ID

		Returns:
			是否成功
		"""
		if self.cancel_order_func:
			return self.cancel_order_func(order_id)
		return False

	# ==================== 风控检查 ====================

	def check_risk (
			self,
			ts_code: str,
			direction: str,
			quantity: int,
			price: float
	) -> tuple:
		"""
		风控检查

		Args:
			ts_code: 股票代码
			direction: 方向
			quantity: 数量
			price: 价格

		Returns:
			(是否通过, 错误信息)
		"""
		# 计算订单金额
		amount = price * quantity

		# 检查资金是否充足
		if amount > self.available_capital:
			return False, "资金不足"

		# 检查是否超过最大持仓
		if direction in ["long"]:
			position_value = self.get_total_position_value() + amount
			if position_value > self.total_assets * self.max_position:
				return False, "超过最大持仓比例"

		return True, ""

	# ==================== 缓存管理 ====================

	def cache_data (self, key: str, data: pd.DataFrame) -> None:
		"""缓存数据"""
		self._data_cache[key] = data

	def get_cached_data (self, key: str) -> Optional[pd.DataFrame]:
		"""获取缓存数据"""
		return self._data_cache.get(key)

	def clear_cache (self) -> None:
		"""清除缓存"""
		self._data_cache.clear()

	# ==================== 时间更新 ====================

	def update_time (self, date: datetime, time: datetime) -> None:
		"""更新时间"""
		self.current_date = date
		self.current_time = time