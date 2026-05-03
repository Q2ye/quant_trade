# -*- coding: utf-8 -*-
"""
优化服务

负责处理优化相关的业务逻辑
"""
import logging
from typing import Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession

from core.engines.types.entities import EngineConfigEntity
from modules.backtest.engines.optimization_engine import OptimizationEngine
from modules.backtest.schemas import BacktestOptimizeRequest
from shared.database.repositories.strategy.backtest.task_repo import BacktestTaskRepository
from shared.database.repositories.strategy.management import StrategyRepository, \
	StrategyParameterRepository

logger = logging.getLogger(__name__)


class OptimizationService:
	"""
	优化服务

	负责处理优化相关的业务逻辑
	"""

	def __init__ (self, db: AsyncSession):
		"""
		初始化优化服务

		Args:
			db: 数据库会话
		"""
		self.db = db
		# 创建配置对象
		self.optimization_engine = OptimizationEngine(
			EngineConfigEntity(name="OptimizationEngine", engine_type="optimization"))

	@staticmethod
	async def create_optimization_task (request: BacktestOptimizeRequest, user_id: str) -> Dict[str, Any]:
		"""
		创建优化任务

		Args:
			request: 优化请求
			user_id: 用户ID

		Returns:
			优化任务信息
		"""
		try:
			# 由于OptimizationTask模型不存在，我们返回一个模拟的响应
			# 实际应用中需要创建对应的数据库模型
			import time
			task_id = str(int(time.time() * 1000))

			# 记录请求信息（使用参数）
			logger.info(f"创建优化任务: strategy_id={request.strategy_id}, user_id={user_id}")

			return {
				"task_id": task_id,
				"status": "pending"
			}
		except Exception as e:
			logger.error(f"创建优化任务失败: {str(e)}")
			raise

	@staticmethod
	async def get_optimization_task (task_id: str) -> Dict[str, Any]:
		"""
		获取优化任务详情

		Args:
			task_id: 任务ID

		Returns:
			优化任务详情
		"""
		try:
			# 由于OptimizationTask模型不存在，我们返回一个模拟的响应
			# 实际应用中需要从数据库获取
			logger.info(f"获取优化任务详情: task_id={task_id}")

			return {
				"id": task_id,
				"name": "Optimization Task",
				"strategy_id": 1,
				"start_date": "2023-01-01",
				"end_date": "2023-12-31",
				"initial_capital": 1000000.0,
				"parameters": {"param1": [1, 2, 3], "param2": [0.1, 0.2, 0.3]},
				"method": "grid",
				"status": "completed",
				"result": {"best_params": {"param1": 2, "param2": 0.2}, "best_score": 0.85},
				"created_at": "2023-01-01T00:00:00",
				"updated_at": "2023-01-02T00:00:00"
			}
		except Exception as e:
			logger.error(f"获取优化任务详情失败: {str(e)}")
			raise

	@staticmethod
	async def get_optimization_tasks (user_id: str, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
		"""
		获取优化任务列表

		Args:
			user_id: 用户ID
			skip: 跳过数量
			limit: 限制数量

		Returns:
			优化任务列表
		"""
		try:
			# 由于OptimizationTask模型不存在，我们返回一个模拟的响应
			# 实际应用中需要从数据库获取
			logger.info(f"获取优化任务列表: user_id={user_id}, skip={skip}, limit={limit}")

			return [{
				"id": "1",
				"name": "Optimization Task 1",
				"strategy_id": 1,
				"status": "completed",
				"created_at": "2023-01-01T00:00:00",
				"updated_at": "2023-01-02T00:00:00"
			}]
		except Exception as e:
			logger.error(f"获取优化任务列表失败: {str(e)}")
			raise

	@staticmethod
	async def cancel_optimization_task (task_id: str) -> Dict[str, Any]:
		"""
		取消优化任务

		Args:
			task_id: 任务ID

		Returns:
			取消结果
		"""
		try:
			# 由于OptimizationTask模型不存在，我们返回一个模拟的响应
			# 实际应用中需要从数据库获取并更新
			logger.info(f"取消优化任务: task_id={task_id}")

			return {
				"task_id": task_id,
				"status": "cancelled"
			}
		except Exception as e:
			logger.error(f"取消优化任务失败: {str(e)}")
			raise

	async def run_optimization (self, task_id: str) -> Dict[str, Any]:
		"""
		执行优化

		Args:
			task_id: 任务ID

		Returns:
			优化结果
		"""
		try:
			logger.info(f"执行优化任务: task_id={task_id}")

			# 初始化仓库
			task_repo = BacktestTaskRepository(self.db)
			strategy_repo = StrategyRepository(self.db)
			param_repo = StrategyParameterRepository(self.db)

			# 获取任务信息
			task = await task_repo.get(task_id)
			if not task:
				raise ValueError(f"优化任务不存在: {task_id}")

			# 获取策略信息
			strategy = await strategy_repo.get_by_id(task.strategy_id)
			if not strategy:
				raise ValueError(f"策略不存在: {task.strategy_id}")

			# 获取策略参数配置
			strategy_params = await param_repo.get_by_strategy_id(task.strategy_id)

			# 构建优化参数
			parameters = {}
			for param in strategy_params:
				# 获取验证规则
				validation_rules = param.validation_rules or {}
				
				# 根据参数类型构建参数范围
				if param.param_type == "int":
					# 整数参数：从最小值到最大值，步长为1
					min_val = int(validation_rules.get("min", 1))
					max_val = int(validation_rules.get("max", 10))
					parameters[param.param_name] = list(range(min_val, max_val + 1))
				elif param.param_type == "float":
					# 浮点数参数：从最小值到最大值，步长为0.1
					min_val = float(validation_rules.get("min", 0.1))
					max_val = float(validation_rules.get("max", 1.0))
					step = float(validation_rules.get("step", 0.1))
					parameters[param.param_name] = [
						round(min_val + i * step, 2)
						for i in range(int((max_val - min_val) / step) + 1)
					]
				elif param.param_type == "bool":
					# 布尔参数：True/False
					parameters[param.param_name] = [True, False]
				elif param.param_type in ["string", "enum"]:
					# 枚举参数：从验证规则中获取选项
					options = validation_rules.get("options", ["value1", "value2", "value3"])
					parameters[param.param_name] = options

			# 如果没有参数，使用默认参数
			if not parameters:
				logger.warning("未找到策略参数，使用默认参数")
				parameters = {
					"window": [5, 10, 20],
					"threshold": [0.01, 0.02, 0.05]
				}

			# 获取优化方法（从任务配置或使用默认值）
			method = "grid"
			if task.config and "optimization_method" in task.config:
				method = task.config["optimization_method"]

			# 执行优化
			result = await self.optimization_engine.optimize(
				strategy_id=str(task.strategy_id),
				parameters=parameters,
				method=method
			)

			# 更新任务结果
			await task_repo.update(task_id, {
				"result": result,
				"status": "completed"
			})

			logger.info(f"优化任务完成: task_id={task_id}")
			return result
		except Exception as e:
			logger.error(f"执行优化失败: {str(e)}")
			raise