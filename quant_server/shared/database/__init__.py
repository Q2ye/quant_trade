# quant_server/shared/database/__init__.py
"""
共享数据库模块
提供数据库连接、模型、Repository等基础设施

架构层次：共享资源层
职责：数据库基础设施，所有模块共享使用
"""

from .session import (
	# 会话管理
	SessionManager,
	get_session_manager,
	get_db_session,
	DBSessionDep,
	with_transaction,
	SessionScope,

	# 连接池
	ConnectionPoolManager,
	get_connection_pool,

	# 事务管理
	TransactionManager,
	TransactionError,
	IsolationLevel,
	atomic,
	transaction_scope,
	NestedTransaction,

	# 初始化函数
	initialize_database,
	close_database,
	get_database_status,
)

# 导出模型和Repository（将在后续文件创建）
# from .models import *
# from .repositories import *

__all__ = [
	# 会话管理
	"SessionManager",
	"get_session_manager",
	"get_db_session",
	"DBSessionDep",
	"with_transaction",
	"SessionScope",

	# 连接池
	"ConnectionPoolManager",
	"get_connection_pool",

	# 事务管理
	"TransactionManager",
	"TransactionError",
	"IsolationLevel",
	"atomic",
	"transaction_scope",
	"NestedTransaction",

	# 初始化函数
	"initialize_database",
	"close_database",
	"get_database_status",

	# 模型和Repository（后续补充）
	# "BaseModel",
	# "Stock",
	# "get_repository",
]

# 数据库模块版本
__version__ = "1.0.0"
__author__ = "量化交易系统团队"
__description__ = "量化交易系统数据库共享模块"