# -*- coding: utf-8 -*-
"""股票每日涨跌停价格数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import StockDailyLimit
from shared.database.repositories.base import BaseRepository


class StockDailyLimitRepository(BaseRepository[StockDailyLimit]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, StockDailyLimit)
