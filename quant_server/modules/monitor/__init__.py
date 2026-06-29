# -*- coding: utf-8 -*-
"""
监控模块

负责系统资源监控、风险阈值检查、业务指标聚合和告警管理。

引擎：
- SystemMonitorEngine: 定时采集 OS 资源指标
- RiskMonitorEngine: → 已迁移到 modules.risk（定时检查风险指标突破）
- BusinessMonitorEngine: 定时聚合业务指标
- AlertEngine: 告警生命周期管理（创建/分发/通知）

模块间通过 EventEngine 异步通信，禁止直接 import。
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

__version__ = "1.0.0"
__author__ = "量化交易系统团队"
__description__ = "量化交易平台监控模块"


async def initialize(
    main_engine=None,
    event_engine=None,
    config: Optional[Dict[str, Any]] = None,
) -> bool:
    """监控模块初始化函数

    符合主启动框架接口规范，创建并启动所有监控子引擎，
    注册到 main_engine 中。

    Args:
        main_engine: 主引擎实例
        event_engine: 事件引擎实例
        config: 模块配置

    Returns:
        bool: 初始化是否成功
    """
    cfg = config or {}
    monitor_cfg = cfg  # config 本身就是 monitor 模块平铺配置

    try:
        logger.info("开始初始化监控模块...")

        from modules.monitor.engines import (
            SystemMonitorEngine,
            RiskMonitorEngine,
            BusinessMonitorEngine,
            AlertEngine,
        )

        engines_initialized = 0
        engines_total = 4

        # 1. 系统监控引擎
        try:
            sys_engine = SystemMonitorEngine(
                config={
                    "name": "system_monitor",
                    "system_collect_interval": monitor_cfg.get(
                        "system_collect_interval", 30
                    ),
                },
                event_engine=event_engine,
            )
            if main_engine and hasattr(main_engine, '_module_engines'):
                main_engine._module_engines["system_monitor"] = sys_engine
            await sys_engine.initialize()
            await sys_engine.start()
            engines_initialized += 1
            logger.info("SystemMonitorEngine 启动成功")
        except Exception as e:
            logger.error(f"SystemMonitorEngine 启动失败: {e}")

        # 2. 风险监控引擎 → 已迁移到 modules.risk
        #    由 modules/risk/__init__.py 的 initialize() 统一管理 RiskEngine
        #    此处不再独立创建，仅尝试导入确认模块可用
        try:
            from modules.risk.engines.risk_engine import RiskEngine  # noqa: F401
            logger.info("RiskEngine 由 modules.risk 模块管理，monitor 不再独立创建")
            engines_initialized += 1
        except ImportError:
            logger.warning("modules.risk 不可用，回退到独立 RiskMonitorEngine")
            try:
                risk_engine = RiskMonitorEngine(
                    config={
                        "name": "risk_monitor",
                        "risk_check_interval": monitor_cfg.get("risk_check_interval", 60),
                    },
                    event_engine=event_engine,
                )
                if main_engine and hasattr(main_engine, '_module_engines'):
                    main_engine._module_engines["risk_monitor"] = risk_engine
                await risk_engine.initialize()
                await risk_engine.start()
                engines_initialized += 1
                logger.info("RiskMonitorEngine（回退模式）启动成功")
            except Exception as e2:
                logger.error(f"RiskMonitorEngine 启动失败: {e2}")

        # 3. 业务监控引擎
        try:
            biz_engine = BusinessMonitorEngine(
                config={
                    "name": "business_monitor",
                    "business_metrics_interval": monitor_cfg.get(
                        "business_metrics_interval", 300
                    ),
                },
                event_engine=event_engine,
            )
            if main_engine and hasattr(main_engine, '_module_engines'):
                main_engine._module_engines["business_monitor"] = biz_engine
            await biz_engine.initialize()
            await biz_engine.start()
            engines_initialized += 1
            logger.info("BusinessMonitorEngine 启动成功")
        except Exception as e:
            logger.error(f"BusinessMonitorEngine 启动失败: {e}")

        # 4. 告警引擎
        try:
            # v2.3: 注入 session_factory
            try:
                from shared.database.session.session_manager import get_session_manager
                sm = get_session_manager()
                db_session_factory = sm.get_session if sm else None
            except Exception:
                db_session_factory = None

            alert_engine = AlertEngine(
                config={
                    "name": "alert_engine",
                    "max_retries": 3,
                    "retry_delay": 1.0,
                    "monitor": {"config": monitor_cfg},
                },
                event_engine=event_engine,
                db_session_factory=db_session_factory,
            )
            if main_engine and hasattr(main_engine, '_module_engines'):
                main_engine._module_engines["alert_engine"] = alert_engine
            await alert_engine.initialize()
            await alert_engine.start()
            engines_initialized += 1
            logger.info("AlertEngine 启动成功")
        except Exception as e:
            logger.error(f"AlertEngine 启动失败: {e}")

        success = engines_initialized > 0
        if success:
            print(f"✅ 监控模块初始化成功: {engines_initialized}/{engines_total} 个引擎已启动")
        else:
            print("❌ 监控模块初始化失败: 没有引擎成功启动")

        return success

    except Exception as e:
        print(f"❌ 监控模块初始化失败: {str(e)}")
        logger.exception("监控模块初始化失败")
        return False


async def shutdown(main_engine=None) -> None:
    """监控模块关闭函数 — 停止所有引擎并从主引擎注销"""
    engine_names = [
        "system_monitor",
        "risk_monitor",
        "business_monitor",
        "alert_engine",
    ]
    for name in engine_names:
        try:
            if main_engine and hasattr(main_engine, '_module_engines'):
                engine = main_engine._module_engines.pop(name, None)
                if engine:
                    await engine.stop()
                    logger.info(f"已停止引擎: {name}")
        except Exception as e:
            logger.warning(f"停止引擎 {name} 失败: {e}")

    logger.info("监控模块已关闭")
