# -*- coding: utf-8 -*-
"""股东增减持数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import StockStkHoldertrade
from shared.database.repositories.base import BaseRepository


class StockHoldertradeRepository(BaseRepository[StockStkHoldertrade]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, StockStkHoldertrade)
