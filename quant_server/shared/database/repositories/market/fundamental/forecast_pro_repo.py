# -*- coding: utf-8 -*-
"""卖方盈利预测数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import StockForecastPro
from shared.database.repositories.base import BaseRepository


class StockForecastProRepository(BaseRepository[StockForecastPro]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, StockForecastPro)
