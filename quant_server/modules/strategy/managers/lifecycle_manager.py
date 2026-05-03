# -*- coding: utf-8 -*-
"""
策略生命周期管理器
负责策略的完整生命周期管理
"""
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, Callable

from modules.strategy.models import StrategyState

logger = logging.getLogger(__name__)


class LifecycleState(str, Enum):
	"""生命周期状态"""
	CREATED = "created"
	INITIALIZED = "initialized"
	READY = "ready"
	RUNNING = "running"
	PAUSED = "paused"
	STOPPING = "stopping"
	STOPPED = "stopped"
	ERROR = "error"


class LifecycleEvent:
	"""生命周期事件"""

	def __init__ (self, event_type: str, strategy_id: str, data: Any = None):
		self.event_type = event_type
		self.strategy_id = strategy_id
		self.data = data or {}
		self.timestamp = datetime.now()


class LifecycleManager:
	"""
	策略生命周期管理器

	负责：
	- 策略状态转换管理
	- 生命周期事件处理
	- 启动/停止/暂停/恢复流程
	- 异常处理和恢复
	"""

	def __init__ (self, event_engine=None):
		"""
		初始化生命周期管理器

		Args:
			event_engine: 事件引擎
		"""
		self.event_engine = event_engine

		# 策略生命周期状态 {strategy_id: state}
		self._states: Dict[str, LifecycleState] = {}

		# 策略回调 {strategy_id: {event: callback}}
		self._callbacks: Dict[str, Dict[str, List[Callable]]] = {}

		# 策略状态 {strategy_id: StrategyState}
		self._strategy_states: Dict[str, StrategyState] = {}

	async def register_strategy (
			self,
			strategy_id: str,
			on_state_change: Optional[Callable] = None,
	) -> None:
		"""
		注册策略

		Args:
			strategy_id: 策略ID
			on_state_change: 状态变化回调
		"""
		self._states[strategy_id] = LifecycleState.CREATED
		self._callbacks[strategy_id] = {
			"on_created": [],
			"on_initialized": [],
			"on_ready": [],
			"on_running": [],
			"on_paused": [],
			"on_stopped": [],
			"on_error": [],
		}

		if on_state_change:
			self._callbacks[strategy_id]["on_state_change"].append(on_state_change)

		logger.info(f"策略注册到生命周期管理器: {strategy_id}")

	async def unregister_strategy (self, strategy_id: str) -> None:
		"""
		注销策略

		Args:
			strategy_id: 策略ID
		"""
		if strategy_id in self._states:
			del self._states[strategy_id]
		if strategy_id in self._callbacks:
			del self._callbacks[strategy_id]
		if strategy_id in self._strategy_states:
			del self._strategy_states[strategy_id]

		logger.info(f"策略从生命周期管理器注销: {strategy_id}")

	async def initialize (self, strategy_id: str) -> bool:
		"""
		初始化策略

		Args:
			strategy_id: 策略ID

		Returns:
			是否成功
		"""
		if strategy_id not in self._states:
			logger.error(f"策略未注册: {strategy_id}")
			return False

		try:
			# 触发初始化事件
			await self._trigger_event(strategy_id, "on_initialized")

			# 更新状态
			self._states[strategy_id] = LifecycleState.INITIALIZED

			logger.info(f"策略初始化完成: {strategy_id}")
			return True

		except Exception as e:
			logger.error(f"策略初始化失败: {e}")
			await self._handle_error(strategy_id, e)
			return False

	async def start (self, strategy_id: str) -> bool:
		"""
		启动策略

		Args:
			strategy_id: 策略ID

		Returns:
			是否成功
		"""
		if strategy_id not in self._states:
			logger.error(f"策略未注册: {strategy_id}")
			return False

		current_state = self._states[strategy_id]

		# 检查是否可以启动
		if current_state not in [
			LifecycleState.INITIALIZED,
			LifecycleState.READY,
			LifecycleState.PAUSED,
			LifecycleState.STOPPED,
		]:
			logger.warning(f"策略当前状态不允许启动: {current_state}")
			return False

		try:
			# 触发启动前回调
			await self._trigger_event(strategy_id, "on_starting")

			# 更新状态
			self._states[strategy_id] = LifecycleState.RUNNING

			# 触发启动事件
			await self._trigger_event(strategy_id, "on_running")

			logger.info(f"策略启动成功: {strategy_id}")
			return True

		except Exception as e:
			logger.error(f"策略启动失败: {e}")
			await self._handle_error(strategy_id, e)
			return False

	async def stop (self, strategy_id: str, force: bool = False) -> bool:  # force参数未使用
		"""
		停止策略

		Args:
			strategy_id: 策略ID
			force: 是否强制停止

		Returns:
			是否成功
		"""
		if strategy_id not in self._states:
			logger.error(f"策略未注册: {strategy_id}")
			return False

		current_state = self._states[strategy_id]

		if current_state not in [
			LifecycleState.RUNNING,
			LifecycleState.PAUSED,
		]:
			logger.warning(f"策略当前状态不允许停止: {current_state}")
			return False

		try:
			# 更新状态为停止中
			self._states[strategy_id] = LifecycleState.STOPPING

			# 触发停止前回调
			await self._trigger_event(strategy_id, "on_stopping")

			# 执行清理
			# await self._cleanup(strategy_id)

			# 更新状态为已停止
			self._states[strategy_id] = LifecycleState.STOPPED

			# 触发停止事件
			await self._trigger_event(strategy_id, "on_stopped")

			logger.info(f"策略停止成功: {strategy_id}")
			return True

		except Exception as e:
			logger.error(f"策略停止失败: {e}")
			await self._handle_error(strategy_id, e)
			return False

	async def pause (self, strategy_id: str) -> bool:
		"""
		暂停策略

		Args:
			strategy_id: 策略ID

		Returns:
			是否成功
		"""
		if strategy_id not in self._states:
			logger.error(f"策略未注册: {strategy_id}")
			return False

		current_state = self._states[strategy_id]

		if current_state != LifecycleState.RUNNING:
			logger.warning(f"策略当前状态不允许暂停: {current_state}")
			return False

		try:
			# 触发暂停前回调
			await self._trigger_event(strategy_id, "on_pausing")

			# 更新状态
			self._states[strategy_id] = LifecycleState.PAUSED

			# 触发暂停事件
			await self._trigger_event(strategy_id, "on_paused")

			logger.info(f"策略暂停成功: {strategy_id}")
			return True

		except Exception as e:
			logger.error(f"策略暂停失败: {e}")
			await self._handle_error(strategy_id, e)
			return False

	async def resume (self, strategy_id: str) -> bool:
		"""
		恢复策略

		Args:
			strategy_id: 策略ID

		Returns:
			是否成功
		"""
		if strategy_id not in self._states:
			logger.error(f"策略未注册: {strategy_id}")
			return False

		current_state = self._states[strategy_id]

		if current_state != LifecycleState.PAUSED:
			logger.warning(f"策略当前状态不允许恢复: {current_state}")
			return False

		try:
			# 触发恢复前回调
			await self._trigger_event(strategy_id, "on_resuming")

			# 更新状态
			self._states[strategy_id] = LifecycleState.RUNNING

			# 触发恢复事件
			await self._trigger_event(strategy_id, "on_running")

			logger.info(f"策略恢复成功: {strategy_id}")
			return True

		except Exception as e:
			logger.error(f"策略恢复失败: {e}")
			await self._handle_error(strategy_id, e)
			return False

	def get_state (self, strategy_id: str) -> Optional[LifecycleState]:
		"""
		获取策略生命周期状态

		Args:
			strategy_id: 策略ID

		Returns:
			生命周期状态
		"""
		return self._states.get(strategy_id)

	def is_running (self, strategy_id: str) -> bool:
		"""策略是否在运行"""
		return self._states.get(strategy_id) == LifecycleState.RUNNING

	def is_paused (self, strategy_id: str) -> bool:
		"""策略是否暂停"""
		return self._states.get(strategy_id) == LifecycleState.PAUSED

	def register_callback (
			self,
			strategy_id: str,
			event: str,
			callback: Callable,
	) -> None:
		"""
		注册回调

		Args:
			strategy_id: 策略ID
			event: 事件名称
			callback: 回调函数
		"""
		if strategy_id not in self._callbacks:
			self._callbacks[strategy_id] = {
				"on_created": [],
				"on_initialized": [],
				"on_ready": [],
				"on_running": [],
				"on_paused": [],
				"on_stopped": [],
				"on_error": [],
			}

		if event in self._callbacks[strategy_id]:
			self._callbacks[strategy_id][event].append(callback)

	async def _trigger_event (
			self,
			strategy_id: str,
			event: str,
	) -> None:
		"""
		触发事件

		Args:
			strategy_id: 策略ID
			event: 事件名称
		"""
		callbacks = self._callbacks.get(strategy_id, {}).get(event, [])

		for callback in callbacks:
			try:
				if asyncio.iscoroutinefunction(callback):
					await callback(strategy_id, event)
				else:
					callback(strategy_id, event)
			except Exception as e:
				logger.error(f"执行回调失败: {e}")

	async def _handle_error (
			self,
			strategy_id: str,
			error: Exception,
	) -> None:
		"""
		处理错误

		Args:
			strategy_id: 策略ID
			error: 异常
		"""
		self._states[strategy_id] = LifecycleState.ERROR

		# 触发错误事件
		await self._trigger_event(strategy_id, "on_error")

		# 发布错误事件到事件引擎
		if self.event_engine:
			from modules.strategy.events.management_events import StrategyErrorEvent
			event = StrategyErrorEvent(
				strategy_id=strategy_id,
				strategy_name="",
				user_id="0",
				error_code=500,
				error_message=str(error),
			)
			await self.event_engine.put(event)


# 解决循环导入
import asyncio