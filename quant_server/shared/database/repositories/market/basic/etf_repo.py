# -*- coding: utf-8 -*-
"""
ETF数据仓库
位置：quant_server/shared/database/repositories/market/basic/etf_repo.py
职责：管理ETF基础信息、持仓、行情等数据访问
设计原则：继承BaseRepository，使用统一数据访问接口
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models import (
	EtfBasic,
	EtfIndex,
	EtfDaily,
	EtfMinute,
	FundAdjFactor
)
from shared.database.repositories.base import BaseRepository, RepositoryError


class EtfBasicRepository(BaseRepository[EtfBasic]):
	"""ETF基础信息仓库 - 继承BaseRepository"""

	def __init__ (self, session: AsyncSession):
		"""初始化ETF基础信息仓库"""
		super().__init__(session, EtfBasic)

	async def search_by_keyword (self, keyword: str, limit: int = 100, skip: int = 0) -> List[EtfBasic]:
		"""
		根据关键词搜索ETF

		Args:
			keyword: 搜索关键词（匹配代码、简称、全称）
			limit: 返回数量限制
			skip: 跳过记录数

		Returns:
			ETF基础信息列表
		"""
		try:
			query = select(self.model).where(
				or_(
					self.model.ts_code.like(f"%{keyword}%"),
					self.model.name.like(f"%{keyword}%"),
					self.model.name.like(f"%{keyword}%"),
					self.model.name.like(f"%{keyword}%")
				)
			).order_by(self.model.ts_code).offset(skip).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"搜索ETF失败: {str(e)}")

	async def get_by_exchange (self, exchange: str) -> List[EtfBasic]:
		"""
		根据交易所获取ETF列表

		Args:
			exchange: 交易所代码

		Returns:
			ETF列表
		"""
		return await self.get_many(exchange=exchange)

	async def get_by_fund_type (self, fund_type: str) -> List[EtfBasic]:
		"""
		根据基金类型获取ETF列表

		Args:
			fund_type: 基金类型

		Returns:
			ETF列表
		"""
		return await self.get_many(etf_type=fund_type)

	async def get_by_index_code (self, index_code: str) -> List[EtfBasic]:
		"""
		根据跟踪指数代码获取ETF列表

		Args:
			index_code: 指数代码

		Returns:
			ETF列表
		"""
		return await self.get_many(index_code=index_code)


class EtfIndexRepository(BaseRepository[EtfIndex]):
	"""ETF跟踪指数仓库 - 继承BaseRepository"""

	def __init__ (self, session: AsyncSession):
		"""初始化ETF指数仓库"""
		super().__init__(session, EtfIndex)

	async def search_by_keyword (self, keyword: str, limit: int = 50, skip: int = 0) -> List[EtfIndex]:
		"""
		根据关键词搜索指数

		Args:
			keyword: 搜索关键词（匹配代码、名称、简称）
			limit: 返回数量限制
			skip: 跳过记录数

		Returns:
			指数列表
		"""
		try:
			query = select(self.model).where(
				or_(
					self.model.ts_code.like(f"%{keyword}%"),
					self.model.indx_name.like(f"%{keyword}%"),
					self.model.indx_csname.like(f"%{keyword}%")
				)
			).order_by(self.model.ts_code).offset(skip).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"搜索指数失败: {str(e)}")


class EtfDailyRepository(BaseRepository[EtfDaily]):
	"""ETF日线行情仓库 - 继承BaseRepository"""

	def __init__ (self, session: AsyncSession):
		"""初始化ETF日线行情仓库"""
		super().__init__(session, EtfDaily)

	async def get_by_date_range (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[EtfDaily]:
		"""
		获取指定时间范围内的ETF日线行情

		Args:
			ts_code: ETF代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			ETF日线行情列表
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.ts_code == ts_code,
					self.model.trade_date >= start_date,
					self.model.trade_date <= end_date
				)
			).order_by(self.model.trade_date)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取ETF日线行情失败: {str(e)}")

	async def get_latest_by_ts_code (self, ts_code: str) -> Optional[EtfDaily]:
		"""
		获取最新的ETF日线行情

		Args:
			ts_code: ETF代码

		Returns:
			最新的ETF日线行情或None
		"""
		try:
			query = select(self.model).where(
				self.model.ts_code == ts_code
			).order_by(desc(self.model.trade_date)).limit(1)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"获取最新ETF日线行情失败: {str(e)}")


class EtfMinuteRepository(BaseRepository[EtfMinute]):
	"""ETF分钟行情仓库 - 继承BaseRepository"""

	def __init__ (self, session: AsyncSession):
		"""初始化ETF分钟行情仓库"""
		super().__init__(session, EtfMinute)

	async def get_by_time_range (
			self,
			ts_code: str,
			start_time: datetime,
			end_time: datetime,
			freq: str = "1min"
	) -> List[EtfMinute]:
		"""
		获取指定时间范围内的ETF分钟行情

		Args:
			ts_code: ETF代码
			start_time: 开始时间
			end_time: 结束时间
			freq: 频率（1min/5min/15min/30min/60min）

		Returns:
			ETF分钟行情列表
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.ts_code == ts_code,
					self.model.trade_time >= start_time,
					self.model.trade_time <= end_time,
					self.model.freq == freq
				)
			).order_by(self.model.trade_time)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取ETF分钟行情失败: {str(e)}")


class FundAdjFactorRepository(BaseRepository[FundAdjFactor]):
	"""基金复权因子仓库 - 继承BaseRepository"""

	def __init__ (self, session: AsyncSession):
		"""初始化基金复权因子仓库"""
		super().__init__(session, FundAdjFactor)

	async def get_by_date_range (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[FundAdjFactor]:
		"""
		获取指定时间范围内的复权因子

		Args:
			ts_code: ETF代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			复权因子列表
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.ts_code == ts_code,
					self.model.trade_date >= start_date,
					self.model.trade_date <= end_date
				)
			).order_by(self.model.trade_date)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取复权因子失败: {str(e)}")

	async def get_latest_by_ts_code (self, ts_code: str) -> Optional[FundAdjFactor]:
		"""
		获取最新的复权因子

		Args:
			ts_code: ETF代码

		Returns:
			最新的复权因子或None
		"""
		try:
			query = select(self.model).where(
				self.model.ts_code == ts_code
			).order_by(desc(self.model.trade_date)).limit(1)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"获取最新复权因子失败: {str(e)}")


# ==================== ETF聚合仓库（协调多个具体仓库）====================

class ETFRepository:
	"""ETF聚合仓库 - 协调ETF相关所有数据访问"""

	def __init__ (self, session: AsyncSession):
		"""初始化ETF聚合仓库"""
		self.session = session
		self.etf_basic_repo = EtfBasicRepository(session)
		self.etf_index_repo = EtfIndexRepository(session)
		self.etf_daily_repo = EtfDailyRepository(session)
		self.etf_minute_repo = EtfMinuteRepository(session)
		self.adj_factor_repo = FundAdjFactorRepository(session)

	# ==================== 基础信息操作 ====================

	async def get_etf_basic (self, ts_code: str) -> Optional[EtfBasic]:
		"""获取ETF基础信息"""
		return await self.etf_basic_repo.get_by(ts_code=ts_code)

	async def get_by_ts_code (self, ts_code: str) -> Optional[Dict[str, Any]]:
		"""
		根据ETF代码获取完整的ETF信息（基础信息+指数+最新行情）

		Args:
			ts_code: ETF代码

		Returns:
			完整的ETF信息字典或None
		"""
		try:
			# 获取基础信息
			etf_basic = await self.get_etf_basic(ts_code)
			if not etf_basic:
				return None

			# 获取最新行情
			latest_daily = await self.get_latest_etf_daily(ts_code)

			# 获取指数信息
			index_info = None
			if etf_basic.index_code:
				index_info = await self.get_etf_index(etf_basic.index_code)

			return {
				"basic_info": {
					"ts_code": etf_basic.ts_code,
					"name": etf_basic.name,
					"short_name": etf_basic.name,
					"exchange": etf_basic.exchange,
					"fund_type": etf_basic.fund_type,
					"manager": etf_basic.management,
					"setup_date": etf_basic.found_date,
					"list_date": etf_basic.list_date,
					"management_fee": etf_basic.m_fee
				},
				"index_info": {
					"index_code": etf_basic.index_code,
					"index_name": etf_basic.index_name,
					"base_index": index_info.indx_name if index_info else None,
					"base_date": index_info.base_date if index_info else None
				} if etf_basic.index_code else {},
				"latest_price": {
					"trade_date": latest_daily.trade_date if latest_daily else None,
					"close": latest_daily.close if latest_daily else None,
					"change": latest_daily.change if latest_daily else None,
					"pct_chg": latest_daily.pct_chg if latest_daily else None,
					"volume": latest_daily.vol if latest_daily else None,
					"amount": latest_daily.amount if latest_daily else None
				} if latest_daily else {}
			}

		except Exception as e:
			raise RepositoryError(f"获取ETF信息失败: {str(e)}")

	async def search_etfs (self, keyword: str, limit: int = 100, skip: int = 0) -> List[EtfBasic]:
		"""搜索ETF"""
		return await self.etf_basic_repo.search_by_keyword(keyword, limit, skip)

	async def get_all_etfs (self, active_only: bool = True, limit: Optional[int] = None, offset: int = 0) -> List[EtfBasic]:
		"""获取所有ETF"""
		if active_only:
			if limit:
				return await self.etf_basic_repo.get_many(list_status="L", limit=limit, skip=offset)
			return await self.etf_basic_repo.get_many(list_status="L")
		if limit:
			return await self.etf_basic_repo.get_all(limit=limit)
		return await self.etf_basic_repo.get_all()

	async def count_etfs(self, active_only: bool = True) -> int:
		"""统计ETF总数"""
		if active_only:
			return await self.etf_basic_repo.count(list_status="L")
		return await self.etf_basic_repo.count()

	# ==================== 行情数据操作 ====================

	async def get_etf_daily (self, ts_code: str, trade_date: date) -> Optional[EtfDaily]:
		"""获取ETF日线行情"""
		return await self.etf_daily_repo.get_by(
			ts_code=ts_code,
			trade_date=trade_date
		)

	async def get_etf_daily_range (self, ts_code: str, start_date: date, end_date: date) -> List[EtfDaily]:
		"""获取ETF日线行情范围"""
		return await self.etf_daily_repo.get_by_date_range(ts_code, start_date, end_date)

	async def get_latest_etf_daily (self, ts_code: str) -> Optional[EtfDaily]:
		"""获取最新ETF日线行情"""
		return await self.etf_daily_repo.get_latest_by_ts_code(ts_code)

	# ==================== 指数信息操作 ====================

	async def get_etf_index (self, ts_code: str) -> Optional[EtfIndex]:
		"""获取ETF跟踪指数信息"""
		return await self.etf_index_repo.get_by(ts_code=ts_code)

	async def search_indices (self, keyword: str, limit: int = 50, skip: int = 0) -> List[EtfIndex]:
		"""搜索指数"""
		return await self.etf_index_repo.search_by_keyword(keyword, limit, skip)

	# ==================== 复权因子操作 ====================

	async def get_adj_factor (self, ts_code: str, trade_date: date) -> Optional[FundAdjFactor]:
		"""获取复权因子"""
		return await self.adj_factor_repo.get_by(
			ts_code=ts_code,
			trade_date=trade_date
		)

	async def get_adj_factors_range (self, ts_code: str, start_date: date, end_date: date) -> List[FundAdjFactor]:
		"""获取复权因子范围"""
		return await self.adj_factor_repo.get_by_date_range(ts_code, start_date, end_date)

	async def get_latest_adj_factor (self, ts_code: str) -> Optional[FundAdjFactor]:
		"""获取最新复权因子"""
		return await self.adj_factor_repo.get_latest_by_ts_code(ts_code)

	# ==================== 统计分析操作 ====================

	async def get_etf_summary (self, ts_code: str) -> Dict[str, Any]:
		"""
		获取ETF概要信息

		Args:
			ts_code: ETF代码

		Returns:
			ETF概要信息字典
		"""
		# 获取基础信息
		etf_basic = await self.get_etf_basic(ts_code)
		if not etf_basic:
			return {}

		# 获取最新行情
		latest_daily = await self.get_latest_etf_daily(ts_code)

		# 获取指数信息
		index_info = None
		if etf_basic.index_code:
			index_info = await self.get_etf_index(etf_basic.index_code)

		return {
			"basic_info": {
				"ts_code": etf_basic.ts_code,
				"name": etf_basic.name,
				"short_name": etf_basic.name,
				"exchange": etf_basic.exchange,
				"fund_type": etf_basic.fund_type,
				"manager": etf_basic.management,
				"setup_date": etf_basic.found_date,
				"list_date": etf_basic.list_date,
				"management_fee": etf_basic.m_fee
			},
			"index_info": {
				"index_code": etf_basic.index_code,
				"index_name": etf_basic.index_name,
				"base_index": index_info.indx_name if index_info else None,
				"base_date": index_info.base_date if index_info else None
			},
			"latest_price": {
				"trade_date": latest_daily.trade_date if latest_daily else None,
				"close": latest_daily.close if latest_daily else None,
				"change": latest_daily.change if latest_daily else None,
				"pct_chg": latest_daily.pct_chg if latest_daily else None,
				"volume": latest_daily.vol if latest_daily else None,
				"amount": latest_daily.amount if latest_daily else None
			}
		}

	# ==================== 批量操作 ====================

	async def batch_create_etf_dailies (self, dailies_data: List[Dict[str, Any]]) -> List[EtfDaily]:
		"""批量创建ETF日线行情"""
		return await self.etf_daily_repo.batch_create(dailies_data)

	async def batch_create_etf_minutes (self, minutes_data: List[Dict[str, Any]]) -> List[EtfMinute]:
		"""批量创建ETF分钟行情"""
		return await self.etf_minute_repo.batch_create(minutes_data)

	async def batch_upsert_etf_basics (self, etfs_data: List[Dict[str, Any]]) -> List[EtfBasic]:
		"""批量插入或更新ETF基础信息"""
		return await self.etf_basic_repo.batch_upsert(
			match_fields=["ts_code"],
			data_list=etfs_data
		)

	async def batch_upsert_adj_factors (self, factors_data: List[Dict[str, Any]]) -> List[FundAdjFactor]:
		"""批量插入或更新复权因子"""
		return await self.adj_factor_repo.batch_upsert(
			match_fields=["ts_code", "trade_date"],
			data_list=factors_data
		)

	# ==================== 基本CRUD操作 ====================

	async def create (self, etf_data: Dict[str, Any]) -> EtfBasic:
		"""
		创建ETF基础信息记录

		Args:
			etf_data: ETF数据字典

		Returns:
			创建的ETF记录
		"""
		try:
			return await self.etf_basic_repo.create(etf_data)
		except Exception as e:
			raise RepositoryError(f"创建ETF记录失败: {str(e)}")

	async def update (self, ts_code: str, update_data: Dict[str, Any]) -> Optional[EtfBasic]:
		"""
		更新ETF基础信息记录

		Args:
			ts_code: ETF代码
			update_data: 要更新的数据

		Returns:
			更新后的ETF记录
		"""
		try:
			# 先获取现有记录
			existing = await self.get_etf_basic(ts_code)
			if not existing:
				return None

			return await self.etf_basic_repo.update(existing.ts_code, update_data)
		except Exception as e:
			raise RepositoryError(f"更新ETF记录失败: {str(e)}")

	async def delete (self, ts_code: str) -> bool:
		"""
		删除ETF记录

		Args:
			ts_code: ETF代码

		Returns:
			删除是否成功
		"""
		try:
			# 先获取现有记录
			existing = await self.get_etf_basic(ts_code)
			if not existing:
				return False

			await self.etf_basic_repo.delete(existing.ts_code)
			return True
		except Exception as e:
			raise RepositoryError(f"删除ETF记录失败: {str(e)}")