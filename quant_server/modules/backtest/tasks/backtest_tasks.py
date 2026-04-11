# -*- coding: utf-8 -*-
"""
回测任务

负责定义回测任务
"""
import logging
from typing import Dict, Any

from quant_server.core.engines.types.entities import EngineConfig
from quant_server.modules.backtest.engines.backtest_engine import BacktestEngine
from quant_server.modules.backtest.engines.report_engine import ReportEngine
from quant_server.modules.backtest.engines.simulation_engine import SimulationEngine

logger = logging.getLogger(__name__)


class BacktestTask:
	"""
	回测任务

	负责执行回测任务
	"""

	def __init__ (self, task_id: str, strategy_id: str, start_date: str, end_date: str, initial_capital: float):
		"""
		初始化回测任务

		Args:
			task_id: 任务ID
			strategy_id: 策略ID
			start_date: 开始日期
			end_date: 结束日期
			initial_capital: 初始资金
		"""
		self.task_id = task_id
		self.strategy_id = strategy_id
		self.start_date = start_date
		self.end_date = end_date
		self.initial_capital = initial_capital
		self.status = "pending"
		self.result = None

		# 初始化引擎 (使用正确的 EngineConfig 类型)
		backtest_config = EngineConfig(
			name="backtest_engine",
			engine_type="backtest"
		)
		simulation_config = EngineConfig(
			name="simulation_engine",
			engine_type="simulation"
		)
		report_config = EngineConfig(
			name="report_engine",
			engine_type="report"
		)
		
		self.backtest_engine = BacktestEngine(config=backtest_config)
		self.simulation_engine = SimulationEngine(config=simulation_config)
		self.report_engine = ReportEngine(config=report_config)

	async def run (self) -> Dict[str, Any]:
		"""
		运行回测任务

		Returns:
			回测结果
		"""
		try:
			self.status = "running"
			logger.info(f"开始运行回测任务: {self.task_id}")

			# 模拟回测数据
			data = {}
			
			# 模拟策略上下文
			from quant_server.modules.strategy.strategies.base.strategy_context import StrategyContext
			context = StrategyContext(
				strategy_id=self.strategy_id,
				strategy_name=f"Strategy_{self.strategy_id}",
				user_id="1",
				initial_capital=self.initial_capital
			)

			# 执行回测
			backtest_result = self.backtest_engine.run_backtest(
				strategy_id=self.strategy_id,
				data=data,
				context=context
			)

			# 生成报告
			report = self.report_engine.generate_report(backtest_result)

			# 合并结果
			self.result = {
				**backtest_result,
				"report": report
			}

			self.status = "completed"
			logger.info(f"回测任务完成: {self.task_id}")

			return self.result
		except Exception as e:
			self.status = "failed"
			logger.error(f"回测任务失败: {str(e)}")
			raise

	def get_status (self) -> str:
		"""
		获取任务状态

		Returns:
			任务状态
		"""
		return self.status

	def get_result (self) -> Dict[str, Any]:
		"""
		获取任务结果

		Returns:
			任务结果
		"""
		return self.result