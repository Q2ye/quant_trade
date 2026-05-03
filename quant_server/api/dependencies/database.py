# quant_server/api/dependencies/database.py
"""
数据库依赖模块 - 优化版

基于混合架构设计，API层使用共享层的数据库会话管理功能
避免重复实现，确保架构层次清晰

定位：API网关层 → 依赖注入模块
职责：为FastAPI路由提供数据库会话依赖
"""

import logging
from datetime import datetime
from typing import AsyncGenerator, Optional, Dict, Any

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import TransactionManager
from shared.database.session import (
    get_session_manager,
    get_db_session as shared_get_db_session,
    DBSessionDep as SharedDBSessionDep,
    with_transaction as shared_with_transaction,
    IsolationLevel,
    transaction_scope,
    get_database_status as shared_get_database_status,
)

logger = logging.getLogger(__name__)


class APIDatabaseDependencies:
    """
    API层数据库依赖管理器

    设计原则：
    1. API层只做HTTP层适配，不重复实现数据库功能
    2. 所有数据库功能都使用共享层提供的能力
    3. 只添加API层特定的错误处理和监控
    """

    def __init__(self):
        """初始化API数据库依赖"""
        self._initialized = False
        logger.info("API数据库依赖初始化完成")

    async def initialize(self) -> bool:
        """
        初始化数据库依赖

        注意：API层需要确保共享层的数据库连接池已初始化

        Returns:
            bool: 是否已正确连接到数据库
        """
        try:
            # 获取共享层的会话管理器
            session_manager = get_session_manager()

            # 检查数据库是否已初始化，如果没有则初始化
            db_status = session_manager.get_status()
            if db_status.get("status") != "initialized":
                logger.info("数据库连接未初始化，正在初始化共享层数据库连接...")
                success = await session_manager.initialize()
                if not success:
                    logger.error("共享层数据库初始化失败")
                    self._initialized = False
                    return False

            # 设置API层初始化状态
            self._initialized = True
            logger.info("API数据库依赖初始化成功")

            # 获取连接池状态
            db_status = session_manager.get_status()
            pool_stats = db_status.get("pool_stats", {})
            logger.info(f"数据库连接池状态: {pool_stats}")

            return True

        except Exception as e:
            logger.error(f"API数据库依赖初始化失败: {str(e)}", exc_info=True)
            self._initialized = False
            return False

    async def get_db_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        FastAPI依赖注入：获取数据库会话

        直接使用共享层的会话管理，添加API层特定的错误处理

        Yields:
            AsyncSession: 异步数据库会话

        Raises:
            HTTPException: 500 - 数据库服务未就绪
            HTTPException: 503 - 数据库服务不可用
        """
        if not self._initialized:
            logger.error("数据库依赖未初始化")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="数据库服务未就绪",
            )

        try:
            # 直接使用共享层的会话获取器
            async with shared_get_db_session() as session:
                logger.debug("数据库会话获取成功")
                yield session

        except Exception as e:
            logger.error(f"数据库会话获取异常: {str(e)}", exc_info=True)

            # 根据错误类型返回不同的HTTP状态码
            if "connection" in str(e).lower() or "connect" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="数据库连接失败，请稍后重试",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="数据库操作异常",
                )

    async def get_readonly_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        获取只读数据库会话依赖

        注意：目前使用普通会话，后续可扩展为读写分离

        Yields:
            AsyncSession: 只读异步数据库会话
        """
        async for session in self.get_db_session():
            # 这里可以设置只读模式，但需要数据库支持
            # await session.execute(text("SET TRANSACTION READ ONLY"))
            yield session

    async def get_transaction_session(
            self,
            isolation_level: Optional[IsolationLevel] = None
    ) -> AsyncGenerator[AsyncSession, None]:
        """
        获取事务数据库会话依赖

        使用共享层的事务作用域管理器

        Args:
            isolation_level: 事务隔离级别

        Yields:
            AsyncSession: 事务数据库会话
        """
        if not self._initialized:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="数据库服务未就绪",
            )

        # 获取会话管理器
        session_manager = get_session_manager()

        async with session_manager.get_session() as session:
            try:
                # 使用共享层的事务作用域
                async with transaction_scope(
                        session=session,
                        isolation_level=isolation_level,
                        auto_commit=True
                ) as transaction:
                    logger.debug(f"事务会话创建成功，隔离级别: {isolation_level or 'default'}")
                    yield session

            except Exception as e:
                logger.error(f"事务执行失败: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"事务操作失败: {str(e)}"
                )

    @staticmethod
    async def get_database_health() -> Dict[str, Any]:
        """
        获取数据库健康状态

        使用共享层的状态检查，添加API层特定的格式化

        Returns:
            Dict[str, Any]: 数据库健康状态信息
        """
        try:
            # 使用共享层的状态获取
            status_info = shared_get_database_status()

            # 添加API层特定的信息
            health_info = {
                "healthy": status_info.get("status") == "initialized",
                "status": status_info.get("status", "unknown"),
                "timestamp": datetime.now().isoformat(),
                "api_layer": "quant_server.api.dependencies.database",
                "shared_layer_status": status_info,
            }

            logger.debug(f"数据库健康检查结果: {health_info['healthy']}")
            return health_info

        except Exception as e:
            logger.error(f"数据库健康检查失败: {str(e)}")
            return {
                "healthy": False,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "api_layer": "quant_server.api.dependencies.database",
            }

    @staticmethod
    def get_transaction_decorator(isolation_level: Optional[IsolationLevel] = None):
        """
        获取事务装饰器（API层业务逻辑使用）

        Args:
            isolation_level: 事务隔离级别

        Returns:
            装饰器函数
        """
        # 直接使用共享层的事务装饰器
        return shared_with_transaction(isolation_level)

    async def close(self):
        """
        关闭数据库依赖

        注意：API层不负责关闭数据库连接，由共享层统一管理
        """
        logger.info("API数据库依赖关闭（实际关闭由共享层管理）")
        self._initialized = False


# 创建全局API数据库依赖实例
_api_db_deps = APIDatabaseDependencies()

# 导出依赖函数（FastAPI可以直接使用）
get_db_session = _api_db_deps.get_db_session
get_readonly_session = _api_db_deps.get_readonly_session
get_transaction_session = _api_db_deps.get_transaction_session
get_database_health = _api_db_deps.get_database_health
get_transaction_decorator = _api_db_deps.get_transaction_decorator

# 导出类型注解
DBSessionDep = Depends(get_db_session)
ReadonlySessionDep = Depends(get_readonly_session)


# 带隔离级别的事务会话依赖工厂函数
def TransactionSessionDep(isolation: Optional[IsolationLevel] = None):
    """事务会话依赖工厂"""
    return Depends(lambda: _api_db_deps.get_transaction_session(isolation))


# 为了兼容性，导出共享层的DBSessionDep
SharedDBSessionDep = SharedDBSessionDep

# 事务装饰器别名
with_transaction = get_transaction_decorator


async def initialize_api_database() -> bool:
    """
    初始化API数据库依赖（应用启动时调用）

    注意：实际上只是检查共享层是否已初始化

    Returns:
        bool: 初始化是否成功
    """
    return await _api_db_deps.initialize()


async def close_api_database():
    """
    关闭API数据库依赖（应用关闭时调用）

    注意：只关闭API层状态，实际连接由共享层关闭
    """
    await _api_db_deps.close()


# 简化的事务上下文管理器（API层使用）
class APITransactionScope:
    """API层事务作用域管理器"""

    def __init__(self, isolation_level: Optional[IsolationLevel] = None):
        self.isolation_level = isolation_level
        self.session = None
        self.transaction = None

    async def __aenter__(self) -> AsyncSession:
        """进入事务作用域"""
        # 获取会话
        session_manager = get_session_manager()
        self.session = await session_manager.get_session().__aenter__()

        # 开始事务
        self.transaction = TransactionManager(self.session)
        await self.transaction.begin(self.isolation_level)

        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出事务作用域"""
        if self.transaction:
            if exc_type is None:
                await self.transaction.commit()
            else:
                await self.transaction.rollback()

        if self.session:
            await self.session.close()


def create_session():
    """创建数据库会话工厂"""
    return get_db_session()


# 初始化函数别名
initialize_database = initialize_api_database
close_database = close_api_database
