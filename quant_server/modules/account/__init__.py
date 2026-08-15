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
from .engines.settlement_engine import SettlementEngine

def _register_daily_settlement_schedule(settlement_engine) -> None:
    """注册交易日 21:00 日终结算调度（APScheduler）

    兜底机制：即使当日无交易信号触发结算，21:00 也会执行一次。
    半自动模式下，21:00 确保人工确认交易信号的时间窗口已关闭后再结算。
    """
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = AsyncIOScheduler()

        async def _settlement_job():
            from datetime import date as _date
            from modules.account.tasks.settlement_tasks import create_settlement_tasks

            db_factory = settlement_engine._db_session_factory
            if not db_factory:
                logger.warning("结算调度跳过：db_session_factory 未配置")
                return

            try:
                async with db_factory() as session:
                    tasks = create_settlement_tasks(session, event_engine=settlement_engine.event_engine)
                    result = await tasks.daily_settlement_task(_date.today())
                    await session.commit()
                    logger.info(f"日终结算调度完成: {result.get('total_accounts', 0)} 个账户")
            except Exception:
                logger.exception("日终结算调度执行失败")

        scheduler.add_job(
            _settlement_job,
            trigger=CronTrigger(day_of_week="mon-fri", hour=21, minute=0, timezone="Asia/Shanghai"),
            id="daily_settlement_21_00",
            name="日终结算(21:00)",
            max_instances=1,
            misfire_grace_time=300,
            coalesce=True,
        )
        scheduler.start()
        logger.info("日终结算调度已注册: 交易日 21:00")
    except ImportError:
        logger.info("APScheduler 未安装，跳过日终结算调度注册")
    except Exception:
        logger.warning("日终结算调度注册失败（非致命）", exc_info=True)


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
    "SettlementEngine",
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
            factory = main_engine.get_async_session()
            async with factory() as session:
                result = await _do_initialize(session)
        else:
            from shared.database.session import get_session_manager

            session_manager = get_session_manager()
            async with session_manager.get_session() as session:
                result = await _do_initialize(session)

        # 注册 SettlementEngine
        if main_engine and event_engine:
            try:
                # v3.2: 优先从 main_engine 获取 session factory（MainEngine.get_async_session），
                # 回退到全局 session_manager。修复此前 hasattr 永远为 False 导致 db_factory=None 的问题。
                if main_engine and hasattr(main_engine, "get_async_session"):
                    db_factory = main_engine.get_async_session()
                else:
                    from shared.database.session import get_session_manager
                    db_factory = get_session_manager().get_session
                settlement_engine = SettlementEngine(
                    config={"name": "settlement_engine"},
                    event_engine=event_engine,
                    db_session_factory=db_factory,
                )
                if hasattr(main_engine, "register_engine"):
                    main_engine.register_engine("settlement_engine", settlement_engine)
                await settlement_engine.start()
                logger.info("SettlementEngine 已注册并启动")

                # 注册日终结算调度（交易日 21:00）
                _register_daily_settlement_schedule(settlement_engine)
            except Exception as e:
                logger.warning(f"SettlementEngine 注册失败（非致命）: {e}")

        if result["success"]:
            print(f"✅ 账户模块初始化成功")
        else:
            print(f"⚠️  账户模块初始化警告: {result.get('message', '存在警告')}")

        return result["success"]

    except Exception as e:
        print(f"❌ 账户模块初始化失败: {str(e)}")
        logger.exception("账户模块初始化失败")
        return False


        # ===== 2026-08 C15：注册日终结算任务（依赖反转）=====
        if main_engine and hasattr(main_engine, "register_daily_task"):
            async def _task_settlement(today):
                from shared.database.session import get_session_manager
                from modules.account.tasks.settlement_tasks import create_settlement_tasks
                sm = get_session_manager()
                try:
                    async with sm.get_session() as _settle_session:
                        _st = create_settlement_tasks(_settle_session)
                        _sres = await _st.daily_settlement_task(today)
                        _sok = sum(
                            1 for r in _sres.get("results", {}).values()
                            if r.get("status") == "success"
                        )
                        logger.info("日终账户结算完成: 共 %s 账户, 成功 %s",
                            _sres.get("total_accounts", 0), _sok)
                except Exception as settle_err:
                    logger.error("日终账户结算失败: %s", settle_err, exc_info=True)

            await main_engine.register_daily_task("daily_settlement", _task_settlement, phase="pre_gate", order=40)

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
