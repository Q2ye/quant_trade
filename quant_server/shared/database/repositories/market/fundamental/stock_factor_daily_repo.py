# -*- coding: utf-8 -*-
"""股票技术因子基础版数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import StockFactorDaily
from shared.database.repositories.base import BaseRepository


class StockFactorDailyRepository(BaseRepository[StockFactorDaily]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, StockFactorDaily)
