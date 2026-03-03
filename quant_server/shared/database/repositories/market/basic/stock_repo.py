# -*- coding: utf-8 -*-
"""
股票基础信息Repository
位置：quant_server/shared/database/repositories/market/basic/stock_basic_repository.py
职责：管理股票基础信息表（StockBasic）的数据访问
设计原则：
1. 继承BaseRepository，复用CRUD操作
2. 提供股票特有的查询方法
3. 处理股票行业、地域等维度的聚合查询
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, desc

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.repositories.types import (
	PaginationParams,
	PaginationResult,
	FilterCondition,
	SortCondition
)
from quant_server.shared.database.models.data_models import StockBasic, StockCompany


class StockBasicRepository(BaseRepository[StockBasic]):
	"""股票基础信息Repository - 管理StockBasic表的数据访问"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化股票基础信息Repository

		Args:
			session: 异步数据库会话
		"""
		super().__init__(session, StockBasic)

	# ==================== 股票查询方法 ====================

	async def get_by_symbol (self, symbol: str) -> Optional[StockBasic]:
		"""
		根据股票代码获取股票信息

		Args:
			symbol: 股票代码（如'000001.SZ'）

		Returns:
			StockBasic对象或None
		"""
		try:
			return await self.get_by(symbol=symbol)
		except Exception as e:
			raise RepositoryError(f"根据symbol查询失败: {str(e)}")

	async def get_by_ts_code (self, ts_code: str) -> Optional[StockBasic]:
		"""
		根据股票TS代码获取股票信息

		Args:
			ts_code: 股票TS代码（如'000001.SZ'）

		Returns:
			StockBasic对象或None
		"""
		try:
			return await self.get_by(ts_code=ts_code)
		except Exception as e:
			raise RepositoryError(f"根据ts_code查询失败: {str(e)}")

	async def get_by_name (self, name: str) -> List[StockBasic]:
		"""
		根据股票名称获取股票列表

		Args:
			name: 股票名称（支持模糊匹配）

		Returns:
			股票列表
		"""
		try:
			query = select(self.model).where(self.model.name.like(f"%{name}%"))
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"根据name查询失败: {str(e)}")

	async def get_by_industry (self, industry: str, limit: int = 100) -> List[StockBasic]:
		"""
		根据行业获取股票列表

		Args:
			industry: 行业名称
			limit: 返回数量限制

		Returns:
			行业股票列表
		"""
		try:
			query = (
				select(self.model)
				.where(self.model.industry == industry)
				.order_by(self.model.symbol)
				.limit(limit)
			)
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"根据industry查询失败: {str(e)}")

	async def get_by_market (self, market: str, active_only: bool = True) -> List[StockBasic]:
		"""
		根据市场获取股票列表

		Args:
			market: 市场类型（如'主板', '创业板'等）
			active_only: 是否只返回上市状态股票

		Returns:
			市场股票列表
		"""
		try:
			query = select(self.model).where(self.model.market == market)

			if active_only:
				query = query.where(self.model.list_status == 'L')

			query = query.order_by(self.model.symbol)
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"根据market查询失败: {str(e)}")

	async def get_stock_with_company (self, ts_code: str) -> Optional[Dict[str, Any]]:
		"""
		获取股票信息及其公司信息

		Args:
			ts_code: 股票TS代码

		Returns:
			股票及公司信息字典
		"""
		try:
			query = (
				select(StockBasic, StockCompany)
				.join(StockCompany, StockCompany.ts_code == StockBasic.ts_code)
				.where(StockBasic.ts_code == ts_code)
			)

			result = await self.session.execute(query)
			row = result.first()

			if row:
				stock, company = row
				return {
					"stock": stock,
					"company": company,
					"combined_info": {
						"symbol": stock.symbol,
						"name": stock.name,
						"industry": stock.industry,
						"company_name": company.com_name if company else None,
						"province": company.province if company else None,
						"employees": company.employees if company else None
					}
				}
			return None
		except Exception as e:
			raise RepositoryError(f"获取股票及公司信息失败: {str(e)}")

	# ==================== 统计分析方法 ====================

	async def get_industry_distribution (self) -> Dict[str, int]:
		"""
		获取行业分布统计

		Returns:
			行业分布字典（行业:股票数量）
		"""
		try:
			query = (
				select(self.model.industry, func.count(self.model.ts_code).label('count'))
				.where(self.model.industry.isnot(None))
				.group_by(self.model.industry)
				.order_by(desc('count'))
			)

			result = await self.session.execute(query)
			rows = result.all()

			return {row.industry: row.count for row in rows}
		except Exception as e:
			raise RepositoryError(f"获取行业分布失败: {str(e)}")

	async def get_market_distribution (self) -> Dict[str, int]:
		"""
		获取市场分布统计

		Returns:
			市场分布字典（市场:股票数量）
		"""
		try:
			query = (
				select(self.model.market, func.count(self.model.ts_code).label('count'))
				.group_by(self.model.market)
				.order_by(desc('count'))
			)

			result = await self.session.execute(query)
			rows = result.all()

			return {row.market: row.count for row in rows}
		except Exception as e:
			raise RepositoryError(f"获取市场分布失败: {str(e)}")

	async def get_area_distribution (self) -> Dict[str, int]:
		"""
		获取地域分布统计

		Returns:
			地域分布字典（地域:股票数量）
		"""
		try:
			query = (
				select(self.model.area, func.count(self.model.ts_code).label('count'))
				.where(self.model.area.isnot(None))
				.group_by(self.model.area)
				.order_by(desc('count'))
			)

			result = await self.session.execute(query)
			rows = result.all()

			return {row.area: row.count for row in rows}
		except Exception as e:
			raise RepositoryError(f"获取地域分布失败: {str(e)}")

	async def get_list_status_summary (self) -> Dict[str, int]:
		"""
		获取上市状态统计

		Returns:
			上市状态分布字典（状态:股票数量）
		"""
		try:
			query = (
				select(self.model.list_status, func.count(self.model.ts_code).label('count'))
				.group_by(self.model.list_status)
			)

			result = await self.session.execute(query)
			rows = result.all()

			return {row.list_status: row.count for row in rows}
		except Exception as e:
			raise RepositoryError(f"获取上市状态统计失败: {str(e)}")

	# ==================== 高级查询方法 ====================

	async def search_stocks (
			self,
			keyword: str,
			pagination: PaginationParams = None,
			filters: List[FilterCondition] = None,
			sorts: List[SortCondition] = None
	) -> PaginationResult[StockBasic]:
		"""
		搜索股票（支持分页、过滤、排序）

		Args:
			keyword: 搜索关键词（可匹配代码、名称、拼音缩写）
			pagination: 分页参数
			filters: 过滤条件列表
			sorts: 排序条件列表

		Returns:
			分页搜索结果
		"""
		try:
			# 构建基础查询
			query = select(self.model).where(
				or_(
					self.model.ts_code.like(f"%{keyword}%"),
					self.model.symbol.like(f"%{keyword}%"),
					self.model.name.like(f"%{keyword}%"),
					self.model.cnspell.like(f"%{keyword}%")
				)
			)

			# 合并过滤器
			all_filters = filters or []

			# 添加默认排序（按代码升序）
			all_sorts = sorts or [SortCondition(field="symbol", descending=False)]

			# 使用基类的分页方法
			if pagination is None:
				pagination = PaginationParams(page=1, page_size=100)

			return await self.paginate(pagination, all_filters, all_sorts)
		except Exception as e:
			raise RepositoryError(f"搜索股票失败: {str(e)}")

	async def get_stocks_by_list_date_range (
			self,
			start_date: date,
			end_date: date,
			pagination: PaginationParams = None
	) -> PaginationResult[StockBasic]:
		"""
		获取指定上市日期范围内的股票

		Args:
			start_date: 开始日期
			end_date: 结束日期
			pagination: 分页参数

		Returns:
			分页结果
		"""
		try:
			filters = [
				FilterCondition(field="list_date", operator="gte", value=start_date),
				FilterCondition(field="list_date", operator="lte", value=end_date)
			]

			sorts = [SortCondition(field="list_date", descending=False)]

			if pagination is None:
				pagination = PaginationParams(page=1, page_size=100)

			return await self.paginate(pagination, filters, sorts)
		except Exception as e:
			raise RepositoryError(f"按上市日期范围查询失败: {str(e)}")

	# ==================== 批量操作方法 ====================

	async def bulk_upsert_stocks (self, stock_data_list: List[Dict[str, Any]]) -> List[StockBasic]:
		"""
		批量插入或更新股票信息

		Args:
			stock_data_list: 股票数据列表

		Returns:
			更新后的股票列表
		"""
		try:
			return await self.batch_upsert(
				match_fields=["ts_code"],
				data_list=stock_data_list,
				update_fields=None  # 更新所有字段
			)
		except Exception as e:
			raise RepositoryError(f"批量插入或更新股票失败: {str(e)}")

	async def update_stock_status (self, ts_code: str, list_status: str) -> Optional[StockBasic]:
		"""
		更新股票上市状态

		Args:
			ts_code: 股票TS代码
			list_status: 上市状态（L-上市，D-退市，P-暂停上市）

		Returns:
			更新后的股票对象
		"""
		try:
			update_data = {
				"list_status": list_status,
				"updated_at": datetime.now()
			}

			if list_status == 'D':  # 退市
				update_data["delist_date"] = datetime.now()

			return await self.update_by(
				filters={"ts_code": ts_code},
				data=update_data
			)
		except Exception as e:
			raise RepositoryError(f"更新股票状态失败: {str(e)}")

	# ==================== 数据验证方法 ====================
	async def validate_stock_exists (self, ts_code: str) -> bool:
		"""
		验证股票是否存在

		Args:
			ts_code: 股票TS代码

		Returns:
			是否存在
		"""
		try:
			return await self.exists(ts_code=ts_code)
		except Exception as e:
			raise RepositoryError(f"验证股票存在性失败: {str(e)}")

	async def get_active_stocks(self, limit: int = 0) -> List[StockBasic]:
		"""
		获取活跃（上市）股票列表

		Args:
			limit: 返回数量限制（0表示无限制）

		Returns:
			活跃股票列表
		"""
		try:
			query = select(self.model).where(
				self.model.list_status == 'L'
			).order_by(self.model.ts_code)

			if limit > 0:
				query = query.limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取活跃股票列表失败: {str(e)}")

	async def get_active_stocks_count (self) -> int:
		"""
		获取活跃（上市）股票数量

		Returns:
			活跃股票数量
		"""
		try:
			return await self.count(list_status='L')
		except Exception as e:
			raise RepositoryError(f"获取活跃股票数量失败: {str(e)}")


class RepositoryError(Exception):
	"""Repository异常基类"""

	def __init__ (self, message: str, code: str = "STOCK_BASIC_REPOSITORY_ERROR"):
		"""
		初始化异常

		Args:
			message: 错误信息
			code: 错误码
		"""
		self.message = message
		self.code = code
		super().__init__(self.message)