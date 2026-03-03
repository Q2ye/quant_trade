# -*- coding: utf-8 -*-
"""
策略组合关联表Repository
位置：shared/database/repositories/strategy/portfolio_strategy_repo.py
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc, case
from sqlalchemy.orm import joinedload

from quant_server.core.exceptions import ValidationError
from quant_server.shared.database.models.business_models import PortfolioStrategy
from quant_server.shared.database.repositories.base import BaseRepository, RepositoryError


class PortfolioStrategyRepository(BaseRepository[PortfolioStrategy]):
	"""策略组合关联Repository"""

	def __init__ (self, session: AsyncSession):
		"""初始化Repository"""
		super().__init__(session, PortfolioStrategy)

	async def add_strategy_to_portfolio (
			self,
			portfolio_id: str,
			strategy_id: str,
			weight: float = 0.0,
			allocation: Optional[Decimal] = None,
			is_active: bool = True
	) -> PortfolioStrategy:
		"""
		添加策略到组合

		Args:
			portfolio_id: 组合ID
			strategy_id: 策略ID
			weight: 权重（0-1）
			allocation: 分配资金
			is_active: 是否激活

		Returns:
			组合策略关联记录
		"""
		try:
			# 检查权重范围
			if weight < 0 or weight > 1:
				raise ValidationError("权重必须在0-1之间")

			data = {
				"portfolio_id": portfolio_id,
				"strategy_id": strategy_id,
				"weight": weight,
				"allocation": allocation,
				"is_active": is_active
			}

			return await self.create(data)
		except Exception as e:
			if isinstance(e, ValidationError):
				raise e
			raise RepositoryError(f"添加策略到组合失败: {str(e)}")

	async def get_by_portfolio_id (
			self,
			portfolio_id: str,
			is_active: Optional[bool] = None,
			include_strategy: bool = False
	) -> List[PortfolioStrategy]:
		"""
		根据组合ID获取策略

		Args:
			portfolio_id: 组合ID
			is_active: 是否激活
			include_strategy: 是否包含策略信息

		Returns:
			组合策略关联列表
		"""
		try:
			if include_strategy:
				query = select(self.model).options(
					joinedload(self.model.strategy)
				)
			else:
				query = select(self.model)

			query = query.where(
				self.model.portfolio_id == portfolio_id
			)

			if is_active is not None:
				query = query.where(self.model.is_active == is_active)

			query = query.order_by(
				desc(self.model.weight)
			)

			result = await self.session.execute(query)

			if include_strategy:
				return result.unique().scalars().all()
			else:
				return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取组合策略失败: {str(e)}")

	async def get_by_strategy_id (
			self,
			strategy_id: str,
			is_active: Optional[bool] = None
	) -> List[PortfolioStrategy]:
		"""
		根据策略ID获取组合关联

		Args:
			strategy_id: 策略ID
			is_active: 是否激活

		Returns:
			组合策略关联列表
		"""
		try:
			query = select(self.model).where(
				self.model.strategy_id == strategy_id
			)

			if is_active is not None:
				query = query.where(self.model.is_active == is_active)

			query = query.order_by(
				desc(self.model.created_at)
			)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取策略组合关联失败: {str(e)}")

	async def get_portfolio_strategy (
			self,
			portfolio_id: str,
			strategy_id: str
	) -> Optional[PortfolioStrategy]:
		"""
		获取特定的组合策略关联

		Args:
			portfolio_id: 组合ID
			strategy_id: 策略ID

		Returns:
			组合策略关联或None
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.portfolio_id == portfolio_id,
					self.model.strategy_id == strategy_id
				)
			)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()
		except Exception as e:
			raise RepositoryError(f"获取特定组合策略失败: {str(e)}")

	async def update_strategy_weight (
			self,
			portfolio_id: str,
			strategy_id: str,
			weight: float
	) -> Optional[PortfolioStrategy]:
		"""
		更新策略权重

		Args:
			portfolio_id: 组合ID
			strategy_id: 策略ID
			weight: 新权重

		Returns:
			更新后的组合策略关联
		"""
		try:
			# 检查权重范围
			if weight < 0 or weight > 1:
				raise ValidationError("权重必须在0-1之间")

			portfolio_strategy = await self.get_portfolio_strategy(portfolio_id, strategy_id)
			if portfolio_strategy:
				return await self.update(portfolio_strategy.id, {
					"weight": weight,
					"updated_at": datetime.now()
				})
			return None
		except Exception as e:
			if isinstance(e, ValidationError):
				raise e
			raise RepositoryError(f"更新策略权重失败: {str(e)}")

	async def update_strategy_allocation (
			self,
			portfolio_id: str,
			strategy_id: str,
			allocation: Optional[Decimal]
	) -> Optional[PortfolioStrategy]:
		"""
		更新策略分配资金

		Args:
			portfolio_id: 组合ID
			strategy_id: 策略ID
			allocation: 分配资金

		Returns:
			更新后的组合策略关联
		"""
		try:
			portfolio_strategy = await self.get_portfolio_strategy(portfolio_id, strategy_id)
			if portfolio_strategy:
				return await self.update(portfolio_strategy.id, {
					"allocation": allocation,
					"updated_at": datetime.now()
				})
			return None
		except Exception as e:
			raise RepositoryError(f"更新策略分配资金失败: {str(e)}")

	async def activate_strategy (
			self,
			portfolio_id: str,
			strategy_id: str
	) -> Optional[PortfolioStrategy]:
		"""
		激活策略

		Args:
			portfolio_id: 组合ID
			strategy_id: 策略ID

		Returns:
			更新后的组合策略关联
		"""
		try:
			portfolio_strategy = await self.get_portfolio_strategy(portfolio_id, strategy_id)
			if portfolio_strategy:
				return await self.update(portfolio_strategy.id, {
					"is_active": True,
					"updated_at": datetime.now()
				})
			return None
		except Exception as e:
			raise RepositoryError(f"激活策略失败: {str(e)}")

	async def deactivate_strategy (
			self,
			portfolio_id: str,
			strategy_id: str
	) -> Optional[PortfolioStrategy]:
		"""
		停用策略

		Args:
			portfolio_id: 组合ID
			strategy_id: 策略ID

		Returns:
			更新后的组合策略关联
		"""
		try:
			portfolio_strategy = await self.get_portfolio_strategy(portfolio_id, strategy_id)
			if portfolio_strategy:
				return await self.update(portfolio_strategy.id, {
					"is_active": False,
					"updated_at": datetime.now()
				})
			return None
		except Exception as e:
			raise RepositoryError(f"停用策略失败: {str(e)}")

	async def get_portfolio_summary (
			self,
			portfolio_id: str
	) -> Dict[str, Any]:
		"""
		获取组合摘要

		Args:
			portfolio_id: 组合ID

		Returns:
			组合摘要信息
		"""
		try:
			query = select(
				func.count().label("total_strategies"),
				func.count(
					case([(self.model.is_active == True, 1)], else_=None)
				).label("active_strategies"),
				func.sum(self.model.weight).label("total_weight"),
				func.sum(self.model.allocation).label("total_allocation"),
				func.avg(self.model.weight).label("avg_weight")
			).where(
				self.model.portfolio_id == portfolio_id
			)

			result = await self.session.execute(query)
			row = result.fetchone()

			if not row:
				return {
					"total_strategies": 0,
					"active_strategies": 0,
					"inactive_strategies": 0,
					"total_weight": 0.0,
					"total_allocation": 0.0,
					"avg_weight": 0.0,
					"weight_valid": True
				}

			total_strategies = row.total_strategies or 0
			active_strategies = row.active_strategies or 0
			total_weight = float(row.total_weight or 0)
			total_allocation = row.total_allocation or Decimal('0')
			avg_weight = float(row.avg_weight or 0)

			# 检查权重总和是否为1（允许小的误差）
			weight_valid = abs(total_weight - 1.0) < 0.001

			return {
				"total_strategies": total_strategies,
				"active_strategies": active_strategies,
				"inactive_strategies": total_strategies - active_strategies,
				"total_weight": round(total_weight, 4),
				"total_allocation": float(total_allocation),
				"avg_weight": round(avg_weight, 4),
				"weight_valid": weight_valid
			}
		except Exception as e:
			raise RepositoryError(f"获取组合摘要失败: {str(e)}")

	async def rebalance_portfolio (
			self,
			portfolio_id: str,
			new_weights: Dict[str, float]
	) -> List[PortfolioStrategy]:
		"""
		重新平衡组合权重

		Args:
			portfolio_id: 组合ID
			new_weights: 新权重字典（策略ID: 权重）

		Returns:
			更新后的组合策略关联列表
		"""
		try:
			# 验证权重总和为1
			total_weight = sum(new_weights.values())
			if abs(total_weight - 1.0) > 0.001:
				raise ValidationError(f"权重总和必须为1，当前为{total_weight}")

			updated_strategies = []

			for strategy_id, weight in new_weights.items():
				# 检查权重范围
				if weight < 0 or weight > 1:
					raise ValidationError(f"权重必须在0-1之间: {strategy_id} = {weight}")

				portfolio_strategy = await self.get_portfolio_strategy(portfolio_id, strategy_id)
				if portfolio_strategy:
					updated = await self.update(portfolio_strategy.id, {
						"weight": weight,
						"updated_at": datetime.now()
					})
					updated_strategies.append(updated)
				else:
					# 如果策略不在组合中，添加它
					new_association = await self.add_strategy_to_portfolio(
						portfolio_id=portfolio_id,
						strategy_id=strategy_id,
						weight=weight
					)
					updated_strategies.append(new_association)

			return updated_strategies
		except Exception as e:
			if isinstance(e, ValidationError):
				raise e
			raise RepositoryError(f"重新平衡组合失败: {str(e)}")

	async def normalize_weights (
			self,
			portfolio_id: str
	) -> List[PortfolioStrategy]:
		"""
		标准化组合权重（使总和为1）

		Args:
			portfolio_id: 组合ID

		Returns:
			更新后的组合策略关联列表
		"""
		try:
			portfolio_strategies = await self.get_by_portfolio_id(portfolio_id, is_active=True)

			if not portfolio_strategies:
				return []

			total_weight = sum(float(ps.weight) for ps in portfolio_strategies)

			if total_weight == 0:
				# 如果总权重为0，平均分配
				normalized_weight = 1.0 / len(portfolio_strategies)
				for ps in portfolio_strategies:
					await self.update(ps.id, {
						"weight": normalized_weight,
						"updated_at": datetime.now()
					})
			else:
				# 按比例标准化
				for ps in portfolio_strategies:
					normalized_weight = float(ps.weight) / total_weight
					await self.update(ps.id, {
						"weight": normalized_weight,
						"updated_at": datetime.now()
					})

			# 重新获取更新后的列表
			return await self.get_by_portfolio_id(portfolio_id)
		except Exception as e:
			raise RepositoryError(f"标准化权重失败: {str(e)}")

	async def get_portfolio_performance_analysis (
			self,
			portfolio_id: str
	) -> Dict[str, Any]:
		"""
		获取组合绩效分析

		Args:
			portfolio_id: 组合ID

		Returns:
			组合绩效分析
		"""
		try:
			portfolio_strategies = await self.get_by_portfolio_id(portfolio_id, is_active=True, include_strategy=True)

			analysis = {
				"portfolio_id": portfolio_id,
				"total_strategies": len(portfolio_strategies),
				"strategy_details": [],
				"weight_distribution": [],
				"performance_summary": {
					"total_weight": 0.0,
					"weighted_avg_performance": 0.0  # 这里需要从绩效表中获取实际数据
				}
			}

			total_weight = 0.0

			for ps in portfolio_strategies:
				weight = float(ps.weight)
				total_weight += weight

				strategy_detail = {
					"strategy_id": ps.strategy_id,
					"strategy_name": ps.strategy.name if ps.strategy else None,
					"weight": weight,
					"allocation": float(ps.allocation) if ps.allocation else None,
					"is_active": ps.is_active,
					"created_at": ps.created_at
				}

				analysis["strategy_details"].append(strategy_detail)
				analysis["weight_distribution"].append({
					"strategy_id": ps.strategy_id,
					"weight": weight,
					"percentage": weight * 100
				})

			analysis["performance_summary"]["total_weight"] = total_weight

			# 按权重排序
			analysis["strategy_details"].sort(key=lambda x: x["weight"], reverse=True)
			analysis["weight_distribution"].sort(key=lambda x: x["weight"], reverse=True)

			return analysis
		except Exception as e:
			raise RepositoryError(f"获取组合绩效分析失败: {str(e)}")