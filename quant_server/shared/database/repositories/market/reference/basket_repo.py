"""
股票篮子数据仓库 - 继承BaseRepository
管理股票篮子、篮子成分等业务数据访问

设计说明：
1. Basket和BasketItem是业务表，非时序数据，继承BaseRepository
2. 提供完整的篮子管理功能：创建、更新、删除、搜索等
3. 提供篮子成分管理功能：添加、删除、更新权重、批量操作
4. 支持篮子统计摘要和批量重建功能
5. 为交易系统和策略系统提供篮子数据服务
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func, text, delete
from sqlalchemy.orm import selectinload

from quant_server.shared.database.repositories.base.repository_base import BaseRepository, RepositoryError
from quant_server.shared.database.models.business_models import Basket, BasketItem
from quant_server.shared.database.repositories.types import PaginationParams, PaginationResult


class BasketRepository(BaseRepository[Basket]):
	"""
	股票篮子数据仓库 - 负责篮子相关数据访问

	继承BaseRepository，提供标准的CRUD操作
	同时包含业务特定的篮子和篮子成分管理方法
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化股票篮子Repository

		Args:
			session: 数据库会话
		"""
		super().__init__(session, Basket)
		# 内部使用独立的BasketItem Repository
		self.basket_item_repo = BaseRepository[BasketItem](session, BasketItem)

	# ==================== 篮子基础操作 ====================

	async def get_basket_by_id (self, basket_id: str) -> Optional[Basket]:
		"""
		根据篮子ID获取篮子信息（包含篮子成分）

		Args:
			basket_id: 篮子ID

		Returns:
			篮子对象（包含items关系）或None
		"""
		try:
			query = select(self.model).where(self.model.id == basket_id).options(
				selectinload(self.model.items)
			)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"根据ID获取篮子失败: {str(e)}")

	async def get_all_baskets (self, with_items: bool = False) -> List[Basket]:
		"""
		获取所有篮子

		Args:
			with_items: 是否加载篮子成分

		Returns:
			篮子列表
		"""
		try:
			query = select(self.model)

			if with_items:
				query = query.options(selectinload(self.model.items))

			query = query.order_by(self.model.name)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取所有篮子失败: {str(e)}")

	async def search_baskets (
			self,
			keyword: str,
			limit: int = 50,
			skip: int = 0,
			with_items: bool = False
	) -> List[Basket]:
		"""
		搜索篮子

		Args:
			keyword: 搜索关键词（匹配ID或名称）
			limit: 返回数量限制
			skip: 跳过数量
			with_items: 是否加载篮子成分

		Returns:
			搜索结果列表
		"""
		try:
			query = select(self.model).where(
				or_(
					self.model.id.like(f"%{keyword}%"),
					self.model.name.like(f"%{keyword}%")
				)
			)

			if with_items:
				query = query.options(selectinload(self.model.items))

			query = query.order_by(self.model.name).offset(skip).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"搜索篮子失败: {str(e)}")

	async def paginate_baskets (
			self,
			pagination: PaginationParams,
			keyword: Optional[str] = None
	) -> PaginationResult[Basket]:
		"""
		分页查询篮子

		Args:
			pagination: 分页参数
			keyword: 搜索关键词（可选）

		Returns:
			分页结果
		"""
		try:
			filters = []

			if keyword:
				filters.append(
					or_(
						self.model.id.like(f"%{keyword}%"),
						self.model.name.like(f"%{keyword}%")
					)
				)

			return await self.paginate(
				pagination=pagination,
				filters=[{"field": "id", "operator": "like", "value": f"%{keyword}%"},
				         {"field": "name", "operator": "like", "value": f"%{keyword}%"}] if keyword else None,
				sorts=[{"field": "name", "descending": False}]
			)

		except Exception as e:
			raise RepositoryError(f"分页查询篮子失败: {str(e)}")

	async def create_basket_with_items (
			self,
			basket_data: Dict[str, Any],
			items_data: List[Dict[str, Any]]
	) -> Basket:
		"""
		创建篮子并添加初始成分

		Args:
			basket_data: 篮子数据
			items_data: 初始成分数据列表

		Returns:
			创建的篮子（包含items关系）
		"""
		try:
			# 开始事务
			await self.begin_transaction()

			try:
				# 创建篮子
				basket = await self.create(basket_data)

				# 添加篮子成分
				if items_data:
					for item in items_data:
						item["basket_id"] = basket.id

					await self.basket_item_repo.batch_create(items_data)

				# 提交事务
				await self.commit()

				# 重新加载篮子（包含items）
				return await self.get_basket_by_id(basket.id)

			except Exception as e:
				await self.rollback()
				raise e

		except Exception as e:
			raise RepositoryError(f"创建篮子及成分失败: {str(e)}")

	async def update_basket_with_items (
			self,
			basket_id: str,
			basket_update_data: Dict[str, Any],
			items_update_data: Optional[List[Dict[str, Any]]] = None
	) -> Optional[Basket]:
		"""
		更新篮子信息及成分

		Args:
			basket_id: 篮子ID
			basket_update_data: 篮子更新数据
			items_update_data: 成分更新数据列表（可选）

		Returns:
			更新后的篮子（包含items关系）
		"""
		try:
			# 开始事务
			await self.begin_transaction()

			try:
				# 更新篮子信息
				basket = await self.get_by(id=basket_id)
				if not basket:
					await self.rollback()
					return None

				await self.update(basket.id, basket_update_data)

				# 如果提供了成分更新数据，则更新成分
				if items_update_data:
					# 清空现有成分
					await self.basket_item_repo.delete_by(basket_id=basket_id)

					# 添加新的成分
					for item in items_update_data:
						item["basket_id"] = basket_id

					await self.basket_item_repo.batch_create(items_update_data)

				# 提交事务
				await self.commit()

				# 重新加载篮子
				return await self.get_basket_by_id(basket_id)

			except Exception as e:
				await self.rollback()
				raise e

		except Exception as e:
			raise RepositoryError(f"更新篮子及成分失败: {str(e)}")

	async def delete_basket_cascade (self, basket_id: str) -> bool:
		"""
		级联删除篮子（删除篮子和所有成分）

		Args:
			basket_id: 篮子ID

		Returns:
			是否成功删除
		"""
		try:
			# 开始事务
			await self.begin_transaction()

			try:
				# 先删除篮子成分
				await self.basket_item_repo.delete_by(basket_id=basket_id)

				# 再删除篮子
				result = await self.delete_by(id=basket_id)

				# 提交事务
				await self.commit()

				return result > 0

			except Exception as e:
				await self.rollback()
				raise e

		except Exception as e:
			raise RepositoryError(f"级联删除篮子失败: {str(e)}")

	# ==================== 篮子成分操作 ====================

	async def get_basket_items (
			self,
			basket_id: str,
			skip: int = 0,
			limit: int = 1000
	) -> List[BasketItem]:
		"""
		获取篮子所有成分股

		Args:
			basket_id: 篮子ID
			skip: 跳过数量
			limit: 限制数量

		Returns:
			篮子项列表
		"""
		try:
			return await self.basket_item_repo.get_many(
				skip=skip,
				limit=limit,
				basket_id=basket_id
			)

		except Exception as e:
			raise RepositoryError(f"获取篮子成分失败: {str(e)}")

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
		try:
			return await self.basket_item_repo.get_by(
				basket_id=basket_id,
				ts_code=ts_code
			)

		except Exception as e:
			raise RepositoryError(f"获取篮子成分项失败: {str(e)}")

	async def add_basket_item (
			self,
			basket_id: str,
			ts_code: str,
			weight: float
	) -> BasketItem:
		"""
		添加篮子成分股

		Args:
			basket_id: 篮子ID
			ts_code: 股票代码
			weight: 权重

		Returns:
			创建的篮子项
		"""
		try:
			# 检查篮子是否存在
			basket = await self.get_by(id=basket_id)
			if not basket:
				raise RepositoryError(f"篮子不存在: {basket_id}")

			# 检查是否已存在
			existing = await self.get_basket_item(basket_id, ts_code)
			if existing:
				raise RepositoryError(f"成分股已存在: {ts_code}")

			# 创建篮子项
			item_data = {
				"basket_id": basket_id,
				"ts_code": ts_code,
				"weight": weight
			}

			return await self.basket_item_repo.create(item_data)

		except Exception as e:
			raise RepositoryError(f"添加篮子成分失败: {str(e)}")

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
		try:
			# 获取篮子项
			item = await self.get_basket_item(basket_id, ts_code)
			if not item:
				return None

			# 更新权重
			return await self.basket_item_repo.update(item.id, {"weight": weight})

		except Exception as e:
			raise RepositoryError(f"更新篮子成分权重失败: {str(e)}")

	async def remove_basket_item (self, basket_id: str, ts_code: str) -> bool:
		"""
		从篮子中移除成分股

		Args:
			basket_id: 篮子ID
			ts_code: 股票代码

		Returns:
			是否成功移除
		"""
		try:
			# 获取篮子项
			item = await self.get_basket_item(basket_id, ts_code)
			if not item:
				return False

			# 删除篮子项
			return await self.basket_item_repo.delete(item.id)

		except Exception as e:
			raise RepositoryError(f"移除篮子成分失败: {str(e)}")

	async def delete_all_basket_items (self, basket_id: str) -> int:
		"""
		删除篮子所有成分股

		Args:
			basket_id: 篮子ID

		Returns:
			删除的项数
		"""
		try:
			return await self.basket_item_repo.delete_by(basket_id=basket_id)

		except Exception as e:
			raise RepositoryError(f"删除篮子所有成分失败: {str(e)}")

	# ==================== 批量操作 ====================

	async def batch_add_basket_items (
			self,
			basket_id: str,
			items_data: List[Dict[str, Any]]
	) -> List[BasketItem]:
		"""
		批量添加篮子成分股

		Args:
			basket_id: 篮子ID
			items_data: 成分股数据列表（每个字典需包含ts_code和weight）

		Returns:
			创建的篮子项列表
		"""
		try:
			# 检查篮子是否存在
			basket = await self.get_by(id=basket_id)
			if not basket:
				raise RepositoryError(f"篮子不存在: {basket_id}")

			# 为每个项添加basket_id
			for item in items_data:
				item["basket_id"] = basket_id

			return await self.basket_item_repo.batch_create(items_data)

		except Exception as e:
			raise RepositoryError(f"批量添加篮子成分失败: {str(e)}")

	async def batch_update_basket_items (
			self,
			basket_id: str,
			items_data: List[Dict[str, Any]]
	) -> List[BasketItem]:
		"""
		批量更新篮子成分股（插入或更新）

		Args:
			basket_id: 篮子ID
			items_data: 成分股数据列表

		Returns:
			更新后的篮子项列表
		"""
		try:
			# 为每个项添加basket_id
			for item in items_data:
				item["basket_id"] = basket_id

			# 使用upsert操作
			return await self.basket_item_repo.batch_upsert(
				match_fields=["basket_id", "ts_code"],
				data_list=items_data,
				update_fields=["weight"]
			)

		except Exception as e:
			raise RepositoryError(f"批量更新篮子成分失败: {str(e)}")

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
		try:
			# 开始事务
			await self.begin_transaction()

			try:
				# 清空现有成分股
				await self.delete_all_basket_items(basket_id)

				# 添加新的成分股
				if items_data:
					result = await self.batch_add_basket_items(basket_id, items_data)
				else:
					result = []

				# 提交事务
				await self.commit()

				return result

			except Exception as e:
				await self.rollback()
				raise e

		except Exception as e:
			raise RepositoryError(f"清空并重建篮子失败: {str(e)}")

	# ==================== 统计分析操作 ====================

	async def get_basket_summary (self, basket_id: str) -> Dict[str, Any]:
		"""
		获取篮子统计摘要

		Args:
			basket_id: 篮子ID

		Returns:
			统计摘要字典
		"""
		try:
			# 获取篮子信息
			basket = await self.get_basket_by_id(basket_id)
			if not basket:
				return {
					"basket_id": basket_id,
					"error": "篮子不存在"
				}

			# 获取篮子项
			items = await self.get_basket_items(basket_id)

			# 计算统计信息
			total_weight = sum(item.weight for item in items)
			stock_count = len(items)

			# 按权重排序
			sorted_items = sorted(items, key=lambda x: x.weight, reverse=True)

			return {
				"basket_id": basket_id,
				"basket_name": basket.name,
				"description": basket.description,
				"stock_count": stock_count,
				"total_weight": total_weight,
				"weight_normalized": total_weight == 1.0,
				"items": [
					{
						"ts_code": item.ts_code,
						"weight": item.weight,
						"weight_percentage": round(item.weight * 100, 2),
						"created_at": item.created_at
					}
					for item in sorted_items
				],
				"created_at": basket.created_at,
				"updated_at": basket.updated_at
			}

		except Exception as e:
			raise RepositoryError(f"获取篮子摘要失败: {str(e)}")

	async def get_basket_statistics (self, basket_id: str) -> Dict[str, Any]:
		"""
		获取篮子详细统计信息

		Args:
			basket_id: 篮子ID

		Returns:
			详细统计信息字典
		"""
		try:
			# 获取篮子摘要
			summary = await self.get_basket_summary(basket_id)

			if "error" in summary:
				return summary

			# 计算额外统计信息
			items = summary["items"]

			if not items:
				summary.update({
					"max_weight": 0,
					"min_weight": 0,
					"avg_weight": 0,
					"weight_std": 0,
					"concentration_ratio": 0,
					"weight_distribution": []
				})
				return summary

			weights = [item["weight"] for item in items]

			# 计算基本统计
			max_weight = max(weights)
			min_weight = min(weights)
			avg_weight = sum(weights) / len(weights)

			# 计算标准差
			variance = sum((w - avg_weight) ** 2 for w in weights) / len(weights)
			weight_std = variance ** 0.5

			# 计算集中度（前5成分权重和）
			top_5_count = min(5, len(weights))
			sorted_weights = sorted(weights, reverse=True)
			concentration_ratio = sum(sorted_weights[:top_5_count])

			# 权重分布（按区间统计）
			distribution_bins = [0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0]
			distribution = []

			for i in range(len(distribution_bins) - 1):
				low = distribution_bins[i]
				high = distribution_bins[i + 1]

				if i == len(distribution_bins) - 2:
					count = sum(1 for w in weights if low <= w <= high)
				else:
					count = sum(1 for w in weights if low <= w < high)

				if count > 0:
					distribution.append({
						"range": f"{low * 100:.0f}%-{high * 100:.0f}%" if high < 1.0 else f"{low * 100:.0f}%+",
						"count": count,
						"percentage": round(count / len(weights) * 100, 1)
					})

			# 更新统计信息
			summary.update({
				"max_weight": max_weight,
				"min_weight": min_weight,
				"avg_weight": avg_weight,
				"weight_std": weight_std,
				"concentration_ratio": concentration_ratio,
				"top_5_concentration": concentration_ratio,
				"weight_distribution": distribution,
				"statistics_summary": {
					"total_stocks": len(weights),
					"avg_weight_percent": round(avg_weight * 100, 2),
					"weight_range": f"{min_weight * 100:.1f}% - {max_weight * 100:.1f}%",
					"concentration": f"{concentration_ratio * 100:.1f}% (前{top_5_count}只)"
				}
			})

			return summary

		except Exception as e:
			raise RepositoryError(f"获取篮子统计信息失败: {str(e)}")

	async def get_baskets_summary (self) -> List[Dict[str, Any]]:
		"""
		获取所有篮子的简要摘要

		Returns:
			所有篮子简要摘要列表
		"""
		try:
			# 获取所有篮子
			baskets = await self.get_all_baskets()

			summaries = []
			for basket in baskets:
				# 获取篮子项数量
				item_count = await self.basket_item_repo.count(basket_id=basket.id)

				# 获取篮子总权重
				items = await self.get_basket_items(basket.id, limit=1000)
				total_weight = sum(item.weight for item in items) if items else 0

				summaries.append({
					"basket_id": basket.id,
					"basket_name": basket.name,
					"description": basket.description,
					"stock_count": item_count,
					"total_weight": total_weight,
					"created_at": basket.created_at,
					"updated_at": basket.updated_at
				})

			return summaries

		except Exception as e:
			raise RepositoryError(f"获取所有篮子摘要失败: {str(e)}")

	async def get_basket_usage_statistics (self) -> Dict[str, Any]:
		"""
		获取篮子使用统计

		Returns:
			篮子使用统计字典
		"""
		try:
			# 获取篮子总数
			total_baskets = await self.count()

			# 获取有成分的篮子数
			baskets_with_items = await self.session.execute(
				select(func.count(distinct(BasketItem.basket_id)))
			)
			baskets_with_items_count = baskets_with_items.scalar() or 0

			# 获取成分总数
			total_items = await self.basket_item_repo.count()

			# 获取平均成分数
			avg_items_per_basket = total_items / total_baskets if total_baskets > 0 else 0

			# 获取最新篮子创建时间
			latest_basket = await self.session.execute(
				select(self.model).order_by(desc(self.model.created_at)).limit(1)
			)
			latest_basket_record = latest_basket.scalar_one_or_none()

			return {
				"total_baskets": total_baskets,
				"baskets_with_items": baskets_with_items_count,
				"empty_baskets": total_baskets - baskets_with_items_count,
				"total_items": total_items,
				"avg_items_per_basket": round(avg_items_per_basket, 2),
				"latest_basket": {
					"id": latest_basket_record.id if latest_basket_record else None,
					"name": latest_basket_record.name if latest_basket_record else None,
					"created_at": latest_basket_record.created_at if latest_basket_record else None
				},
				"created_today": await self.count(
					func.date(self.model.created_at) == datetime.now().date()
				)
			}

		except Exception as e:
			raise RepositoryError(f"获取篮子使用统计失败: {str(e)}")

	# ==================== 验证和工具方法 ====================

	async def validate_basket_items (self, basket_id: str) -> Dict[str, Any]:
		"""
		验证篮子成分的有效性

		Args:
			basket_id: 篮子ID

		Returns:
			验证结果字典
		"""
		try:
			items = await self.get_basket_items(basket_id)

			if not items:
				return {
					"valid": True,
					"message": "篮子为空",
					"issues": []
				}

			issues = []

			# 检查权重总和
			total_weight = sum(item.weight for item in items)

			if abs(total_weight - 1.0) > 0.0001:  # 允许微小误差
				issues.append({
					"type": "weight_sum",
					"message": f"权重总和为{total_weight:.4f}，应接近1.0",
					"severity": "warning" if abs(total_weight - 1.0) < 0.1 else "error"
				})

			# 检查负权重
			negative_weights = [item.ts_code for item in items if item.weight < 0]
			if negative_weights:
				issues.append({
					"type": "negative_weight",
					"message": f"存在负权重成分: {', '.join(negative_weights)}",
					"severity": "error"
				})

			# 检查权重过大（超过50%）
			large_weights = [(item.ts_code, item.weight) for item in items if item.weight > 0.5]
			if large_weights:
				issues.append({
					"type": "large_weight",
					"message": f"存在权重过大的成分: {', '.join([f'{ts_code}({weight:.1%})' for ts_code, weight in large_weights])}",
					"severity": "warning"
				})

			# 检查重复股票代码
			ts_codes = [item.ts_code for item in items]
			duplicates = {ts_code for ts_code in ts_codes if ts_codes.count(ts_code) > 1}
			if duplicates:
				issues.append({
					"type": "duplicate_ts_code",
					"message": f"存在重复股票代码: {', '.join(duplicates)}",
					"severity": "error"
				})

			return {
				"valid": len(issues) == 0 or all(issue["severity"] != "error" for issue in issues),
				"has_errors": any(issue["severity"] == "error" for issue in issues),
				"has_warnings": any(issue["severity"] == "warning" for issue in issues),
				"total_items": len(items),
				"total_weight": total_weight,
				"issues": issues,
				"summary": {
					"is_valid": len(issues) == 0,
					"issue_count": len(issues),
					"error_count": sum(1 for issue in issues if issue["severity"] == "error"),
					"warning_count": sum(1 for issue in issues if issue["severity"] == "warning")
				}
			}

		except Exception as e:
			raise RepositoryError(f"验证篮子成分失败: {str(e)}")

	async def normalize_basket_weights (self, basket_id: str) -> bool:
		"""
		归一化篮子成分权重（使权重总和为1）

		Args:
			basket_id: 篮子ID

		Returns:
			是否成功归一化
		"""
		try:
			items = await self.get_basket_items(basket_id)

			if not items:
				return True

			# 计算当前权重总和
			total_weight = sum(item.weight for item in items)

			if abs(total_weight - 1.0) < 0.0001:
				return True  # 已经归一化

			if total_weight == 0:
				return False  # 权重总和为0，无法归一化

			# 开始事务
			await self.begin_transaction()

			try:
				# 更新每个成分的权重
				for item in items:
					normalized_weight = item.weight / total_weight
					await self.basket_item_repo.update(item.id, {"weight": normalized_weight})

				# 提交事务
				await self.commit()
				return True

			except Exception as e:
				await self.rollback()
				raise e

		except Exception as e:
			raise RepositoryError(f"归一化篮子权重失败: {str(e)}")

	# ==================== 高级查询 ====================

	async def find_baskets_by_stock (
			self,
			ts_code: str,
			min_weight: Optional[float] = None,
			max_weight: Optional[float] = None
	) -> List[Dict[str, Any]]:
		"""
		查找包含指定股票的篮子

		Args:
			ts_code: 股票代码
			min_weight: 最小权重（可选）
			max_weight: 最大权重（可选）

		Returns:
			包含篮子和权重的列表
		"""
		try:
			query = select(
				Basket.id,
				Basket.name,
				BasketItem.weight,
				BasketItem.created_at
			).join(
				BasketItem, Basket.id == BasketItem.basket_id
			).where(
				BasketItem.ts_code == ts_code
			)

			# 添加权重过滤
			if min_weight is not None:
				query = query.where(BasketItem.weight >= min_weight)
			if max_weight is not None:
				query = query.where(BasketItem.weight <= max_weight)

			query = query.order_by(desc(BasketItem.weight))

			result = await self.session.execute(query)
			rows = result.all()

			return [
				{
					"basket_id": row[0],
					"basket_name": row[1],
					"weight": row[2],
					"added_at": row[3]
				}
				for row in rows
			]

		except Exception as e:
			raise RepositoryError(f"查找包含股票的篮子失败: {str(e)}")

	async def find_common_stocks_across_baskets (
			self,
			basket_ids: List[str]
	) -> List[Dict[str, Any]]:
		"""
		查找多个篮子中的共同股票

		Args:
			basket_ids: 篮子ID列表

		Returns:
			共同股票及在各篮子的权重
		"""
		try:
			if not basket_ids:
				return []

			# 获取所有篮子中的股票
			all_stocks = {}

			for basket_id in basket_ids:
				items = await self.get_basket_items(basket_id)
				for item in items:
					if item.ts_code not in all_stocks:
						all_stocks[item.ts_code] = {}
					all_stocks[item.ts_code][basket_id] = item.weight

			# 找出在所有篮子中都出现的股票
			common_stocks = []
			for ts_code, weights in all_stocks.items():
				if len(weights) == len(basket_ids):
					# 该股票出现在所有篮子中
					common_stocks.append({
						"ts_code": ts_code,
						"weights": weights,
						"avg_weight": sum(weights.values()) / len(weights)
					})

			# 按平均权重排序
			common_stocks.sort(key=lambda x: x["avg_weight"], reverse=True)

			return common_stocks

		except Exception as e:
			raise RepositoryError(f"查找共同股票失败: {str(e)}")