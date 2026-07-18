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

from ...config.config_manager import config

logger = logging.getLogger(__name__)


class ConnectionPoolManager:
	"""数据库连接池管理器"""

	def __init__ (self):
		import threading as _threading
		self._engine: Optional[AsyncEngine] = None
		self._session_factory: Optional[async_sessionmaker] = None
		self._pool_size: int = config.settings.DATABASE.POOL_SIZE
		self._max_overflow: int = config.settings.DATABASE.MAX_OVERFLOW
		self._main_thread_id: int = _threading.current_thread().ident
		# 后台线程独立 pool（避免 "Future attached to a different loop"）

	async def initialize (self) -> bool:
		"""初始化连接池"""
		try:
			# 构建数据库URL
			db_url = self._build_database_url()

			# 导入自定义JSON编码器和解码器
			from ...cache.serializers import JSONEncoder, JSONDecoder

			# 创建异步引擎
			self._engine = create_async_engine(
				db_url,
				pool_size=self._pool_size,
				max_overflow=self._max_overflow,
				pool_recycle=3600,  # 1小时回收连接
				pool_pre_ping=True,  # 连接前ping检查
				echo=config.settings.DATABASE.ECHO_SQL,
				echo_pool=config.settings.DATABASE.ECHO_POOL,
				future=True,
				json_serializer=JSONEncoder().encode,
				json_deserializer=JSONDecoder().decode,
				# PostgreSQL特殊配置
				connect_args={"server_settings": {"jit": "off"}}
				if config.settings.DATABASE.TYPE == "postgresql"
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
				from sqlalchemy import text
				await conn.execute(text("SELECT 1"))

			logger.info(
				f"数据库连接池初始化成功: "
				f"{config.settings.DATABASE.HOST}:{config.settings.DATABASE.PORT}/"
				f"{config.settings.DATABASE.NAME} "
				f"(pool_size={self._pool_size}, max_overflow={self._max_overflow})"
			)
			return True

		except Exception as e:
			logger.error(f"数据库连接池初始化失败: {str(e)}", exc_info=True)
			return False

	@staticmethod
	def _build_database_url () -> str:
		"""构建数据库连接URL"""
		from ...config.config_manager import config
		db_type = config.settings.DATABASE.TYPE

		if db_type == "postgresql":
			return (
				f"postgresql+asyncpg://{config.settings.DATABASE.USER}:"
				f"{config.settings.DATABASE.PASSWORD}@{config.settings.DATABASE.HOST}:"
				f"{config.settings.DATABASE.PORT}/{config.settings.DATABASE.NAME}"
			)
		elif db_type == "mysql":
			return (
				f"mysql+aiomysql://{config.settings.DATABASE.USER}:"
				f"{config.settings.DATABASE.PASSWORD}@{config.settings.DATABASE.HOST}:"
				f"{config.settings.DATABASE.PORT}/{config.settings.DATABASE.NAME}"
				"?charset=utf8mb4"
			)
		else:
			raise ValueError(f"不支持的数据库类型: {db_type}")

	def get_session_factory (self) -> async_sessionmaker:
		"""获取会话工厂。

		如果在后台线程中调用（threading.current_thread() != main_thread），
		自动为当前线程创建独立的 AsyncEngine + session factory，
		避免 asyncpg "Future attached to a different loop" 错误。

		v3.5 修复：线程级 engine 绑定当前 event loop。BackgroundTaskExecutor
		每个任务创建新 event loop，线程复用时旧 engine 的连接池绑定到
		已关闭的旧 loop → 后续所有 DB 操作崩溃。现在检测 loop 变更后
		自动 dispose 旧 engine 并重建。
		"""
		import threading as _threading
		current_tid = _threading.current_thread().ident
		main_tid = getattr(self, "_main_thread_id", current_tid)

		if current_tid != main_tid:
			# 后台线程 → 线程独立 engine（绑定当前 event loop）
			try:
				_loop = asyncio.get_running_loop()
			except RuntimeError:
				_loop = None

			loop_id = id(_loop) if _loop is not None else 0

			try:
				_cached_factory, _cached_loop_id = self._thread_pools[current_tid]
			except AttributeError:
				self._thread_pools: Dict[int, tuple] = {}
			except KeyError:
				pass
			else:
				if _cached_loop_id == loop_id:
					return _cached_factory
				# loop 已变更（线程复用）→ dispose 旧 engine 并重建
				_old_engine = _cached_factory.kw.get("bind")
				if _old_engine is not None:
					try:
						# 同步 dispose（旧 loop 可能已关闭，不能 await）
						import concurrent.futures
						_fut = _old_engine.dispose()
					except Exception:
						pass
				logger.info(
					"Worker 线程 (tid=%s) event loop 变更 (%s→%s)，重建 DB 池",
					current_tid, _cached_loop_id, loop_id,
				)

			db_url = self._build_database_url()
			_engine = create_async_engine(
				db_url, pool_size=2, max_overflow=1,
				pool_recycle=3600, pool_pre_ping=True,
			)
			_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
			self._thread_pools[current_tid] = (_factory, loop_id)
			logger.info("Worker 线程独立 DB 池已创建 (tid=%s, loop=%s)", current_tid, loop_id)
			return _factory

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
				start_time = asyncio.get_running_loop().time()
				await conn.execute("SELECT 1")
				response_time = asyncio.get_running_loop().time() - start_time

				return {
				"status": "healthy",
				"database_type": config.settings.DATABASE.TYPE,
				"pool_status": {
					"checked_out": getattr(self._engine.pool, 'checkedout', lambda: 0)(),
					"overflow": getattr(self._engine.pool, 'overflow', lambda: 0)(),
					"size": getattr(self._engine.pool, 'size', lambda: 0)(),
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
		"checked_out": getattr(pool, 'checkedout', lambda: 0)(),
		"overflow": getattr(pool, 'overflow', lambda: 0)(),
		"size": getattr(pool, 'size', lambda: 0)(),
		"connections": getattr(pool, 'checkedin', lambda: 0)() + getattr(pool, 'checkedout', lambda: 0)(),
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