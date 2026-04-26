"""
状态机模式实现

允许一个对象在其内部状态改变时改变它的行为。
状态机模式将状态逻辑分散到不同的状态类中，避免了大量的条件判断语句。

在量化交易系统中的典型应用：
1. 订单状态机（待提交、已提交、部分成交、完全成交、已撤销等）
2. 策略状态机（初始化、运行中、暂停、停止）
3. 系统状态机（启动中、运行中、停止中、已停止）
4. 连接状态机（连接中、已连接、断开中、已断开）
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable


class State:
	"""
	状态基类

	定义状态的行为和转换。
	"""

	def __init__ (self, name: str, description: str = ""):
		"""
		初始化状态

		Args:
			name: 状态名称
			description: 状态描述
		"""
		self.name = name
		self.description = description
		self.transitions: Dict[str, 'Transition'] = {}
		self.entry_actions: List[Callable] = []
		self.exit_actions: List[Callable] = []

	def add_transition (self, event: str, target_state: 'State',
	                    condition: Optional[Callable] = None) -> 'Transition':
		"""
		添加状态转换

		Args:
			event: 触发事件
			target_state: 目标状态
			condition: 转换条件函数（可选）

		Returns:
			Transition: 创建的转换对象
		"""
		transition = Transition(self, event, target_state, condition)
		self.transitions[event] = transition
		return transition

	def add_entry_action (self, action: Callable) -> None:
		"""添加入口动作"""
		self.entry_actions.append(action)

	def add_exit_action (self, action: Callable) -> None:
		"""添加出口动作"""
		self.exit_actions.append(action)

	async def enter (self, context: Dict[str, Any]) -> None:
		"""进入状态时执行的动作"""
		for action in self.entry_actions:
			if asyncio.iscoroutinefunction(action):
				await action(context)
			else:
				action(context)

	async def exit (self, context: Dict[str, Any]) -> None:
		"""离开状态时执行的动作"""
		for action in self.exit_actions:
			if asyncio.iscoroutinefunction(action):
				await action(context)
			else:
				action(context)

	def get_available_events (self) -> List[str]:
		"""获取可触发的事件列表"""
		return list(self.transitions.keys())

	def can_transition (self, event: str, context: Dict[str, Any]) -> bool:
		"""检查是否可以转换到目标状态"""
		if event not in self.transitions:
			return False

		transition = self.transitions[event]
		return transition.can_transition(context)

	def __str__ (self) -> str:
		return self.name

	def __repr__ (self) -> str:
		return f"State(name='{self.name}', transitions={list(self.transitions.keys())})"


@dataclass
class Transition:
	"""
	状态转换

	定义从一个状态到另一个状态的转换。
	"""

	source_state: State
	event: str
	target_state: State
	condition: Optional[Callable] = None
	actions: List[Callable] = field(default_factory=list)

	def can_transition (self, context: Dict[str, Any]) -> bool:
		"""检查是否满足转换条件"""
		if self.condition is None:
			return True

		try:
			if asyncio.iscoroutinefunction(self.condition):
				# 异步条件需要在调用时处理
				return True  # 实际检查在状态机中处理
			else:
				return self.condition(context)
		except Exception:
			return False

	def add_action (self, action: Callable) -> None:
		"""添加转换动作"""
		self.actions.append(action)

	async def execute_actions (self, context: Dict[str, Any]) -> None:
		"""执行转换动作"""
		for action in self.actions:
			if asyncio.iscoroutinefunction(action):
				await action(context)
			else:
				action(context)

	def __str__ (self) -> str:
		return f"{self.source_state.name} --[{self.event}]--> {self.target_state.name}"


class StateMachine:
	"""
	状态机

	管理状态的转换和状态的行为。
	"""

	def __init__ (self, initial_state: State, name: Optional[str] = None):
		"""
		初始化状态机

		Args:
			initial_state: 初始状态
			name: 状态机名称（可选）
		"""
		self.name = name or self.__class__.__name__
		self.current_state = initial_state
		self.states: Dict[str, State] = {initial_state.name: initial_state}
		self.history: List[Dict[str, Any]] = []
		self.context: Dict[str, Any] = {}
		self._lock = asyncio.Lock()

	def add_state (self, state: State) -> None:
		"""添加状态"""
		self.states[state.name] = state

	def get_state (self, state_name: str) -> Optional[State]:
		"""获取状态"""
		return self.states.get(state_name)

	async def transition (self, event: str, data: Optional[Dict[str, Any]] = None) -> bool:
		"""
		触发状态转换

		Args:
			event: 触发事件
			data: 事件数据

		Returns:
			bool: 转换是否成功
		"""
		async with self._lock:
			# 记录事件
			event_record = {
				"timestamp": asyncio.get_event_loop().time(),
				"event": event,
				"from_state": self.current_state.name,
				"events": data
			}

			# 检查当前状态是否可以转换
			if not self.current_state.can_transition(event, self.context):
				event_record["result"] = "rejected"
				event_record["reason"] = "transition_not_allowed"
				self.history.append(event_record)
				return False

			# 获取转换
			transition = self.current_state.transitions[event]

			# 检查条件
			if transition.condition:
				try:
					if asyncio.iscoroutinefunction(transition.condition):
						condition_result = await transition.condition(self.context)
					else:
						condition_result = transition.condition(self.context)

					if not condition_result:
						event_record["result"] = "rejected"
						event_record["reason"] = "condition_not_met"
						self.history.append(event_record)
						return False
				except Exception as e:
					event_record["result"] = "error"
					event_record["reason"] = f"condition_error: {str(e)}"
					self.history.append(event_record)
					return False

			# 执行离开当前状态的动作
			await self.current_state.exit(self.context)

			# 执行转换动作
			await transition.execute_actions(self.context)

			# 更新状态
			old_state = self.current_state
			self.current_state = transition.target_state

			# 执行进入新状态的动作
			await self.current_state.enter(self.context)

			# 记录成功转换
			event_record.update({
				"result": "success",
				"to_state": self.current_state.name,
				"transition": str(transition)
			})
			self.history.append(event_record)

			# 触发状态变化事件
			await self._on_state_changed(old_state, self.current_state, event, data)

			return True

	async def _on_state_changed (self, old_state: State, new_state: State,
	                             event: str, data: Optional[Dict[str, Any]]) -> None:
		"""状态变化回调（子类可以重写）"""
		pass

	def get_available_events (self) -> List[str]:
		"""获取当前状态可触发的事件"""
		return self.current_state.get_available_events()

	def get_state_history (self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
		"""获取状态历史"""
		if limit:
			return self.history[-limit:]
		return self.history

	def reset (self, state: Optional[State] = None) -> None:
		"""重置状态机"""
		if state:
			self.current_state = state
		else:
			# 重置到初始状态
			initial_state_name = list(self.states.keys())[0]
			self.current_state = self.states[initial_state_name]

		self.history.clear()
		self.context.clear()

	def __str__ (self) -> str:
		return f"StateMachine({self.name}, current={self.current_state.name})"


class AsyncStateMachine(StateMachine):
	"""
	异步状态机

	支持异步状态动作和条件的状态机。
	"""

	async def transition (self, event: str, data: Optional[Dict[str, Any]] = None) -> bool:
		"""异步状态转换"""
		# 使用父类的同步转换，但支持异步条件检查
		return await super().transition(event, data)


class StateMachineBuilder:
	"""
	状态机构建器

	简化状态机的创建过程。
	"""

	def __init__ (self, name: str = ""):
		self.name = name
		self.states: Dict[str, State] = {}
		self.initial_state: Optional[str] = None
		self.transitions: List[tuple] = []

	def add_state (self, name: str, description: str = "") -> 'StateMachineBuilder':
		"""添加状态"""
		self.states[name] = State(name, description)
		if self.initial_state is None:
			self.initial_state = name
		return self

	def set_initial_state (self, state_name: str) -> 'StateMachineBuilder':
		"""设置初始状态"""
		if state_name not in self.states:
			raise ValueError(f"状态未定义: {state_name}")
		self.initial_state = state_name
		return self

	def add_transition (self, from_state: str, event: str, to_state: str,
	                    condition: Optional[Callable] = None) -> 'StateMachineBuilder':
		"""添加转换"""
		self.transitions.append((from_state, event, to_state, condition))
		return self

	def add_entry_action (self, state_name: str, action: Callable) -> 'StateMachineBuilder':
		"""添加入口动作"""
		if state_name not in self.states:
			raise ValueError(f"状态未定义: {state_name}")
		self.states[state_name].add_entry_action(action)
		return self

	def add_exit_action (self, state_name: str, action: Callable) -> 'StateMachineBuilder':
		"""添加出口动作"""
		if state_name not in self.states:
			raise ValueError(f"状态未定义: {state_name}")
		self.states[state_name].add_exit_action(action)
		return self

	def add_transition_action (self, from_state: str, event: str, action: Callable) -> 'StateMachineBuilder':
		"""添加转换动作"""
		# 这个需要在构建时处理
		self.transitions.append((from_state, event, None, None, action))
		return self

	def build (self) -> StateMachine:
		"""构建状态机"""
		if not self.initial_state:
			raise ValueError("未设置初始状态")

		# 创建状态机
		initial_state = self.states[self.initial_state]
		state_machine = StateMachine(initial_state, self.name)

		# 添加所有状态
		for state in self.states.values():
			if state.name != self.initial_state:
				state_machine.add_state(state)

		# 添加转换
		for transition in self.transitions:
			if len(transition) == 4:
				from_state, event, to_state, condition = transition
				action = None
			else:
				from_state, event, to_state, condition, action = transition

			if from_state not in self.states:
				raise ValueError(f"源状态未定义: {from_state}")
			if to_state not in self.states:
				raise ValueError(f"目标状态未定义: {to_state}")

			source = self.states[from_state]
			target = self.states[to_state]

			trans = source.add_transition(event, target, condition)
			if action:
				trans.add_action(action)

		return state_machine
