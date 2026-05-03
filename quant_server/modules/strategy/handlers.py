# -*- coding: utf-8 -*-
"""
策略模块API处理函数
负责处理HTTP请求，调用服务层完成业务逻辑
"""
import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.strategy.constants import (
	StrategyType,
	StrategyLifecycleStatus,
	RunMode,
)
from modules.strategy.services.execution_service import ExecutionService
from modules.strategy.services.strategy_service import StrategyService

logger = logging.getLogger(__name__)


class StrategyHandler:
	"""策略API处理器"""

	def __init__ (self, db: AsyncSession):
		self.db = db
		self.strategy_service = StrategyService(db)
		self.execution_service = ExecutionService(db)

	async def get_strategy_list (
			self,
			request,
			user_id: str
	) -> Dict[str, Any]:
		"""
		获取策略列表

		Args:
			request: 请求参数
			user_id: 用户ID

		Returns:
			策略列表
		"""
		try:
			# 转换状态
			status = None
			if hasattr(request, 'status') and request.status:
				try:
					status = StrategyLifecycleStatus(request.status)
				except ValueError:
					pass

			# 转换策略类型
			strategy_type = None
			if hasattr(request, 'strategy_type') and request.strategy_type:
				try:
					strategy_type = StrategyType(request.strategy_type)
				except ValueError:
					pass

			# 获取分页参数
			page = getattr(request, 'page', 1) if request else 1
			page_size = getattr(request, 'page_size', 20) if request else 20

			result = await self.strategy_service.get_strategy_list(
				user_id=user_id,
				status=status,
				strategy_type=strategy_type,
				page=page,
				page_size=page_size,
			)

			return result

		except Exception as e:
			logger.error(f"获取策略列表失败: {e}")
			return {
				"success": False,
				"error": str(e),
				"data": [],
				"pagination": {"page": 1, "page_size": 20, "total": 0}
			}

	async def get_strategy_detail (
			self,
			strategy_id: str,
			request,
			user_id: str
	) -> Dict[str, Any]:
		"""
		获取策略详情

		Args:
			strategy_id: 策略ID
			request: 请求参数
			user_id: 用户ID

		Returns:
			策略详情
		"""
		try:
			# 获取 include_positions 参数
			include_positions = getattr(request, 'include_positions', None) if request else None
			return await self.strategy_service.get_strategy_detail(
				strategy_id=strategy_id,
				user_id=user_id,
				include_positions=include_positions,
			)
		except Exception as e:
			logger.error(f"获取策略详情失败: {e}")
			return {
				"success": False,
				"error": str(e)
			}

	async def create_strategy (
			self,
			request,
			user_id: str
	) -> Dict[str, Any]:
		"""
		创建策略

		Args:
			request: 创建请求
			user_id: 用户ID

		Returns:
			创建结果
		"""
		try:
			# 转换策略类型
			strategy_type = StrategyType.CTA
			if hasattr(request, 'strategy_type') and request.strategy_type:
				try:
					strategy_type = StrategyType(request.strategy_type)
				except ValueError:
					pass

			# 创建策略
			result = await self.strategy_service.create_strategy(
				name=request.name,
				strategy_type=strategy_type,
				code=request.code or "",
				description=request.description or "",
				parameters=request.parameters or {},
				user_id=user_id,
			)

			return result

		except Exception as e:
			logger.error(f"创建策略失败: {e}")
			return {
				"success": False,
				"error": str(e)
			}

	async def update_strategy (
			self,
			strategy_id: str,
			request,
			user_id: str
	) -> Dict[str, Any]:
		"""
		更新策略

		Args:
			strategy_id: 策略ID
			request: 更新请求
			user_id: 用户ID

		Returns:
			更新结果
		"""
		try:
			# 转换状态
			status = None
			if hasattr(request, 'status') and request.status:
				try:
					status = StrategyLifecycleStatus(request.status)
				except ValueError:
					pass

			result = await self.strategy_service.update_strategy(
				strategy_id=strategy_id,
				user_id=user_id,
				name=request.name,
				description=request.description,
				code=request.code,
				parameters=request.parameters,
				status=status,
			)

			return result

		except Exception as e:
			logger.error(f"更新策略失败: {e}")
			return {
				"success": False,
				"error": str(e)
			}

	async def delete_strategy (
			self,
			strategy_id: str,
			user_id: str
	) -> None:
		"""
		删除策略

		Args:
			strategy_id: 策略ID
			user_id: 用户ID
		"""
		try:
			result = await self.strategy_service.delete_strategy(
				strategy_id=strategy_id,
				user_id=user_id,
			)

			if not result["success"]:
				raise HTTPException(
					status_code=400,
					detail=result.get("error", "删除失败")
				)

		except HTTPException:
			raise
		except Exception as e:
			logger.error(f"删除策略失败: {e}")
			raise HTTPException(status_code=500, detail=str(e))

	async def start_strategy (
			self,
			strategy_id: str,
			request,
			user_id: str,
			capital: float = None
	) -> Dict[str, Any]:
		"""
		启动策略

		Args:
			strategy_id: 策略ID
			request: 启动请求
			user_id: 用户ID
			capital: 初始资金（可选）

		Returns:
			启动结果
		"""
		try:
			# 获取参数，优先使用传入的 capital，其次从 request 获取
			if capital is None:
				if hasattr(request, 'capital') and request.capital:
					capital = request.capital

			parameters = {}
			if hasattr(request, 'parameters') and request.parameters:
				parameters = request.parameters

			result = await self.execution_service.start_strategy(
				strategy_id=strategy_id,
				user_id=user_id,
				capital=capital,
				parameters=parameters,
				run_mode=RunMode.SIMULATION,
			)

			return result

		except Exception as e:
			logger.error(f"启动策略失败: {e}")
			return {
				"success": False,
				"error": str(e)
			}

	async def stop_strategy (
			self,
			strategy_id: str,
			request,
			user_id: str,
			force: bool = None
	) -> Dict[str, Any]:
		"""
		停止策略

		Args:
			strategy_id: 策略ID
			request: 停止请求
			user_id: 用户ID
			force: 是否强制停止

		Returns:
			停止结果
		"""
		try:
			# 优先使用传入的 force 参数，其次从 request 获取
			if force is None:
				force = False
				if hasattr(request, 'force'):
					force = request.force

			result = await self.execution_service.stop_strategy(
				strategy_id=strategy_id,
				user_id=user_id,
				force=force,
			)

			return result

		except Exception as e:
			logger.error(f"停止策略失败: {e}")
			return {
				"success": False,
				"error": str(e)
			}

	async def get_strategy_performance (
			self,
			strategy_id: str,
			request,  # 未使用参数
			user_id: str
	) -> Dict[str, Any]:
		"""
		获取策略绩效

		Args:
			strategy_id: 策略ID
			request: 绩效请求
			user_id: 用户ID

		Returns:
			绩效数据
		"""
		try:
			# 先获取策略状态
			status_result = await self.execution_service.get_strategy_status(
				strategy_id=strategy_id,
				user_id=user_id,
			)

			if not status_result.get("success"):
				return status_result

			# 获取策略信息
			detail_result = await self.strategy_service.get_strategy_detail(
				strategy_id=strategy_id,
				user_id=user_id,
			)

			data = status_result.get("data", {})

			# 添加策略信息
			if detail_result.get("success"):
				data["strategy_name"] = detail_result["data"].get("name")
				data["strategy_type"] = detail_result["data"].get("strategy_type")

			# 添加绩效数据（实际需要从数据库查询）
			data["performance"] = {
				"total_return": 0.0,
				"annual_return": 0.0,
				"win_rate": 0.0,
				"max_drawdown": 0.0,
				"sharpe_ratio": 0.0,
			}

			return {
				"success": True,
				"data": data
			}

		except Exception as e:
			logger.error(f"获取策略绩效失败: {e}")
			return {
				"success": False,
				"error": str(e)
			}

	async def get_strategy_status (
			self,
			strategy_id: str,
			user_id: str
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
			return await self.execution_service.get_strategy_status(
				strategy_id=strategy_id,
				user_id=user_id,
			)
		except Exception as e:
			logger.error(f"获取策略状态失败: {e}")
			return {
				"success": False,
				"error": str(e)
			}


# ==================== 导出函数供router使用 ====================

async def get_strategy_list (session: AsyncSession, request, user_id: str):
	handler = StrategyHandler(session)
	return await handler.get_strategy_list(request, user_id)


async def get_strategy_detail (session: AsyncSession, strategy_id: str, request, user_id: str):
	handler = StrategyHandler(session)
	return await handler.get_strategy_detail(strategy_id, request, user_id)


async def create_strategy (session: AsyncSession, request, user_id: str):
	handler = StrategyHandler(session)
	return await handler.create_strategy(request, user_id)


async def update_strategy (session: AsyncSession, strategy_id: str, request, user_id: str):
	handler = StrategyHandler(session)
	return await handler.update_strategy(strategy_id, request, user_id)


async def delete_strategy (session: AsyncSession, strategy_id: str, user_id: str):
	handler = StrategyHandler(session)
	return await handler.delete_strategy(strategy_id, user_id)


async def start_strategy (session: AsyncSession, strategy_id: str, request, user_id: str, capital: float = None):
	handler = StrategyHandler(session)
	return await handler.start_strategy(strategy_id, request, user_id, capital)


async def stop_strategy (session: AsyncSession, strategy_id: str, request, user_id: str, force: bool = None):
	handler = StrategyHandler(session)
	return await handler.stop_strategy(strategy_id, request, user_id, force)


async def get_strategy_performance (session: AsyncSession, strategy_id: str, request, user_id: str):
	handler = StrategyHandler(session)
	return await handler.get_strategy_performance(strategy_id, request, user_id)


async def get_strategy_status (session: AsyncSession, strategy_id: str, user_id: str):
	handler = StrategyHandler(session)
	return await handler.get_strategy_status(strategy_id, user_id)


async def check_strategy_module_health (session: AsyncSession) -> Dict[str, Any]:
	"""检查策略模块健康状态"""
	try:
		# 简单检查数据库连接
		await session.execute(text("SELECT 1"))

		return {
			"status": "healthy",
			"module": "strategy",
			"timestamp": datetime.now().isoformat()
		}
	except Exception as e:
		logger.error(f"策略模块健康检查失败: {e}")
		return {
			"status": "unhealthy",
			"module": "strategy",
			"error": str(e),
			"timestamp": datetime.now().isoformat()
		}
