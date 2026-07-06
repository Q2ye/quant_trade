# quant_server/shared/database/__init__.py
"""
共享数据库模块 — 顶层入口

架构层次：共享资源层
职责：数据库基础设施，所有模块共享使用

导入指南：
  会话管理    → from shared.database import get_db_session, DBSessionDep
  事务管理    → from shared.database import atomic, transaction_scope
  数据模型    → from shared.database.models import StockBasic, Order, ...
  数据仓库    → from shared.database.repositories import OrderRepository, ...
"""

# ============================================
# 会话管理（高频使用，从顶层导入更方便）
# ============================================
from .session import (
    SessionManager,
    get_session_manager,
    get_db_session,
    DBSessionDep,
    with_transaction,
    SessionScope,
    ConnectionPoolManager,
    get_connection_pool,
    initialize_database,
    close_database,
    get_database_status,
)

# ============================================
# 事务管理（Service 层高频使用）
# ============================================
from .session import (
    TransactionManager,
    TransactionError,
    IsolationLevel,
    atomic,
    transaction_scope,
    NestedTransaction,
)

# ============================================
# 基础类（跨层依赖）
# ============================================
from .models import Base
from .repositories import (
    BaseRepository,
    HyperRepositoryBase,
    QueryBuilder,
    PaginationParams,
    PaginationResult,
    repository_factory,
    RepositoryFactory,
    get_repository_by_domain,
)
# RepositoryError 在 repository_base 中定义，直接导入避免循环依赖
from .repositories.base.repository_base import RepositoryError

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

    # 生命周期
    "initialize_database",
    "close_database",
    "get_database_status",

    # 基础类
    "Base",
    "BaseRepository",
    "HyperRepositoryBase",
    "RepositoryError",
    "QueryBuilder",
    "PaginationParams",
    "PaginationResult",

    # 工厂
    "repository_factory",
    "RepositoryFactory",
    "get_repository_by_domain",
]

__version__ = "1.0.0"
__author__ = "量化交易系统团队"
