# -*- coding: utf-8 -*-
"""限售股解禁数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import StockShareFloat
from shared.database.repositories.base import BaseRepository


class StockShareFloatRepository(BaseRepository[StockShareFloat]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, StockShareFloat)
