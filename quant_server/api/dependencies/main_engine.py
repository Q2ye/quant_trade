# quant_server/api/dependencies/main_engine.py
"""
主引擎依赖模块

提供FastAPI依赖注入的主引擎功能，作为系统的协调中心。
负责管理所有业务引擎的生命周期、协调模块间通信、系统状态管理等。

Author: 量化交易系统团队
Version: 1.0.0
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum

from fastapi import Depends

from quant_server.core.engines.system.main_engine import MainEngine
from quant_server.core.engines.system.engine_registry import EngineRegistry
from quant_server.api.dependencies.event_engine import (
	get_event_engine,
	publish_system_event,
	EventPriority
)
from quant_server.core.exceptions.event_exceptions import EventException

logger = logging.getLogger(__name__)


class SystemMode(Enum):
	"""系统运行模式"""
	BACKTEST = "backtest"  # 回测模式
	PAPER_TRADING = "paper"  # 模拟交易模式
	LIVE_TRADING = "live"  # 实盘交易模式
	MAINTENANCE = "maintenance"  # 维护模式


class MainEngineDependencies:
	"""主引擎依赖管理类"""

	def __init__ (self):
		"""初始化主引擎依赖"""
		self._main_engine: Optional[MainEngine] = None
		self._engine_registry: Optional[EngineRegistry] = None
		self._system_mode: SystemMode = SystemMode.PAPER_TRADING
		self._is_initialized = False
		self._startup_time: Optional[datetime] = None
		logger.info("主引擎依赖初始化完成")

	async def initialize (
			self,
			system_mode: SystemMode = SystemMode.PAPER_TRADING
	) -> bool:
		"""
		初始化主引擎依赖

		Args:
			system_mode: 系统运行模式

		Returns:
			bool: 初始化是否成功
		"""
		try:
			self._system_mode = system_mode
			self._startup_time = datetime.utcnow()

			# 获取引擎注册表
			self._engine_registry = EngineRegistry()

			# 获取主引擎实例
			engine_record = await self._engine_registry.get_engine("main_engine")

			if not engine_record or not engine_record.instance:
				logger.warning("主引擎未在注册表中找到，创建新实例")

				# 获取事件引擎依赖
				event_engine = await get_event_engine()

				# 创建主引擎实例
				self._main_engine = MainEngine(
					event_engine=event_engine,
					system_mode=system_mode.value
				)

				# 注册到引擎注册表
				await self._engine_registry.register_engine(
					name="main_engine",
					engine_type="main",
					instance=self._main_engine,
					metadata={"mode": system_mode.value}
				)
			else:
				self._main_engine = engine_record.instance

			# 初始化主引擎
			await self._main_engine.initialize()

			# 设置系统模式
			await self._main_engine.set_system_mode(system_mode.value)

			self._is_initialized = True

			# 发布系统启动事件
			await publish_system_event(
				event_type="ENGINE_INITIALIZED",
				data={
					"engine": "main_engine",
					"mode": system_mode.value,
					"startup_time": self._startup_time.isoformat()
				},
				priority=EventPriority.HIGH
			)

			logger.info(f"主引擎依赖初始化成功，模式: {system_mode.value}")
			return True

		except Exception as e:
			logger.error(f"主引擎依赖初始化失败: {str(e)}", exc_info=True)
			return False

	@property
	def main_engine (self) -> MainEngine:
		"""
		获取主引擎实例

		Returns:
			MainEngine: 主引擎实例

		Raises:
			EngineInitializationError: 主引擎未初始化
		"""
		if not self._main_engine or not self._is_initialized:
			raise EventException("主引擎未初始化")
		return self._main_engine

	async def get_main_engine (self) -> MainEngine:
		"""
		获取主引擎依赖

		Returns:
			MainEngine: 主引擎实例
		"""
		if not self._is_initialized:
			# 尝试初始化
			success = await self.initialize()
			if not success:
				raise EventException("主引擎初始化失败")

		return self.main_engine

	async def get_engine (self, engine_name: str) -> Any:
		"""
		通过主引擎获取其他引擎实例

		Args:
			engine_name: 引擎名称

		Returns:
			Any: 引擎实例

		Raises:
			EngineNotFoundError: 引擎未找到
		"""
		try:
			engine = await self.main_engine.get_engine(engine_name)

			if not engine:
				raise EventException(f"引擎未找到: {engine_name}")

			return engine

		except EventException:
			raise
		except Exception as e:
			logger.error(f"获取引擎失败: {engine_name}, 错误: {str(e)}")
			raise EventException(f"获取引擎失败: {str(e)}")

	async def start_engine (self, engine_name: str) -> bool:
		"""
		启动指定引擎

		Args:
			engine_name: 引擎名称

		Returns:
			bool: 是否启动成功
		"""
		try:
			success = await self.main_engine.start_engine(engine_name)

			if success:
				logger.info(f"引擎启动成功: {engine_name}")

				await publish_system_event(
					event_type="ENGINE_STARTED",
					data={
						"engine": engine_name,
						"timestamp": datetime.utcnow().isoformat()
					},
					priority=EventPriority.NORMAL
				)
			else:
				logger.warning(f"引擎启动失败: {engine_name}")

			return success

		except Exception as e:
			logger.error(f"启动引擎异常: {engine_name}, 错误: {str(e)}")
			return False

	async def stop_engine (self, engine_name: str) -> bool:
		"""
		停止指定引擎

		Args:
			engine_name: 引擎名称

		Returns:
			bool: 是否停止成功
		"""
		try:
			success = await self.main_engine.stop_engine(engine_name)

			if success:
				logger.info(f"引擎停止成功: {engine_name}")

				await publish_system_event(
					event_type="ENGINE_STOPPED",
					data={
						"engine": engine_name,
						"timestamp": datetime.utcnow().isoformat()
					},
					priority=EventPriority.NORMAL
				)
			else:
				logger.warning(f"引擎停止失败: {engine_name}")

			return success

		except Exception as e:
			logger.error(f"停止引擎异常: {engine_name}, 错误: {str(e)}")
			return False

	async def restart_engine (self, engine_name: str) -> bool:
		"""
		重启指定引擎

		Args:
			engine_name: 引擎名称

		Returns:
			bool: 是否重启成功
		"""
		try:
			# 先停止
			await self.stop_engine(engine_name)

			# 等待一段时间
			await asyncio.sleep(1)

			# 再启动
			success = await self.start_engine(engine_name)

			if success:
				logger.info(f"引擎重启成功: {engine_name}")

				await publish_system_event(
					event_type="ENGINE_RESTARTED",
					data={
						"engine": engine_name,
						"timestamp": datetime.utcnow().isoformat()
					},
					priority=EventPriority.NORMAL
				)

			return success

		except Exception as e:
			logger.error(f"重启引擎异常: {engine_name}, 错误: {str(e)}")
			return False

	async def get_engine_status (self, engine_name: str) -> Dict[str, Any]:
		"""
		获取引擎状态

		Args:
			engine_name: 引擎名称

		Returns:
			Dict[str, Any]: 引擎状态信息
		"""
		try:
			engine = await self.get_engine(engine_name)

			if hasattr(engine, 'get_status'):
				status = await engine.get_status()
			else:
				# 默认状态
				status = {
					"name": engine_name,
					"status": "unknown",
					"initialized": True,
					"timestamp": datetime.utcnow().isoformat()
				}

			# 添加引擎类信息
			status["engine_class"] = engine.__class__.__name__

			return status

		except EventException:
			return {
				"name": engine_name,
				"status": "not_found",
				"error": f"引擎未找到: {engine_name}",
				"timestamp": datetime.utcnow().isoformat()
			}
		except Exception as e:
			logger.error(f"获取引擎状态失败: {engine_name}, 错误: {str(e)}")
			return {
				"name": engine_name,
				"status": "error",
				"error": str(e),
				"timestamp": datetime.utcnow().isoformat()
			}

	async def get_all_engines_status (self) -> Dict[str, Dict[str, Any]]:
		"""
		获取所有引擎状态

		Returns:
			Dict[str, Dict[str, Any]]: 所有引擎状态字典
		"""
		try:
			if not self._engine_registry:
				return {}

			# 获取所有引擎记录
			all_engines = await self._engine_registry.get_all_engines()

			status_dict = {}
			for engine_name, record in all_engines.items():
				if record.instance:
					status = await self.get_engine_status(engine_name)
					status_dict[engine_name] = status

			return status_dict

		except Exception as e:
			logger.error(f"获取所有引擎状态失败: {str(e)}")
			return {}

	async def get_system_status (self) -> Dict[str, Any]:
		"""
		获取系统状态

		Returns:
			Dict[str, Any]: 系统状态信息
		"""
		try:
			# 获取所有引擎状态
			engines_status = await self.get_all_engines_status()

			# 计算统计信息
			total_engines = len(engines_status)
			running_engines = sum(
				1 for status in engines_status.values()
				if status.get("status") == "running"
			)
			error_engines = sum(
				1 for status in engines_status.values()
				if status.get("status") == "error"
			)

			# 系统状态
			system_health = "healthy"
			if error_engines > 0:
				system_health = "degraded"
			if running_engines == 0:
				system_health = "unhealthy"

			system_status = {
				"system_health": system_health,
				"system_mode": self._system_mode.value,
				"startup_time": self._startup_time.isoformat()
				if self._startup_time else None,
				"uptime": (
					(datetime.utcnow() - self._startup_time).total_seconds()
					if self._startup_time else 0
				),
				"engines": {
					"total": total_engines,
					"running": running_engines,
					"stopped": total_engines - running_engines,
					"error": error_engines
				},
				"engines_status": engines_status,
				"timestamp": datetime.utcnow().isoformat()
			}

			return system_status

		except Exception as e:
			logger.error(f"获取系统状态失败: {str(e)}")
			return {
				"system_health": "error",
				"error": str(e),
				"timestamp": datetime.utcnow().isoformat()
			}

	async def change_system_mode (self, new_mode: SystemMode) -> bool:
		"""
		切换系统运行模式

		Args:
			new_mode: 新的系统模式

		Returns:
			bool: 是否切换成功
		"""
		try:
			old_mode = self._system_mode

			# 通知所有引擎模式即将变更
			await publish_system_event(
				event_type="SYSTEM_MODE_CHANGING",
				data={
					"old_mode": old_mode.value,
					"new_mode": new_mode.value,
					"timestamp": datetime.utcnow().isoformat()
				},
				priority=EventPriority.HIGH
			)

			# 停止当前运行的所有引擎（根据模式切换策略）
			if new_mode == SystemMode.MAINTENANCE:
				# 维护模式下停止所有引擎
				engines_status = await self.get_all_engines_status()
				for engine_name in engines_status.keys():
					await self.stop_engine(engine_name)

			# 更新系统模式
			self._system_mode = new_mode
			await self.main_engine.set_system_mode(new_mode.value)

			# 发布模式变更完成事件
			await publish_system_event(
				event_type="SYSTEM_MODE_CHANGED",
				data={
					"old_mode": old_mode.value,
					"new_mode": new_mode.value,
					"timestamp": datetime.utcnow().isoformat()
				},
				priority=EventPriority.HIGH
			)

			logger.info(f"系统模式已变更: {old_mode.value} -> {new_mode.value}")
			return True

		except Exception as e:
			logger.error(f"切换系统模式失败: {str(e)}")

			# 发布模式变更失败事件
			await publish_system_event(
				event_type="SYSTEM_MODE_CHANGE_FAILED",
				data={
					"old_mode": old_mode.value,
					"new_mode": new_mode.value,
					"error": str(e),
					"timestamp": datetime.utcnow().isoformat()
				},
				priority=EventPriority.CRITICAL
			)

			return False

	async def execute_system_command (
			self,
			command: str,
			params: Optional[Dict[str, Any]] = None
	) -> Dict[str, Any]:
		"""
		执行系统命令

		Args:
			command: 命令名称
			params: 命令参数

		Returns:
			Dict[str, Any]: 命令执行结果
		"""
		try:
			result = await self.main_engine.execute_command(
				command=command,
				params=params or {}
			)

			logger.debug(f"系统命令执行成功: {command}")
			return result

		except Exception as e:
			logger.error(f"系统命令执行失败: {command}, 错误: {str(e)}")
			raise

	async def close (self):
		"""关闭主引擎依赖"""
		try:
			if self._main_engine:
				# 停止所有引擎
				engines_status = await self.get_all_engines_status()
				for engine_name, status in engines_status.items():
					if status.get("status") == "running":
						await self.stop_engine(engine_name)

				# 关闭主引擎
				await self._main_engine.close()

			self._is_initialized = False

			logger.info("主引擎依赖已关闭")

		except Exception as e:
			logger.error(f"关闭主引擎依赖失败: {str(e)}")


# 创建全局主引擎依赖实例
_main_engine_deps = MainEngineDependencies()

# 导出依赖函数
get_main_engine = _main_engine_deps.get_main_engine
get_engine = _main_engine_deps.get_engine
start_engine = _main_engine_deps.start_engine
stop_engine = _main_engine_deps.stop_engine
restart_engine = _main_engine_deps.restart_engine
get_engine_status = _main_engine_deps.get_engine_status
get_all_engines_status = _main_engine_deps.get_all_engines_status
get_system_status = _main_engine_deps.get_system_status
change_system_mode = _main_engine_deps.change_system_mode
execute_system_command = _main_engine_deps.execute_system_command

# 导出类型注解
MainEngineDep = Depends(get_main_engine)

# 导出系统模式枚举
SystemMode = SystemMode


async def initialize_main_engine (
		system_mode: SystemMode = SystemMode.PAPER_TRADING
) -> bool:
	"""
	初始化主引擎依赖（应用启动时调用）

	Args:
		system_mode: 系统运行模式

	Returns:
		bool: 初始化是否成功
	"""
	return await _main_engine_deps.initialize(system_mode)


async def close_main_engine ():
	"""关闭主引擎依赖（应用关闭时调用）"""
	await _main_engine_deps.close()


@asynccontextmanager
async def engine_context (engine_name: str):
	"""
	引擎上下文管理器

	确保引擎在上下文中正确启动和停止

	Args:
		engine_name: 引擎名称

	Yields:
		Any: 引擎实例
	"""
	try:
		# 启动引擎
		success = await start_engine(engine_name)

		if not success:
			raise EventException(f"引擎启动失败: {engine_name}")

		# 获取引擎实例
		engine = await get_engine(engine_name)

		yield engine

	finally:
		# 停止引擎
		await stop_engine(engine_name)


def require_engine (engine_name: str):
	"""
	创建引擎依赖装饰器/函数

	Args:
		engine_name: 需要的引擎名称

	Returns:
		Callable: 依赖函数
	"""

	async def dependency () -> Any:
		"""引擎依赖函数"""
		return await _main_engine_deps.get_engine(engine_name)

	return Depends(dependency)


# 常用引擎依赖快捷方式
def get_data_engine ():
	"""获取数据引擎依赖"""
	return require_engine("data_engine")


def get_strategy_engine ():
	"""获取策略引擎依赖"""
	return require_engine("strategy_engine")


def get_trade_engine ():
	"""获取交易引擎依赖"""
	return require_engine("trade_engine")


def get_backtest_engine ():
	"""获取回测引擎依赖"""
	return require_engine("backtest_engine")


# 导出快捷依赖
DataEngineDep = get_data_engine()
StrategyEngineDep = get_strategy_engine()
TradeEngineDep = get_trade_engine()
BacktestEngineDep = get_backtest_engine()