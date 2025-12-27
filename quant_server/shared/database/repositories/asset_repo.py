# -*- coding: utf-8 -*-
"""
资产数据仓库  todo
位置：quant_server/shared/database/repositories/asset_repo.py
职责：管理股票、ETF等资产基础数据访问
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func, text
from sqlalchemy.orm import selectinload, joinedload

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.data_models import (
	StockBasic,
	StockCompany,
	EtfBasic,
	EtfIndex
)


class AssetRepository:
	"""资产数据仓库 - 负责股票、ETF等资产基础数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.stock_basic_repo = BaseRepository[StockBasic](session, StockBasic)
		self.stock_company_repo = BaseRepository[StockCompany](session, StockCompany)
		self.etf_basic_repo = BaseRepository[EtfBasic](session, EtfBasic)
		self.etf_index_repo = BaseRepository[EtfIndex](session, EtfIndex)

	# ==================== 股票基础信息操作 ====================

	async def get_stock_by_ts_code (self, ts_code: str) -> Optional[StockBasic]:
		"""
		根据股票代码获取股票基础信息

		Args:
			ts_code: 股票代码

		Returns:
			股票基础信息或None
		"""
		return await self.stock_basic_repo.get_by(ts_code=ts_code)

	async def get_stock_by_symbol (self, symbol: str, market: str = None) -> Optional[StockBasic]:
		"""
		根据股票Symbol获取股票信息

		Args:
			symbol: 股票Symbol
			market: 市场类型（可选）

		Returns:
			股票基础信息或None
		"""
		filters = {"symbol": symbol}
		if market:
			filters["market"] = market

		return await self.stock_basic_repo.get_by(**filters)

	async def search_stocks (
			self,
			keyword: str,
			limit: int = 100,
			skip: int = 0,
			market: str = None
	) -> List[StockBasic]:
		"""
		搜索股票

		Args:
			keyword: 搜索关键词（可匹配代码、名称、拼音等）
			limit: 返回数量限制
			skip: 跳过数量
			market: 市场类型过滤

		Returns:
			股票列表
		"""
		query = select(StockBasic).where(
			or_(
				StockBasic.ts_code.like(f"%{keyword}%"),
				StockBasic.symbol.like(f"%{keyword}%"),
				StockBasic.name.like(f"%{keyword}%"),
				StockBasic.cnspell.like(f"%{keyword}%")
			)
		)

		if market:
			query = query.where(StockBasic.market == market)

		query = query.order_by(StockBasic.ts_code).offset(skip).limit(limit)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_stocks_by_industry (self, industry: str) -> List[StockBasic]:
		"""
		根据行业获取股票列表

		Args:
			industry: 行业名称

		Returns:
			股票列表
		"""
		return await self.stock_basic_repo.get_many(industry=industry)

	async def get_stocks_by_market (self, market: str) -> List[StockBasic]:
		"""
		根据市场获取股票列表

		Args:
			market: 市场类型

		Returns:
			股票列表
		"""
		return await self.stock_basic_repo.get_many(market=market)

	async def get_all_stocks (self, active_only: bool = True) -> List[StockBasic]:
		"""
		获取所有股票

		Args:
			active_only: 是否只获取上市状态的股票

		Returns:
			股票列表
		"""
		if active_only:
			return await self.stock_basic_repo.get_many(list_status="L")
		else:
			return await self.stock_basic_repo.get_all()

	async def create_stock (self, stock_data: Dict[str, Any]) -> StockBasic:
		"""
		创建股票记录

		Args:
			stock_data: 股票数据

		Returns:
			创建的股票记录
		"""
		return await self.stock_basic_repo.create(stock_data)

	async def update_stock (self, ts_code: str, update_data: Dict[str, Any]) -> Optional[StockBasic]:
		"""
		更新股票信息

		Args:
			ts_code: 股票代码
			update_data: 更新数据

		Returns:
			更新后的股票信息
		"""
		# 由于StockBasic使用ts_code作为主键，我们需要特殊处理
		stock = await self.stock_basic_repo.get_by(ts_code=ts_code)
		if not stock:
			return None

		return await self.stock_basic_repo.update(stock.id, update_data)

	# ==================== 公司信息操作 ====================

	async def get_company_by_ts_code (self, ts_code: str) -> Optional[StockCompany]:
		"""
		获取公司信息

		Args:
			ts_code: 股票代码

		Returns:
			公司信息或None
		"""
		return await self.stock_company_repo.get_by(ts_code=ts_code)

	async def create_company (self, company_data: Dict[str, Any]) -> StockCompany:
		"""
		创建公司信息记录

		Args:
			company_data: 公司数据

		Returns:
			创建的公司记录
		"""
		return await self.stock_company_repo.create(company_data)

	# ==================== ETF信息操作 ====================

	async def get_etf_by_ts_code (self, ts_code: str) -> Optional[EtfBasic]:
		"""
		获取ETF信息

		Args:
			ts_code: ETF代码

		Returns:
			ETF信息或None
		"""
		return await self.etf_basic_repo.get_by(ts_code=ts_code)

	async def get_etfs_by_index (self, index_code: str) -> List[EtfBasic]:
		"""
		获取跟踪特定指数的ETF列表

		Args:
			index_code: 指数代码

		Returns:
			ETF列表
		"""
		return await self.etf_basic_repo.get_many(index_code=index_code)

	async def search_etfs (
			self,
			keyword: str,
			limit: int = 50,
			skip: int = 0
	) -> List[EtfBasic]:
		"""
		搜索ETF

		Args:
			keyword: 搜索关键词
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			ETF列表
		"""
		query = select(EtfBasic).where(
			or_(
				EtfBasic.ts_code.like(f"%{keyword}%"),
				EtfBasic.csname.like(f"%{keyword}%"),
				EtfBasic.cname.like(f"%{keyword}%")
			)
		).order_by(EtfBasic.ts_code).offset(skip).limit(limit)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def create_etf (self, etf_data: Dict[str, Any]) -> EtfBasic:
		"""
		创建ETF记录

		Args:
			etf_data: ETF数据

		Returns:
			创建的ETF记录
		"""
		return await self.etf_basic_repo.create(etf_data)

	# ==================== 指数信息操作 ====================

	async def get_index_by_ts_code (self, ts_code: str) -> Optional[EtfIndex]:
		"""
		获取指数信息

		Args:
			ts_code: 指数代码

		Returns:
			指数信息或None
		"""
		return await self.etf_index_repo.get_by(ts_code=ts_code)

	async def search_indices (
			self,
			keyword: str,
			limit: int = 50,
			skip: int = 0
	) -> List[EtfIndex]:
		"""
		搜索指数

		Args:
			keyword: 搜索关键词
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			指数列表
		"""
		query = select(EtfIndex).where(
			or_(
				EtfIndex.ts_code.like(f"%{keyword}%"),
				EtfIndex.indx_name.like(f"%{keyword}%"),
				EtfIndex.indx_csname.like(f"%{keyword}%")
			)
		).order_by(EtfIndex.ts_code).offset(skip).limit(limit)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def create_index (self, index_data: Dict[str, Any]) -> EtfIndex:
		"""
		创建指数记录

		Args:
			index_data: 指数数据

		Returns:
			创建的指数记录
		"""
		return await self.etf_index_repo.create(index_data)

	# ==================== 批量操作 ====================

	async def batch_upsert_stocks (self, stocks_data: List[Dict[str, Any]]) -> List[StockBasic]:
		"""
		批量插入或更新股票数据

		Args:
			stocks_data: 股票数据列表

		Returns:
			更新后的股票记录列表
		"""
		return await self.stock_basic_repo.batch_upsert(
			match_fields=["ts_code"],
			data_list=stocks_data
		)

	async def batch_upsert_companies (self, companies_data: List[Dict[str, Any]]) -> List[StockCompany]:
		"""
		批量插入或更新公司数据

		Args:
			companies_data: 公司数据列表

		Returns:
			更新后的公司记录列表
		"""
		return await self.stock_company_repo.batch_upsert(
			match_fields=["ts_code"],
			data_list=companies_data
		)

	async def batch_upsert_etfs (self, etfs_data: List[Dict[str, Any]]) -> List[EtfBasic]:
		"""
		批量插入或更新ETF数据

		Args:
			etfs_data: ETF数据列表

		Returns:
			更新后的ETF记录列表
		"""
		return await self.etf_basic_repo.batch_upsert(
			match_fields=["ts_code"],
			data_list=etfs_data
		)