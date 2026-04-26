# -*- coding: utf-8 -*-
"""
CTA策略引擎
处理趋势跟踪类CTA策略的执行
"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from quant_server.core.engines.base.engine_base import EngineBase
from quant_server.core.engines.types.entities import EngineConfigEntity
from quant_server.core.engines.types.enums import EngineType
from quant_server.modules.strategy.models import TradingSignal
from quant_server.modules.strategy.strategies.base.base_strategy import BaseStrategy
from quant_server.modules.strategy.strategies.base.strategy_context import StrategyContext

logger = logging.getLogger(__name__)


class CTAEngine(EngineBase):
	"""
	CTA策略引擎

	负责：
	- CTA策略的加载和执行
	- 趋势信号的识别和处理
	- 持仓管理和止盈止损
	- 策略时间序列管理

	CTA策略特点：
	- 趋势跟踪
	- 多周期支持
	- 严格的止盈止损
	"""

	def __init__ (self, event_engine=None):
		"""
		初始化CTA引擎

		Args:
			event_engine: 事件引擎
		"""
		# 创建配置实体
		config = EngineConfigEntity(
			name="CTAEngine",
			engine_type=EngineType.CTA_ENGINE.value
		)
		super().__init__(config=config, event_engine=event_engine)
		self.event_engine = event_engine

		# 策略实例 {strategy_id: strategy_instance}
		self._strategies: Dict[str, BaseStrategy] = {}

		# 策略上下文 {strategy_id: context}
		self._contexts: Dict[str, StrategyContext] = {}

		# 订阅的股票池
		self._watching_symbols: Dict[str, List[str]] = {}

		# 当前处理的K线数据
		self._bar_cache: Dict[str, Any] = {}

	async def load_strategy (
			self,
			strategy_id: str,
			strategy: BaseStrategy,
			context: StrategyContext,
			symbols: Optional[List[str]] = None,
	) -> None:
		"""
		加载策略

		Args:
			strategy_id: 策略ID
			strategy: 策略实例
			context: 策略上下文
			symbols: 订阅的股票列表
		"""
		self._strategies[strategy_id] = strategy
		self._contexts[strategy_id] = context
		self._watching_symbols[strategy_id] = symbols or []

		# 初始化策略
		strategy.context = context
		strategy.initialize()

		logger.info(f"CTA策略加载成功: {strategy_id}, 订阅: {len(symbols)} 只股票")

	async def unload_strategy (self, strategy_id: str) -> None:
		"""
		卸载策略

		Args:
			strategy_id: 策略ID
		"""
		if strategy_id in self._strategies:
			strategy = self._strategies[strategy_id]
			strategy.stop()

			del self._strategies[strategy_id]
			del self._contexts[strategy_id]
			if strategy_id in self._watching_symbols:
				del self._watching_symbols[strategy_id]

			logger.info(f"CTA策略卸载成功: {strategy_id}")

	async def start (self) -> bool:
		"""启动引擎"""
		# 调用基类的start方法
		result = await super().start()
		logger.info("CTA引擎启动")
		return result

	async def stop (self, force: bool = False, timeout: float = 30.0) -> bool:
		"""停止引擎"""
		# 停止所有策略
		for strategy_id, strategy in self._strategies.items():
			try:
				strategy.stop()
			except Exception as e:
				logger.error(f"停止策略 {strategy_id} 失败: {e}")

		# 调用基类的stop方法
		result = await super().stop(force, timeout)
		logger.info("CTA引擎停止")
		return result

	async def process_bar (
			self,
			strategy_id: str,
			bar_data: Any,
	) -> List[TradingSignal]:
		"""
		处理K线数据

		Args:
			strategy_id: 策略ID
			bar_data: K线数据

		Returns:
			产生的信号列表
		"""
		if strategy_id not in self._strategies:
			logger.warning(f"策略 {strategy_id} 未加载")
			return []

		strategy = self._strategies[strategy_id]
		context = self._contexts.get(strategy_id)

		if not context or not context.is_running:
			return []

		try:
			# 更新上下文时间
			if hasattr(bar_data, 'trade_date'):
				context.update_time(
					date=bar_data.trade_date,
					time=bar_data.trade_time or datetime.now()
				)

			# 调用策略的on_bar方法
			signals = strategy.on_bar(bar_data)

			# 处理信号
			if signals:
				await self._process_signals(strategy_id, signals)

			return signals

		except Exception as e:
			logger.error(f"处理K线数据失败: {e}", exc_info=True)
			return []

	async def process_tick (
			self,
			strategy_id: str,
			tick_data: Any,
	) -> List[TradingSignal]:
		"""
		处理Tick数据

		Args:
			strategy_id: 策略ID
			tick_data: Tick数据

		Returns:
			产生的信号列表
		"""
		if strategy_id not in self._strategies:
			return []

		strategy = self._strategies[strategy_id]

		try:
			# 调用策略的on_tick方法
			signals = strategy.on_tick(tick_data)

			if signals:
				await self._process_signals(strategy_id, signals)

			return signals

		except Exception as e:
			logger.error(f"处理Tick数据失败: {e}")
			return []

	async def _process_signals (
			self,
			strategy_id: str,
			signals: List[TradingSignal],
	) -> None:
		"""
		处理信号

		Args:
			strategy_id: 策略ID
			signals: 信号列表
		"""
		for signal in signals:
			try:
				# 验证信号
				if not self._validate_signal(signal):
					logger.warning(f"信号验证失败: {signal}")
					continue

				# 发布信号事件
				if self.event_engine:
					from quant_server.modules.strategy.events.signal_events import (
						StrategySignalEvent,
					)
					event = StrategySignalEvent(
						strategy_id=strategy_id,
						strategy_name=signal.strategy_name,
						ts_code=signal.ts_code,
						signal_type=signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(
							signal.signal_type),
						signal_direction=signal.direction.value if hasattr(signal.direction, 'value') else str(
							signal.direction),
						price=signal.price,
						quantity=signal.quantity,
						reason=signal.reason,
						confidence=signal.confidence,
					)
					await self.event_engine.put(event)

			except Exception as e:
				logger.error(f"处理信号失败: {e}")

	@staticmethod
	def _validate_signal (signal: TradingSignal) -> bool:
		"""
		验证信号

		Args:
			signal: 交易信号

		Returns:
			是否有效
		"""
		# 基本验证
		if not signal.ts_code:
			return False
		if signal.price <= 0:
			return False
		if signal.quantity <= 0:
			return False
		if signal.confidence < 0 or signal.confidence > 1:
			return False

		return True

	def get_strategy (self, strategy_id: str) -> Optional[BaseStrategy]:
		"""
		获取策略实例

		Args:
			strategy_id: 策略ID

		Returns:
			策略实例
		"""
		return self._strategies.get(strategy_id)

	def get_context (self, strategy_id: str) -> Optional[StrategyContext]:
		"""
		获取策略上下文

		Args:
			strategy_id: 策略ID

		Returns:
			策略上下文
		"""
		return self._contexts.get(strategy_id)

	def get_watching_symbols (self, strategy_id: str) -> List[str]:
		"""
		获取策略订阅的股票列表

		Args:
			strategy_id: 策略ID

		Returns:
			股票列表
		"""
		return self._watching_symbols.get(strategy_id, [])

	def get_all_strategies (self) -> Dict[str, BaseStrategy]:
		"""获取所有策略"""
		return self._strategies.copy()

	# ==================== 抽象方法实现 ====================

	async def _on_initialize (self):
		"""引擎初始化时的具体逻辑"""
		logger.info("CTA引擎初始化")

	async def _on_start (self):
		"""引擎启动时的具体逻辑"""
		logger.info("CTA引擎启动")

	async def _on_stop (self):
		"""引擎停止时的具体逻辑"""
		# 停止所有策略
		for strategy_id, strategy in self._strategies.items():
			try:
				strategy.stop()
			except Exception as e:
				logger.error(f"停止策略 {strategy_id} 失败: {e}")
		logger.info("CTA引擎停止")

	# ==================== 其他方法 ====================

	@property
	def engine_type (self):
		"""获取引擎类型"""
		from quant_server.core.engines.types.enums import EngineType
		return EngineType.CTA_ENGINE