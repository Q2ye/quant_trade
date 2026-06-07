# -*- coding: utf-8 -*-
"""股东人数数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import StockStkHoldernumber
from shared.database.repositories.base import BaseRepository


class StockHoldernumberRepository(BaseRepository[StockStkHoldernumber]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, StockStkHoldernumber)
