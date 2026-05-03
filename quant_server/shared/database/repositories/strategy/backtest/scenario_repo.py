# shared/database/repositories/strategy/backtest/scenario_repo.py
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, desc, func

from shared.database.models.business_models import BacktestScenario
from shared.database.repositories.base import BaseRepository


class BacktestScenarioRepository(BaseRepository[BacktestScenario]):
	"""回测场景数据仓库"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, BacktestScenario)

	async def get_by_scenario_id (self, scenario_id: str) -> Optional[BacktestScenario]:
		"""根据场景ID获取回测场景"""
		query = select(self.model).where(self.model.scenario_id == scenario_id)
		result = await self.session.execute(query)
		return result.scalars().first()

	async def get_user_scenarios (self, user_id: str, skip: int = 0,
	                              limit: int = 50) -> List[BacktestScenario]:
		"""获取用户创建的回测场景"""
		query = (
			select(self.model)
			.where(self.model.created_by == user_id)
			.order_by(desc(self.model.created_at))
			.offset(skip)
			.limit(limit)
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_public_scenarios (self, skip: int = 0, limit: int = 100) -> List[BacktestScenario]:
		"""获取公开的回测场景"""
		# 假设所有场景都是公开的，可以通过扩展字段控制
		query = (
			select(self.model)
			.order_by(desc(self.model.created_at))
			.offset(skip)
			.limit(limit)
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def search_scenarios (self, keyword: str, scenario_type: Optional[str] = None,
	                            skip: int = 0, limit: int = 50) -> List[BacktestScenario]:
		"""搜索回测场景"""
		query = select(self.model)

		# 关键词搜索（场景名称和描述）
		if keyword:
			keyword_pattern = f"%{keyword}%"
			query = query.where(
				and_(
					self.model.scenario_name.ilike(keyword_pattern) |
					self.model.description.ilike(keyword_pattern)
				)
			)

		# 类型筛选（可根据需要扩展）
		if scenario_type:
			# 这里可以根据market_conditions中的类型字段进行筛选
			pass

		query = query.order_by(desc(self.model.created_at)).offset(skip).limit(limit)
		result = await self.session.execute(query)
		return result.scalars().all()

	async def update_scenario (self, scenario_id: str, update_data: Dict[str, Any]) -> bool:
		"""更新回测场景"""
		stmt = (
			update(self.model)
			.where(self.model.scenario_id == scenario_id)
			.values(
				**update_data,
				updated_at=datetime.now()
			)
		)

		result = await self.session.execute(stmt)
		return result.rowcount > 0

	async def clone_scenario (self, source_scenario_id: str, new_name: str,
	                          new_description: Optional[str] = None,
	                          created_by: Optional[int] = None) -> Optional[BacktestScenario]:
		"""克隆回测场景"""
		source = await self.get_by_scenario_id(source_scenario_id)
		if not source:
			return None

		# 创建克隆场景
		import uuid
		from copy import deepcopy

		cloned_data = {
			"scenario_id": str(uuid.uuid4()),
			"scenario_name": new_name,
			"description": new_description or f"Cloned from {source.scenario_name}",
			"market_conditions": deepcopy(source.market_conditions),
			"economic_conditions": deepcopy(source.economic_conditions) if source.economic_conditions else {},
			"risk_factors": deepcopy(source.risk_factors) if source.risk_factors else {},
			"created_by": created_by or source.created_by,
			"created_at": datetime.now(),
			"updated_at": datetime.now()
		}

		cloned_scenario = self.model(**cloned_data)
		self.session.add(cloned_scenario)
		await self.session.flush()

		return cloned_scenario

	async def get_scenario_statistics (self) -> Dict[str, Any]:
		"""获取回测场景统计信息"""
		# 统计场景数量
		total_query = select(func.count()).select_from(self.model)
		total_result = await self.session.execute(total_query)
		total = total_result.scalar() or 0

		# 按创建人统计
		user_query = (
			select(
				self.model.created_by,
				func.count().label('count')
			)
			.group_by(self.model.created_by)
			.order_by(desc('count'))
			.limit(10)
		)

		user_result = await self.session.execute(user_query)
		top_users = [{"user_id": row.created_by, "count": row.count} for row in user_result.all()]

		# 按时间段统计
		time_query = (
			select(
				func.date_trunc('month', self.model.created_at).label('month'),
				func.count().label('count')
			)
			.group_by(func.date_trunc('month', self.model.created_at))
			.order_by(func.date_trunc('month', self.model.created_at).desc())
			.limit(12)
		)

		time_result = await self.session.execute(time_query)
		monthly_stats = [{"month": row.month, "count": row.count} for row in time_result.all()]

		return {
			"total_scenarios": total,
			"top_users": top_users,
			"monthly_stats": monthly_stats
		}