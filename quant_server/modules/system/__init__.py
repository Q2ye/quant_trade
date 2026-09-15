# -*- coding: utf-8 -*-
"""
系统模块
负责用户权限、任务调度、全局配置、日志管理等基础服务

模块结构：
- constants: 常量定义
- models: 业务DTO
- events: 事件定义
- services: 业务服务（user/auth/role/config/task/log）
- auth: 认证授权（jwt/authentication/authorization）
- managers: 资源管理器（含 ConfigManager 配置热加载）
- tasks: 定时任务
- handlers: API处理函数
- utils: 工具函数

v2.0: ConfigManager 已支持热更新事件推送（set → ConfigUpdatedEvent）
"""

import logging

from . import constants
from . import models
from . import events
from . import services
from . import auth
from . import managers
from . import handlers
from . import utils

logger = logging.getLogger(__name__)

__version__ = "2.0.0"
__author__ = "量化交易系统团队"
__description__ = "量化交易系统管理模块（用户/权限/配置/调度）"

# 全局 ConfigManager 实例（供其他模块获取）
_config_manager_instance = None


def get_config_manager():
    """获取全局 ConfigManager 实例"""
    return _config_manager_instance


async def shutdown() -> None:
    """系统模块关闭函数"""
    global _config_manager_instance
    if _config_manager_instance:
        try:
            await _config_manager_instance.stop_watcher()
        except Exception as e:
            logger.warning("停止配置监听失败: %s", e)
    _config_manager_instance = None
    logger.info("系统模块已关闭")


async def initialize(
    main_engine=None,
    event_engine=None,
    config=None,
) -> bool:
    """
    系统模块初始化函数（最先被调用，提供基础服务）

    v2.0: 初始化 ConfigManager 并启动配置热加载监听。

    Args:
        main_engine: 主引擎实例
        event_engine: 事件引擎实例
        config: 模块配置

    Returns:
        bool: 初始化是否成功
    """
    global _config_manager_instance
    success = False
    init_result = {}

    try:
        logger.info("开始初始化系统模块 (v%s)...", __version__)

        # 获取 session
        if main_engine and hasattr(main_engine, 'get_async_session'):
            factory = main_engine.get_async_session()
            async with factory() as session:
                init_result = await _initialize_system_module(session, config or {})
            success = init_result.get('status') != 'failed'
        else:
            from shared.database.session import get_session_manager
            session_manager = get_session_manager()
            async with session_manager.get_session() as session:
                init_result = await _initialize_system_module(session, config or {})
                success = init_result.get('status') != 'failed'

        # 2026-09-15：注册「日志归档」日终任务（详见 scripts/ops/archive_logs.py）
        # ⚠️ 放在 **pre_gate order=1** 而不是 post_gate：
        #    post_gate 阶段在「数据完整性门」失败时会被**整体跳过**
        #    （`main_engine.py:241-243`：gate_ok=False → 直接 return）。
        #    日志归档是**幂等的运维任务**，与数据是否完整无关，必须每天必跑。
        #    order=1 让它排在数据同步（sync_daily=10）之前 —— 归档的是「今天之前」的日志。
        # ⚠️ 非致命：任何异常都只 warning，绝不影响日终流水线。
        if success and main_engine and hasattr(main_engine, "register_daily_task"):
            async def _task_archive_logs(today):
                """日终日志归档：决策日志按月合并（永久）+ 系统日志超期清理。"""
                import subprocess as _sp
                import sys as _sys
                from pathlib import Path as _P
                _script = _P(__file__).resolve().parents[2] / "scripts" / "ops" / "archive_logs.py"
                if not _script.exists():
                    logger.warning("日志归档脚本不存在，跳过: %s", _script)
                    return
                _py = _P(_sys.executable)
                try:
                    _p = _sp.run([str(_py), str(_script), "--apply"],
                                 capture_output=True, text=True, timeout=300,
                                 encoding="utf-8", errors="replace")
                    if _p.returncode == 0:
                        _tail = [l for l in (_p.stdout or "").splitlines() if l.strip()][-1:]
                        logger.info("日终日志归档完成: %s", _tail[0] if _tail else "ok")
                    else:
                        logger.warning("日终日志归档返回码 %s: %s",
                                       _p.returncode, (_p.stderr or "")[:300])
                except Exception as _e:
                    logger.warning("日终日志归档失败（非致命）: %s", _e)

            try:
                await main_engine.register_daily_task(
                    "archive_logs", _task_archive_logs, phase="pre_gate", order=1)
                logger.info("已注册日终任务: archive_logs (pre_gate, order=1)")
            except Exception as e:
                logger.warning("注册日志归档任务失败（非致命）: %s", e)

        # v2.0: 初始化配置管理器（含热加载）
        if success and event_engine:
            try:
                from shared.database.session import get_session_manager
                sm = get_session_manager()
                _config_manager_instance = managers.config_manager.ConfigManager(
                    session_factory=sm.get_session,
                    event_engine=event_engine,
                )
                await _config_manager_instance.refresh()
                await _config_manager_instance.start_watcher()
                logger.info("ConfigManager 已初始化（热加载就绪）")
            except Exception as e:
                logger.warning("ConfigManager 初始化失败: %s", e)

        if success:
            print(f"✅ 系统模块初始化成功: {init_result.get('message', '完成')}")
        else:
            print(f"⚠️  系统模块初始化警告: {init_result.get('message', '存在警告')}")

        return success

    except Exception as e:
        pass  # logged below
        logger.exception("系统模块初始化失败")
        return False


async def _initialize_system_module(session, config: dict) -> dict:
    """
    系统模块内部初始化逻辑

    Args:
        session: 数据库会话
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
            "sys_users",
            "sys_roles",
            "sys_user_roles",
            "system_configs",
            "system_logs",
        ]

        missing_tables = [t for t in required_tables if t not in tables]

        if missing_tables:
            logger.warning("系统模块缺少表: %s", missing_tables)
            return {
                "status": "degraded",
                "missing_tables": missing_tables,
                "message": "系统模块初始化完成，但缺少必要的表",
            }

        # 2. 检查数据库连接
        await session.execute(text("SELECT 1"))

        # 3. 加载全局配置
        logger.info("系统模块初始化完成")

        return {
            "status": "success",
            "message": "系统模块初始化完成",
            "loaded_components": ["auth", "user", "role", "config_watcher"],
        }

    except Exception as e:
        logger.error("系统模块初始化失败: %s", str(e))
        return {
            "status": "failed",
            "message": f"系统模块初始化失败: {str(e)}",
        }


__all__ = [
    "constants",
    "models",
    "events",
    "services",
    "auth",
    "managers",
    "handlers",
    "utils",
    "initialize",
    "shutdown",
    "get_config_manager",
]
