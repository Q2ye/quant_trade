# quant_server/api/dependencies/database.py
"""
数据库依赖模块 - 优化版

基于混合架构设计，API层使用共享层的数据库会话管理功能
避免重复实现，确保架构层次清晰

定位：API网关层 → 依赖注入模块
职责：为FastAPI路由提供数据库会话依赖
"""

import logging
from typing import AsyncGenerator

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.session import (
    get_session_manager,
    get_db_session as shared_get_db_session,
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
            logger.error(f"API数据库依赖初始化失败: {'服务器内部错误'}", exc_info=True)
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
            logger.error(f"数据库会话获取异常: {'服务器内部错误'}", exc_info=True)

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


async def initialize_api_database() -> bool:
    """
    初始化API数据库依赖（应用启动时调用）

    注意：实际上只是检查共享层是否已初始化

    Returns:
        bool: 初始化是否成功
    """
    return await _api_db_deps.initialize()
