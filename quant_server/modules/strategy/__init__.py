# -*- coding: utf-8 -*-
"""
策略模块
负责策略管理、策略执行、信号生成等核心功能

模块结构：
- constants: 常量定义
- models: 数据模型
- events: 事件定义
- engines: 策略引擎
- services: 业务服务
- strategies: 策略实现
- tasks: 异步任务
- handlers: API处理函数
"""

import logging

# 导入子模块
from . import constants
from . import engines
from . import events
from . import handlers
from . import models
from . import services
from . import strategies
from . import tasks
# 导入常量
from .constants import (
	StrategyType,
	StrategyLifecycleStatus,
	RunMode,
	ErrorCode,
)

# 模块元数据
__version__ = "1.0.0"
__author__ = "量化交易系统团队"
__description__ = "量化交易系统策略管理模块"

logger = logging.getLogger(__name__)


# 导出主要接口
async def shutdown () -> None:
	"""策略模块关闭函数"""
	logger.info("策略模块已关闭")


__all__ = [
	# 子模块
	"constants",
	"models",
	"events",
	"engines",
	"services",
	"strategies",
	"tasks",
	"handlers",
	# 常量
	"StrategyType",
	"StrategyLifecycleStatus",
	"RunMode",
	"ErrorCode",
	# 初始化函数
	"initialize",
	"shutdown",
]


# 模块初始化函数 - 符合主启动文件期望的接口
async def initialize (
        main_engine=None,
        event_engine=None,
        config=None
) -> bool:
    """
    策略模块初始化函数（Eager Manager + Lazy Engine 模式）

    策略管理器（StrategyManager）常驻运行，订阅数据事件；
    具体策略引擎（CTA/Alpha/AI）按需由 EngineFactory 创建。

    Args:
        main_engine: 主引擎实例
        event_engine: 事件引擎实例
        config: 模块配置

    Returns:
        bool: 初始化是否成功
    """
    # 初始化变量
    success = False
    init_result = {}

    try:
        logger.info("开始初始化策略模块...")

        # 获取数据库会话 - 使用正确的上下文管理器方式
        if main_engine and hasattr(main_engine, 'get_async_session'):
            session = main_engine.get_async_session()
            init_result = await _initialize_strategy_module(
                session, main_engine, event_engine, config or {}
            )
            success = init_result.get('status') != 'failed'
        else:
            from shared.database.session import get_session_manager

            session_manager = get_session_manager()
            async with session_manager.get_session() as session:
                init_result = await _initialize_strategy_module(
                    session, main_engine, event_engine, config or {}
                )
                success = init_result.get('status') != 'failed'

        # 记录初始化结果
        if success:
            print(f"✅ 策略模块初始化成功: {init_result.get('message', '完成')}")
        else:
            print(f"⚠️  策略模块初始化警告: {init_result.get('message', '存在警告')}")

        return success

    except Exception as e:
        print(f"❌ 策略模块初始化失败: {str(e)}")
        logger.exception("策略模块初始化失败")
        return False


async def _initialize_strategy_module(session, main_engine, event_engine, config: dict) -> dict:
    """
    策略模块内部初始化逻辑（Eager Manager + Lazy Engine 模式）

    StrategyManager 常驻运行，订阅数据同步事件，驱动策略执行；
    EngineFactory 按策略类型懒加载创建 CTA/Alpha/AI 引擎。

    Args:
        session: 数据库会话
        main_engine: 主引擎实例
        event_engine: 事件引擎实例
        config: 模块配置

    Returns:
        dict: 初始化结果
    """
    from sqlalchemy import text

    try:
        # 1. 检查必要的表
        from sqlalchemy import inspect
        tables = await session.run_sync(
            lambda sync_session: inspect(sync_session.connection()).get_table_names()
        )

        required_tables = [
            "strategies",
            "strategy_runs",
            "strategy_templates",
            "positions"
        ]

        missing_tables = [t for t in required_tables if t not in tables]

        if missing_tables:
            logger.warning(f"策略模块缺少表: {missing_tables}")
            return {
                "status": "degraded",
                "missing_tables": missing_tables,
                "message": "策略模块初始化完成，但缺少必要的表"
            }

        # 2. 检查数据库连接
        await session.execute(text("SELECT 1"))

        # 3. 创建 Eager Manager — StrategyManager（常驻运行，订阅数据事件）
        from modules.strategy.engines.strategy_manager import StrategyManager
        from modules.strategy.engines.engine_factory import EngineFactory

        strategy_manager = StrategyManager(event_engine=event_engine)
        engine_factory = EngineFactory(event_engine=event_engine)

        # 注册到主引擎（供其他模块通过 main_engine 获取）
        if main_engine:
            main_engine.register_engine("strategy_manager", strategy_manager)
            main_engine.register_engine("engine_factory", engine_factory)

        # 启动 StrategyManager（触发 _on_start → 订阅 DataSyncCompletedEvent 等）
        await strategy_manager.start()

        # 4. 加载可用策略类型
        logger.info("策略模块初始化完成（Eager Manager + Lazy Engine 模式）")

        return {
            "status": "success",
            "message": "策略模块初始化完成（Manager常驻 + Engine按需）",
            "loaded_strategies": ["cta", "alpha", "ai", "technical"],
            "manager_status": strategy_manager.get_status()
        }

    except Exception as e:
        logger.error(f"策略模块初始化失败: {str(e)}")
        return {
            "status": "failed",
            "message": f"策略模块初始化失败: {str(e)}"
        }
