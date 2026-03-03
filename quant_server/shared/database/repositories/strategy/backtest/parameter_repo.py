# shared/database/repositories/strategy/backtest/parameter_repo.py
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

from quant_server.shared.database.models.business_models import BacktestParameter
from quant_server.shared.database.repositories.base import BaseRepository


class BacktestParameterRepository(BaseRepository[BacktestParameter]):
	"""回测参数配置数据仓库"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, BacktestParameter)

	async def get_task_parameters (self, task_id: str,
	                               category: Optional[str] = None) -> List[BacktestParameter]:
		"""获取回测任务的参数配置"""
		query = select(self.model).where(self.model.task_id == task_id)

		if category:
			query = query.where(self.model.param_category == category)

		query = query.order_by(self.model.param_category, self.model.param_name)
		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_parameters_by_category (self, task_id: str, category: str) -> Dict[str, Any]:
		"""按分类获取参数配置"""
		query = (
			select(self.model)
			.where(
				and_(
					self.model.task_id == task_id,
					self.model.param_category == category
				)
			)
			.order_by(self.model.param_name)
		)

		result = await self.session.execute(query)
		parameters = result.scalars().all()

		# 转换为字典格式
		param_dict = {}
		for param in parameters:
			param_dict[param.param_name] = param.param_value

		return param_dict

	async def get_all_parameters_dict (self, task_id: str) -> Dict[str, Dict[str, Any]]:
		"""获取所有参数配置（按分类组织）"""
		query = (
			select(self.model)
			.where(self.model.task_id == task_id)
			.order_by(self.model.param_category, self.model.param_name)
		)

		result = await self.session.execute(query)
		parameters = result.scalars().all()

		# 按分类组织参数
		categorized_params = {}
		for param in parameters:
			if param.param_category not in categorized_params:
				categorized_params[param.param_category] = {}

			categorized_params[param.param_category][param.param_name] = param.param_value

		return categorized_params

	async def update_parameter (self, task_id: str, category: str, name: str,
	                            value: Any, description: Optional[str] = None) -> bool:
		"""更新参数配置"""
		# 先检查是否存在
		existing = await self.get_by_filters(
			task_id=task_id,
			param_category=category,
			param_name=name
		)

		if existing:
			# 更新现有参数
			update_data = {"param_value": value, "updated_at": datetime.now()}
			if description:
				update_data["description"] = description

			stmt = (
				update(self.model)
				.where(
					and_(
						self.model.task_id == task_id,
						self.model.param_category == category,
						self.model.param_name == name
					)
				)
				.values(**update_data)
			)
		else:
			# 创建新参数
			param_data = {
				"task_id": task_id,
				"param_category": category,
				"param_name": name,
				"param_value": value,
				"description": description or "",
				"created_at": datetime.now()
			}

			instance = self.model(**param_data)
			self.session.add(instance)

		await self.session.flush()
		return True

	async def batch_update_parameters (self, task_id: str, parameters: Dict[str, Dict[str, Any]]) -> int:
		"""批量更新参数配置"""
		count = 0
		now = datetime.now()

		for category, param_dict in parameters.items():
			for name, value in param_dict.items():
				# 检查是否存在
				existing = await self.get_by_filters(
					task_id=task_id,
					param_category=category,
					param_name=name
				)

				if existing:
					# 更新
					stmt = (
						update(self.model)
						.where(
							and_(
								self.model.task_id == task_id,
								self.model.param_category == category,
								self.model.param_name == name
							)
						)
						.values(param_value=value, updated_at=now)
					)
					await self.session.execute(stmt)
				else:
					# 创建
					instance = self.model(
						task_id=task_id,
						param_category=category,
						param_name=name,
						param_value=value,
						description=f"Auto-generated at {now}",
						created_at=now
					)
					self.session.add(instance)

				count += 1

		await self.session.flush()
		return count