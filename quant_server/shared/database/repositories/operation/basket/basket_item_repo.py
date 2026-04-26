# -*- coding: utf-8 -*-
"""
BasketItemRepository - 篮子成分数据访问层

基于BaseRepository实现，支持篮子成分的CRUD操作和批量处理
位置：quant_server/shared/database/repositories/operation/basket/basket_item_repo.py

设计原则：
1. 继承BaseRepository，使用普通表模型（非超表）
2. 提供篮子成分特定业务查询方法
3. 支持批量操作和权重计算
"""
from datetime import timezone, datetime
from typing import List, Dict, Any, Optional, Union

from sqlalchemy import select, func, and_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.business_models import BasketItem
from quant_server.shared.database.models.data_models import StockBasic
from quant_server.shared.database.repositories.base.repository_base import BaseRepository, RepositoryError
from quant_server.shared.database.repositories.types import (
	PaginationParams,
	PaginationResult
)


class BasketItemRepository(BaseRepository[BasketItem]):
	"""篮子成分Repository - 继承BaseRepository"""

	def __init__ (self, session: AsyncSession):
		"""初始化篮子成分Repository"""
		super().__init__(session, BasketItem)

	# ==================== 业务特定方法 ====================

	async def get_items_with_stock_info (
			self,
			basket_id: str,
			pagination: PaginationParams = None
	) -> PaginationResult[Dict[str, Any]]:
		"""
		获取篮子成分股及股票基本信息（连接查询）

		Args:
			basket_id: 篮子ID
			pagination: 分页参数

		Returns:
			分页结果（包含BasketItem和StockBasic）

		Raises:
			RepositoryError: 查询失败时抛出
		"""
		try:
			# 构建连接查询
			query = (
				select(BasketItem, StockBasic)
				.outerjoin(StockBasic, BasketItem.ts_code == StockBasic.ts_code)
				.where(BasketItem.basket_id == basket_id)
				.order_by(desc(BasketItem.weight), asc(BasketItem.ts_code))
			)

			# 获取总数
			count_query = (
				select(func.count())
				.select_from(BasketItem)
				.where(BasketItem.basket_id == basket_id)
			)
			total_result = await self.session.execute(count_query)
			total = total_result.scalar() or 0

			# 应用分页
			if pagination:
				query = query.offset(pagination.get_offset()).limit(pagination.get_limit())

			# 执行查询
			result = await self.session.execute(query)
			items = result.all()

			# 转换为字典列表以便使用
			formatted_items = []
			for basket_item, stock_basic in items:
				formatted_items.append({
					"basket_item": basket_item,
					"stock_info": stock_basic
				})

			# 如果是分页查询，返回分页结果
			if pagination:
				return PaginationResult.create(
					items=formatted_items,
					total=total,
					page=pagination.page,
					page_size=pagination.page_size
				)
			else:
				# 非分页查询，返回所有数据
				return PaginationResult.create(
					items=formatted_items,
					total=total,
					page=1,
					page_size=total
				)

		except Exception as e:
			raise RepositoryError(f"获取篮子成分及股票信息失败: {str(e)}")

	async def get_basket_items_by_stock (self, ts_code: str) -> List[BasketItem]:
		"""
		根据股票代码查询包含该股票的所有篮子

		Args:
			ts_code: 股票代码

		Returns:
			篮子成分列表
		"""
		try:
			query = select(self.model).where(self.model.ts_code == ts_code)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"根据股票查询篮子失败: {str(e)}")

	async def batch_create_items (self, basket_id: str, items_data: List[Dict[str, Any]]) -> List[BasketItem]:
		"""
		批量创建篮子成分股

		Args:
			basket_id: 篮子ID
			items_data: 成分股数据列表

		Returns:
			创建的成分股列表
		"""
		try:
			# 验证权重总和
			total_weight = sum(item.get('weight', 0) for item in items_data)
			if total_weight > 1.0:
				raise RepositoryError(f"权重总和超过1.0: {total_weight}")

			# 开始事务
			await self.begin_transaction()

			instances = []
			for item_data in items_data:
				item_data['basket_id'] = basket_id
				instance = await self.create(item_data)
				instances.append(instance)

			# 提交事务
			await self.commit()

			return instances

		except Exception as e:
			await self.rollback()
			if isinstance(e, RepositoryError):
				raise e
			else:
				raise RepositoryError(f"批量创建篮子成分失败: {str(e)}")

	async def update_item_weight (self, basket_id: str, ts_code: str, weight: float) -> Optional[BasketItem]:
		"""
		更新篮子中某股票的权重

		Args:
			basket_id: 篮子ID
			ts_code: 股票代码
			weight: 新权重

		Returns:
			更新后的篮子成分对象或None
		"""
		try:
			# 验证权重范围
			if not 0 <= weight <= 1:
				raise RepositoryError(f"权重必须在0-1之间: {weight}")

			# 查找现有记录
			query = select(self.model).where(
				and_(
					self.model.basket_id == basket_id,
					self.model.ts_code == ts_code
				)
			)

			result = await self.session.execute(query)
			item = result.scalar_one_or_none()

			if not item:
				raise RepositoryError(f"篮子{basket_id}中未找到股票{ts_code}")

			# 更新权重
			return await self.update(item.id, {"weight": weight})

		except Exception as e:
			if isinstance(e, RepositoryError):
				raise e
			else:
				raise RepositoryError(f"更新权重失败: {str(e)}")

	async def normalize_basket_weights (self, basket_id: str) -> List[BasketItem]:
		"""
		归一化篮子权重（使所有权重总和为1）

		Args:
			basket_id: 篮子ID

		Returns:
			归一化后的成分股列表
		"""
		try:
			# 获取所有成分
			items = await self.get_all(basket_id=basket_id)
			if not items:
				return []

			# 计算当前总权重
			total_weight = sum(item.weight for item in items)

			if total_weight == 0:
				# 如果总权重为0，平均分配
				equal_weight = 1.0 / len(items)
				for item in items:
					await self.update(item.id, {"weight": equal_weight})
			else:
				# 按比例归一化
				for item in items:
					normalized_weight = item.weight / total_weight
					await self.update(item.id, {"weight": normalized_weight})

			# 重新查询并返回
			return await self.get_all(basket_id=basket_id)

		except Exception as e:
			raise RepositoryError(f"归一化权重失败: {str(e)}")

	async def get_basket_weight_summary (self, basket_id: str) -> Dict[str, Any]:
		"""
		获取篮子权重统计摘要

		Args:
			basket_id: 篮子ID

		Returns:
			权重统计摘要
		"""
		try:
			# 获取所有成分
			items = await self.get_all(basket_id=basket_id)

			if not items:
				return {
					"basket_id": basket_id,
					"total_weight": 0,
					"item_count": 0,
					"avg_weight": 0,
					"max_weight": 0,
					"min_weight": 0,
					"weight_variance": 0
				}

			# 计算统计指标
			weights = [item.weight for item in items]
			total_weight = sum(weights)
			avg_weight = total_weight / len(weights)
			max_weight = max(weights)
			min_weight = min(weights)

			# 计算方差
			if len(weights) > 1:
				variance = sum((w - avg_weight) ** 2 for w in weights) / (len(weights) - 1)
			else:
				variance = 0

			return {
				"basket_id": basket_id,
				"total_weight": total_weight,
				"item_count": len(items),
				"avg_weight": avg_weight,
				"max_weight": max_weight,
				"min_weight": min_weight,
				"weight_variance": variance,
				"is_normalized": abs(total_weight - 1.0) < 0.001
			}

		except Exception as e:
			raise RepositoryError(f"获取权重统计失败: {str(e)}")

	async def find_duplicate_stocks (self, basket_id: str) -> List[str]:
		"""
		查找篮子中的重复股票代码

		Args:
			basket_id: 篮子ID

		Returns:
			重复的股票代码列表
		"""
		try:
			query = (
				select(self.model.ts_code, func.count().label('count'))
				.where(self.model.basket_id == basket_id)
				.group_by(self.model.ts_code)
				.having(func.count() > 1)
			)

			result = await self.session.execute(query)
			duplicates = [row.ts_code for row in result.all()]

			return duplicates

		except Exception as e:
			raise RepositoryError(f"查找重复股票失败: {str(e)}")

	async def remove_duplicates (self, basket_id: str) -> int:
		"""
		移除篮子中的重复股票（保留权重最大的记录）

		Args:
			basket_id: 篮子ID

		Returns:
			移除的记录数
		"""
		try:
			# 查找重复股票
			duplicates = await self.find_duplicate_stocks(basket_id)
			if not duplicates:
				return 0

			removed_count = 0

			# 开始事务
			await self.begin_transaction()

			for ts_code in duplicates:
				# 获取该股票的所有记录
				query = (
					select(self.model)
					.where(
						and_(
							self.model.basket_id == basket_id,
							self.model.ts_code == ts_code
						)
					)
					.order_by(desc(self.model.weight))
				)

				result = await self.session.execute(query)
				items = result.scalars().all()

				if len(items) > 1:
					# 保留权重最大的记录，删除其他
					for item in items[1:]:
						await self.delete(item.id)
						removed_count += 1

			# 提交事务
			await self.commit()

			return removed_count

		except Exception as e:
			await self.rollback()
			raise RepositoryError(f"移除重复股票失败: {str(e)}")

	async def export_basket_items (self, basket_id: str, export_format: str = 'json') -> Union[Dict, List, str]:
		"""
		导出篮子成分数据

		Args:
			basket_id: 篮子ID
			export_format: 导出格式（json/csv/list）

		Returns:
			格式化后的篮子数据
		"""
		try:
			# 获取篮子成分及股票信息
			items_result = await self.get_items_with_stock_info(basket_id)
			items = items_result.items

			if export_format == 'json':
				# JSON格式
				export_data = []
				for item_info in items:
					basket_item = item_info['basket_item']
					stock_info = item_info['stock_info']

					item_data = {
						"ts_code": basket_item.ts_code,
						"weight": float(basket_item.weight),
						"created_at": basket_item.created_at.isoformat() if basket_item.created_at else None
					}

					if stock_info:
						item_data.update({
							"stock_name": stock_info.name,
							"stock_fullname": stock_info.fullname,
							"industry": stock_info.industry,
							"area": stock_info.area
						})

					export_data.append(item_data)

				return {
					"basket_id": basket_id,
					"total_items": items_result.total,
					"items": export_data,
					"exported_at": datetime.now(timezone.utc).isoformat()
				}

			elif export_format == 'csv':
				# CSV格式（简化版，实际使用可能需要pandas）
				csv_lines = ["ts_code,weight,stock_name,industry"]
				for item_info in items:
					basket_item = item_info['basket_item']
					stock_info = item_info['stock_info']

					stock_name = stock_info.name if stock_info else ""
					industry = stock_info.industry if stock_info else ""

					csv_lines.append(
						f"{basket_item.ts_code},{basket_item.weight},{stock_name},{industry}"
					)

				return "\n".join(csv_lines)

			elif export_format == 'list':
				# 简单列表格式
				simple_list = []
				for item_info in items:
					basket_item = item_info['basket_item']
					stock_info = item_info['stock_info']

					stock_name = f" ({stock_info.name})" if stock_info else ""
					simple_list.append(f"{basket_item.ts_code}{stock_name}: {basket_item.weight:.2%}")

				return simple_list
			else:
				raise RepositoryError(f"不支持的导出格式: {format}")

		except Exception as e:
			raise RepositoryError(f"导出篮子数据失败: {str(e)}")
