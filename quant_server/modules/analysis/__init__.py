#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析模块
负责绩效评估、归因分析、对比分析、交易分析等功能
"""

from .handlers import AnalysisHandler, check_analysis_module_health
from .models import (
    PerformanceMetrics,
    RiskMetrics,
    StrategyComparison,
    AttributionAnalysis,
    TradeAnalysis,
    AnalysisReport,
)
from .engines import AnalysisEngine
from .constants import (
    AnalysisModuleConstants,
    AnalysisType,
    ReportStatus,
    PERFORMANCE_METRICS,
    RISK_METRICS,
    ATTRIBUTION_METRICS,
)
from .events import *
from .schemas import *

__all__ = [
    "shutdown",
    "AnalysisHandler",
    "check_analysis_module_health",
    "PerformanceMetrics",
    "RiskMetrics",
    "StrategyComparison",
    "AttributionAnalysis",
    "TradeAnalysis",
    "AnalysisReport",
    "AnalysisEngine",
    "AnalysisModuleConstants",
    "AnalysisType",
    "ReportStatus",
    "PERFORMANCE_METRICS",
    "RISK_METRICS",
    "ATTRIBUTION_METRICS",
]

__version__ = "1.0.0"
__author__ = "量化平台团队"
__description__ = "量化交易平台分析模块"


async def initialize(
    main_engine=None, event_engine=None, _config=None,
) -> bool:
    """初始化分析模块"""
    import logging
    logger = logging.getLogger(__name__)

    # 预导入 — 将 import 提升到 try 外部，满足 linter 对 except 块可见性要求
    try:
        from shared.database.session import get_db_session
    except ImportError:
        get_db_session = None  # type: ignore

    try:
        from sqlalchemy import inspect

        # 表检查 — 使用会话管理器上下文
        if get_db_session is not None:
            try:
                async with get_db_session() as session:
                    tables = await session.run_sync(
                        lambda sync_session: inspect(sync_session.connection()).get_table_names()
                    )
                    required_tables = [
                        "strategies", "accounts", "positions",
                        "trades", "orders", "backtest_results",
                    ]
                    missing = [t for t in required_tables if t not in tables]
                    if missing:
                        logger.warning(f"分析模块缺少表: {missing}")
                    else:
                        logger.info("分析模块表检查通过")
            except Exception as e:
                logger.warning(f"表检查失败（非致命）: {e}")
        else:
            logger.warning("无法获取数据库会话，跳过表检查")

        if event_engine:
            from .engines import AnalysisEngine
            from shared.database.session import get_connection_pool

            pool = get_connection_pool()
            session_factory = pool.get_session_factory() if pool else None

            if session_factory:
                engine = AnalysisEngine(
                    event_engine=event_engine,
                    db_session_factory=session_factory,
                )
                if main_engine:
                    main_engine.register_engine("analysis", engine)
                logger.info("分析引擎已注册")
            else:
                logger.warning("数据库连接池未初始化，跳过分析引擎注册")

        return True

    except Exception as e:
        print(f"分析模块初始化失败: {str(e)}")
        logger.exception("分析模块初始化失败")
        return False


async def shutdown(main_engine=None) -> None:
    """分析模块关闭函数"""
    import logging
    logger = logging.getLogger(__name__)
    try:
        if main_engine is not None:
            engine = await main_engine.get_engine("analysis")
            if engine and hasattr(engine, 'stop'):
                await engine.stop()
                logger.info("已停止分析引擎")
    except Exception as e:
        logger.warning(f"停止分析引擎失败: {e}")
    logger.info("分析模块已关闭")
