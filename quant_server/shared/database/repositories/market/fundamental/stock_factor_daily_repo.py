# -*- coding: utf-8 -*-
"""股票技术因子基础版数据仓库"""
from typing import Dict
from datetime import date
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import StockFactorDaily
from shared.database.repositories.base import BaseRepository


class StockFactorDailyRepository(BaseRepository[StockFactorDaily]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, StockFactorDaily)

	async def get_latest_trade_dates_batch(self, ts_codes: list) -> Dict[str, date]:
		"""批量获取多只股票的最新因子交易日（一次 SQL 查询，用于增量判断）"""
		if not ts_codes:
			return {}
		query = (
			select(self.model.ts_code, func.max(self.model.trade_date))
			.where(self.model.ts_code.in_(ts_codes))
			.group_by(self.model.ts_code)
		)
		result = await self.session.execute(query)
		date_map = {}
		for row in result:
			if row[0] and row[1]:
				d = row[1]
				date_map[row[0]] = d.date() if hasattr(d, "date") else d
		return date_map

	async def get_latest_trade_date(self, ts_code: str) -> date | None:
		"""获取单只股票的最新因子交易日"""
		query = (
			select(func.max(self.model.trade_date))
			.where(self.model.ts_code == ts_code)
		)
		result = await self.session.execute(query)
		val = result.scalar()
		if val is None:
			return None
		return val.date() if hasattr(val, "date") else val
