# -*- coding: utf-8 -*-
"""
策略基类
所有具体策略的父类，定义策略的通用接口和方法
"""
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any

import pandas as pd

from core.engines.types.entities import BarData
from modules.strategy.constants import (
	StrategyType,
	SignalDirection,
)
from modules.strategy.models import TradingSignal, Position
from modules.strategy.strategies.base.strategy_context import StrategyContext


@dataclass
class MarketData:
	"""市场数据"""
	ts_code: str
	open: float
	high: float
	low: float
	close: float
	volume: float
	amount: float = 0.0
	trade_date: Any = None
	trade_time: Optional[datetime] = None


class BaseStrategy(ABC):
	"""
	策略基类

	所有具体策略都需要继承此类并实现以下方法：
	- on_init: 初始化策略参数
	- on_start: 策略启动时调用
	- on_stop: 策略停止时调用
	- on_bar: 收到K线数据时调用
	- on_tick: 收到Tick数据时调用

	属性:
		name: 策略名称
		strategy_type: 策略类型
		parameters: 策略参数
		positions: 当前持仓
		signals: 产生的信号列表
	"""

	def __init__ (
			self,
			name: str,
			strategy_type: StrategyType = StrategyType.CTA,
			parameters: Optional[Dict[str, Any]] = None,
	):
		"""
		初始化策略

		Args:
			name: 策略名称
			strategy_type: 策略类型
			parameters: 策略参数
		"""
		self.name = name
		self.strategy_type = strategy_type
		self.parameters = parameters or {}
		self.positions: Dict[str, Position] = {}
		self.signals: List[TradingSignal] = []

		# 策略运行状态
		self._is_initialized = False
		self._is_running = False

		# 策略上下文（运行时由外部注入）
		self.context: Optional['StrategyContext'] = None

		# 股票池 — 策略在 on_start 中可从 DB 加载，外部通过 universe property 读取
		self._universe: List[str] = []

		# 数据缓存
		self._data_cache: Dict[str, pd.DataFrame] = {}
		self._bar_count = 0

	@property
	def is_initialized (self) -> bool:
		"""是否已初始化"""
		return self._is_initialized

	@property
	def is_running (self) -> bool:
		"""是否在运行"""
		return self._is_running

	@property
	def universe (self) -> List[str]:
		"""
		策略股票池（公开只读 API）。

		策略在 on_start() 中可从 DB 加载股票列表写入 self._universe，
		外部模块（如 BacktestService）通过此 property 读取，避免直接
		触碰 protected 成员 _universe。

		Returns:
			股票代码列表，未设置时返回空列表
		"""
		return self._universe

	def initialize (self) -> None:
		"""
		初始化策略

		调用on_init方法，执行策略初始化逻辑
		"""
		if self._is_initialized:
			return

		self.on_init()
		self._is_initialized = True

	async def start (self) -> None:
		"""
		启动策略

		调用on_start方法，执行策略启动逻辑
		兼容 sync/async on_start
		"""
		if not self._is_initialized:
			self.initialize()

		result = self.on_start()
		if asyncio.iscoroutine(result):
			await result
		self._is_running = True

	async def stop (self) -> None:
		"""
		停止策略

		调用on_stop方法，执行策略停止逻辑
		兼容 sync/async on_stop
		"""
		result = self.on_stop()
		if asyncio.iscoroutine(result):
			await result
		self._is_running = False

	def on_init (self) -> None:
		"""
		策略初始化

		在initialize时调用，可以在此方法中：
		- 加载策略参数
		- 初始化技术指标
		- 订阅数据
		"""
		pass

	def on_start (self) -> None:
		"""
		策略启动

		在start时调用，可以在此方法中：
		- 初始化仓位
		- 加载历史数据
		"""
		pass

	def on_stop (self) -> None:
		"""
		策略停止

		在stop时调用，可以在此方法中：
		- 清理资源
		- 平仓处理
		"""
		pass

	@abstractmethod
	def on_bar (self, bar: BarData) -> List[TradingSignal]:
		"""
		收到K线数据时调用

		Args:
			bar: K线数据

		Returns:
			产生的交易信号列表
		"""
		pass

	@staticmethod
	def on_tick (tick: MarketData) -> List[TradingSignal]:
		"""
		收到Tick数据时调用（可选实现）

		Args:
			tick: Tick数据

		Returns:
			产生的交易信号列表
		"""
		_ = tick  # 避免未使用参数警告
		return []

	def on_calculate_indicators (self, data: pd.DataFrame) -> pd.DataFrame:
		"""
		计算技术指标

		Args:
			data: 包含OHLCV数据的DataFrame

		Returns:
			添加了技术指标的DataFrame
		"""
		df = data.copy()

		# 计算简单移动平均
		for period in self.parameters.get('ma_periods', [5, 10, 20]):
			df[f'ma_{period}'] = df['close'].rolling(window=period).mean()

		# 计算成交量移动平均
		if 'volume_ma_period' in self.parameters:
			period = self.parameters['volume_ma_period']
			df[f'volume_ma'] = df['volume'].rolling(window=period).mean()

		return df

	def has_position (self, ts_code: str) -> bool:
		"""是否有持仓"""
		return ts_code in self.positions

	def get_position (self, ts_code: str) -> Optional[Position]:
		"""获取持仓"""
		return self.positions.get(ts_code)

	def update_position (self, position: Position) -> None:
		"""更新持仓"""
		self.positions[position.ts_code] = position

	def clear_position (self, ts_code: str) -> None:
		"""清除持仓"""
		if ts_code in self.positions:
			del self.positions[ts_code]

	def clear_all_positions (self) -> None:
		"""清除所有持仓"""
		self.positions.clear()

	def add_signal (self, signal: TradingSignal) -> None:
		"""添加信号"""
		self.signals.append(signal)

	def clear_signals (self) -> None:
		"""清除信号"""
		self.signals.clear()

	# ==================== 辅助方法 ====================

	def get_cache_data (self, key: str) -> Optional[pd.DataFrame]:
		"""获取缓存数据"""
		return self._data_cache.get(key)

	def set_cache_data (self, key: str, data: pd.DataFrame) -> None:
		"""设置缓存数据"""
		self._data_cache[key] = data

	@staticmethod
	def calculate_pnl (
			ts_code: str,
			entry_price: float,
			current_price: float,
			quantity: int,
			direction: SignalDirection
	) -> float:
		"""
		计算盈亏

		Args:
			ts_code: 股票代码
			entry_price: 入场价格
			current_price: 当前价格
			quantity: 数量
			direction: 方向

		Returns:
			盈亏金额
		"""
		_ = ts_code  # 避免未使用参数警告
		if direction == SignalDirection.LONG:
			return (current_price - entry_price) * quantity
		elif direction == SignalDirection.SHORT:
			return (entry_price - current_price) * quantity
		return 0.0

	def validate_signal (self, signal: TradingSignal) -> bool:
		"""
		验证信号是否有效

		Args:
			signal: 交易信号

		Returns:
			是否有效
		"""
		# 基本验证
		if signal.price <= 0:
			return False
		if signal.quantity <= 0:
			return False
		if signal.confidence < 0 or signal.confidence > 1:
			return False

		# 资金验证（如果有context）
		if self.context:
			required_amount = signal.price * signal.quantity
			if required_amount > self.context.available_capital:
				return False

		return True


class TechnicalStrategy(BaseStrategy):
	"""
	技术指标策略基类

	继承自BaseStrategy，添加了技术指标计算的辅助方法
	"""

	def __init__ (
			self,
			name: str,
			strategy_type: StrategyType = StrategyType.TECHNICAL,
			parameters: Optional[Dict[str, Any]] = None,
	):
		super().__init__(name, strategy_type, parameters)

	def on_bar (self, bar: BarData) -> List[TradingSignal]:
		"""
		收到K线数据时调用

		Args:
			bar: K线数据

		Returns:
			产生的交易信号列表
		"""
		return []

	@staticmethod
	def calculate_ma (data: pd.Series, period: int) -> pd.Series:
		"""计算移动平均"""
		return data.rolling(window=period).mean()

	@staticmethod
	def calculate_ema (data: pd.Series, period: int) -> pd.Series:
		"""计算指数移动平均"""
		return data.ewm(span=period, adjust=False).mean()

	@staticmethod
	def calculate_macd (
			data: pd.Series,
			fast_period: int = 12,
			slow_period: int = 26,
			signal_period: int = 9
	) -> tuple:
		"""计算MACD"""
		ema_fast = TechnicalStrategy.calculate_ema(data, fast_period)
		ema_slow = TechnicalStrategy.calculate_ema(data, slow_period)
		macd = ema_fast - ema_slow
		signal = TechnicalStrategy.calculate_ema(macd, signal_period)
		histogram = macd - signal
		return macd, signal, histogram

	@staticmethod
	def calculate_rsi (
			data: pd.Series,
			period: int = 14
	) -> pd.Series:
		"""计算RSI"""
		delta = data.diff()
		gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
		loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
		rs = gain / loss
		rsi = 100 - (100 / (1 + rs))
		return rsi

	@staticmethod
	def calculate_bollinger_bands (
			data: pd.Series,
			period: int = 20,
			std_dev: float = 2.0
	) -> tuple:
		"""计算布林带"""
		ma = data.rolling(window=period).mean()
		std = data.rolling(window=period).std()
		upper = ma + (std * std_dev)
		lower = ma - (std * std_dev)
		return upper, ma, lower

	@staticmethod
	def calculate_atr (
			high: pd.Series,
			low: pd.Series,
			close: pd.Series,
			period: int = 14
	) -> pd.Series:
		"""计算ATR"""
		tr1 = high - low
		tr2 = (high - close.shift()).abs()
		tr3 = (low - close.shift()).abs()
		tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
		atr = tr.rolling(window=period).mean()
		return atr
