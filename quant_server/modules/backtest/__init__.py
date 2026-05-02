"""
回测模块

负责策略回测、参数优化、绩效分析等功能。

引擎（均为按需计算引擎，不在 initialize 时自动启动）：
- BacktestEngine: 策略回测执行
- SimulationEngine: 交易模拟（市场/成本/滑点）
- OptimizationEngine: 策略参数优化（网格/遗传/贝叶斯）
- ReportEngine: 回测报告生成与导出

模块结构：
- engines/ analyzers/ optimizers/ simulators/ services/ events/ managers/ tasks/ utils/
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

__version__ = "1.0.0"
__author__ = "Quant System Team"

from .engines import (
    BacktestEngine,
    SimulationEngine,
    OptimizationEngine,
    ReportEngine,
)
from .services import (
    BacktestService,
    OptimizationService,
    ReportService,
)
from .analyzers import (
    PerformanceAnalyzer,
    RiskAnalyzer,
    TradeAnalyzer,
)
from .optimizers import (
    GridSearch,
    GeneticAlgorithm,
    BayesianOptimization,
)
from .simulators import (
    MarketSimulator,
    CostSimulator,
    SlippageSimulator,
)
from .managers import (
    TaskManager,
    ResourceManager,
)
from .tasks import (
    BacktestTask,
    OptimizationTask,
)
from .events import *
from . import schemas


async def initialize(
    main_engine=None,
    event_engine=None,
    config: Optional[Dict[str, Any]] = None,
) -> bool:
    """回测模块初始化

    执行启动前验证：检查必要数据库表是否存在，验证模块组件可用性。
    回测引擎为按需计算引擎，不在此处自动启动（与监控模块不同）。

    Args:
        main_engine: 主引擎实例
        event_engine: 事件引擎实例
        config: 模块配置

    Returns:
        bool: 初始化是否成功
    """
    try:
        logger.info("开始初始化回测模块...")

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
            print(f"✅ 回测模块初始化成功（{len(result.get('present_tables', []))}/{len(result.get('required_tables', []))} 张表）")
        else:
            print(f"⚠️  回测模块初始化警告: {result.get('message', '存在警告')}")

        return result["success"]

    except Exception as e:
        print(f"❌ 回测模块初始化失败: {str(e)}")
        logger.exception("回测模块初始化失败")
        return False


async def _do_initialize(session) -> Dict[str, Any]:
    """内部初始化逻辑：检查数据库表是否存在"""

    from sqlalchemy import inspect

    tables = await session.run_sync(
        lambda sync_session: inspect(sync_session.connection()).get_table_names()
    )

    required_tables = [
        "backtest_tasks",
        "backtest_equity_curves",
        "backtest_trades",
        "backtest_positions",
        "backtest_parameters",
        "backtest_scenarios",
        "backtest_comparisons",
        "backtest_resource_usage",
    ]

    present = [t for t in required_tables if t in tables]
    missing = [t for t in required_tables if t not in tables]

    if missing:
        logger.warning(f"回测模块缺少表: {missing}")
        return {
            "success": True,  # 允许降级运行，不阻塞其他模块启动
            "status": "degraded",
            "required_tables": required_tables,
            "present_tables": present,
            "missing_tables": missing,
            "message": f"缺少 {len(missing)} 张表，部分功能不可用: {missing}",
        }

    return {
        "success": True,
        "status": "ready",
        "required_tables": required_tables,
        "present_tables": present,
        "message": "回测模块就绪",
    }

async def shutdown(main_engine=None) -> None:
    """回测模块关闭函数"""
    logger.info("回测模块已关闭")


__all__ = [
    # 引擎
    "BacktestEngine",
    "SimulationEngine",
    "OptimizationEngine",
    "ReportEngine",
    
    # 服务
    "BacktestService",
    "OptimizationService",
    "ReportService",
    
    # 分析器
    "PerformanceAnalyzer",
    "RiskAnalyzer",
    "TradeAnalyzer",
    
    # 优化器
    "GridSearch",
    "GeneticAlgorithm",
    "BayesianOptimization",
    
    # 模拟器
    "MarketSimulator",
    "CostSimulator",
    "SlippageSimulator",
    
    # 管理器
    "TaskManager",
    "ResourceManager",
    
    # 任务
    "BacktestTask",
    "OptimizationTask",
    
    # 其他
    "schemas",
    # 初始化函数
    "initialize",
    "shutdown",
]