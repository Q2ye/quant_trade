# quant_server/shared/database/session/__init__.py
"""
数据库会话管理模块
提供连接池管理、会话管理、事务管理等核心功能

使用方法：
    1. 通过 get_session_manager() 获取全局会话管理器
    2. 使用 DBSessionDep 作为 FastAPI 依赖注入
    3. 使用 with_transaction 装饰器管理事务

注意：
    - 在应用启动时需要调用 initialize_database()
    - 在应用关闭时需要调用 close_database()
"""

from .connection_pool import (
	ConnectionPoolManager,
	get_connection_pool,
	get_db_session as get_pool_session,
)
from .session_manager import (
	SessionManager,
	get_session_manager,
	get_db_session,
	DBSessionDep,
	with_transaction,
	SessionScope,
)
from .transaction import (
	TransactionManager,
	TransactionError,
	IsolationLevel,
	atomic,
	transaction_scope,
	NestedTransaction,
)

# 导出公共接口
__all__ = [
	# 连接池管理
	"ConnectionPoolManager",
	"get_connection_pool",
	"get_pool_session",

	# 会话管理
	"SessionManager",
	"get_session_manager",
	"get_db_session",
	"DBSessionDep",
	"with_transaction",
	"SessionScope",

	# 事务管理
	"TransactionManager",
	"TransactionError",
	"IsolationLevel",
	"atomic",
	"transaction_scope",
	"NestedTransaction",
]


# 初始化函数
async def initialize_database () -> bool:
	"""初始化数据库连接池（应用启动时调用）"""
	try:
		session_manager = get_session_manager()
		return await session_manager.initialize()
	except Exception as e:
		import logging
		logging.getLogger(__name__).error(f"数据库初始化失败: {str(e)}", exc_info=True)
		return False


async def close_database ():
	"""关闭数据库连接池（应用关闭时调用）"""
	try:
		session_manager = get_session_manager()
		await session_manager.close()
	except Exception as e:
		import logging
		logging.getLogger(__name__).error(f"数据库关闭失败: {str(e)}", exc_info=True)


def get_database_status () -> dict:
	"""获取数据库状态"""
	try:
		session_manager = get_session_manager()
		return session_manager.get_status()
	except Exception:
		return {"status": "uninitialized"}