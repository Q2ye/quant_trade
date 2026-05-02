# -*- coding: utf-8 -*-
"""
账户模块

负责账户管理、持仓管理、资产计算、结算与对账。

模块结构：
- services: 业务服务（account/asset/cash/fee/position）
- calculators: 计算器（asset/pnl/exposure）
- managers: 资源管理器（AccountManager/ReconciliationManager）
- tasks: 定时任务（settlement/reconciliation）
- events: 事件定义
- handlers: API处理函数

模块间通过 EventEngine 异步通信，禁止直接 import 其他模块。
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

__version__ = "1.0.0"
__author__ = "Quant System Team"

from .handlers import AccountHandler
from .schemas import (
    AccountCreateRequest,
    AccountResponse,
    AccountUpdateRequest,
    AccountBalanceResponse,
    AccountPositionResponse,
    AccountSummaryResponse,
    PositionResponse,
    AccountFilter,
)
from .handlers import router as account_router

async def shutdown(main_engine=None) -> None:
    """账户模块关闭函数"""
    logger.info("账户模块已关闭")


__all__ = [
    "AccountHandler",
    "AccountCreateRequest",
    "AccountResponse",
    "AccountUpdateRequest",
    "AccountBalanceResponse",
    "AccountPositionResponse",
    "AccountSummaryResponse",
    "PositionResponse",
    "AccountFilter",
    "account_router",
    "initialize",
    "shutdown",
]


async def initialize(
    main_engine=None,
    event_engine=None,
    config: Optional[Dict[str, Any]] = None,
) -> bool:
    """账户模块初始化函数

    执行启动前验证：检查必要数据库表是否存在，验证连接可用性。

    Args:
        main_engine: 主引擎实例
        event_engine: 事件引擎实例
        config: 模块配置

    Returns:
        bool: 初始化是否成功
    """
    try:
        logger.info("开始初始化账户模块...")

        from sqlalchemy import text

        # 获取数据库会话
        if main_engine and hasattr(main_engine, "get_async_session"):
            session_factory = main_engine.get_async_session()
            session = session_factory() if callable(session_factory) else session_factory
            result = await _do_initialize(session)
        else:
            from quant_server.shared.database.session import get_session_manager

            session_manager = get_session_manager()
            async with session_manager.get_session() as session:
                result = await _do_initialize(session)

        if result["success"]:
            print(f"✅ 账户模块初始化成功")
        else:
            print(f"⚠️  账户模块初始化警告: {result.get('message', '存在警告')}")

        return result["success"]

    except Exception as e:
        print(f"❌ 账户模块初始化失败: {str(e)}")
        logger.exception("账户模块初始化失败")
        return False


async def _do_initialize(session) -> Dict[str, Any]:
    """内部初始化逻辑"""

    from sqlalchemy import inspect

    tables = await session.run_sync(
        lambda sync_session: inspect(sync_session.connection()).get_table_names()
    )

    required_tables = [
        "accounts",
        "positions",
        "orders",
        "trades",
    ]

    missing = [t for t in required_tables if t not in tables]

    if missing:
        logger.warning(f"账户模块缺少表: {missing}")
        return {
            "success": True,
            "status": "degraded",
            "missing_tables": missing,
            "message": f"缺少 {len(missing)} 张表，部分功能不可用",
        }

    return {
        "success": True,
        "status": "ready",
        "message": "账户模块就绪",
    }
