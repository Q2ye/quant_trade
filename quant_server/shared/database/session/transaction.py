# shared/database/session/transaction.py
"""
事务管理工具
提供事务控制、隔离级别管理和分布式事务支持
"""

import logging
from typing import Optional, Callable, Any, TypeVar, Generic
from functools import wraps
from contextlib import asynccontextmanager
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)

T = TypeVar('T')


class IsolationLevel(Enum):
	"""事务隔离级别"""
	READ_UNCOMMITTED = "READ UNCOMMITTED"
	READ_COMMITTED = "READ COMMITTED"
	REPEATABLE_READ = "REPEATABLE READ"
	SERIALIZABLE = "SERIALIZABLE"


class TransactionError(Exception):
	"""事务相关异常"""
	pass


class TransactionManager:
	"""事务管理器"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self._is_active = False
		self._savepoints = []

	async def begin (
			self,
			isolation_level: Optional[IsolationLevel] = None
	) -> None:
		"""开始事务"""
		if self._is_active:
			raise TransactionError("事务已在活动中")

		try:
			if isolation_level:
				# 设置隔离级别
				await self.session.execute(
					text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level.value}")
				)

			# 开始事务
			await self.session.begin()
			self._is_active = True

			logger.debug(f"事务已开始，隔离级别: {isolation_level or 'default'}")

		except Exception as e:
			logger.error(f"开始事务失败: {str(e)}")
			raise TransactionError(f"开始事务失败: {str(e)}")

	async def commit (self) -> None:
		"""提交事务"""
		if not self._is_active:
			raise TransactionError("没有活动的事务可提交")

		try:
			await self.session.commit()
			self._is_active = False
			self._savepoints.clear()

			logger.debug("事务已提交")

		except Exception as e:
			logger.error(f"提交事务失败: {str(e)}")
			await self.rollback()
			raise TransactionError(f"提交事务失败: {str(e)}")

	async def rollback (self) -> None:
		"""回滚事务"""
		if not self._is_active:
			logger.warning("没有活动的事务可回滚")
			return

		try:
			await self.session.rollback()
			self._is_active = False
			self._savepoints.clear()

			logger.debug("事务已回滚")

		except Exception as e:
			logger.error(f"回滚事务失败: {str(e)}")
			raise TransactionError(f"回滚事务失败: {str(e)}")

	async def create_savepoint (self, name: str) -> None:
		"""创建保存点"""
		if not self._is_active:
			raise TransactionError("没有活动的事务，无法创建保存点")

		try:
			await self.session.execute(text(f"SAVEPOINT {name}"))
			self._savepoints.append(name)

			logger.debug(f"保存点已创建: {name}")

		except Exception as e:
			logger.error(f"创建保存点失败: {str(e)}")
			raise

	async def rollback_to_savepoint (self, name: str) -> None:
		"""回滚到保存点"""
		if name not in self._savepoints:
			raise TransactionError(f"保存点不存在: {name}")

		try:
			await self.session.execute(text(f"ROLLBACK TO SAVEPOINT {name}"))

			# 移除该保存点之后的所有保存点
			index = self._savepoints.index(name)
			self._savepoints = self._savepoints[:index]

			logger.debug(f"已回滚到保存点: {name}")

		except Exception as e:
			logger.error(f"回滚到保存点失败: {str(e)}")
			raise

	async def release_savepoint (self, name: str) -> None:
		"""释放保存点"""
		if name not in self._savepoints:
			raise TransactionError(f"保存点不存在: {name}")

		try:
			await self.session.execute(text(f"RELEASE SAVEPOINT {name}"))
			self._savepoints.remove(name)

			logger.debug(f"保存点已释放: {name}")

		except Exception as e:
			logger.error(f"释放保存点失败: {str(e)}")
			raise

	@property
	def is_active (self) -> bool:
		"""检查事务是否在活动中"""
		return self._is_active

	def get_savepoints (self) -> list:
		"""获取所有保存点"""
		return self._savepoints.copy()


# 事务装饰器
def atomic (
		isolation_level: Optional[IsolationLevel] = None,
		auto_commit: bool = True
):
	"""
	事务装饰器

	Args:
		isolation_level: 隔离级别
		auto_commit: 是否自动提交
	"""

	def decorator (func: Callable):
		@wraps(func)
		async def wrapper (*args, **kwargs):
			# 查找session参数
			session = None

			# 从kwargs中查找
			if 'session' in kwargs:
				session = kwargs['session']
			# 从args中查找（通常是最后一个参数）
			elif args and isinstance(args[-1], AsyncSession):
				session = args[-1]

			if not session:
				raise TransactionError("未找到数据库会话参数")

			# 创建事务管理器
			transaction = TransactionManager(session)

			try:
				# 开始事务
				await transaction.begin(isolation_level)

				# 执行函数
				result = await func(*args, **kwargs)

				# 自动提交
				if auto_commit:
					await transaction.commit()

				return result

			except Exception as e:
				# 自动回滚
				if transaction.is_active:
					await transaction.rollback()
				raise

		return wrapper

	return decorator


# 上下文管理器
@asynccontextmanager
async def transaction_scope (
		session: AsyncSession,
		isolation_level: Optional[IsolationLevel] = None,
		auto_commit: bool = True
):
	"""
	事务作用域上下文管理器

	Args:
		session: 数据库会话
		isolation_level: 隔离级别
		auto_commit: 是否自动提交
	"""
	transaction = TransactionManager(session)

	try:
		# 开始事务
		await transaction.begin(isolation_level)

		yield transaction

		# 自动提交
		if auto_commit and transaction.is_active:
			await transaction.commit()

	except Exception:
		# 自动回滚
		if transaction.is_active:
			await transaction.rollback()
		raise
	finally:
		# 清理
		if transaction.is_active:
			await transaction.rollback()


# 嵌套事务支持
class NestedTransaction:
	"""嵌套事务支持"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.savepoint_counter = 0
		self.savepoints = []

	async def begin_nested (self) -> str:
		"""开始嵌套事务"""
		self.savepoint_counter += 1
		savepoint_name = f"sp_{self.savepoint_counter}"

		await self.session.execute(text(f"SAVEPOINT {savepoint_name}"))
		self.savepoints.append(savepoint_name)

		return savepoint_name

	async def commit_nested (self, savepoint_name: str) -> None:
		"""提交嵌套事务"""
		if savepoint_name not in self.savepoints:
			raise TransactionError(f"保存点不存在: {savepoint_name}")

		# 嵌套事务通过释放保存点来"提交"
		await self.session.execute(text(f"RELEASE SAVEPOINT {savepoint_name}"))
		self.savepoints.remove(savepoint_name)

	async def rollback_nested (self, savepoint_name: str) -> None:
		"""回滚嵌套事务"""
		if savepoint_name not in self.savepoints:
			raise TransactionError(f"保存点不存在: {savepoint_name}")

		await self.session.execute(text(f"ROLLBACK TO SAVEPOINT {savepoint_name}"))

		# 移除该保存点之后的所有保存点
		index = self.savepoints.index(savepoint_name)
		self.savepoints = self.savepoints[:index]

	def get_current_savepoint (self) -> Optional[str]:
		"""获取当前保存点"""
		return self.savepoints[-1] if self.savepoints else None