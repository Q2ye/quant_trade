# -*- coding: utf-8 -*-
"""
持仓调整记录表Repository
位置：shared/database/repositories/trading/position_adjustment_repo.py
"""
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, asc, between, case
from sqlalchemy.orm import joinedload, load_only

from quant_server.shared.database.models.business_models import PositionAdjustment, Position
from quant_server.shared.database.repositories.base import BaseRepository, RepositoryError
from quant_server.shared.database.repositories.types import (
	RepositoryResult, PaginationParams, PaginationResult,
	FilterCondition, SortCondition, QueryParams
)


class PositionAdjustmentRepository(BaseRepository[PositionAdjustment]):
	"""持仓调整记录Repository"""

	def __init__ (self, session: AsyncSession):
		"""初始化Repository"""
		super().__init__(session, PositionAdjustment)

	async def create_adjustment (
			self,
			position_id: int,
			adjustment_type: str,
			volume_change: int,
			description: Optional[str] = None,
			cost_price_change: Optional[Decimal] = None,
			reference_id: Optional[str] = None,
			reference_type: Optional[str] = None
	) -> PositionAdjustment:
		"""
		创建持仓调整记录

		Args:
			position_id: 持仓ID
			adjustment_type: 调整类型（buy/sell/dividend/split/merge）
			volume_change: 数量变化
			description: 描述
			cost_price_change: 成本价变化
			reference_id: 关联ID
			reference_type: 关联类型

		Returns:
			持仓调整记录
		"""
		try:
			data = {
				"position_id": position_id,
				"adjustment_type": adjustment_type,
				"volume_change": volume_change,
				"cost_price_change": cost_price_change,
				"description": description,
				"reference_id": reference_id,
				"reference_type": reference_type
			}

			return await self.create(data)
		except Exception as e:
			raise RepositoryError(f"创建持仓调整记录失败: {str(e)}")

	async def create_buy_adjustment (
			self,
			position_id: int,
			volume_change: int,
			cost_price_change: Optional[Decimal] = None,
			reference_id: Optional[str] = None,
			reference_type: Optional[str] = None,
			description: Optional[str] = None
	) -> PositionAdjustment:
		"""
		创建买入调整记录

		Args:
			position_id: 持仓ID
			volume_change: 买入数量
			cost_price_change: 成本价变化
			reference_id: 关联ID（如订单ID）
			reference_type: 关联类型
			description: 描述

		Returns:
			持仓调整记录
		"""
		try:
			return await self.create_adjustment(
				position_id=position_id,
				adjustment_type="buy",
				volume_change=volume_change,
				cost_price_change=cost_price_change,
				reference_id=reference_id,
				reference_type=reference_type,
				description=description or f"买入 {volume_change} 股"
			)
		except Exception as e:
			raise RepositoryError(f"创建买入调整记录失败: {str(e)}")

	async def create_sell_adjustment (
			self,
			position_id: int,
			volume_change: int,
			reference_id: Optional[str] = None,
			reference_type: Optional[str] = None,
			description: Optional[str] = None
	) -> PositionAdjustment:
		"""
		创建卖出调整记录

		Args:
			position_id: 持仓ID
			volume_change: 卖出数量（应为负数）
			reference_id: 关联ID（如订单ID）
			reference_type: 关联类型
			description: 描述

		Returns:
			持仓调整记录
		"""
		try:
			# 卖出数量应为负数
			if volume_change > 0:
				volume_change = -volume_change

			return await self.create_adjustment(
				position_id=position_id,
				adjustment_type="sell",
				volume_change=volume_change,
				reference_id=reference_id,
				reference_type=reference_type,
				description=description or f"卖出 {abs(volume_change)} 股"
			)
		except Exception as e:
			raise RepositoryError(f"创建卖出调整记录失败: {str(e)}")

	async def create_dividend_adjustment (
			self,
			position_id: int,
			dividend_per_share: Decimal,
			reference_id: Optional[str] = None,
			description: Optional[str] = None
	) -> PositionAdjustment:
		"""
		创建分红调整记录

		Args:
			position_id: 持仓ID
			dividend_per_share: 每股分红金额
			reference_id: 关联ID
			description: 描述

		Returns:
			持仓调整记录
		"""
		try:
			# 分红会降低成本价，但不会改变持仓数量
			cost_price_change = -dividend_per_share  # 成本价减少分红金额

			return await self.create_adjustment(
				position_id=position_id,
				adjustment_type="dividend",
				volume_change=0,  # 数量不变
				cost_price_change=cost_price_change,
				reference_id=reference_id,
				reference_type="dividend",
				description=description or f"现金分红，每股 {dividend_per_share}"
			)
		except Exception as e:
			raise RepositoryError(f"创建分红调整记录失败: {str(e)}")

	async def get_by_position_id (
			self,
			position_id: int,
			adjustment_type: Optional[str] = None,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			limit: int = 100
	) -> List[PositionAdjustment]:
		"""
		根据持仓ID获取调整记录

		Args:
			position_id: 持仓ID
			adjustment_type: 调整类型
			start_date: 开始日期
			end_date: 结束日期
			limit: 限制记录数

		Returns:
			持仓调整记录列表
		"""
		try:
			query = select(self.model).where(
				self.model.position_id == position_id
			)

			if adjustment_type:
				query = query.where(self.model.adjustment_type == adjustment_type)
			if start_date:
				query = query.where(self.model.adjustment_date >= start_date)
			if end_date:
				query = query.where(self.model.adjustment_date <= end_date)

			query = query.order_by(
				desc(self.model.adjustment_date)
			).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取持仓调整记录失败: {str(e)}")

	async def get_by_reference (
			self,
			reference_type: str,
			reference_id: str
	) -> List[PositionAdjustment]:
		"""
		根据关联信息获取调整记录

		Args:
			reference_type: 关联类型
			reference_id: 关联ID

		Returns:
			持仓调整记录列表
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.reference_type == reference_type,
					self.model.reference_id == reference_id
				)
			).order_by(
				desc(self.model.adjustment_date)
			)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取关联调整记录失败: {str(e)}")

	async def get_position_history (
			self,
			position_id: int,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None
	) -> List[Dict[str, Any]]:
		"""
		获取持仓历史记录

		Args:
			position_id: 持仓ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			持仓历史记录列表
		"""
		try:
			query = select(self.model).where(
				self.model.position_id == position_id
			)

			if start_date:
				query = query.where(self.model.adjustment_date >= start_date)
			if end_date:
				query = query.where(self.model.adjustment_date <= end_date)

			query = query.order_by(
				asc(self.model.adjustment_date)
			)

			result = await self.session.execute(query)
			adjustments = result.scalars().all()

			history = []
			current_volume = 0

			for adjustment in adjustments:
				current_volume += adjustment.volume_change

				history.append({
					"adjustment_date": adjustment.adjustment_date,
					"adjustment_type": adjustment.adjustment_type,
					"volume_change": adjustment.volume_change,
					"cumulative_volume": current_volume,
					"cost_price_change": float(adjustment.cost_price_change) if adjustment.cost_price_change else None,
					"description": adjustment.description,
					"reference_id": adjustment.reference_id,
					"reference_type": adjustment.reference_type
				})

			return history
		except Exception as e:
			raise RepositoryError(f"获取持仓历史失败: {str(e)}")

	async def get_adjustment_statistics (
			self,
			position_id: Optional[int] = None,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None
	) -> Dict[str, Any]:
		"""
		获取调整统计信息

		Args:
			position_id: 持仓ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			调整统计信息
		"""
		try:
			query = select(
				func.count().label("total_adjustments"),
				func.sum(self.model.volume_change).label("total_volume_change"),
				func.sum(
					case([(self.model.volume_change > 0, self.model.volume_change)], else_=0)
				).label("total_buy_volume"),
				func.sum(
					case([(self.model.volume_change < 0, self.model.volume_change)], else_=0)
				).label("total_sell_volume"),
				self.model.adjustment_type
			)

			conditions = []
			if position_id:
				conditions.append(self.model.position_id == position_id)
			if start_date:
				conditions.append(self.model.adjustment_date >= start_date)
			if end_date:
				conditions.append(self.model.adjustment_date <= end_date)

			if conditions:
				query = query.where(and_(*conditions))

			query = query.group_by(
				self.model.adjustment_type
			)

			result = await self.session.execute(query)
			rows = result.fetchall()

			total_adjustments = 0
			total_volume_change = 0
			total_buy_volume = 0
			total_sell_volume = 0
			adjustments_by_type = {}

			for row in rows:
				total_adjustments += row.total_adjustments or 0
				total_volume_change += row.total_volume_change or 0
				total_buy_volume += row.total_buy_volume or 0
				total_sell_volume += row.total_sell_volume or 0

				adjustment_type = row.adjustment_type
				adjustments_by_type[adjustment_type] = {
					"count": row.total_adjustments or 0,
					"total_volume_change": row.total_volume_change or 0,
					"buy_volume": row.total_buy_volume or 0,
					"sell_volume": row.total_sell_volume or 0
				}

			return {
				"total_adjustments": total_adjustments,
				"total_volume_change": total_volume_change,
				"total_buy_volume": total_buy_volume,
				"total_sell_volume": total_sell_volume,
				"net_volume_change": total_buy_volume + total_sell_volume,  # 卖出为负数
				"adjustments_by_type": adjustments_by_type,
				"buy_sell_ratio": abs(total_buy_volume / total_sell_volume) if total_sell_volume != 0 else float('inf')
			}
		except Exception as e:
			raise RepositoryError(f"获取调整统计失败: {str(e)}")

	async def get_adjustment_trend (
			self,
			position_id: int,
			days: int = 30
	) -> List[Dict[str, Any]]:
		"""
		获取调整趋势

		Args:
			position_id: 持仓ID
			days: 天数

		Returns:
			调整趋势列表
		"""
		try:
			end_date = datetime.now()
			start_date = end_date - timedelta(days=days)

			# 按天分组统计
			date_format = func.date_format(self.model.adjustment_date, "%Y-%m-%d")

			query = select(
				date_format.label("adjustment_day"),
				func.count().label("adjustment_count"),
				func.sum(self.model.volume_change).label("total_volume_change"),
				func.sum(
					case([(self.model.volume_change > 0, self.model.volume_change)], else_=0)
				).label("buy_volume"),
				func.sum(
					case([(self.model.volume_change < 0, self.model.volume_change)], else_=0)
				).label("sell_volume"),
				self.model.adjustment_type
			).where(
				and_(
					self.model.position_id == position_id,
					self.model.adjustment_date >= start_date,
					self.model.adjustment_date <= end_date
				)
			).group_by(
				"adjustment_day",
				self.model.adjustment_type
			).order_by(
				asc("adjustment_day")
			)

			result = await self.session.execute(query)
			rows = result.fetchall()

			# 按日期组织数据
			trend_data = {}
			for row in rows:
				adjustment_day = row.adjustment_day
				if adjustment_day not in trend_data:
					trend_data[adjustment_day] = {
						"adjustment_count": 0,
						"total_volume_change": 0,
						"buy_volume": 0,
						"sell_volume": 0,
						"adjustments_by_type": {}
					}

				trend_data[adjustment_day]["adjustment_count"] += row.adjustment_count or 0
				trend_data[adjustment_day]["total_volume_change"] += row.total_volume_change or 0
				trend_data[adjustment_day]["buy_volume"] += row.buy_volume or 0
				trend_data[adjustment_day]["sell_volume"] += row.sell_volume or 0

				adjustment_type = row.adjustment_type
				if adjustment_type not in trend_data[adjustment_day]["adjustments_by_type"]:
					trend_data[adjustment_day]["adjustments_by_type"][adjustment_type] = {
						"count": 0,
						"volume_change": 0
					}

				trend_data[adjustment_day]["adjustments_by_type"][adjustment_type]["count"] += row.adjustment_count or 0
				trend_data[adjustment_day]["adjustments_by_type"][adjustment_type][
					"volume_change"] += row.total_volume_change or 0

			# 转换为列表格式
			trend_list = []
			for adjustment_day, data in sorted(trend_data.items()):
				trend_list.append({
					"adjustment_day": adjustment_day,
					"adjustment_count": data["adjustment_count"],
					"total_volume_change": data["total_volume_change"],
					"buy_volume": data["buy_volume"],
					"sell_volume": data["sell_volume"],
					"net_volume_change": data["buy_volume"] + data["sell_volume"],  # 卖出为负数
					"adjustments_by_type": data["adjustments_by_type"]
				})

			return trend_list
		except Exception as e:
			raise RepositoryError(f"获取调整趋势失败: {str(e)}")