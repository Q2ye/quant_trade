# -*- coding: utf-8 -*-
"""
资源管理器

负责管理回测过程中的资源
"""
import asyncio
import logging
import threading

logger = logging.getLogger(__name__)


class ResourceManager:
	"""
	资源管理器

	负责管理回测过程中的资源
	"""

	def __init__ (self, max_concurrent_tasks: int = 4):
		"""
		初始化资源管理器

		Args:
			max_concurrent_tasks: 最大并发任务数
		"""
		self.max_concurrent_tasks = max_concurrent_tasks
		self.active_tasks = 0
		self.task_semaphore = asyncio.Semaphore(max_concurrent_tasks)
		self.lock = threading.Lock()

	async def acquire_resource (self) -> bool:
		"""
		获取资源

		Returns:
			是否成功获取资源
		"""
		try:
			await self.task_semaphore.acquire()
			with self.lock:
				self.active_tasks += 1
			logger.info(f"获取资源成功，当前活跃任务数: {self.active_tasks}")
			return True
		except Exception as e:
			logger.error(f"获取资源失败: {str(e)}")
			return False

	def release_resource (self) -> bool:
		"""
		释放资源

		Returns:
			是否成功释放资源
		"""
		try:
			with self.lock:
				self.active_tasks -= 1
			self.task_semaphore.release()
			logger.info(f"释放资源成功，当前活跃任务数: {self.active_tasks}")
			return True
		except Exception as e:
			logger.error(f"释放资源失败: {str(e)}")
			return False

	def get_active_tasks (self) -> int:
		"""
		获取当前活跃任务数

		Returns:
			当前活跃任务数
		"""
		with self.lock:
			return self.active_tasks

	def get_available_resources (self) -> int:
		"""
		获取可用资源数

		Returns:
			可用资源数
		"""
		return self.max_concurrent_tasks - self.get_active_tasks()
