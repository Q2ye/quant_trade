# -*- coding: utf-8 -*-
"""
公司信息Repository
位置：quant_server/shared/database/repositories/market/basic/company_repository.py
职责：管理公司信息表（StockCompany）的数据访问
设计原则：
1. 继承BaseRepository，复用CRUD操作
2. 提供公司特有的查询方法
3. 管理公司与股票、管理层的关系
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, asc
from sqlalchemy.orm import selectinload, joinedload

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.data_models import StockCompany, StockBasic, StkManager


class CompanyRepository(BaseRepository[StockCompany]):
	"""公司信息Repository - 管理StockCompany表的数据访问"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化公司信息Repository

		Args:
			session: 异步数据库会话
		"""
		super().__init__(session, StockCompany)

	# ==================== 公司查询方法 ====================

	async def get_company_with_stock (self, ts_code: str) -> Optional[Dict[str, Any]]:
		"""
		获取公司信息及其对应的股票信息

		Args:
			ts_code: 股票TS代码

		Returns:
			公司及股票信息字典
		"""
		try:
			query = (
				select(StockCompany, StockBasic)
				.join(StockBasic, StockBasic.ts_code == StockCompany.ts_code)
				.where(StockCompany.ts_code == ts_code)
			)

			result = await self.session.execute(query)
			row = result.first()

			if row:
				company, stock = row
				return {
					"company": company,
					"stock": stock,
					"combined_info": {
						"ts_code": company.ts_code,
						"company_name": company.com_name,
						"stock_name": stock.name if stock else None,
						"exchange": company.exchange,
						"province": company.province,
						"city": company.city
					}
				}
			return None
		except Exception as e:
			raise RepositoryError(f"获取公司及股票信息失败: {str(e)}")

	async def get_companies_by_province (self, province: str) -> List[StockCompany]:
		"""
		根据省份获取公司列表

		Args:
			province: 省份名称

		Returns:
			公司列表
		"""
		try:
			query = (
				select(self.model)
				.where(self.model.province == province)
				.order_by(self.model.ts_code)
			)
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"根据省份查询公司失败: {str(e)}")

	async def get_companies_by_city (self, city: str) -> List[StockCompany]:
		"""
		根据城市获取公司列表

		Args:
			city: 城市名称

		Returns:
			公司列表
		"""
		try:
			query = (
				select(self.model)
				.where(self.model.city == city)
				.order_by(self.model.ts_code)
			)
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"根据城市查询公司失败: {str(e)}")

	async def search_companies (self, keyword: str, limit: int = 100) -> List[StockCompany]:
		"""
		搜索公司信息

		Args:
			keyword: 搜索关键词（可匹配公司名、业务等）
			limit: 返回数量限制

		Returns:
			公司列表
		"""
		try:
			query = (
				select(self.model)
				.where(
					or_(
						self.model.com_name.like(f"%{keyword}%"),
						self.model.main_business.like(f"%{keyword}%"),
						self.model.business_scope.like(f"%{keyword}%")
					)
				)
				.order_by(self.model.ts_code)
				.limit(limit)
			)
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"搜索公司失败: {str(e)}")

	async def get_companies_by_employee_range (
			self,
			min_employees: int = None,
			max_employees: int = None
	) -> List[StockCompany]:
		"""
		根据员工人数范围获取公司列表

		Args:
			min_employees: 最小员工数
			max_employees: 最大员工数

		Returns:
			公司列表
		"""
		try:
			query = select(self.model).where(self.model.employees.isnot(None))

			if min_employees is not None:
				query = query.where(self.model.employees >= min_employees)

			if max_employees is not None:
				query = query.where(self.model.employees <= max_employees)

			query = query.order_by(desc(self.model.employees))
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"根据员工人数查询公司失败: {str(e)}")

	# ==================== 公司关联查询方法 ====================

	async def get_company_with_managers (self, ts_code: str) -> Optional[Dict[str, Any]]:
		"""
		获取公司信息及其管理层

		Args:
			ts_code: 股票TS代码

		Returns:
			公司及管理层信息字典
		"""
		try:
			query = (
				select(StockCompany)
				.where(StockCompany.ts_code == ts_code)
				.options(selectinload(StockCompany.managers))
			)

			result = await self.session.execute(query)
			company = result.scalar_one_or_none()

			if company:
				return {
					"company": company,
					"managers": company.managers,
					"manager_count": len(company.managers)
				}
			return None
		except Exception as e:
			raise RepositoryError(f"获取公司及管理层信息失败: {str(e)}")

	async def get_active_managers_count (self, ts_code: str) -> int:
		"""
		获取公司在职管理层数量

		Args:
			ts_code: 股票TS代码

		Returns:
			在职管理层数量
		"""
		try:
			query = (
				select(func.count(StkManager.id))
				.where(StkManager.ts_code == ts_code)
				.where(StkManager.end_date.is_(None))  # 结束日期为None表示在职
			)

			result = await self.session.execute(query)
			return result.scalar() or 0
		except Exception as e:
			raise RepositoryError(f"获取在职管理层数量失败: {str(e)}")

	# ==================== 统计分析方法 ====================

	async def get_province_distribution (self) -> Dict[str, int]:
		"""
		获取省份分布统计

		Returns:
			省份分布字典（省份:公司数量）
		"""
		try:
			query = (
				select(self.model.province, func.count(self.model.ts_code).label('count'))
				.where(self.model.province.isnot(None))
				.group_by(self.model.province)
				.order_by(desc('count'))
			)

			result = await self.session.execute(query)
			rows = result.all()

			return {row.province: row.count for row in rows}
		except Exception as e:
			raise RepositoryError(f"获取省份分布失败: {str(e)}")

	async def get_city_distribution (self, province: str = None) -> Dict[str, int]:
		"""
		获取城市分布统计

		Args:
			province: 省份（可选，用于筛选）

		Returns:
			城市分布字典（城市:公司数量）
		"""
		try:
			query = (
				select(self.model.city, func.count(self.model.ts_code).label('count'))
				.where(self.model.city.isnot(None))
			)

			if province:
				query = query.where(self.model.province == province)

			query = query.group_by(self.model.city).order_by(desc('count'))

			result = await self.session.execute(query)
			rows = result.all()

			return {row.city: row.count for row in rows}
		except Exception as e:
			raise RepositoryError(f"获取城市分布失败: {str(e)}")

	async def get_employee_statistics (self) -> Dict[str, Any]:
		"""
		获取员工人数统计

		Returns:
			员工人数统计信息
		"""
		try:
			query = select(
				func.count(self.model.ts_code).label('total_companies'),
				func.sum(self.model.employees).label('total_employees'),
				func.avg(self.model.employees).label('avg_employees'),
				func.max(self.model.employees).label('max_employees'),
				func.min(self.model.employees).label('min_employees')
			).where(self.model.employees.isnot(None))

			result = await self.session.execute(query)
			row = result.first()

			if row:
				return {
					"total_companies": row.total_companies,
					"total_employees": row.total_employees,
					"average_employees": float(row.avg_employees) if row.avg_employees else 0,
					"max_employees": row.max_employees,
					"min_employees": row.min_employees
				}
			return {}
		except Exception as e:
			raise RepositoryError(f"获取员工人数统计失败: {str(e)}")

	# ==================== 批量操作方法 ====================

	async def bulk_upsert_companies (self, company_data_list: List[Dict[str, Any]]) -> List[StockCompany]:
		"""
		批量插入或更新公司信息

		Args:
			company_data_list: 公司数据列表

		Returns:
			更新后的公司列表
		"""
		try:
			return await self.batch_upsert(
				match_fields=["ts_code"],
				data_list=company_data_list,
				update_fields=None  # 更新所有字段
			)
		except Exception as e:
			raise RepositoryError(f"批量插入或更新公司失败: {str(e)}")

	async def update_company_employees (self, ts_code: str, employees: int) -> Optional[StockCompany]:
		"""
		更新公司员工人数

		Args:
			ts_code: 股票TS代码
			employees: 员工人数

		Returns:
			更新后的公司对象
		"""
		try:
			return await self.update_by(
				filters={"ts_code": ts_code},
				data={"employees": employees, "updated_at": datetime.now()}
			)
		except Exception as e:
			raise RepositoryError(f"更新公司员工人数失败: {str(e)}")


class RepositoryError(Exception):
	"""Repository异常基类"""

	def __init__ (self, message: str, code: str = "COMPANY_REPOSITORY_ERROR"):
		"""
		初始化异常

		Args:
			message: 错误信息
			code: 错误码
		"""
		self.message = message
		self.code = code
		super().__init__(self.message)