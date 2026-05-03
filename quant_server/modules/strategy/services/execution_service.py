# -*- coding: utf-8 -*-
"""
策略执行服务
负责策略的启动、停止、暂停、恢复等运行控制
"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from modules.strategy.constants import (
	StrategyLifecycleStatus,
	RunMode,
	ErrorCode,
)
from modules.strategy.models import StrategyState
from shared.database.repositories.strategy.management import (
	StrategyRepository,
	StrategyRunRepository,
)

logger = logging.getLogger(__name__)


class ExecutionService:
	"""
	策略执行服务

	负责：
	- 策略启动/停止
	- 策略暂停/恢复
	- 运行状态管理
	- 持仓和资金管理
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化服务

		Args:
			session: 数据库会话
		"""
		self.session = session
		self.strategy_repo = StrategyRepository(session)
		self.strategy_run_repo = StrategyRunRepository(session)
		self._running_strategies: Dict[str, StrategyState] = {}

	async def start_strategy (
			self,
			strategy_id: str,
			user_id: str,
			capital: Optional[float] = None,
			parameters: Optional[Dict[str, Any]] = None,
			run_mode: RunMode = RunMode.SIMULATION,
	) -> Dict[str, Any]:
		"""
		启动策略

		Args:
			strategy_id: 策略ID
			user_id: 用户ID
			capital: 初始资金
			parameters: 运行参数
			run_mode: 运行模式

		Returns:
			启动结果
		"""
		try:
			# 获取策略
			strategy = await self.strategy_repo.get_by_id(strategy_id)
			if not strategy:
				return {
					"success": False,
					"error": f"策略 {strategy_id} 不存在",
					"error_code": ErrorCode.STRATEGY_NOT_FOUND
				}

			if strategy.user_id != user_id:
				return {
					"success": False,
					"error": "无权操作此策略",
					"error_code": ErrorCode.STRATEGY_NOT_FOUND
				}

			# 检查状态
			if strategy.status == StrategyLifecycleStatus.RUNNING:
				return {
					"success": False,
					"error": "策略已在运行中",
					"error_code": ErrorCode.STRATEGY_ALREADY_RUNNING
				}

			# 检查是否可启动
			if strategy.status not in [
				StrategyLifecycleStatus.COMPILED,
				StrategyLifecycleStatus.DEPLOYED,
				StrategyLifecycleStatus.PAUSED,
				StrategyLifecycleStatus.STOPPED,
			]:
				return {
					"success": False,
					"error": f"策略当前状态 {strategy.status} 无法启动",
					"error_code": ErrorCode.STRATEGY_NOT_RUNNING
				}

			# 获取或设置初始资金
			if capital is None:
				capital = 1000000.0

			if capital <= 0:
				return {
					"success": False,
					"error": "初始资金必须大于0",
					"error_code": ErrorCode.STRATEGY_INSUFFICIENT_CAPITAL
				}

			# 创建策略运行记录
			run_data = {
				"strategy_id": strategy_id,
				"run_mode": run_mode.value,
				"capital": capital,
				"status": "running",
				"started_at": datetime.now(),
				"parameters": parameters or {},
			}
			await self.strategy_run_repo.create(run_data)

			# 更新策略状态
			await self.strategy_repo.update(strategy_id, {
				"status": StrategyLifecycleStatus.RUNNING.value,
				"updated_at": datetime.now(),
			})

			# 初始化策略状态
			strategy_state = StrategyState(
				strategy_id=strategy_id,
				is_running=True,
				available_capital=capital,
				total_assets=capital,
			)
			self._running_strategies[strategy_id] = strategy_state

			await self.session.commit()

			logger.info(f"策略启动成功: {strategy_id}, 资金: {capital}")

			return {
				"success": True,
				"data": {
					"strategy_id": strategy_id,
					"run_id": run_data.get("id"),
					"status": "running",
					"capital": capital,
					"started_at": datetime.now().isoformat()
				}
			}
		except Exception as e:
			logger.error(f"启动策略失败: {e}")
			await self.session.rollback()
			return {
				"success": False,
				"error": str(e)
			}

	async def stop_strategy (
			self,
			strategy_id: str,
			user_id: str,
			force: bool = False,  # 未使用参数
	) -> Dict[str, Any]:
		"""
		停止策略

		Args:
			strategy_id: 策略ID
			user_id: 用户ID
			force: 是否强制停止

		Returns:
			停止结果
		"""
		try:
			# 获取策略
			strategy = await self.strategy_repo.get_by_id(strategy_id)
			if not strategy:
				return {
					"success": False,
					"error": f"策略 {strategy_id} 不存在",
					"error_code": ErrorCode.STRATEGY_NOT_FOUND
				}

			if strategy.user_id != user_id:
				return {
					"success": False,
					"error": "无权操作此策略",
					"error_code": ErrorCode.STRATEGY_NOT_FOUND
				}

			# 检查状态
			if strategy.status != StrategyLifecycleStatus.RUNNING:
				return {
					"success": False,
					"error": "策略不在运行中",
					"error_code": ErrorCode.STRATEGY_NOT_RUNNING
				}

			# 获取运行记录
			runs = await self.strategy_run_repo.get_by_strategy_id(strategy_id)
			active_run = None
			for run in runs:
				if run.status == "running":
					active_run = run
					break

			# 更新运行记录
			if active_run:
				await self.strategy_run_repo.update(active_run.id, {
					"status": "stopped",
					"stopped_at": datetime.now(),
				})

			# 计算绩效
			performance = await self._calculate_performance(strategy_id)

			# 更新策略状态
			await self.strategy_repo.update(strategy_id, {
				"status": StrategyLifecycleStatus.STOPPED.value,
				"updated_at": datetime.now(),
			})

			# 移除运行状态
			if strategy_id in self._running_strategies:
				del self._running_strategies[strategy_id]

			await self.session.commit()

			logger.info(f"策略停止成功: {strategy_id}")

			return {
				"success": True,
				"data": {
					"strategy_id": strategy_id,
					"status": "stopped",
					"performance": performance,
					"stopped_at": datetime.now().isoformat()
				}
			}
		except Exception as e:
			logger.error(f"停止策略失败: {e}")
			await self.session.rollback()
			return {
				"success": False,
				"error": str(e)
			}

	async def pause_strategy (
			self,
			strategy_id: str,
			user_id: str,
	) -> Dict[str, Any]:
		"""
		暂停策略

		Args:
			strategy_id: 策略ID
			user_id: 用户ID

		Returns:
			暂停结果
		"""
		try:
			strategy = await self.strategy_repo.get_by_id(strategy_id)
			if not strategy:
				return {
					"success": False,
					"error": f"策略 {strategy_id} 不存在"
				}

			if strategy.user_id != user_id:
				return {
					"success": False,
					"error": "无权操作此策略"
				}

			if strategy.status != StrategyLifecycleStatus.RUNNING:
				return {
					"success": False,
					"error": "策略不在运行中"
				}

			# 更新状态
			await self.strategy_repo.update(strategy_id, {
				"status": StrategyLifecycleStatus.PAUSED.value,
				"updated_at": datetime.now(),
			})

			# 更新运行状态
			if strategy_id in self._running_strategies:
				self._running_strategies[strategy_id].is_running = False

			await self.session.commit()

			return {
				"success": True,
				"data": {
					"strategy_id": strategy_id,
					"status": "paused"
				}
			}
		except Exception as e:
			logger.error(f"暂停策略失败: {e}")
			await self.session.rollback()
			return {
				"success": False,
				"error": str(e)
			}

	async def resume_strategy (
			self,
			strategy_id: str,
			user_id: str,
	) -> Dict[str, Any]:
		"""
		恢复策略

		Args:
			strategy_id: 策略ID
			user_id: 用户ID

		Returns:
			恢复结果
		"""
		try:
			strategy = await self.strategy_repo.get_by_id(strategy_id)
			if not strategy:
				return {
					"success": False,
					"error": f"策略 {strategy_id} 不存在"
				}

			if strategy.user_id != user_id:
				return {
					"success": False,
					"error": "无权操作此策略"
				}

			if strategy.status != StrategyLifecycleStatus.PAUSED:
				return {
					"success": False,
					"error": "策略不在暂停状态"
				}

			# 更新状态
			await self.strategy_repo.update(strategy_id, {
				"status": StrategyLifecycleStatus.RUNNING.value,
				"updated_at": datetime.now(),
			})

			# 更新运行状态
			if strategy_id in self._running_strategies:
				self._running_strategies[strategy_id].is_running = True

			await self.session.commit()

			return {
				"success": True,
				"data": {
					"strategy_id": strategy_id,
					"status": "running"
				}
			}
		except Exception as e:
			logger.error(f"恢复策略失败: {e}")
			await self.session.rollback()
			return {
				"success": False,
				"error": str(e)
			}

	async def get_strategy_status (
			self,
			strategy_id: str,
			user_id: str,
	) -> Dict[str, Any]:
		"""
		获取策略状态

		Args:
			strategy_id: 策略ID
			user_id: 用户ID

		Returns:
			策略状态
		"""
		try:
			strategy = await self.strategy_repo.get_by_id(strategy_id)
			if not strategy:
				return {
					"success": False,
					"error": f"策略 {strategy_id} 不存在"
				}

			if strategy.user_id != user_id:
				return {
					"success": False,
					"error": "无权访问此策略"
				}

			# 获取运行信息
			runs = await self.strategy_run_repo.get_by_strategy_id(strategy_id)
			active_run = None
			for run in runs:
				if run.status == "running":
					active_run = run
					break

			# 获取内存中的运行状态
			running_state = self._running_strategies.get(strategy_id)

			return {
				"success": True,
				"data": {
					"strategy_id": strategy_id,
					"name": strategy.name,
					"status": strategy.status,
					"is_running": strategy.status == StrategyLifecycleStatus.RUNNING,
					"run_id": active_run.id if active_run else None,
					"available_capital": running_state.available_capital if running_state else None,
					"total_assets": running_state.total_assets if running_state else None,
					"positions_count": len(running_state.positions) if running_state else 0,
					"started_at": active_run.started_at.isoformat() if active_run and active_run.started_at else None,
				}
			}
		except Exception as e:
			logger.error(f"获取策略状态失败: {e}")
			return {
				"success": False,
				"error": str(e)
			}

	async def get_running_strategies (self) -> List[StrategyState]:
		"""
		获取所有运行中的策略

		Returns:
			运行中的策略列表
		"""
		return list(self._running_strategies.values())

	async def _calculate_performance (self, strategy_id: str) -> Dict[str, Any]:
		"""
		计算策略绩效

		Args:
			strategy_id: 策略ID

		Returns:
			绩效数据
		"""
		# 获取运行记录
		runs = await self.strategy_run_repo.get_by_strategy_id(strategy_id)
		if not runs:
			return {}

		# 简化实现，实际需要根据成交记录计算
		return {
			"total_trades": 0,
			"winning_trades": 0,
			"losing_trades": 0,
			"total_pnl": 0.0,
		}