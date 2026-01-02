"""
命令模式实现

将请求封装为对象，从而使你可以用不同的请求对客户进行参数化，
对请求排队或记录请求日志，以及支持可撤销的操作。

在量化交易系统中的典型应用：
1. 交易命令（买入、卖出、撤销）
2. 系统操作命令（启动、停止、重启）
3. 批量任务命令
4. 可撤销的操作（如订单修改）
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from enum import Enum
import uuid


class CommandStatus(Enum):
	"""命令状态"""
	PENDING = "pending"  # 等待执行
	EXECUTING = "executing"  # 执行中
	COMPLETED = "completed"  # 已完成
	FAILED = "failed"  # 失败
	CANCELLED = "cancelled"  # 已取消


class Command(ABC):
	"""
	命令接口

	所有具体命令必须实现此接口。
	"""

	def __init__ (self, command_id: Optional[str] = None):
		"""
		初始化命令

		Args:
			command_id: 命令ID（如未提供则自动生成）
		"""
		self.command_id = command_id or str(uuid.uuid4())
		self.status = CommandStatus.PENDING
		self.created_at = datetime.now()
		self.completed_at: Optional[datetime] = None
		self.result: Optional[Any] = None
		self.error: Optional[str] = None

	@abstractmethod
	async def execute (self) -> Any:
		"""
		执行命令

		Returns:
			Any: 命令执行结果
		"""
		pass

	@abstractmethod
	async def undo (self) -> bool:
		"""
		撤销命令

		Returns:
			bool: 撤销是否成功
		"""
		pass

	def get_command_info (self) -> Dict[str, Any]:
		"""获取命令信息"""
		return {
			"command_id": self.command_id,
			"status": self.status.value,
			"created_at": self.created_at.isoformat(),
			"completed_at": self.completed_at.isoformat() if self.completed_at else None,
			"command_type": self.__class__.__name__
		}

	def set_status (self, status: CommandStatus) -> None:
		"""设置命令状态"""
		self.status = status
		if status in [CommandStatus.COMPLETED, CommandStatus.FAILED, CommandStatus.CANCELLED]:
			self.completed_at = datetime.now()

	def set_result (self, result: Any) -> None:
		"""设置执行结果"""
		self.result = result

	def set_error (self, error: str) -> None:
		"""设置错误信息"""
		self.error = error


class CommandInvoker:
	"""
	命令调用者

	负责执行命令，并可以支持命令队列、重试、撤销等功能。
	"""

	def __init__ (self, max_retries: int = 3):
		"""
		初始化命令调用者

		Args:
			max_retries: 最大重试次数
		"""
		self._command_history: List[Command] = []
		self._undo_stack: List[Command] = []
		self._max_retries = max_retries
		self._is_executing = False

	async def execute_command (self, command: Command) -> Any:
		"""
		执行命令

		Args:
			command: 要执行的命令

		Returns:
			Any: 命令执行结果

		Raises:
			Exception: 如果命令执行失败
		"""
		try:
			self._is_executing = True
			command.set_status(CommandStatus.EXECUTING)

			# 执行命令（支持重试）
			for attempt in range(self._max_retries):
				try:
					result = await command.execute()
					command.set_status(CommandStatus.COMPLETED)
					command.set_result(result)

					# 记录到历史
					self._command_history.append(command)

					# 推入撤销栈
					self._undo_stack.append(command)

					return result

				except Exception as e:
					if attempt == self._max_retries - 1:
						# 最后一次尝试也失败了
						command.set_status(CommandStatus.FAILED)
						command.set_error(str(e))
						raise

					# 等待后重试
					import asyncio
					await asyncio.sleep(2 ** attempt)  # 指数退避

			self._is_executing = False

		except Exception as e:
			self._is_executing = False
			raise

	async def execute_commands (self, commands: List[Command],
	                            sequential: bool = True) -> List[Any]:
		"""
		执行多个命令

		Args:
			commands: 命令列表
			sequential: 是否顺序执行（True顺序，False并行）

		Returns:
			List[Any]: 所有命令的执行结果
		"""
		if sequential:
			return await self._execute_sequentially(commands)
		else:
			return await self._execute_in_parallel(commands)

	async def _execute_sequentially (self, commands: List[Command]) -> List[Any]:
		"""顺序执行命令"""
		results = []
		for command in commands:
			try:
				result = await self.execute_command(command)
				results.append(result)
			except Exception as e:
				results.append(e)
		return results

	async def _execute_in_parallel (self, commands: List[Command]) -> List[Any]:
		"""并行执行命令"""
		import asyncio
		tasks = [self.execute_command(cmd) for cmd in commands]
		return await asyncio.gather(*tasks, return_exceptions=True)

	async def undo_last_command (self) -> bool:
		"""撤销最后一个命令"""
		if not self._undo_stack:
			return False

		command = self._undo_stack.pop()
		try:
			success = await command.undo()
			if success:
				# 从历史中移除
				if command in self._command_history:
					self._command_history.remove(command)
			return success
		except Exception as e:
			print(f"撤销命令失败: {e}")
			return False

	def get_command_history (self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
		"""获取命令历史"""
		history = self._command_history
		if limit:
			history = history[-limit:]
		return [cmd.get_command_info() for cmd in history]

	def get_undo_stack_size (self) -> int:
		"""获取撤销栈大小"""
		return len(self._undo_stack)

	def clear_history (self) -> None:
		"""清除命令历史"""
		self._command_history.clear()
		self._undo_stack.clear()


class MacroCommand(Command):
	"""
	宏命令

	包含多个命令的组合命令。
	"""

	def __init__ (self, commands: Optional[List[Command]] = None):
		"""
		初始化宏命令

		Args:
			commands: 子命令列表
		"""
		super().__init__()
		self._commands = commands or []
		self._executed_commands: List[Command] = []

	def add_command (self, command: Command) -> None:
		"""添加子命令"""
		self._commands.append(command)

	def remove_command (self, command: Command) -> None:
		"""移除子命令"""
		if command in self._commands:
			self._commands.remove(command)

	async def execute (self) -> List[Any]:
		"""执行所有子命令"""
		self._executed_commands = []
		results = []

		for command in self._commands:
			try:
				result = await command.execute()
				results.append(result)
				self._executed_commands.append(command)
			except Exception as e:
				# 某个子命令失败，可以决定是否继续执行
				results.append(e)
			# 可以选择中断或继续
			# break

		return results

	async def undo (self) -> bool:
		"""撤销所有已执行的子命令（逆序撤销）"""
		success = True
		for command in reversed(self._executed_commands):
			try:
				cmd_success = await command.undo()
				if not cmd_success:
					success = False
			except Exception as e:
				print(f"撤销子命令失败: {e}")
				success = False

		return success


class AsyncCommand(Command):
	"""
	异步命令装饰器

	将同步函数转换为异步命令。
	"""

	def __init__ (self, func: Callable, *args, **kwargs):
		"""
		初始化异步命令

		Args:
			func: 要执行的函数
			*args, **kwargs: 函数参数
		"""
		super().__init__()
		self._func = func
		self._args = args
		self._kwargs = kwargs

	async def execute (self) -> Any:
		"""执行函数"""
		# 如果函数是异步的，直接调用
		if asyncio.iscoroutinefunction(self._func):
			return await self._func(*self._args, **self._kwargs)
		else:
			# 同步函数在线程池中执行
			import concurrent.futures
			loop = asyncio.get_event_loop()
			with concurrent.futures.ThreadPoolExecutor() as pool:
				return await loop.run_in_executor(
					pool, self._func, *self._args, **self._kwargs
				)

	async def undo (self) -> bool:
		"""默认撤销操作（无操作）"""
		# 如果没有撤销逻辑，可以记录日志
		print(f"命令 {self.command_id} 无撤销操作")
		return True