# shared/database/session/session_manager.py
"""
数据库会话管理器
提供会话生命周期管理和依赖注入支持
"""

import logging
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from typing import Annotated

from .connection_pool import get_connection_pool
from ...config.config_manager import config

logger = logging.getLogger(__name__)


class SessionManager:
	"""会话管理器"""

	def __init__ (self):
		self._connection_pool = None
		self._is_initialized = False

	async def initialize (self) -> bool:
		"""初始化会话管理器"""
		try:
			self._connection_pool = get_connection_pool()
			success = await self._connection_pool.initialize()

			if success:
				self._is_initialized = True
				logger.info("数据库会话管理器初始化成功")
			else:
				logger.error("数据库会话管理器初始化失败")

			return success

		except Exception as e:
			logger.error(f"数据库会话管理器初始化异常: {str(e)}", exc_info=True)
			return False

	@asynccontextmanager
	async def get_session (self) -> AsyncGenerator[AsyncSession, None]:
		"""获取数据库会话"""
		if not self._is_initialized or not self._connection_pool:
			raise RuntimeError("数据库会话管理器未初始化")

		session_factory = self._connection_pool.get_session_factory()
		session = session_factory()

		try:
			yield session
			await session.commit()
		except Exception as e:
			await session.rollback()
			# ⚠️ 本分支也会捕获**业务性拒绝**：FastAPI 会把端点的异常 throw 进 yield
			# 依赖点，因此 HTTPException(400/404/409…) 同样走到这里。此时 rollback 只是
			# 正常的事务收尾，并非数据库故障 —— 统一打「数据库操作失败」会让排查误入
			# 歧途（2026-09-17 512400 录单 400 事故：日志只剩一句空白的"已回滚"，
			# 真实原因被吞掉）。故按是否有 status_code 区分，并用 repr 输出 ——
			# starlette 0.27 的 HTTPException 未定义 __str__，str(e) 恒为空字符串。
			# 依赖方向约束：shared/ 不 import fastapi，故用 duck-typing 判定。
			_status = getattr(e, "status_code", None)
			if _status is not None:
				logger.info(
					f"事务回滚（业务拒绝 {_status}）: "
					f"{getattr(e, 'detail', None) or e!r}"
				)
			else:
				logger.warning(f"数据库操作失败，已回滚: {e!r}")
			raise
		finally:
			await session.close()

	async def close (self):
		"""关闭会话管理器"""
		if self._connection_pool:
			await self._connection_pool.close()
			self._is_initialized = False
			logger.info("数据库会话管理器已关闭")

	def get_status (self) -> dict:
		"""获取会话管理器状态"""
		if not self._connection_pool:
			return {"status": "uninitialized"}

		pool_stats = self._connection_pool.get_pool_stats()
		return {
			"status": "initialized" if self._is_initialized else "error",
			"pool_stats": pool_stats,
			"database_config": {
			"type": config.settings.DATABASE.TYPE,
			"host": config.settings.DATABASE.HOST,
			"port": config.settings.DATABASE.PORT,
			"database": config.settings.DATABASE.NAME,
		}
		}


# 全局会话管理器实例
_session_manager: Optional[SessionManager] = None


def get_session_manager () -> SessionManager:
	"""获取会话管理器实例"""
	global _session_manager
	if _session_manager is None:
		_session_manager = SessionManager()
	return _session_manager


@asynccontextmanager
async def get_db_session () -> AsyncGenerator[AsyncSession, None]:
	"""FastAPI依赖注入：获取数据库会话"""
	session_manager = get_session_manager()

	async with session_manager.get_session() as session:
		yield session


# FastAPI依赖注入类型
DBSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


# 事务管理装饰器
def with_transaction (func):
	"""事务管理装饰器"""

	async def wrapper (*args, **kwargs):
		session_manager = get_session_manager()

		async with session_manager.get_session() as session:
			try:
				# 将会话注入到函数参数中
				if 'session' in kwargs:
					result = await func(*args, **kwargs)
				else:
					# 将会话作为最后一个位置参数
					result = await func(*args, session, **kwargs)
				return result
			except Exception as e:
				logger.error(f"事务执行失败: {str(e)}", exc_info=True)
				raise

	return wrapper
