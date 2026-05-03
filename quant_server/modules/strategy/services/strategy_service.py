# -*- coding: utf-8 -*-
"""
策略管理服务
负责策略的CRUD操作和基本管理
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from modules.strategy.constants import (
	StrategyType,
	StrategyLifecycleStatus,
	ErrorCode,
)
from shared.database.repositories.strategy.management import (
	StrategyRepository,
	StrategyVersionRepository,
	StrategyParameterRepository,
)
from shared.database.repositories.trading.position import PositionRepository

logger = logging.getLogger(__name__)


class StrategyService:
	"""
	策略管理服务

	负责：
	- 策略的增删改查
	- 策略版本管理
	- 策略参数管理
	- 策略编译和验证
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化服务

		Args:
			session: 数据库会话
		"""
		self.session = session
		self.strategy_repo = StrategyRepository(session)
		self.version_repo = StrategyVersionRepository(session)
		self.param_repo = StrategyParameterRepository(session)
		self.position_repo = PositionRepository(session)

	async def get_strategy_list (
			self,
			user_id: str,
			status: Optional[StrategyLifecycleStatus] = None,
			strategy_type: Optional[StrategyType] = None,
			page: int = 1,
			page_size: int = 20,
	) -> Dict[str, Any]:
		"""
		获取策略列表

		Args:
			user_id: 用户ID
			status: 状态筛选
			strategy_type: 策略类型筛选
			page: 页码
			page_size: 每页数量

		Returns:
			策略列表和分页信息
		"""
		try:
			# 确保分页参数有默认值
			page = page or 1
			page_size = page_size or 20

			# 构建过滤条件
			filters = {"user_id": user_id}
			if status:
				filters["status"] = status.value # type: ignore
			if strategy_type:
				filters["strategy_type"] = strategy_type.value # type: ignore

			# 使用 get_many 方法进行分页查询
			skip = (page - 1) * page_size

			# get_many 使用 **filters 关键字参数方式传递过滤条件
			strategies = await self.strategy_repo.get_many(
				skip=skip,
				limit=page_size,
				**filters
			)
			total = await self.strategy_repo.count(**filters)

			return {
				"success": True,
				"data": [self._to_dict(s) for s in strategies],
				"pagination": {
					"page": page,
					"page_size": page_size,
					"total": total,
					"total_pages": (total + page_size - 1) // page_size,
				}
			}
		except Exception as e:
			logger.error(f"获取策略列表失败: {e}")
			return {
				"success": False,
				"error": str(e),
				"data": [],
				"pagination": {"page": page, "page_size": page_size, "total": 0}
			}

	async def get_strategy_detail (
			self,
			strategy_id: str,
			user_id: str,
			include_positions: Optional[bool] = None,
	) -> Dict[str, Any]:
		"""
		获取策略详情

		Args:
			strategy_id: 策略ID
			user_id: 用户ID
			include_positions: 是否包含持仓信息

		Returns:
			策略详情
		"""
		try:
			strategy = await self.strategy_repo.get_by_id(strategy_id)
			if not strategy:
				return {
					"success": False,
					"error": f"策略 {strategy_id} 不存在",
					"error_code": ErrorCode.STRATEGY_NOT_FOUND
				}

			# 检查权限
			if strategy.user_id != user_id:
				return {
					"success": False,
					"error": "无权访问此策略",
					"error_code": ErrorCode.STRATEGY_NOT_FOUND
				}

			# 获取参数
			parameters = await self.param_repo.get_by_strategy_id(strategy_id)

			# 获取版本信息
			versions = await self.version_repo.get_by_strategy_id(strategy_id)

			# 构建返回数据
			result = {
				"id": strategy.id,
				"name": strategy.name,
				"description": strategy.description,
				"strategy_type": strategy.strategy_type,
				"status": strategy.status,
				"code": strategy.code,
				"parameters": {p.param_name: p.param_value for p in parameters},
				"versions": [self._version_to_dict(v) for v in versions],
				"created_at": strategy.created_at.isoformat() if strategy.created_at else None,
				"updated_at": strategy.updated_at.isoformat() if strategy.updated_at else None,
			}

			# 获取持仓信息
			if include_positions:
				try:
					# 获取用户的所有持仓（策略关联用户的持仓）
					positions = await self.position_repo.get_user_positions(
						user_id=user_id,
						include_zero=True
					)
					result["positions"] = [
						{
							"ts_code": p.ts_code,
							"volume": p.volume,
							"available_volume": p.available_volume,
							"frozen_volume": p.frozen_volume,
							"cost_price": float(p.cost_price) if p.cost_price else 0,
							"market_value": float(p.market_value) if p.market_value else 0,
							"last_price": float(p.last_price) if p.last_price else 0,
							"pnl": float(p.pnl) if p.pnl else 0,
							"pnl_rate": float(p.pnl_rate) if p.pnl_rate else 0,
							"last_update": p.last_update.isoformat() if p.last_update else None,
						}
						for p in positions
					]
				except Exception as pos_err:
					logger.warning(f"获取持仓信息失败: {pos_err}")
					result["positions"] = []

			return {
				"success": True,
				"data": result
			}
		except Exception as e:
			logger.error(f"获取策略详情失败: {e}")
			return {
				"success": False,
				"error": str(e)
			}

	async def create_strategy (
			self,
			name: str,
			strategy_type: StrategyType,
			code: str,
			description: str = "",
			parameters: Optional[Dict[str, Any]] = None,
			user_id: str = "0",
	) -> Dict[str, Any]:
		"""
		创建策略

		Args:
			name: 策略名称
			strategy_type: 策略类型
			code: 策略代码
			description: 策略描述
			parameters: 策略参数
			user_id: 用户ID

		Returns:
			创建结果
		"""
		try:
			# 验证策略代码
			validation_result = await self._validate_strategy_code(code)
			if not validation_result["valid"]:
				return {
					"success": False,
					"error": validation_result["error"],
					"error_code": ErrorCode.STRATEGY_COMPILE_ERROR
				}

			# 从代码中提取类名
			class_name = self._extract_class_name_from_code(code)

			# 创建策略
			strategy_data = {
				"name": name,
			"description": description,
			"strategy_type": strategy_type.value,
			"code": code,
			"class_name": class_name,
			"module_path": f"strategies.user_{user_id}.{class_name.lower()}",
			"status": StrategyLifecycleStatus.DRAFT.value,
				"user_id": user_id,
				"created_at": datetime.now(),
				"updated_at": datetime.now(),
			}

			strategy = await self.strategy_repo.create(strategy_data)

			# 保存参数
			if parameters:
				for key, value in parameters.items():
					# 根据值类型推断 param_type
					param_type = type(value).__name__
					if param_type == "int":
						param_type = "int"
					elif param_type == "float":
						param_type = "float"
					elif param_type == "bool":
						param_type = "bool"
					elif param_type == "str":
						param_type = "string"
					elif param_type == "list":
						param_type = "list"
					elif param_type == "dict":
						param_type = "dict"
					else:
						param_type = "string"

					await self.param_repo.create({
						"strategy_id": strategy.id,
						"param_name": key,
						"param_type": param_type,
						"param_value": value,
						"created_at": datetime.now(),
					})

			# 保存初始版本
			await self.version_repo.create({
				"strategy_id": strategy.id,
				"version_number": "1.0.0",
				"code_content": code,
				"description": "初始版本",
				"is_current": True,
				"created_at": datetime.now(),
			})

			await self.session.commit()

			logger.info(f"创建策略成功: {strategy.id}, {name}")

			return {
				"success": True,
				"data": {
					"id": strategy.id,
					"name": strategy.name,
					"status": strategy.status
				}
			}
		except Exception as e:
			logger.error(f"创建策略失败: {e}")
			await self.session.rollback()
			return {
				"success": False,
				"error": str(e)
			}

	async def update_strategy (
			self,
			strategy_id: str,
			user_id: str,
			name: Optional[str] = None,
			description: Optional[str] = None,
			code: Optional[str] = None,
			parameters: Optional[Dict[str, Any]] = None,
			status: Optional[StrategyLifecycleStatus] = None,
	) -> Dict[str, Any]:
		"""
		更新策略

		Args:
			strategy_id: 策略ID
			user_id: 用户ID
			name: 策略名称
			description: 策略描述
			code: 策略代码
			parameters: 策略参数
			status: 状态

		Returns:
			更新结果
		"""
		try:
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
					"error": "无权修改此策略",
					"error_code": ErrorCode.STRATEGY_NOT_FOUND
				}

			# 检查状态
			if strategy.status in [StrategyLifecycleStatus.RUNNING]:
				return {
					"success": False,
					"error": "策略运行中，无法修改",
					"error_code": ErrorCode.STRATEGY_NOT_RUNNING
				}

			# 更新字段
			update_data = {"updated_at": datetime.now()}
			if name:
				update_data["name"] = name # type: ignore
			if description is not None:
				update_data["description"] = description # type: ignore
			if code:
				# 验证代码
				validation_result = await self._validate_strategy_code(code)
				if not validation_result["valid"]:
					return {
						"success": False,
						"error": validation_result["error"],
						"error_code": ErrorCode.STRATEGY_COMPILE_ERROR
					}
				update_data["code"] = code # type: ignore

			if status:
				update_data["status"] = status.value # type: ignore

			await self.strategy_repo.update(strategy_id, update_data)

			# 更新参数
			if parameters:
				# 删除旧参数
				await self.param_repo.delete_by_strategy_id(strategy_id)
				# 添加新参数
				for key, value in parameters.items():
					# 根据值类型推断 param_type
					param_type = type(value).__name__
					if param_type == "int":
						param_type = "int"
					elif param_type == "float":
						param_type = "float"
					elif param_type == "bool":
						param_type = "bool"
					elif param_type == "str":
						param_type = "string"
					elif param_type == "list":
						param_type = "list"
					elif param_type == "dict":
						param_type = "dict"
					else:
						param_type = "string"

					await self.param_repo.create({
						"strategy_id": strategy_id,
						"param_name": key,
						"param_type": param_type,
						"param_value": value,
						"created_at": datetime.now(),
					})

			await self.session.commit()

			logger.info(f"更新策略成功: {strategy_id}")

			return {
				"success": True,
				"data": {"id": strategy_id}
			}
		except Exception as e:
			logger.error(f"更新策略失败: {e}")
			await self.session.rollback()
			return {
				"success": False,
				"error": str(e)
			}

	async def delete_strategy (
			self,
			strategy_id: str,
			user_id: str,
	) -> Dict[str, Any]:
		"""
		删除策略

		Args:
			strategy_id: 策略ID
			user_id: 用户ID

		Returns:
			删除结果
		"""
		try:
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
					"error": "无权删除此策略",
					"error_code": ErrorCode.STRATEGY_NOT_FOUND
				}

			if strategy.status == StrategyLifecycleStatus.RUNNING:
				return {
					"success": False,
					"error": "策略运行中，无法删除",
					"error_code": ErrorCode.STRATEGY_NOT_RUNNING
				}

			# 删除参数
			await self.param_repo.delete_by_strategy_id(strategy_id)

			# 删除版本
			# await self.version_repo.delete_by_strategy_id(strategy_id)

			# 删除策略
			await self.strategy_repo.delete(strategy_id)

			await self.session.commit()

			logger.info(f"删除策略成功: {strategy_id}")

			return {
				"success": True,
				"data": {"id": strategy_id}
			}
		except Exception as e:
			logger.error(f"删除策略失败: {e}")
			await self.session.rollback()
			return {
				"success": False,
				"error": str(e)
			}

	async def compile_strategy (
			self,
			strategy_id: str,
			user_id: str,
	) -> Dict[str, Any]:
		"""
		编译策略

		Args:
			strategy_id: 策略ID
			user_id: 用户ID

		Returns:
			编译结果
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

			# 验证代码
			validation_result = await self._validate_strategy_code(strategy.code)
			if not validation_result["valid"]:
				return {
					"success": False,
					"error": validation_result["error"]
				}

			# 更新状态为已编译
			await self.strategy_repo.update(strategy_id, {
				"status": str(StrategyLifecycleStatus.COMPILED.value),
				"updated_at": datetime.now()
			})

			await self.session.commit()

			return {
				"success": True,
				"data": {"id": strategy_id, "status": StrategyLifecycleStatus.COMPILED.value}
			}
		except Exception as e:
			logger.error(f"编译策略失败: {e}")
			await self.session.rollback()
			return {
				"success": False,
				"error": str(e)
			}

	@staticmethod
	async def _validate_strategy_code (code: str) -> Dict[str, Any]:
		"""
		验证策略代码

		Args:
			code: 策略代码

		Returns:
			验证结果
		"""
		try:
			# 基本语法检查
			compile(code, '<string>', 'exec')
			return {"valid": True}
		except SyntaxError as e:
			return {
				"valid": False,
				"error": f"代码语法错误: {e}"
			}
		except Exception as e:
			return {
				"valid": False,
				"error": f"验证失败: {str(e)}"
			}

	@staticmethod
	def _extract_class_name_from_code (code: str) -> str:
		"""
		从策略代码中提取类名

		Args:
			code: 策略代码

		Returns:
			类名
		"""
		import re
		# 匹配 class Xxx: 格式
		match = re.search(r'class\s+(\w+)\s*[(:]', code)
		if match:
			return match.group(1)
		# 如果没有找到类，默认使用 Strategy
		return "Strategy"

	@staticmethod
	def _to_dict (strategy) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"id": strategy.id,
			"name": strategy.name,
			"description": strategy.description,
			"strategy_type": strategy.strategy_type,
			"status": strategy.status,
			"created_at": strategy.created_at.isoformat() if strategy.created_at else None,
			"updated_at": strategy.updated_at.isoformat() if strategy.updated_at else None,
		}

	@staticmethod
	def _version_to_dict (version) -> Dict[str, Any]:
		"""版本转换为字典"""
		return {
			"id": version.id,
			"version": version.version_number,
			"description": version.description,
			"code_content": version.code_content,
			"is_current": version.is_current,
			"created_at": version.created_at.isoformat() if version.created_at else None,
		}