# -*- coding: utf-8 -*-
"""
# 公司信息数据仓库
# 位置：quant_server/shared/database/repositories/company_repo.py
# 职责：管理公司基本信息、管理层、薪酬等数据访问
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func, text
from sqlalchemy.orm import selectinload, joinedload

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.data_models import (
	StockCompany,
	StkManager,
	StkReward
)


class CompanyRepository:
	"""公司信息数据仓库 - 负责公司相关数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.company_repo = BaseRepository[StockCompany](session, StockCompany)
		self.manager_repo = BaseRepository[StkManager](session, StkManager)
		self.reward_repo = BaseRepository[StkReward](session, StkReward)

	# ==================== 公司基本信息操作 ====================

	async def get_company_by_ts_code (self, ts_code: str) -> Optional[StockCompany]:
		"""
		根据股票代码获取公司信息

		Args:
			ts_code: 股票代码

		Returns:
			公司信息或None
		"""
		return await self.company_repo.get_by(ts_code=ts_code)

	async def get_companies_by_industry (self, industry_keyword: str) -> List[StockCompany]:
		"""
		根据行业关键词获取公司列表

		Args:
			industry_keyword: 行业关键词

		Returns:
			公司列表
		"""
		# 注意：行业信息可能在其他表中，这里简化处理
		query = select(StockCompany).where(
			StockCompany.main_business.like(f"%{industry_keyword}%")
		).order_by(StockCompany.ts_code)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_companies_by_region (
			self,
			province: str = None,
			city: str = None
	) -> List[StockCompany]:
		"""
		根据地区获取公司列表

		Args:
			province: 省份（可选）
			city: 城市（可选）

		Returns:
			公司列表
		"""
		query = select(StockCompany)

		if province:
			query = query.where(StockCompany.province == province)

		if city:
			query = query.where(StockCompany.city == city)

		query = query.order_by(StockCompany.ts_code)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def search_companies (
			self,
			keyword: str,
			limit: int = 100,
			skip: int = 0
	) -> List[StockCompany]:
		"""
		搜索公司信息

		Args:
			keyword: 搜索关键词（可匹配公司名、主营业务等）
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			公司列表
		"""
		query = select(StockCompany).where(
			or_(
				StockCompany.com_name.like(f"%{keyword}%"),
				StockCompany.main_business.like(f"%{keyword}%"),
				StockCompany.business_scope.like(f"%{keyword}%")
			)
		).order_by(StockCompany.ts_code).offset(skip).limit(limit)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def create_company (self, company_data: Dict[str, Any]) -> StockCompany:
		"""
		创建公司信息

		Args:
			company_data: 公司数据

		Returns:
			创建的公司信息
		"""
		return await self.company_repo.create(company_data)

	async def update_company (self, ts_code: str, update_data: Dict[str, Any]) -> Optional[StockCompany]:
		"""
		更新公司信息

		Args:
			ts_code: 股票代码
			update_data: 更新数据

		Returns:
			更新后的公司信息
		"""
		company = await self.company_repo.get_by(ts_code=ts_code)
		if not company:
			return None

		return await self.company_repo.update(company.ts_code, update_data)

	async def get_company_with_managers (self, ts_code: str) -> Optional[Dict[str, Any]]:
		"""
		获取公司信息及其管理层

		Args:
			ts_code: 股票代码

		Returns:
			公司信息及管理层数据
		"""
		company = await self.get_company_by_ts_code(ts_code)
		if not company:
			return None

		# 获取管理层信息
		managers = await self.get_managers_by_company(ts_code)

		return {
			"company": company,
			"managers": managers,
			"manager_count": len(managers)
		}

	# ==================== 管理层信息操作 ====================

	async def get_manager_by_id (self, manager_id: int) -> Optional[StkManager]:
		"""
		根据ID获取管理层信息

		Args:
			manager_id: 管理层ID

		Returns:
			管理层信息或None
		"""
		return await self.manager_repo.get(manager_id)

	async def get_managers_by_company (
			self,
			ts_code: str,
			active_only: bool = True
	) -> List[StkManager]:
		"""
		获取公司的所有管理层

		Args:
			ts_code: 股票代码
			active_only: 是否只获取在职人员

		Returns:
			管理层列表
		"""
		query = select(StkManager).where(
			StkManager.ts_code == ts_code
		).order_by(StkManager.ann_date.desc())

		if active_only:
			query = query.where(StkManager.end_date.is_(None))

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_managers_by_position (
			self,
			ts_code: str,
			position: str
	) -> List[StkManager]:
		"""
		获取公司特定职位的管理层

		Args:
			ts_code: 股票代码
			position: 职位关键词

		Returns:
			管理层列表
		"""
		query = select(StkManager).where(
			and_(
				StkManager.ts_code == ts_code,
				StkManager.title.like(f"%{position}%")
			)
		).order_by(StkManager.ann_date.desc())

		result = await self.session.execute(query)
		return result.scalars().all()

	async def create_manager (self, manager_data: Dict[str, Any]) -> StkManager:
		"""
		创建管理层信息

		Args:
			manager_data: 管理层数据

		Returns:
			创建的管理层信息
		"""
		return await self.manager_repo.create(manager_data)

	async def update_manager (
			self,
			manager_id: int,
			update_data: Dict[str, Any]
	) -> Optional[StkManager]:
		"""
		更新管理层信息

		Args:
			manager_id: 管理层ID
			update_data: 更新数据

		Returns:
			更新后的管理层信息
		"""
		return await self.manager_repo.update(manager_id, update_data)

	async def get_manager_with_rewards (self, manager_id: int) -> Optional[Dict[str, Any]]:
		"""
		获取管理层信息及其薪酬

		Args:
			manager_id: 管理层ID

		Returns:
			管理层信息及薪酬数据
		"""
		manager = await self.get_manager_by_id(manager_id)
		if not manager:
			return None

		# 获取薪酬信息
		rewards = await self.get_rewards_by_manager(manager_id)

		total_reward = sum(reward.reward for reward in rewards) if rewards else 0
		total_holdings = sum(reward.hold_vol for reward in rewards) if rewards else 0

		return {
			"manager": manager,
			"rewards": rewards,
			"reward_count": len(rewards),
			"total_reward": total_reward,
			"total_holdings": total_holdings
		}

	# ==================== 薪酬信息操作 ====================

	async def get_reward_by_id (self, reward_id: int) -> Optional[StkReward]:
		"""
		根据ID获取薪酬信息

		Args:
			reward_id: 薪酬ID

		Returns:
			薪酬信息或None
		"""
		return await self.reward_repo.get(reward_id)

	async def get_rewards_by_manager (self, manager_id: int) -> List[StkReward]:
		"""
		获取管理层的所有薪酬记录

		Args:
			manager_id: 管理层ID

		Returns:
			薪酬记录列表
		"""
		return await self.reward_repo.get_many(manager_id=manager_id)

	async def get_rewards_by_year (
			self,
			ts_code: str,
			year: int
	) -> List[StkReward]:
		"""
		获取公司某年度的薪酬记录

		Args:
			ts_code: 股票代码
			year: 年份

		Returns:
			薪酬记录列表
		"""
		query = select(StkReward).join(StkManager).where(
			and_(
				StkManager.ts_code == ts_code,
				func.extract('year', StkReward.ann_date) == year
			)
		).order_by(StkReward.ann_date.desc())

		result = await self.session.execute(query)
		return result.scalars().all()

	async def create_reward (self, reward_data: Dict[str, Any]) -> StkReward:
		"""
		创建薪酬记录

		Args:
			reward_data: 薪酬数据

		Returns:
			创建的薪酬记录
		"""
		return await self.reward_repo.create(reward_data)

	async def update_reward (
			self,
			reward_id: int,
			update_data: Dict[str, Any]
	) -> Optional[StkReward]:
		"""
		更新薪酬记录

		Args:
			reward_id: 薪酬ID
			update_data: 更新数据

		Returns:
			更新后的薪酬记录
		"""
		return await self.reward_repo.update(reward_id, update_data)

	# ==================== 统计分析操作 ====================

	async def get_company_summary (self, ts_code: str) -> Dict[str, Any]:
		"""
		获取公司概要统计信息

		Args:
			ts_code: 股票代码

		Returns:
			公司概要统计
		"""
		company = await self.get_company_by_ts_code(ts_code)
		if not company:
			return {}

		# 统计管理层
		managers = await self.get_managers_by_company(ts_code, active_only=True)
		active_managers = [m for m in managers if m.end_date is None]

		# 按职位统计
		position_stats = {}
		for manager in active_managers:
			position = manager.title.split()[0] if manager.title else "未知"
			if position not in position_stats:
				position_stats[position] = 0
			position_stats[position] += 1

		# 获取最新薪酬信息
		latest_rewards_query = select(StkReward).join(StkManager).where(
			StkManager.ts_code == ts_code
		).order_by(desc(StkReward.ann_date)).limit(10)

		latest_rewards_result = await self.session.execute(latest_rewards_query)
		latest_rewards = latest_rewards_result.scalars().all()

		total_reward = sum(r.reward for r in latest_rewards)
		avg_reward = total_reward / len(latest_rewards) if latest_rewards else 0

		return {
			"company_info": {
				"ts_code": company.ts_code,
				"company_name": company.com_name,
				"exchange": company.exchange,
				"employees": company.employees,
				"registered_capital": company.reg_capital,
				"province": company.province,
				"city": company.city
			},
			"management_stats": {
				"total_managers": len(managers),
				"active_managers": len(active_managers),
				"position_distribution": position_stats
			},
			"compensation_stats": {
				"latest_rewards_count": len(latest_rewards),
				"total_reward_latest": total_reward,
				"average_reward": avg_reward
			}
		}

	async def get_industry_comparison (
			self,
			industry_keyword: str
	) -> Dict[str, Any]:
		"""
		获取行业对比数据

		Args:
			industry_keyword: 行业关键词

		Returns:
			行业对比数据
		"""
		# 获取行业内公司
		companies = await self.get_companies_by_industry(industry_keyword)

		if not companies:
			return {}

		# 统计基本信息
		employee_stats = []
		capital_stats = []
		region_stats = {}

		for company in companies:
			if company.employees:
				employee_stats.append(company.employees)

			if company.reg_capital:
				capital_stats.append(float(company.reg_capital))

			region = f"{company.province}-{company.city}" if company.province and company.city else "未知"
			if region not in region_stats:
				region_stats[region] = 0
			region_stats[region] += 1

		return {
			"industry": industry_keyword,
			"company_count": len(companies),
			"employee_statistics": {
				"total": sum(employee_stats) if employee_stats else 0,
				"average": sum(employee_stats) / len(employee_stats) if employee_stats else 0,
				"max": max(employee_stats) if employee_stats else 0,
				"min": min(employee_stats) if employee_stats else 0
			},
			"capital_statistics": {
				"total": sum(capital_stats) if capital_stats else 0,
				"average": sum(capital_stats) / len(capital_stats) if capital_stats else 0,
				"max": max(capital_stats) if capital_stats else 0,
				"min": min(capital_stats) if capital_stats else 0
			},
			"region_distribution": region_stats
		}

	# ==================== 批量操作 ====================

	async def batch_create_companies (self, companies_data: List[Dict[str, Any]]) -> List[StockCompany]:
		"""
		批量创建公司信息

		Args:
			companies_data: 公司数据列表

		Returns:
			创建的公司信息列表
		"""
		return await self.company_repo.batch_create(companies_data)

	async def batch_create_managers (self, managers_data: List[Dict[str, Any]]) -> List[StkManager]:
		"""
		批量创建管理层信息

		Args:
			managers_data: 管理层数据列表

		Returns:
			创建的管理层信息列表
		"""
		return await self.manager_repo.batch_create(managers_data)

	async def batch_create_rewards (self, rewards_data: List[Dict[str, Any]]) -> List[StkReward]:
		"""
		批量创建薪酬记录

		Args:
			rewards_data: 薪酬数据列表

		Returns:
			创建的薪酬记录列表
		"""
		return await self.reward_repo.batch_create(rewards_data)