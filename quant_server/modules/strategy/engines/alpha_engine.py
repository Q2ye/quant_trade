# -*- coding: utf-8 -*-
"""
Alpha策略引擎
处理Alpha/多因子量化策略的执行
"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from core import BusinessException
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
			factor_values = await self._calculate_factors(strategy_id, date)

			# 更新缓存
			self._factor_cache[strategy_id] = factor_values

			# 生成信号
			signals = await self._generate_signals(factor_values, stock_pool, strategy_id)

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

	async def _calculate_factors (self, strategy_id: str, date: datetime) -> Dict[str, Any]:
		"""
		计算因子值

		对股票池中每只股票计算动量因子和量比因子（基于历史价格数据），
		PE/PB 因子需接入基本面数据源方可启用。

		Args:
			strategy_id: 策略ID
			date: 计算日期

		Returns:
			因子值 {pe: {ts_code: value}, pb: {...}, momentum: {...}, volume_ratio: {...}}
		"""
		stock_pool = self._stock_pools.get(strategy_id, [])
		context = self._contexts.get(strategy_id)

		# 优先使用外部因子计算器
		if self._factor_calculator:
			try:
				result = await self._factor_calculator.calculate(strategy_id, stock_pool, date)
				if result:
					return result
			except Exception as e:
				logger.warning(f"外部因子计算器失败，回退到内置因子: {e}")

		factors = {
			"pe": {},
			"pb": {},
			"momentum": {},
			"volume_ratio": {},
		}

		for ts_code in stock_pool:
			# 动量因子：基于 20 日价格变化率
			if context:
				prices = context.get_price_history(ts_code, 20)
				if len(prices) >= 5:
					avg_price = sum(prices) / len(prices)
					latest = prices[-1]
					factors["momentum"][ts_code] = (
						round((latest - avg_price) / avg_price, 4) if avg_price > 0 else 0.0
					)
				else:
					factors["momentum"][ts_code] = 0.0

				# 量比因子：近 5 日均量 / 总均量
				try:
					cached = context.get_cached_data(f"{ts_code}_market_data")
					if cached is not None and hasattr(cached, 'columns') and 'volume' in cached.columns:
						recent_vol = cached['volume'].tail(5).mean()
						all_vol = cached['volume'].mean()
						factors["volume_ratio"][ts_code] = (
							round(float(recent_vol / all_vol), 4) if all_vol > 0 else 1.0
						)
					else:
						factors["volume_ratio"][ts_code] = 1.0
				except BusinessException:
					factors["volume_ratio"][ts_code] = 1.0
			else:
				factors["momentum"][ts_code] = 0.0
				factors["volume_ratio"][ts_code] = 1.0

			# PE/PB 因子：需接入基本面数据源
			factors["pe"][ts_code] = None
			factors["pb"][ts_code] = None

		return factors

	async def _generate_signals (
			self,
			factor_values: Dict[str, Any],
			stock_pool: List[str],
			strategy_id: str,
	) -> List[TradingSignal]:
		"""
		根据因子值生成交易信号

		多因子综合打分模型：
		- 动量因子权重 0.4（正向动量 = 做多）
		- 量比因子权重 0.2（高换手 = 流动性好）
		- PE/PB 因子各权重 0.2（低估值 = 做多，需基本面数据）
		综合得分绝对值 ≥ 0.2 时触发信号。

		Args:
			factor_values: 因子值字典
			stock_pool: 股票池
			strategy_id: 策略ID

		Returns:
			交易信号列表
		"""
		if not stock_pool or not factor_values:
			return []

		context = self._contexts.get(strategy_id)
		strategy = self._strategies.get(strategy_id)
		strategy_name = strategy.name if strategy else "Unknown"

		# 多因子综合打分
		scores: Dict[str, float] = {}
		for ts_code in stock_pool:
			score = 0.0
			weight_sum = 0.0

			# 动量因子 (权重 0.4)：正向动量加分，负向减分
			mom = factor_values.get("momentum", {}).get(ts_code, 0.0) or 0.0
			score += 0.4 * (1.0 if mom > 0 else (-1.0 if mom < 0 else 0.0))
			weight_sum += 0.4

			# 量比因子 (权重 0.2)：量比偏离 1.0 表示活跃度异常
			vol = factor_values.get("volume_ratio", {}).get(ts_code, 1.0) or 1.0
			vol_signal = (vol - 1.0) * 2  # 归一化到 [-1, ~2]
			score += 0.2 * max(min(vol_signal, 1.0), -1.0)
			weight_sum += 0.2

			# PE 因子 (权重 0.2)：低 PE 加分
			pe = factor_values.get("pe", {}).get(ts_code)
			if pe is not None and pe > 0:
				score += 0.2 * 0.5  # 有 PE 数据时给予中性偏正评分
				weight_sum += 0.2

			# PB 因子 (权重 0.2)：低 PB 加分
			pb = factor_values.get("pb", {}).get(ts_code)
			if pb is not None and pb > 0:
				score += 0.2 * 0.5
				weight_sum += 0.2

			scores[ts_code] = score / weight_sum if weight_sum > 0 else 0.0

		# 按得分排序，生成信号
		signals = []
		timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')

		for ts_code, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
			if abs(score) < 0.2:
				continue

			price = context.get_realtime_price(ts_code) if context else 0.0
			if not price or price <= 0:
				continue

			quantity = max(int(100000 / price / 100) * 100, 100)

			signals.append(TradingSignal(
				id=f"alpha_{timestamp}_{ts_code}",
				strategy_id=strategy_id,
				strategy_name=strategy_name,
				ts_code=ts_code,
				signal_type=SignalType.ENTRY if score > 0 else SignalType.EXIT,
				direction=SignalDirection.LONG if score > 0 else SignalDirection.CLOSE_LONG,
				price=price,
				quantity=quantity,
				amount=price * quantity,
				confidence=round(min(abs(score), 1.0), 4),
				reason=f"Alpha多因子综合得分: {score:.3f}",
			))

		return signals

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