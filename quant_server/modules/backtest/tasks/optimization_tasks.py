# -*- coding: utf-8 -*-
"""
优化任务

负责定义优化任务
"""
import logging
from typing import Dict, Any

from core.engines import EngineConfigEntity
from modules.backtest.engines.optimization_engine import OptimizationEngine

logger = logging.getLogger(__name__)


class OptimizationTask:
	"""
	优化任务

	负责执行优化任务
	"""

	def __init__ (self, task_id: str, strategy_id: str, parameters: Dict[str, Any], method: str, start_date: str,
	              end_date: str, initial_capital: float):
		"""
		初始化优化任务

		Args:
			task_id: 任务ID
			strategy_id: 策略ID
			parameters: 优化参数
			method: 优化方法
			start_date: 开始日期
			end_date: 结束日期
			initial_capital: 初始资金
		"""
		self.task_id = task_id
		self.strategy_id = strategy_id
		self.parameters = parameters
		self.method = method
		self.start_date = start_date
		self.end_date = end_date
		self.initial_capital = initial_capital
		self.status = "pending"
		self.result = None

		# 初始化引擎 (使用正确的 EngineConfig 类型)
		optimization_config = EngineConfigEntity(
			name="optimization_engine",
			engine_type="optimization"
		)
		self.optimization_engine = OptimizationEngine(config=optimization_config)

	async def run (self) -> Dict[str, Any]:
		"""
		运行优化任务

		Returns:
			优化结果
		"""
		try:
			self.status = "running"
			logger.info(f"开始运行优化任务: {self.task_id}")

			# 执行优化
			optimization_result = await self.optimization_engine.optimize(
				strategy_id=self.strategy_id,
				parameters=self.parameters,
				method=self.method
			)

			self.result = optimization_result
			self.status = "completed"
			logger.info(f"优化任务完成: {self.task_id}")

			return self.result
		except Exception as e:
			self.status = "failed"
			logger.error(f"优化任务失败: {str(e)}")
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