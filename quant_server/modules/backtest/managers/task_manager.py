# -*- coding: utf-8 -*-
"""
任务管理器

负责管理回测和优化任务
"""
import logging
import asyncio
from typing import Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from modules.backtest.managers.resource_manager import ResourceManager
from modules.backtest.tasks.backtest_tasks import BacktestTask
from modules.backtest.tasks.optimization_tasks import OptimizationTask
from modules.backtest.services.backtest_service import BacktestService
from modules.backtest.services.optimization_service import OptimizationService

logger = logging.getLogger(__name__)


class TaskManager:
	"""
	任务管理器

	负责管理回测和优化任务
	"""

	def __init__ (self, db: AsyncSession):
		"""
		初始化任务管理器

		Args:
			db: 数据库会话
		"""
		self.db = db
		self.backtest_service = BacktestService(db)
		self.optimization_service = OptimizationService(db)
		self.resource_manager = ResourceManager()
		self.running_tasks = {}

	async def submit_backtest_task (self, task_id: str) -> bool:
		"""
		提交回测任务

		Args:
			task_id: 任务ID

		Returns:
			是否提交成功
		"""
		try:
			# 检查资源
			if not await self.resource_manager.acquire_resource():
				logger.warning(f"资源不足，无法提交回测任务: {task_id}")
				return False

			# 执行回测
			async def run_task ():
				try:
					await self.backtest_service.run_backtest(task_id)
				finally:
					self.resource_manager.release_resource()

			# 启动任务
			task = asyncio.create_task(run_task())
			self.running_tasks[task_id] = task

			logger.info(f"提交回测任务成功: {task_id}")
			return True
		except Exception as e:
			logger.error(f"提交回测任务失败: {str(e)}")
			self.resource_manager.release_resource()
			return False

	async def submit_optimization_task (self, task_id: str) -> bool:
		"""
		提交优化任务

		Args:
			task_id: 任务ID

		Returns:
			是否提交成功
		"""
		try:
			# 检查资源
			if not await self.resource_manager.acquire_resource():
				logger.warning(f"资源不足，无法提交优化任务: {task_id}")
				return False

			# 执行优化
			async def run_task ():
				try:
					await self.optimization_service.run_optimization(task_id)
				finally:
					self.resource_manager.release_resource()

			# 启动任务
			task = asyncio.create_task(run_task())
			self.running_tasks[task_id] = task

			logger.info(f"提交优化任务成功: {task_id}")
			return True
		except Exception as e:
			logger.error(f"提交优化任务失败: {str(e)}")
			self.resource_manager.release_resource()
			return False

	async def cancel_task (self, task_id: str) -> bool:
		"""
		取消任务

		Args:
			task_id: 任务ID

		Returns:
			是否取消成功
		"""
		try:
			# 检查任务是否在运行
			if task_id in self.running_tasks:
				task = self.running_tasks[task_id]
				task.cancel()
				del self.running_tasks[task_id]
				self.resource_manager.release_resource()
				logger.info(f"取消任务成功: {task_id}")
				return True
			else:
				# 任务不在运行，更新状态
				# 检查是回测任务还是优化任务
				backtest_task = await self.db.get(BacktestTask, task_id)
				if backtest_task:
					backtest_task.status = "cancelled"
					await self.db.commit()
					logger.info(f"取消回测任务成功: {task_id}")
					return True

				optimization_task = await self.db.get(OptimizationTask, task_id)
				if optimization_task:
					optimization_task.status = "cancelled"
					await self.db.commit()
					logger.info(f"取消优化任务成功: {task_id}")
					return True

				logger.warning(f"任务不存在: {task_id}")
				return False
		except Exception as e:
			logger.error(f"取消任务失败: {str(e)}")
			return False

	def get_running_tasks (self) -> List[str]:
		"""
		获取运行中的任务

		Returns:
			运行中的任务ID列表
		"""
		return list(self.running_tasks.keys())

	def get_resource_status (self) -> Dict[str, int]:
		"""
		获取资源状态

		Returns:
			资源状态
		"""
		return {
			"active_tasks": self.resource_manager.get_active_tasks(),
			"available_resources": self.resource_manager.get_available_resources(),
			"max_concurrent_tasks": self.resource_manager.max_concurrent_tasks
		}