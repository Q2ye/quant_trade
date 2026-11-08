# shared/database/session/session_manager.py
"""
数据库会话管理器
提供会话生命周期管理和依赖注入支持
"""

import logging
import os
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from typing import Annotated

from .connection_pool import get_connection_pool
from ...config.config_manager import config

logger = logging.getLogger(__name__)


def evaluate_environment_safety (
	environment: str,
	current_user: str,
	search_path: str,
	can_write_accounts: bool,
	current_database: Optional[str] = None,
	expected_database: Optional[str] = None,
) -> list[str]:
	"""评估环境隔离是否生效（纯函数，便于单测）。

	- development: search_path 以 dev 开头，且不能写 public.accounts
	- production/staging: search_path 为 public，且能写 public.accounts
	- testing: 跳过
	- 任何环境: 应用角色不得是 superuser postgres；库名必须与配置一致
	"""
	env = (environment or "").lower()
	if env == "testing":
		return []

	path = (search_path or "").replace(" ", "")
	problems: list[str] = []

	if current_user == "postgres":
		problems.append("current_user=postgres：应用禁止使用 superuser")

	if current_database and expected_database and current_database != expected_database:
		problems.append(
			f"current_database={current_database!r} != 期望 {expected_database!r}"
		)

	if env == "development":
		if not path.startswith("dev"):
			problems.append(f"search_path={search_path!r}：开发环境必须以 dev 开头")
		if can_write_accounts:
			problems.append("开发角色可写 public.accounts：隔离失效")
	else:
		if not path.startswith("public"):
			problems.append(f"search_path={search_path!r}：生产环境必须为 public")
		if not can_write_accounts:
			problems.append("生产角色不可写 public.accounts：账户写入会失败")

	return problems


class SessionManager:
	"""会话管理器"""

	def __init__ (self):
		self._connection_pool = None
		self._is_initialized = False

	async def initialize (self) -> bool:
		"""初始化会话管理器（含环境隔离断言）。"""
		try:
			self._connection_pool = get_connection_pool()
			success = await self._connection_pool.initialize()

			if success:
				# 环境安全断言必须在标记初始化成功之前执行：
				# 失败 → 返回 False → main.py 启动流程抛 RuntimeError
				try:
					await self._assert_environment_safety()
				except Exception as safety_err:
					logger.error("环境安全断言失败，拒绝启动: %s", safety_err, exc_info=True)
					return False

				self._is_initialized = True
				logger.info("数据库会话管理器初始化成功")
			else:
				logger.error("数据库会话管理器初始化失败")

			return success

		except Exception as e:
			logger.error(f"数据库会话管理器初始化异常: {str(e)}", exc_info=True)
			return False

	async def _assert_environment_safety (self) -> None:
		"""校验当前连接角色、search_path、库名与账户写权限。"""
		# 不能读模块导入期的 config 单例：StartupConfig 会在运行时 reload/rebind，
		# 且 --mode 通过 os.environ["ENVIRONMENT"] 生效（main.py:1230-1231）。
		environment = (os.getenv("ENVIRONMENT") or "development").lower()
		if environment == "testing":
			return

		session_factory = self._connection_pool.get_session_factory()
		async with session_factory() as session:
			result = await session.execute(text(
				"SELECT current_user, current_setting('search_path'), current_database(), "
				"has_table_privilege(current_user, 'public.accounts', 'INSERT')"
			))
			current_user, search_path, current_db, can_write_accounts = result.one()

		expected_db = os.getenv(
			"PROD_DB_NAME" if environment != "development" else "DB_DEV_NAME"
		) or "quant_signals"
		problems = evaluate_environment_safety(
			environment, current_user, search_path, bool(can_write_accounts),
			current_database=current_db, expected_database=expected_db,
		)
		if problems:
			raise RuntimeError("; ".join(problems))

		logger.info(
			"环境安全断言通过: user=%s search_path=%s environment=%s",
			current_user, search_path, environment,
		)

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
