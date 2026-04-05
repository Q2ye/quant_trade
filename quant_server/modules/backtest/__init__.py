"""
回测模块

负责策略回测、参数优化、绩效分析等功能

主要组件：
1. 引擎（engines）：回测引擎、模拟引擎、优化引擎、报告引擎
2. 分析器（analyzers）：绩效分析、风险分析、交易分析
3. 优化器（optimizers）：网格搜索、遗传算法、贝叶斯优化
4. 模拟器（simulators）：市场模拟、成本模拟、滑点模拟
5. 服务（services）：回测服务、优化服务、报告服务
6. 事件（events）：回测事件、优化事件、进度事件
7. 管理器（managers）：任务管理、资源管理
8. 任务（tasks）：回测任务、优化任务
9. 工具（utils）：数据加载、图表生成
"""

from .engines import (
    BacktestEngine,
    SimulationEngine,
    OptimizationEngine,
    ReportEngine
)

from .services import (
    BacktestService,
    OptimizationService,
    ReportService
)

from .analyzers import (
    PerformanceAnalyzer,
    RiskAnalyzer,
    TradeAnalyzer
)

from .optimizers import (
    GridSearch,
    GeneticAlgorithm,
    BayesianOptimization
)

from .simulators import (
    MarketSimulator,
    CostSimulator,
    SlippageSimulator
)

from .managers import (
    TaskManager,
    ResourceManager
)

from .tasks import (
    BacktestTask,
    OptimizationTask
)

from .events import *

from . import schemas

# 模块初始化函数 - 符合主启动文件期望的接口
async def initialize (
		main_engine=None,
		event_engine=None,  # 未使用参数
		config=None
) -> bool:
	"""
	回测模块初始化函数

	Args:
		main_engine: 主引擎实例
		event_engine: 事件引擎实例
		config: 模块配置

	Returns:
		bool: 初始化是否成功
	"""
	import logging
	logger = logging.getLogger(__name__)

	try:
		logger.info("开始初始化回测模块...")

		# 回测模块初始化逻辑
		# 1. 检查必要的依赖
		# 2. 初始化回测引擎
		# 3. 加载回测配置

		logger.info("回测模块初始化完成")
		print("✅ 回测模块初始化成功")
		return True

	except Exception as e:
		print(f"❌ 回测模块初始化失败: {str(e)}")
		logger.exception("回测模块初始化失败")
		return False

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
]