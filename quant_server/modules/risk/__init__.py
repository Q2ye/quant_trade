# -*- coding: utf-8 -*-
"""
风控模块（Risk Module）

独立的风控模块，统一管理信号级风控检查和周期级风险巡检。

引擎：
- RiskEngine: 统一风控引擎（信号检查 + 周期巡检）

模块结构：
- constants: 常量定义（规则名枚举、默认阈值、告警级别）
- rules/: 14 条 RiskRule 实现（从 trade/rules/ 迁移）
- events/: 统一风控事件（全部继承 BaseEvent）
- services/: 无状态风控服务
- engines/: RiskEngine
- handlers: API 处理函数
- schemas: Pydantic API 模型

依赖方向：modules/risk/ → shared/ → core/
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

__version__ = "2.0.0"
__author__ = "量化交易系统团队"
__description__ = "量化交易平台风控模块（独立）"


async def initialize(
    main_engine=None,
    event_engine=None,
    config: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    风控模块初始化函数

    创建 RiskEngine 并注册到 MainEngine。
    RiskEngine 启动后自动加载 14 条规则并开始周期巡检。

    Args:
        main_engine: 主引擎实例
        event_engine: 事件引擎实例
        config: 模块配置

    Returns:
        bool: 初始化是否成功
    """
    cfg = config or {}
    risk_cfg = cfg.get("risk", {})

    try:
        logger.info("开始初始化风控模块 (v%s)...", __version__)

        from modules.risk.engines.risk_engine import RiskEngine

        # 获取 session_factory 和 threshold_repo
        session_factory = None
        if main_engine and hasattr(main_engine, "get_async_session"):
            session_factory = main_engine.get_async_session()

        threshold_repo = None
        try:
            from shared.database.repositories.analysis.monitor.monitor_threshold_repo import (
                MonitorThresholdRepository,
            )
            if session_factory:
                async with session_factory() as sess:
                    threshold_repo = MonitorThresholdRepository(sess)
        except ImportError:
            logger.debug("MonitorThresholdRepository 不可用，阈值检查使用默认值")

        # 尝试获取 PositionEngine（如果 trade 模块已初始化）
        position_engine = None
        if main_engine and hasattr(main_engine, "_module_engines"):
            position_engine = main_engine._module_engines.get("position_engine")

        # 创建 RiskEngine
        risk_engine = RiskEngine(
            config={
                "name": "risk_engine",
                "risk_check_enabled": risk_cfg.get(
                    "risk_check_enabled", True
                ),
                "risk_check_interval": risk_cfg.get(
                    "risk_check_interval", 60
                ),
                "initial_capital": risk_cfg.get("initial_capital", 1000000),
            },
            event_engine=event_engine,
            position_engine=position_engine,
            threshold_repo=threshold_repo,
            session_factory=session_factory,
        )

        # 注册到主引擎
        if main_engine and hasattr(main_engine, "_module_engines"):
            main_engine._module_engines["risk_engine"] = risk_engine

        # 同步注册到 EngineRegistry（供回测等独立模块查询）
        try:
            from core.engines.system.engine_registry import EngineRegistry
            from core.engines.types.enums import EngineCategory
            registry = EngineRegistry()
            await registry.register_engine(
                risk_engine,
                category=EngineCategory.TRADE,
                tags=["risk", "risk_engine"],
            )
        except Exception as e:
            logger.debug("注册到 EngineRegistry 失败（非致命）: %s", e)

        # 初始化并启动
        await risk_engine.initialize()
        await risk_engine.start()

        print(f"✅ 风控模块初始化成功 (v{__version__})")
        return True

    except Exception as e:
        print(f"❌ 风控模块初始化失败: {str(e)}")
        logger.exception("风控模块初始化失败")
        return False


async def shutdown(main_engine=None) -> None:
    """风控模块关闭函数"""
    try:
        if main_engine and hasattr(main_engine, "_module_engines"):
            risk_engine = main_engine._module_engines.pop("risk_engine", None)
            if risk_engine:
                await risk_engine.stop()
                logger.info("RiskEngine 已停止并注销")
    except Exception as e:
        logger.warning("停止 RiskEngine 失败: %s", e)

    logger.info("风控模块已关闭")
