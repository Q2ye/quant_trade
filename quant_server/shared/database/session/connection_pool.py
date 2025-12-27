# shared/database/session/connection_pool.py
"""
数据库连接池管理
支持 PostgreSQL 和 MySQL，支持连接池和连接复用
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
	AsyncEngine,
	AsyncSession,
	async_sessionmaker,
	create_async_engine
)
from sqlalchemy.pool import QueuePool

from quant_server.shared.config.settings import settings

logger = logging.getLogger(__name__)


class ConnectionPoolManager:
	"""数据库连接池管理器"""

	def __init__ (self):
		self._engine: Optional[AsyncEngine] = None
		self._session_factory: Optional[async_sessionmaker] = None
		self._pool_size: int = settings.DATABASE.POOL_SIZE
		self._max_overflow: int = settings.DATABASE.MAX_OVERFLOW

	async def initialize (self) -> bool:
		"""初始化连接池"""
		try:
			# 构建数据库URL
			db_url = self._build_database_url()

			# 创建异步引擎
			self._engine = create_async_engine(
				db_url,
				poolclass=QueuePool,
				pool_size=self._pool_size,
				max_overflow=self._max_overflow,
				pool_recycle=3600,  # 1小时回收连接
				pool_pre_ping=True,  # 连接前ping检查
				echo=settings.DATABASE.ECHO_SQL,
				echo_pool=settings.DATABASE.ECHO_POOL,
				future=True,
				# PostgreSQL特殊配置
				connect_args={"server_settings": {"jit": "off"}}
				if settings.DATABASE.TYPE == "postgresql"
				else {}
			)

			# 创建会话工厂
			self._session_factory = async_sessionmaker(
				bind=self._engine,
				class_=AsyncSession,
				expire_on_commit=False,
				autocommit=False,
				autoflush=False,
			)

			# 测试连接
			async with self._engine.connect() as conn:
				await conn.execute("SELECT 1")

			logger.info(
				f"数据库连接池初始化成功: "
				f"{settings.DATABASE.HOST}:{settings.DATABASE.PORT}/"
				f"{settings.DATABASE.NAME} "
				f"(pool_size={self._pool_size}, max_overflow={self._max_overflow})"
			)
			return True

		except Exception as e:
			logger.error(f"数据库连接池初始化失败: {str(e)}", exc_info=True)
			return False

	def _build_database_url (self) -> str:
		"""构建数据库连接URL"""
		db_type = settings.DATABASE.TYPE

		if db_type == "postgresql":
			return (
				f"postgresql+asyncpg://{settings.DATABASE.USER}:"
				f"{settings.DATABASE.PASSWORD}@{settings.DATABASE.HOST}:"
				f"{settings.DATABASE.PORT}/{settings.DATABASE.NAME}"
			)
		elif db_type == "mysql":
			return (
				f"mysql+aiomysql://{settings.DATABASE.USER}:"
				f"{settings.DATABASE.PASSWORD}@{settings.DATABASE.HOST}:"
				f"{settings.DATABASE.PORT}/{settings.DATABASE.NAME}"
				"?charset=utf8mb4"
			)
		else:
			raise ValueError(f"不支持的数据库类型: {db_type}")

	def get_session_factory (self) -> async_sessionmaker:
		"""获取会话工厂"""
		if not self._session_factory:
			raise RuntimeError("数据库连接池未初始化")
		return self._session_factory

	async def get_connection (self):
		"""获取数据库连接"""
		if not self._engine:
			raise RuntimeError("数据库引擎未初始化")
		return await self._engine.connect()

	async def close (self):
		"""关闭连接池"""
		if self._engine:
			await self._engine.dispose()
			logger.info("数据库连接池已关闭")

	async def health_check (self) -> Dict[str, Any]:
		"""健康检查"""
		try:
			async with self._engine.connect() as conn:
				start_time = asyncio.get_event_loop().time()
				await conn.execute("SELECT 1")
				response_time = asyncio.get_event_loop().time() - start_time

				return {
					"status": "healthy",
					"database_type": settings.DATABASE.TYPE,
					"pool_status": {
						"checked_out": self._engine.pool.checkedout(),
						"overflow": self._engine.pool.overflow(),
						"size": self._engine.pool.size(),
					},
					"response_time_ms": round(response_time * 1000, 2),
				}
		except Exception as e:
			return {
				"status": "unhealthy",
				"error": str(e)
			}

	def get_pool_stats (self) -> Dict[str, Any]:
		"""获取连接池统计信息"""
		if not self._engine:
			return {}

		pool = self._engine.pool
		return {
			"checked_out": pool.checkedout(),
			"overflow": pool.overflow(),
			"size": pool.size(),
			"connections": pool.checkedin() + pool.checkedout(),
			"max_overflow": self._max_overflow,
			"pool_size": self._pool_size,
		}


# 全局连接池实例
_connection_pool: Optional[ConnectionPoolManager] = None


def get_connection_pool () -> ConnectionPoolManager:
	"""获取连接池实例（单例）"""
	global _connection_pool
	if _connection_pool is None:
		_connection_pool = ConnectionPoolManager()
	return _connection_pool


@asynccontextmanager
async def get_db_session ():
	"""获取数据库会话的上下文管理器"""
	pool = get_connection_pool()
	session_factory = pool.get_session_factory()
	session = session_factory()

	try:
		yield session
		await session.commit()
	except Exception:
		await session.rollback()
		raise
	finally:
		await session.close()