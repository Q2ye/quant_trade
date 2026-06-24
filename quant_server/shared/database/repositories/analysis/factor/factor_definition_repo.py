# 文件: shared/database/repositories/market/factor_definition_repo.py
"""
因子定义Repository
负责factor_definitions表的数据访问操作
"""

from typing import Optional, List, Dict, Any

from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from shared.database.models.data_models import FactorDefinition
from shared.database.repositories.base import BaseRepository


class FactorDefinitionRepository(BaseRepository[FactorDefinition]):
	"""因子定义Repository"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, FactorDefinition)

	async def create_factor (
			self,
			factor_code: str,
			factor_name: str,
			factor_type: str,
			created_by: int,
			category: Optional[str] = None,
			description: Optional[str] = None,
			formula: Optional[str] = None,
			parameters: Optional[Dict[str, Any]] = None,
			data_requirements: Optional[Dict[str, Any]] = None,
			output_type: str = 'float',
			calculation_frequency: str = 'daily',
			is_public: bool = True,
			is_active: bool = True
	) -> FactorDefinition:
		"""创建因子定义"""
		factor_data = {
			'factor_code': factor_code,
			'factor_name': factor_name,
			'factor_type': factor_type,
			'created_by': created_by,
			'category': category,
			'description': description,
			'formula': formula,
			'parameters': self._dict_to_json(parameters) if parameters else None,
			'data_requirements': self._dict_to_json(data_requirements) if data_requirements else None,
			'output_type': output_type,
			'calculation_frequency': calculation_frequency,
			'is_public': is_public,
			'is_active': is_active
		}
		return await self.create(factor_data)

	async def get_by_code (self, factor_code: str) -> Optional[FactorDefinition]:
		"""根据因子代码获取因子定义"""
		stmt = select(FactorDefinition).where(FactorDefinition.factor_code == factor_code)
		result = await self.session.execute(stmt)
		return result.scalar_one_or_none()

	async def get_by_name (self, factor_name: str) -> Optional[FactorDefinition]:
		"""根据因子名称获取因子定义"""
		stmt = select(FactorDefinition).where(FactorDefinition.factor_name == factor_name).limit(1)
		result = await self.session.execute(stmt)
		return result.scalars().first()

	async def get_by_type (self, factor_type: str, is_active: bool = True) -> List[FactorDefinition]:
		"""根据因子类型获取因子列表"""
		stmt = select(FactorDefinition).where(
			and_(
				FactorDefinition.factor_type == factor_type,
				FactorDefinition.is_active == is_active
			)
		).order_by(FactorDefinition.factor_name)
		result = await self.session.execute(stmt)
		return result.scalars().all()

	async def get_by_category (self, category: str, is_active: bool = True) -> List[FactorDefinition]:
		"""根据因子类别获取因子列表"""
		stmt = select(FactorDefinition).where(
			and_(
				FactorDefinition.category == category,
				FactorDefinition.is_active == is_active
			)
		).order_by(FactorDefinition.factor_name)
		result = await self.session.execute(stmt)
		return result.scalars().all()

	async def get_public_factors (self, factor_type: Optional[str] = None) -> List[FactorDefinition]:
		"""获取公开因子列表"""
		conditions = [FactorDefinition.is_public == True, FactorDefinition.is_active == True]
		if factor_type:
			conditions.append(FactorDefinition.factor_type == factor_type)

		stmt = select(FactorDefinition).where(and_(*conditions)).order_by(FactorDefinition.factor_name)
		result = await self.session.execute(stmt)
		return result.scalars().all()

	async def get_user_factors (self, user_id: str, include_public: bool = True) -> List[FactorDefinition]:
		"""获取用户创建的因子列表（可选包含公开因子）"""
		conditions = [FactorDefinition.is_active == True]
		if include_public:
			conditions.append(
				or_(
					FactorDefinition.created_by == user_id,
					FactorDefinition.is_public == True
				)
			)
		else:
			conditions.append(FactorDefinition.created_by == user_id)

		stmt = select(FactorDefinition).where(and_(*conditions)).order_by(FactorDefinition.factor_name)
		result = await self.session.execute(stmt)
		return result.scalars().all()

	async def search_factors (
			self,
			keyword: Optional[str] = None,
			factor_type: Optional[str] = None,
			category: Optional[str] = None,
			is_public: Optional[bool] = None,
			is_active: Optional[bool] = True,
			offset: int = 0,
			limit: int = 100
	) -> List[FactorDefinition]:
		"""搜索因子定义"""
		conditions = []

		if keyword:
			conditions.append(
				or_(
					FactorDefinition.factor_code.ilike(f'%{keyword}%'),
					FactorDefinition.factor_name.ilike(f'%{keyword}%'),
					FactorDefinition.description.ilike(f'%{keyword}%')
				)
			)

		if factor_type:
			conditions.append(FactorDefinition.factor_type == factor_type)

		if category:
			conditions.append(FactorDefinition.category == category)

		if is_public is not None:
			conditions.append(FactorDefinition.is_public == is_public)

		if is_active is not None:
			conditions.append(FactorDefinition.is_active == is_active)

		stmt = select(FactorDefinition).where(and_(*conditions))
		stmt = stmt.order_by(FactorDefinition.factor_name).offset(offset).limit(limit)
		result = await self.session.execute(stmt)
		return result.scalars().all()

	async def update_factor (
			self,
			factor_id: str,
			**kwargs
	) -> Optional[FactorDefinition]:
		"""更新因子定义"""
		# 处理JSON字段
		if 'parameters' in kwargs and isinstance(kwargs['parameters'], dict):
			kwargs['parameters'] = self._dict_to_json(kwargs['parameters'])

		if 'data_requirements' in kwargs and isinstance(kwargs['data_requirements'], dict):
			kwargs['data_requirements'] = self._dict_to_json(kwargs['data_requirements'])

		return await self.update(factor_id, **kwargs)

	async def deactivate_factor (self, factor_id: str) -> bool:
		"""停用因子"""
		stmt = update(FactorDefinition).where(
			FactorDefinition.id == factor_id
		).values(is_active=False, updated_at=func.now())

		result = await self.session.execute(stmt)
		await self.session.commit()
		return result.rowcount > 0

	async def activate_factor (self, factor_id: str) -> bool:
		"""激活因子"""
		stmt = update(FactorDefinition).where(
			FactorDefinition.id == factor_id
		).values(is_active=True, updated_at=func.now())

		result = await self.session.execute(stmt)
		await self.session.commit()
		return result.rowcount > 0

	async def get_factor_statistics (self) -> Dict[str, Any]:
		"""获取因子统计信息"""
		# 按类型统计
		stmt_type = select(
			FactorDefinition.factor_type,
			func.count(FactorDefinition.id).label('count')
		).where(
			FactorDefinition.is_active == True
		).group_by(FactorDefinition.factor_type)

		result_type = await self.session.execute(stmt_type)
		type_stats = {row[0]: row[1] for row in result_type.all()}

		# 按类别统计
		stmt_category = select(
			FactorDefinition.category,
			func.count(FactorDefinition.id).label('count')
		).where(
			FactorDefinition.is_active == True,
			FactorDefinition.category.isnot(None)
		).group_by(FactorDefinition.category)

		result_category = await self.session.execute(stmt_category)
		category_stats = {row[0]: row[1] for row in result_category.all()}

		# 总数统计
		stmt_total = select(func.count(FactorDefinition.id)).where(FactorDefinition.is_active == True)
		result_total = await self.session.execute(stmt_total)
		total_count = result_total.scalar()

		# 公开因子数
		stmt_public = select(func.count(FactorDefinition.id)).where(
			FactorDefinition.is_active == True,
			FactorDefinition.is_public == True
		)
		result_public = await self.session.execute(stmt_public)
		public_count = result_public.scalar()

		return {
			'total': total_count,
			'public': public_count,
			'private': total_count - public_count,
			'by_type': type_stats,
			'by_category': category_stats
		}

	def _dict_to_json (self, parameters):
		pass
