# -*- coding: utf-8 -*-
"""
# 复权价格数据仓库
# 位置：quant_server/shared/database/repositories/adjusted_price_repo.py
# 职责：管理复权价格、复权因子等数据访问
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func, text
from sqlalchemy.orm import selectinload, joinedload

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.data_models import (
	StockAdjustedPrices,
	StockAdjFactor
)


class AdjustedPriceRepository:
	"""复权价格数据仓库 - 负责复权价格相关数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.adjusted_price_repo = BaseRepository[StockAdjustedPrices](session, StockAdjustedPrices)
		self.adj_factor_repo = BaseRepository[StockAdjFactor](session, StockAdjFactor)

	# ==================== 复权价格操作 ====================

	async def get_adjusted_price (
			self,
			ts_code: str,
			trade_date: date,
			adj_type: str = "qfq"
	) -> Optional[StockAdjustedPrices]:
		"""
		获取指定日期和复权类型的价格数据

		Args:
			ts_code: 股票代码
			trade_date: 交易日期
			adj_type: 复权类型，可选 qfq（前复权）、hfq（后复权）

		Returns:
			复权价格数据或None
		"""
		return await self.adjusted_price_repo.get_by(
			ts_code=ts_code,
			trade_date=trade_date,
			adj_type=adj_type
		)

	async def get_adjusted_prices_in_range (
			self,
			ts_code: str,
			start_date: date,
			end_date: date,
			adj_type: str = "qfq",
			freq: str = "D"
	) -> List[StockAdjustedPrices]:
		"""
		获取指定时间范围内的复权价格数据

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期
			adj_type: 复权类型
			freq: 频率，D-日线，W-周线，M-月线

		Returns:
			复权价格数据列表
		"""
		query = select(StockAdjustedPrices).where(
			and_(
				StockAdjustedPrices.ts_code == ts_code,
				StockAdjustedPrices.trade_date >= start_date,
				StockAdjustedPrices.trade_date <= end_date,
				StockAdjustedPrices.adj_type == adj_type,
				StockAdjustedPrices.freq == freq
			)
		).order_by(StockAdjustedPrices.trade_date)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_latest_adjusted_price (
			self,
			ts_code: str,
			adj_type: str = "qfq",
			freq: str = "D"
	) -> Optional[StockAdjustedPrices]:
		"""
		获取最新的复权价格数据

		Args:
			ts_code: 股票代码
			adj_type: 复权类型
			freq: 频率

		Returns:
			最新的复权价格数据或None
		"""
		query = select(StockAdjustedPrices).where(
			and_(
				StockAdjustedPrices.ts_code == ts_code,
				StockAdjustedPrices.adj_type == adj_type,
				StockAdjustedPrices.freq == freq
			)
		).order_by(desc(StockAdjustedPrices.trade_date)).limit(1)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def create_adjusted_price (self, price_data: Dict[str, Any]) -> StockAdjustedPrices:
		"""
		创建复权价格记录

		Args:
			price_data: 价格数据

		Returns:
			创建的复权价格记录
		"""
		return await self.adjusted_price_repo.create(price_data)

	async def batch_create_adjusted_prices (self, prices_data: List[Dict[str, Any]]) -> List[StockAdjustedPrices]:
		"""
		批量创建复权价格记录

		Args:
			prices_data: 价格数据列表

		Returns:
			创建的复权价格记录列表
		"""
		return await self.adjusted_price_repo.batch_create(prices_data)

	# ==================== 复权因子操作 ====================

	async def get_adj_factor (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[StockAdjFactor]:
		"""
		获取指定日期的复权因子

		Args:
			ts_code: 股票代码
			trade_date: 交易日期

		Returns:
			复权因子数据或None
		"""
		return await self.adj_factor_repo.get_by(
			ts_code=ts_code,
			trade_date=trade_date
		)

	async def get_adj_factors_in_range (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[StockAdjFactor]:
		"""
		获取指定时间范围内的复权因子数据

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			复权因子数据列表
		"""
		query = select(StockAdjFactor).where(
			and_(
				StockAdjFactor.ts_code == ts_code,
				StockAdjFactor.trade_date >= start_date,
				StockAdjFactor.trade_date <= end_date
			)
		).order_by(StockAdjFactor.trade_date)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_latest_adj_factor (self, ts_code: str) -> Optional[StockAdjFactor]:
		"""
		获取最新的复权因子

		Args:
			ts_code: 股票代码

		Returns:
			最新的复权因子或None
		"""
		query = select(StockAdjFactor).where(
			StockAdjFactor.ts_code == ts_code
		).order_by(desc(StockAdjFactor.trade_date)).limit(1)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def create_adj_factor (self, factor_data: Dict[str, Any]) -> StockAdjFactor:
		"""
		创建复权因子记录

		Args:
			factor_data: 因子数据

		Returns:
			创建的复权因子记录
		"""
		return await self.adj_factor_repo.create(factor_data)

	async def batch_create_adj_factors (self, factors_data: List[Dict[str, Any]]) -> List[StockAdjFactor]:
		"""
		批量创建复权因子记录

		Args:
			factors_data: 因子数据列表

		Returns:
			创建的复权因子记录列表
		"""
		return await self.adj_factor_repo.batch_create(factors_data)

	# ==================== 批量操作 ====================

	async def batch_upsert_adjusted_prices (self, prices_data: List[Dict[str, Any]]) -> List[StockAdjustedPrices]:
		"""
		批量插入或更新复权价格数据

		Args:
			prices_data: 价格数据列表

		Returns:
			更新后的复权价格记录列表
		"""
		return await self.adjusted_price_repo.batch_upsert(
			match_fields=["ts_code", "trade_date", "adj_type", "freq"],
			data_list=prices_data
		)

	async def batch_upsert_adj_factors (self, factors_data: List[Dict[str, Any]]) -> List[StockAdjFactor]:
		"""
		批量插入或更新复权因子数据

		Args:
			factors_data: 因子数据列表

		Returns:
			更新后的复权因子记录列表
		"""
		return await self.adj_factor_repo.batch_upsert(
			match_fields=["ts_code", "trade_date"],
			data_list=factors_data
		)