# -*- coding: utf-8 -*-
"""
策略管理器
负责策略的加载、初始化、运行控制
"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Type

from core.engines.base.engine_base import EngineBase, EngineConfigEntity
from core.engines.types.enums import EngineType
from modules.strategy.constants import (
	StrategyType,
	StrategyLifecycleStatus,
)
from modules.strategy.models import (
	StrategyInstance,
	StrategyState,
	StrategyConfig,
	TradingSignal,
)
from modules.strategy.strategies.base.base_strategy import BaseStrategy
from modules.strategy.strategies.base.strategy_context import StrategyContext

logger = logging.getLogger(__name__)


class StrategyManager(EngineBase):
	"""
	策略管理器

	负责：
	- 策略的加载和初始化
	- 策略实例的创建和管理
	- 策略运行控制（启动、停止、暂停、恢复）
	- 策略信号处理
	- 持仓管理

	属性:
		strategies: 加载的策略实例
		running_strategies: 运行中的策略
	"""

	def __init__ (self, event_engine=None):
		"""
		初始化策略管理器

		Args:
			event_engine: 事件引擎
		"""
		# 创建配置实体
		config = EngineConfigEntity(
			name="StrategyManager",
			engine_type=EngineType.STRATEGY_MANAGER.value
		)
		super().__init__(config=config, event_engine=event_engine)
		self.event_engine = event_engine

		# 策略实例 {strategy_id: StrategyInstance}
		self.strategies: Dict[str, StrategyInstance] = {}

		# 运行状态 {strategy_id: StrategyState}
		self.running_states: Dict[str, StrategyState] = {}

		# 策略类注册表 {strategy_type: StrategyClass}
		self._strategy_registry: Dict[StrategyType, Type[BaseStrategy]] = {}

		# 策略对象 {strategy_id: BaseStrategy}
		self._strategy_objects: Dict[str, BaseStrategy] = {}

		# 注册默认策略
		self._register_default_strategies()

	def _register_default_strategies (self) -> None:
		"""注册默认策略"""
		# 延迟导入，避免循环依赖
		try:
			from modules.strategy.strategies.technical.ma_cross_strategy import (
				MACrossStrategy,
			)
			from modules.strategy.strategies.technical.macd_strategy import (
				MACDStrategy,
			)

			self.register_strategy(StrategyType.CTA, MACrossStrategy)
			self.register_strategy(StrategyType.TECHNICAL, MACrossStrategy)
			self.register_strategy(StrategyType.TECHNICAL, MACDStrategy)
		except ImportError as e:
			logger.warning(f"无法注册默认策略: {e}")

	def register_strategy (
			self,
			strategy_type: StrategyType,
			strategy_class: Type[BaseStrategy]
	) -> None:
		"""
		注册策略类

		Args:
			strategy_type: 策略类型
			strategy_class: 策略类
		"""
		self._strategy_registry[strategy_type] = strategy_class
		logger.info(f"注册策略类: {strategy_type.value} -> {strategy_class.__name__}")

	async def load_strategy (
			self,
			strategy_id: str,
			name: str,
			strategy_type: StrategyType,
			code: str,
			parameters: Dict[str, Any],
			config: StrategyConfig,
	) -> StrategyInstance:
		"""
		加载策略

		Args:
			strategy_id: 策略ID
			name: 策略名称
			strategy_type: 策略类型
			code: 策略代码
			parameters: 策略参数
			config: 策略配置

		Returns:
			策略实例
		"""
		# 获取策略类
		strategy_class = self._strategy_registry.get(strategy_type)
		if not strategy_class:
			raise ValueError(f"未注册的策略类型: {strategy_type}")

		# 创建策略实例
		strategy = strategy_class(
			name=name,
			strategy_type=strategy_type,
			parameters=parameters,
		)

		# 创建策略实例对象
		instance = StrategyInstance(
			id=strategy_id,
			name=name,
			strategy_type=strategy_type,
			status=StrategyLifecycleStatus.DRAFT,
			user_id=config.user_id if hasattr(config, 'user_id') else 0,
			code=code,
			parameters=parameters,
			capital=config.initial_capital,
		)

		# 保存策略实例和策略对象
		self.strategies[strategy_id] = instance
		self._strategy_objects[strategy_id] = strategy

		logger.info(f"策略加载成功: {strategy_id}, {name}")

		return instance

	async def initialize_strategy (
			self,
			strategy_id: str,
			context: StrategyContext,
	) -> None:
		"""
		初始化策略

		Args:
			strategy_id: 策略ID
			context: 策略上下文
		"""
		if strategy_id not in self.strategies:
			raise ValueError(f"策略 {strategy_id} 未加载")

		strategy_instance = self.strategies[strategy_id]

		# 获取策略类并初始化
		strategy_type = strategy_instance.strategy_type
		strategy_class = self._strategy_registry.get(strategy_type)
		if not strategy_class:
			raise ValueError(f"未注册的策略类型: {strategy_type}")

		# 创建策略对象
		strategy = strategy_class(
			name=strategy_instance.name,
			strategy_type=strategy_type,
			parameters=strategy_instance.parameters,
		)

		# 注入上下文
		strategy.context = context
		strategy.initialize()

		# 更新实例状态
		strategy_instance.status = StrategyLifecycleStatus.COMPILED

		logger.info(f"策略初始化成功: {strategy_id}")

	async def start_strategy (
			self,
			strategy_id: str,
			context: StrategyContext,
	) -> None:
		"""
		启动策略

		Args:
			strategy_id: 策略ID
			context: 策略上下文
		"""
		if strategy_id not in self.strategies:
			raise ValueError(f"策略 {strategy_id} 未加载")

		strategy_instance = self.strategies[strategy_id]

		# 检查是否可以启动
		if not strategy_instance.can_start():
			raise ValueError(f"策略 {strategy_id} 当前状态无法启动")

		# 初始化策略
		await self.initialize_strategy(strategy_id, context)

		# 启动策略
		if hasattr(self, '_strategy_objects'):
			strategy = self._strategy_objects.get(strategy_id)
			if strategy:
				strategy.start()

		# 创建运行状态
		state = StrategyState(
			strategy_id=str(strategy_id),
			is_running=True,
			available_capital=context.available_capital,
			total_assets=context.total_assets,
		)
		self.running_states[str(strategy_id)] = state

		# 更新实例状态
		strategy_instance.status = StrategyLifecycleStatus.RUNNING
		strategy_instance.started_at = datetime.now()

		logger.info(f"策略启动成功: {strategy_id}")

	async def stop_strategy (
			self,
			strategy_id: str,
	) -> None:
		"""
		停止策略

		Args:
			strategy_id: 策略ID
		"""
		if strategy_id not in self.strategies:
			raise ValueError(f"策略 {strategy_id} 未加载")

		strategy_instance = self.strategies[strategy_id]

		# 停止策略
		if hasattr(self, '_strategy_objects'):
			strategy = self._strategy_objects.get(strategy_id)
			if strategy:
				strategy.stop()

		# 移除运行状态
		if str(strategy_id) in self.running_states:
			del self.running_states[str(strategy_id)]

		# 更新实例状态
		strategy_instance.status = StrategyLifecycleStatus.STOPPED
		strategy_instance.stopped_at = datetime.now()

		logger.info(f"策略停止成功: {strategy_id}")

	async def pause_strategy (
			self,
			strategy_id: str,
	) -> None:
		"""
		暂停策略

		Args:
			strategy_id: 策略ID
		"""
		if strategy_id not in self.strategies:
			raise ValueError(f"策略 {strategy_id} 未加载")

		if str(strategy_id) not in self.running_states:
			raise ValueError(f"策略 {strategy_id} 未在运行")

		# 更新运行状态
		self.running_states[str(strategy_id)].is_running = False

		# 更新实例状态
		self.strategies[strategy_id].status = StrategyLifecycleStatus.PAUSED

		logger.info(f"策略暂停成功: {strategy_id}")

	async def resume_strategy (
			self,
			strategy_id: str,
	) -> None:
		"""
		恢复策略

		Args:
			strategy_id: 策略ID
		"""
		if strategy_id not in self.strategies:
			raise ValueError(f"策略 {strategy_id} 未加载")

		if str(strategy_id) not in self.running_states:
			raise ValueError(f"策略 {strategy_id} 不在暂停状态")

		# 更新运行状态
		self.running_states[str(strategy_id)].is_running = True

		# 更新实例状态
		self.strategies[strategy_id].status = StrategyLifecycleStatus.RUNNING

		logger.info(f"策略恢复成功: {strategy_id}")

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
		if str(strategy_id) not in self.running_states:
			return []

		state = self.running_states[str(strategy_id)]
		if not state.is_running:
			return []

		# 获取策略对象
		if hasattr(self, '_strategy_objects'):
			strategy = self._strategy_objects.get(strategy_id)
			if strategy and hasattr(strategy, 'on_bar'):
				signals = strategy.on_bar(bar_data)

				# 保存信号
				state.pending_signals.extend(signals)

				return signals

		return []

	def get_strategy_state (
			self,
			strategy_id: str,
	) -> Optional[StrategyState]:
		"""
		获取策略状态

		Args:
			strategy_id: 策略ID

		Returns:
			策略状态
		"""
		return self.running_states.get(str(strategy_id))

	def get_all_running_strategies (self) -> List[StrategyState]:
		"""
		获取所有运行中的策略

		Returns:
			运行中的策略列表
		"""
		return list(self.running_states.values())

	def is_strategy_running (self, strategy_id: str) -> bool:
		"""
		策略是否在运行

		Args:
			strategy_id: 策略ID

		Returns:
			是否在运行
		"""
		state = self.running_states.get(str(strategy_id))
		return state is not None and state.is_running

	# ==================== 抽象方法实现 ====================

	async def _on_initialize (self):
		"""引擎初始化时的具体逻辑"""
		logger.info("策略管理器初始化")
		# 初始化策略注册表
		self._register_default_strategies()
		logger.info("策略管理器初始化完成")

	async def _on_start (self):
		"""引擎启动时的具体逻辑 — 订阅数据事件，驱动策略执行"""
		logger.info("策略管理器启动")
		if self.event_engine:
			from modules.data.events.sync_events import DataSyncCompletedEvent
			from modules.trade.events.order_events import OrderFilledEvent

			self.event_engine.subscribe(DataSyncCompletedEvent, self._on_data_sync_completed)
			self.event_engine.subscribe(OrderFilledEvent, self._on_order_filled)
			logger.info("策略管理器已订阅 DataSyncCompletedEvent / OrderFilledEvent")
		logger.info("策略管理器启动完成")

	async def _on_data_sync_completed(self, event) -> None:
		"""数据同步完成 → 遍历运行中策略，调用 on_bar 驱动信号生成"""
		sync_type = event.data.get("sync_type", "")
		logger.info(f"数据同步完成: {sync_type}，驱动运行中策略...")
		for strategy_id, state in self.running_states.items():
			if state.is_running:
				# 将数据事件路由到策略的 on_bar 方法
				await self.process_bar(strategy_id, event.data)

	async def _on_order_filled(self, event) -> None:
		"""订单成交 → 更新策略持仓状态"""
		logger.info(f"订单成交: {event.data.get('order_id')}，更新策略持仓")
		for strategy_id, state in self.running_states.items():
			if state.is_running:
				symbol = event.data.get("symbol")
				if symbol and symbol in state.positions:
					state.positions[symbol] += event.data.get("filled_volume", 0)

	async def _on_stop (self):
		"""引擎停止时的具体逻辑"""
		logger.info("策略管理器停止")
		# 停止所有运行中的策略
		for strategy_id_str in list(self.running_states.keys()):
			try:
				await self.stop_strategy(strategy_id_str)
			except Exception as e:
				logger.error(f"停止策略 {strategy_id_str} 失败: {e}")
		logger.info("策略管理器停止完成")