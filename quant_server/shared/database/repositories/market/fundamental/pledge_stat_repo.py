# -*- coding: utf-8 -*-
"""股权质押统计数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import StockPledgeStat
from shared.database.repositories.base import BaseRepository


class StockPledgeStatRepository(BaseRepository[StockPledgeStat]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, StockPledgeStat)
