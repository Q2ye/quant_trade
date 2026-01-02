# -*- coding: utf-8 -*-
"""
# 股票篮子数据仓库
# 位置：quant_server/shared/database/repositories/basket_repo.py
# 职责：管理股票篮子、篮子成分等数据访问
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func, text
from sqlalchemy.orm import selectinload, joinedload

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.business_models import (
	Basket,
	BasketItem
)


class BasketRepository:
	"""股票篮子数据仓库 - 负责篮子相关数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.basket_repo = BaseRepository[Basket](session, Basket)
		self.basket_item_repo = BaseRepository[BasketItem](session, BasketItem)

	# ==================== 篮子操作 ====================

	async def get_basket_by_id (self, basket_id: str) -> Optional[Basket]:
		"""
		根据篮子ID获取篮子信息

		Args:
			basket_id: 篮子ID

		Returns:
			篮子对象或None
		"""
		return await self.basket_repo.get_by(id=basket_id)

	async def get_all_baskets (self) -> List[Basket]:
		"""
		获取所有篮子

		Returns:
			篮子列表
		"""
		return await self.basket_repo.get_all()

	async def search_baskets (
			self,
			keyword: str,
			limit: int = 50,
			skip: int = 0
	) -> List[Basket]:
		"""
		搜索篮子

		Args:
			keyword: 搜索关键词
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			篮子列表
		"""
		query = select(Basket).where(
			or_(
				Basket.id.like(f"%{keyword}%"),
				Basket.name.like(f"%{keyword}%")
			)
		).order_by(Basket.name).offset(skip).limit(limit)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def create_basket (self, basket_data: Dict[str, Any]) -> Basket:
		"""
		创建篮子

		Args:
			basket_data: 篮子数据

		Returns:
			创建的篮子
		"""
		return await self.basket_repo.create(basket_data)

	async def update_basket (self, basket_id: str, update_data: Dict[str, Any]) -> Optional[Basket]:
		"""
		更新篮子信息

		Args:
			basket_id: 篮子ID
			update_data: 更新数据

		Returns:
			更新后的篮子
		"""
		basket = await self.basket_repo.get_by(id=basket_id)
		if not basket:
			return None

		return await self.basket_repo.update(basket.id, update_data)

	async def delete_basket (self, basket_id: str) -> bool:
		"""
		删除篮子

		Args:
			basket_id: 篮子ID

		Returns:
			是否成功
		"""
		# 先删除篮子项
		await self.delete_all_basket_items(basket_id)

		# 再删除篮子
		return await self.basket_repo.delete(basket_id)

	# ==================== 篮子项操作 ====================

	async def get_basket_items (self, basket_id: str) -> List[BasketItem]:
		"""
		获取篮子所有成分股

		Args:
			basket_id: 篮子ID

		Returns:
			篮子项列表
		"""
		return await self.basket_item_repo.get_many(basket_id=basket_id)

	async def get_basket_item (
			self,
			basket_id: str,
			ts_code: str
	) -> Optional[BasketItem]:
		"""
		获取篮子中的某个成分股

		Args:
			basket_id: 篮子ID
			ts_code: 股票代码

		Returns:
			篮子项或None
		"""
		return await self.basket_item_repo.get_by(
			basket_id=basket_id,
			ts_code=ts_code
		)

	async def add_basket_item (self, item_data: Dict[str, Any]) -> BasketItem:
		"""
		添加篮子成分股

		Args:
			item_data: 成分股数据

		Returns:
			创建的篮子项
		"""
		return await self.basket_item_repo.create(item_data)

	async def update_basket_item (
			self,
			item_id: int,
			update_data: Dict[str, Any]
	) -> Optional[BasketItem]:
		"""
		更新篮子成分股

		Args:
			item_id: 篮子项ID
			update_data: 更新数据

		Returns:
			更新后的篮子项
		"""
		return await self.basket_item_repo.update(item_id, update_data)

	async def update_basket_item_weight (
			self,
			basket_id: str,
			ts_code: str,
			weight: float
	) -> Optional[BasketItem]:
		"""
		更新篮子成分股权重

		Args:
			basket_id: 篮子ID
			ts_code: 股票代码
			weight: 新权重

		Returns:
			更新后的篮子项
		"""
		item = await self.get_basket_item(basket_id, ts_code)
		if not item:
			return None

		return await self.basket_item_repo.update(item.id, {"weight": weight})

	async def remove_basket_item (self, basket_id: str, ts_code: str) -> bool:
		"""
		从篮子中移除成分股

		Args:
			basket_id: 篮子ID
			ts_code: 股票代码

		Returns:
			是否成功
		"""
		item = await self.get_basket_item(basket_id, ts_code)
		if not item:
			return False

		return await self.basket_item_repo.delete(item.id)

	async def delete_all_basket_items (self, basket_id: str) -> int:
		"""
		删除篮子所有成分股

		Args:
			basket_id: 篮子ID

		Returns:
			删除的项数
		"""
		return await self.basket_item_repo.delete_by(basket_id=basket_id)

	# ==================== 批量操作 ====================

	async def batch_add_basket_items (self, items_data: List[Dict[str, Any]]) -> List[BasketItem]:
		"""
		批量添加篮子成分股

		Args:
			items_data: 成分股数据列表

		Returns:
			创建的篮子项列表
		"""
		return await self.basket_item_repo.batch_create(items_data)

	async def batch_update_basket_items (
			self,
			items_data: List[Dict[str, Any]]
	) -> List[BasketItem]:
		"""
		批量更新篮子成分股

		Args:
			items_data: 成分股数据列表

		Returns:
			更新后的篮子项列表
		"""
		return await self.basket_item_repo.batch_upsert(
			match_fields=["basket_id", "ts_code"],
			data_list=items_data,
			update_fields=["weight"]
		)

	async def clear_and_rebuild_basket (
			self,
			basket_id: str,
			items_data: List[Dict[str, Any]]
	) -> List[BasketItem]:
		"""
		清空并重建篮子成分股

		Args:
			basket_id: 篮子ID
			items_data: 新的成分股数据列表

		Returns:
			新的篮子项列表
		"""
		# 清空现有成分股
		await self.delete_all_basket_items(basket_id)

		# 添加新的成分股
		for item in items_data:
			item["basket_id"] = basket_id

		return await self.batch_add_basket_items(items_data)

	# ==================== 统计分析操作 ====================

	async def get_basket_summary (self, basket_id: str) -> Dict[str, Any]:
		"""
		获取篮子统计摘要

		Args:
			basket_id: 篮子ID

		Returns:
			统计摘要字典
		"""
		# 获取篮子信息
		basket = await self.get_basket_by_id(basket_id)
		if not basket:
			return {}

		# 获取篮子项
		items = await self.get_basket_items(basket_id)

		# 计算权重总和
		total_weight = sum(item.weight for item in items)

		# 计算成分股数量
		stock_count = len(items)

		return {
			"basket_id": basket_id,
			"basket_name": basket.name,
			"stock_count": stock_count,
			"total_weight": total_weight,
			"items": [
				{
					"ts_code": item.ts_code,
					"weight": item.weight,
					"created_at": item.created_at
				}
				for item in items
			]
		}