# -*- coding: utf-8 -*-
"""
策略基类
所有具体策略的父类，定义策略的通用接口和方法
"""
import logging
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

logger = logging.getLogger(__name__)

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


# =============================================================================
# v3.4: 实盘状态注入 — 策略通过框架获取持仓/信号/账户信息，不自己查 DB
# =============================================================================

@dataclass
class LivePosition:
    """实盘持仓状态（由框架从 positions 表加载并注入策略）"""
    ts_code: str
    quantity: int = 0
    available_quantity: int = 0
    cost_price: float = 0.0
    last_price: float = 0.0
    market_value: float = 0.0
    pnl_rate: float = 0.0


@dataclass
class LiveSignal:
    """实盘信号状态（由框架从 signals 表加载并注入策略）"""
    ts_code: str
    direction: str = "LONG"
    signal_type: str = "entry"
    status: str = "pending_manual"


@dataclass
class LiveAccount:
    """实盘账户状态（由框架从 accounts 表加载并注入策略）"""
    total_assets: float = 0.0
    available_cash: float = 0.0
    market_value: float = 0.0


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

		# v3.4: 实盘状态注入（由 load_live_state 填充，回测模式为空）
		self._active_positions: Dict[str, 'LivePosition'] = {}
		self._pending_signals: Dict[str, 'LiveSignal'] = {}
		self._account_snapshot: Optional['LiveAccount'] = None

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

	async def load_live_state(self, db, strategy_id: str = "") -> None:
		"""从DB加载实盘持仓/待确认信号/账户状态（仅实盘调用）"""
		from sqlalchemy import text
		sid = strategy_id or self.name  # 优先用 UUID，回退到名称
		logger.info("%s: load_live_state strategy_id=%s", self.name, sid)

		# v3.5: 先清空再加载，避免 DB 中已清除但内存残留脏数据
		self._active_positions.clear()
		self._pending_signals.clear()

		# 1. 持仓
		try:
			result = await db.execute(text(
				"SELECT ts_code, volume, available_volume, cost_price, last_price, "
				"market_value, pnl_rate FROM positions WHERE strategy_id = :sid AND volume > 0"
			), {"sid": sid})
			rows = result.fetchall()
			for row in rows:
				self._active_positions[row[0]] = LivePosition(
					ts_code=row[0], quantity=row[1], available_quantity=row[2],
					cost_price=float(row[3] or 0), last_price=float(row[4] or 0),
					market_value=float(row[5] or 0), pnl_rate=float(row[6] or 0),
				)
			logger.info("%s: positions=%d %s", self.name, len(rows),
				[(r[0], r[1]) for r in rows])
		except Exception as e:
			logger.warning("%s: positions load failed: %s", self.name, e)

		# 2. 待处理信号
		try:
			result = await db.execute(text(
				"SELECT ts_code, direction, signal_type, signal_status FROM signals "
				"WHERE strategy_id = :sid AND direction = 'long' "
				"AND signal_status IN ('pending','pending_manual','confirmed')"
			), {"sid": sid})
			rows = result.fetchall()
			for row in rows:
				self._pending_signals[row[0]] = LiveSignal(
					ts_code=row[0], direction=row[1] or "LONG",
					signal_type=row[2] or "entry", status=row[3] or "pending_manual")
			logger.info("%s: pending_signals=%d %s", self.name, len(rows),
				[(r[0], r[3]) for r in rows])
		except Exception as e:
			logger.warning("%s: signals load failed: %s", self.name, e)

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

	def update_position(self, position: Position = None, **kwargs) -> None:
		"""
		更新持仓。

		支持两种调用方式：
		  1. update_position(position: Position)          — 传入 Position 对象
		  2. update_position(ts_code="xxx", side="long", quantity=100, avg_price=10.5)
		     — 传入关键字参数，内部构造 Position 对象
		"""
		if position is not None:
			self.positions[position.ts_code] = position
		elif kwargs:
			ts_code = kwargs.get("ts_code", "")
			if ts_code:
				from modules.strategy.constants import PositionSide
				side_str = kwargs.get("side", "long")
				side = PositionSide.LONG if side_str == "long" else PositionSide.SHORT
				avg_price = float(kwargs.get("avg_price", kwargs.get("avg_cost", 0)))
				quantity = int(kwargs.get("quantity", 0))
				pos = Position(
					id=f"{self.name}_{ts_code}",
					strategy_id=self.name,
					ts_code=ts_code,
					side=side,
					quantity=quantity,
					avg_cost=avg_price,
					current_price=avg_price,
				)
				self.positions[ts_code] = pos

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
		验证信号语义有效性（纯信号层检查，不涉及数量和资金）。

		price/quantity/amount 的兜底由 Engine+Sizer 层处理，
		资金充足性由 Broker.submit_order() 检查。
		此处只验证信号本身是否语义合法。

		Args:
			signal: 交易信号

		Returns:
			是否有效
		"""
		if signal.ts_code is None or signal.ts_code == "":
			return False
		if signal.confidence < 0 or signal.confidence > 1:
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
