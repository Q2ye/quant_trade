# -*- coding: utf-8 -*-
"""股票技术因子专业版数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import StockFactorProDaily
from shared.database.repositories.base import BaseRepository


class StockFactorProDailyRepository(BaseRepository[StockFactorProDaily]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, StockFactorProDaily)
