# -*- coding: utf-8 -*-
"""
Alpha策略引擎
处理Alpha/多因子量化策略的执行
"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from core.engines.base.engine_base import EngineBase
from core.engines.types.entities import EngineConfigEntity
from core.engines.types.enums import EngineType
from modules.strategy.constants import SignalType, SignalDirection
from modules.strategy.models import TradingSignal
from modules.strategy.strategies.base.base_strategy import BaseStrategy
from modules.strategy.strategies.base.strategy_context import StrategyContext

logger = logging.getLogger(__name__)


class AlphaEngine(EngineBase):
	"""
	Alpha策略引擎

	负责：
	- 多因子策略的加载和执行
	- 因子的计算和更新
	- 股票池管理和筛选
	- 组合权重优化

	Alpha策略特点：
	- 多因子选股
	- 组合权重优化
	- 行业/市值中性
	- 风险预算管理
	"""

	def __init__ (self, config=None, event_engine=None, resource_pool=None):
		"""
		初始化Alpha引擎

		Args:
			config: 引擎配置
			event_engine: 事件引擎
			resource_pool: 资源池
		"""
		if config is None:
			config = EngineConfigEntity(name="AlphaEngine", engine_type="alpha_engine")
		super().__init__(config, event_engine, resource_pool)

		# 策略实例
		self._strategies: Dict[str, BaseStrategy] = {}

		# 策略上下文
		self._contexts: Dict[str, StrategyContext] = {}

		# 因子缓存 {strategy_id: {factor_name: values}}
		self._factor_cache: Dict[str, Dict[str, Any]] = {}

		# 股票池 {strategy_id: [ts_codes]}
		self._stock_pools: Dict[str, List[str]] = {}

		# 因子计算器（可配置）
		self._factor_calculator = None

	@property
	def engine_type (self) -> EngineType:
		"""获取引擎类型"""
		return EngineType.ALPHA_ENGINE

	async def _on_initialize (self) -> None:
		"""引擎初始化"""
		logger.info("Alpha引擎初始化")

	async def _on_start (self) -> None:
		"""引擎启动"""
		logger.info("Alpha引擎启动")

	async def _on_stop (self) -> None:
		"""引擎停止"""
		for strategy_id, strategy in self._strategies.items():
			try:
				strategy.stop()
			except Exception as e:
				logger.error(f"停止策略 {strategy_id} 失败: {e}")

		logger.info("Alpha引擎停止")

	async def _on_force_stop (self) -> None:
		"""强制停止引擎"""
		for strategy_id, strategy in self._strategies.items():
			try:
				strategy.stop()
			except Exception as e:
				logger.error(f"强制停止策略 {strategy_id} 失败: {e}")

	async def load_strategy (
			self,
			strategy_id: str,
			strategy: BaseStrategy,
			context: StrategyContext,
			stock_pool: Optional[List[str]] = None,
	) -> None:
		"""
		加载策略

		Args:
			strategy_id: 策略ID
			strategy: 策略实例
			context: 策略上下文
			stock_pool: 股票池
		"""
		self._strategies[strategy_id] = strategy
		self._contexts[strategy_id] = context
		self._stock_pools[strategy_id] = stock_pool or []
		self._factor_cache[strategy_id] = {}

		# 初始化策略
		strategy.context = context
		strategy.initialize()

		logger.info(f"Alpha策略加载成功: {strategy_id}, 股票池: {len(stock_pool)} 只")

	async def unload_strategy (self, strategy_id: str) -> None:
		"""卸载策略"""
		if strategy_id in self._strategies:
			strategy = self._strategies[strategy_id]
			strategy.stop()

			del self._strategies[strategy_id]
			del self._contexts[strategy_id]
			if strategy_id in self._stock_pools:
				del self._stock_pools[strategy_id]
			if strategy_id in self._factor_cache:
				del self._factor_cache[strategy_id]

			logger.info(f"Alpha策略卸载成功: {strategy_id}")

	async def process_bar (
			self,
			strategy_id: str,
			bar_data: Any,
	) -> List[TradingSignal]:
		"""
		处理K线数据（用于日内策略）

		Args:
			strategy_id: 策略ID
			bar_data: K线数据

		Returns:
			信号列表
		"""
		if strategy_id not in self._strategies:
			return []

		strategy = self._strategies[strategy_id]
		context = self._contexts.get(strategy_id)

		if not context or not context.is_running:
			return []

		try:
			signals = strategy.on_bar(bar_data)
			if signals:
				await self._process_signals(strategy_id, signals)
			return signals
		except Exception as e:
			logger.error(f"处理K线数据失败: {e}")
			return []

	async def run_factor_analysis (
			self,
			strategy_id: str,
			date: datetime,
	) -> Dict[str, Any]:
		"""
		运行因子分析（日频）

		Args:
			strategy_id: 策略ID
			date: 日期

		Returns:
			因子分析结果
		"""
		if strategy_id not in self._strategies:
			return {}

		try:
			# 获取股票池
			stock_pool = self._stock_pools.get(strategy_id, [])

			# 计算因子值
			factor_values = await self._calculate_factors()

			# 更新缓存
			self._factor_cache[strategy_id] = factor_values

			# 生成信号
			signals = await self._generate_signals()

			# 处理信号
			if signals:
				await self._process_signals(strategy_id, signals)

			return {
				"date": date,
				"stock_count": len(stock_pool),
				"signals_count": len(signals),
				"factor_count": len(factor_values),
			}

		except Exception as e:
			logger.error(f"运行因子分析失败: {e}")
			return {}

	async def rebalance (
			self,
			strategy_id: str,
			target_weights: Dict[str, float],
	) -> List[TradingSignal]:
		"""
		调仓

		Args:
			strategy_id: 策略ID
			target_weights: 目标权重 {ts_code: weight}

		Returns:
			交易信号列表
		"""
		if strategy_id not in self._strategies:
			return []

		context = self._contexts.get(strategy_id)
		if not context:
			return []

		signals = []

		try:
			# 获取当前持仓
			current_positions = context.get_all_positions()
			current_weights = {
				pos.ts_code: pos.market_value / context.total_assets
				for pos in current_positions
			}

			# 计算需要调整的仓位
			for ts_code, target_weight in target_weights.items():
				current_weight = current_weights.get(ts_code, 0)
				weight_diff = target_weight - current_weight

				# 如果权重变化超过阈值，产生信号
				if abs(weight_diff) > 0.01:  # 1%阈值
					amount = context.total_assets * abs(weight_diff)
					price = context.get_realtime_price(ts_code)

					if price and amount > 100:  # 最小交易金额
						quantity = int(amount / price / 100) * 100

						if weight_diff > 0:
							signal = TradingSignal(
								id=f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
								strategy_id=strategy_id,
								strategy_name=self._strategies[strategy_id].name,
								ts_code=ts_code,
								signal_type=SignalType.REBALANCE,
								direction=SignalDirection.LONG,
								price=price,
								quantity=quantity,
								reason=f"调仓: {current_weight:.2%} -> {target_weight:.2%}",
							)
						else:
							signal = TradingSignal(
								id=f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
								strategy_id=strategy_id,
								strategy_name=self._strategies[strategy_id].name,
								ts_code=ts_code,
								signal_type=SignalType.REBALANCE,
								direction=SignalDirection.CLOSE_LONG,
								price=price,
								quantity=quantity,
								reason=f"调仓: {current_weight:.2%} -> {target_weight:.2%}",
							)
						signals.append(signal)

			# 处理信号
			if signals:
				await self._process_signals(strategy_id, signals)

			return signals

		except Exception as e:
			logger.error(f"调仓失败: {e}")
			return []

	@staticmethod
	async def _calculate_factors () -> Dict[str, Any]:
		"""
		计算因子值

		Returns:
			因子值
		"""
		# 简化实现，实际需要接入因子计算服务
		return {
			"pe": {},  # 市盈率因子
			"pb": {},  # 市净率因子
			"momentum": {},  # 动量因子
			"volume_ratio": {},  # 量比因子
		}

	@staticmethod
	async def _generate_signals () -> List[TradingSignal]:
		"""
		根据因子值生成信号

		Returns:
			信号列表
		"""
		# 简化实现
		return []

	async def _process_signals (
			self,
			strategy_id: str,
			signals: List[TradingSignal],
	) -> None:
		"""处理信号"""
		for signal in signals:
			try:
				if self.event_engine:
					from modules.strategy.events.signal_events import (
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

	def get_factor_cache (self, strategy_id: str) -> Dict[str, Any]:
		"""获取因子缓存"""
		return self._factor_cache.get(strategy_id, {})

	def get_stock_pool (self, strategy_id: str) -> List[str]:
		"""获取股票池"""
		return self._stock_pools.get(strategy_id, [])