# -*- coding: utf-8 -*-
"""
策略参数配置表Repository
位置：shared/database/repositories/strategy/strategy_parameter_repo.py
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_, func, asc, case
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.business_models import StrategyParameter
from quant_server.shared.database.repositories.base import BaseRepository, RepositoryError


class StrategyParameterRepository(BaseRepository[StrategyParameter]):
	"""策略参数配置Repository"""

	def __init__ (self, session: AsyncSession):
		"""初始化Repository"""
		super().__init__(session, StrategyParameter)

	async def create_parameter (
			self,
			strategy_id: str,
			param_name: str,
			param_type: str,
			param_value: Any,
			description: Optional[str] = None,
			is_required: bool = True,
			validation_rules: Optional[Dict[str, Any]] = None
	) -> StrategyParameter:
		"""
		创建策略参数

		Args:
			strategy_id: 策略ID
			param_name: 参数名称
			param_type: 参数类型（int/float/string/bool/list/dict）
			param_value: 参数值
			description: 参数描述
			is_required: 是否必填
			validation_rules: 验证规则

		Returns:
			策略参数记录
		"""
		try:
			data = {
				"strategy_id": strategy_id,
				"param_name": param_name,
				"param_type": param_type,
				"param_value": param_value,
				"description": description,
				"is_required": is_required,
				"validation_rules": validation_rules or {}
			}

			return await self.create(data)
		except Exception as e:
			raise RepositoryError(f"创建策略参数失败: {str(e)}")

	async def batch_create_parameters (
			self,
			strategy_id: str,
			parameters: List[Dict[str, Any]]
	) -> List[StrategyParameter]:
		"""
		批量创建策略参数

		Args:
			strategy_id: 策略ID
			parameters: 参数列表

		Returns:
			创建的参数列表
		"""
		try:
			created_params = []

			for param_data in parameters:
				param = await self.create_parameter(
					strategy_id=strategy_id,
					param_name=param_data.get("param_name", ""),
					param_type=param_data.get("param_type", "string"),
					param_value=param_data.get("param_value"),
					description=param_data.get("description"),
					is_required=param_data.get("is_required", True),
					validation_rules=param_data.get("validation_rules")
				)
				created_params.append(param)

			return created_params
		except Exception as e:
			raise RepositoryError(f"批量创建策略参数失败: {str(e)}")

	async def get_by_strategy_id (
			self,
			strategy_id: str,
			param_type: Optional[str] = None,
			is_required: Optional[bool] = None
	) -> List[StrategyParameter]:
		"""
		根据策略ID获取参数

		Args:
			strategy_id: 策略ID
			param_type: 参数类型
			is_required: 是否必填

		Returns:
			策略参数列表
		"""
		try:
			query = select(self.model).where(
				self.model.strategy_id == strategy_id
			)

			if param_type:
				query = query.where(self.model.param_type == param_type)
			if is_required is not None:
				query = query.where(self.model.is_required == is_required)

			query = query.order_by(
				asc(self.model.param_name)
			)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取策略参数失败: {str(e)}")

	async def get_parameter (
			self,
			strategy_id: str,
			param_name: str
	) -> Optional[StrategyParameter]:
		"""
		获取特定参数

		Args:
			strategy_id: 策略ID
			param_name: 参数名称

		Returns:
			策略参数或None
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.strategy_id == strategy_id,
					self.model.param_name == param_name
				)
			)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()
		except Exception as e:
			raise RepositoryError(f"获取特定参数失败: {str(e)}")

	async def update_parameter_value (
			self,
			strategy_id: str,
			param_name: str,
			param_value: Any
	) -> Optional[StrategyParameter]:
		"""
		更新参数值

		Args:
			strategy_id: 策略ID
			param_name: 参数名称
			param_value: 参数值

		Returns:
			更新后的参数
		"""
		try:
			param = await self.get_parameter(strategy_id, param_name)
			if param:
				return await self.update(param.id, {
					"param_value": param_value,
					"updated_at": datetime.now()
				})
			return None
		except Exception as e:
			raise RepositoryError(f"更新参数值失败: {str(e)}")

	async def batch_update_parameters (
			self,
			strategy_id: str,
			param_updates: Dict[str, Any]
	) -> List[StrategyParameter]:
		"""
		批量更新参数值

		Args:
			strategy_id: 策略ID
			param_updates: 参数更新字典（参数名: 新值）

		Returns:
			更新后的参数列表
		"""
		try:
			updated_params = []

			for param_name, param_value in param_updates.items():
				param = await self.update_parameter_value(strategy_id, param_name, param_value)
				if param:
					updated_params.append(param)

			return updated_params
		except Exception as e:
			raise RepositoryError(f"批量更新参数失败: {str(e)}")

	async def get_parameters_as_dict (
			self,
			strategy_id: str
	) -> Dict[str, Any]:
		"""
		获取参数作为字典

		Args:
			strategy_id: 策略ID

		Returns:
			参数字典
		"""
		try:
			parameters = await self.get_by_strategy_id(strategy_id)

			param_dict = {}
			for param in parameters:
				param_dict[param.param_name] = param.param_value

			return param_dict
		except Exception as e:
			raise RepositoryError(f"获取参数字典失败: {str(e)}")

	async def get_required_parameters (
			self,
			strategy_id: str
	) -> List[StrategyParameter]:
		"""
		获取必填参数

		Args:
			strategy_id: 策略ID

		Returns:
			必填参数列表
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.strategy_id == strategy_id,
					self.model.is_required == True
				)
			).order_by(
				asc(self.model.param_name)
			)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取必填参数失败: {str(e)}")

	async def get_parameter_types_summary (
			self,
			strategy_id: str
	) -> Dict[str, Any]:
		"""
		获取参数类型摘要

		Args:
			strategy_id: 策略ID

		Returns:
			参数类型摘要
		"""
		try:
			query = select(
				self.model.param_type,
				func.count().label("count"),
				func.count(
					case((self.model.is_required == True, 1), else_=None)
				).label("required_count")
			).where(
				self.model.strategy_id == strategy_id
			).group_by(
				self.model.param_type
			)

			result = await self.session.execute(query)
			rows = result.fetchall()

			summary = {
				"total_parameters": 0,
				"required_parameters": 0,
				"by_type": {}
			}

			for row in rows:
				param_type = row.param_type
				count = row.count or 0
				required_count = row.required_count or 0

				summary["total_parameters"] += count
				summary["required_parameters"] += required_count

				summary["by_type"][param_type] = {
					"count": count,
					"required_count": required_count,
					"optional_count": count - required_count
				}

			summary["optional_parameters"] = summary["total_parameters"] - summary["required_parameters"]

			return summary
		except Exception as e:
			raise RepositoryError(f"获取参数类型摘要失败: {str(e)}")

	async def validate_parameters (
			self,
			strategy_id: str,
			parameters: Dict[str, Any]
	) -> Dict[str, Any]:
		"""
		验证参数

		Args:
			strategy_id: 策略ID
			parameters: 参数字典

		Returns:
			验证结果
		"""
		try:
			# 获取策略的所有参数定义
			param_definitions = await self.get_by_strategy_id(strategy_id)

			validation_result = {
				"valid": True,
				"errors": [],
				"warnings": [],
				"missing_required": [],
				"type_mismatches": []
			}

			param_def_dict = {p.param_name: p for p in param_definitions}

			# 检查所有定义中的必填参数
			for param_name, param_def in param_def_dict.items():
				if param_def.is_required and param_name not in parameters:
					validation_result["valid"] = False
					validation_result["missing_required"].append(param_name)
					validation_result["errors"].append(f"缺少必填参数: {param_name}")

			# 检查提供的参数
			for param_name, param_value in parameters.items():
				if param_name not in param_def_dict:
					validation_result["warnings"].append(f"未知参数: {param_name}")
					continue

				param_def = param_def_dict[param_name]

				# 类型检查
				expected_type = param_def.param_type
				if expected_type == "int":
					if not isinstance(param_value, int):
						validation_result["valid"] = False
						validation_result["type_mismatches"].append({
							"param_name": param_name,
							"expected": "int",
							"actual": type(param_value).__name__,
							"value": param_value
						})
						validation_result["errors"].append(
							f"参数 {param_name} 类型不匹配: 期望 int, 实际 {type(param_value).__name__}")
				elif expected_type == "float":
					if not isinstance(param_value, (int, float)):
						validation_result["valid"] = False
						validation_result["type_mismatches"].append({
							"param_name": param_name,
							"expected": "float",
							"actual": type(param_value).__name__,
							"value": param_value
						})
						validation_result["errors"].append(
							f"参数 {param_name} 类型不匹配: 期望 float, 实际 {type(param_value).__name__}")
				elif expected_type == "bool":
					if not isinstance(param_value, bool):
						validation_result["valid"] = False
						validation_result["type_mismatches"].append({
							"param_name": param_name,
							"expected": "bool",
							"actual": type(param_value).__name__,
							"value": param_value
						})
						validation_result["errors"].append(
							f"参数 {param_name} 类型不匹配: 期望 bool, 实际 {type(param_value).__name__}")
			# 其他类型检查可以根据需要添加

			return validation_result
		except Exception as e:
			raise RepositoryError(f"验证参数失败: {str(e)}")

	async def delete_by_strategy_id (self, strategy_id: str) -> int:
		"""
		根据策略ID删除所有参数

		Args:
			strategy_id: 策略ID

		Returns:
			删除的记录数
		"""
		try:
			from sqlalchemy import delete
			query = delete(self.model).where(
				self.model.strategy_id == strategy_id
			)
			result = await self.session.execute(query) # type:ignore
			return result.rowcount
		except Exception as e:
			raise RepositoryError(f"删除策略参数失败: {str(e)}")

	async def copy_parameters (
			self,
			source_strategy_id: str,
			target_strategy_id: str,
			overwrite_existing: bool = False
	) -> List[StrategyParameter]:
		"""
		复制参数到另一个策略

		Args:
			source_strategy_id: 源策略ID
			target_strategy_id: 目标策略ID
			overwrite_existing: 是否覆盖已存在的参数

		Returns:
			复制的参数列表
		"""
		try:
			source_params = await self.get_by_strategy_id(source_strategy_id)
			copied_params = []

			for source_param in source_params:
				# 检查目标策略是否已有同名参数
				existing_param = await self.get_parameter(target_strategy_id, source_param.param_name)

				if existing_param and not overwrite_existing:
					# 跳过已存在的参数
					continue

				if existing_param:
					# 更新现有参数
					updated_param = await self.update(existing_param.id, {
						"param_type": source_param.param_type,
						"param_value": source_param.param_value,
						"description": source_param.description,
						"is_required": source_param.is_required,
						"validation_rules": source_param.validation_rules,
						"updated_at": datetime.now()
					})
					copied_params.append(updated_param)
				else:
					# 创建新参数
					new_param = await self.create_parameter(
						strategy_id=target_strategy_id,
						param_name=source_param.param_name,
						param_type=source_param.param_type,
						param_value=source_param.param_value,
						description=source_param.description,
						is_required=source_param.is_required,
						validation_rules=source_param.validation_rules
					)
					copied_params.append(new_param)

			return copied_params
		except Exception as e:
			raise RepositoryError(f"复制参数失败: {str(e)}")
