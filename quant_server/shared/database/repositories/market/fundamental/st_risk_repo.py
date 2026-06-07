# -*- coding: utf-8 -*-
"""ST风险警示板数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import StockStRisk
from shared.database.repositories.base import BaseRepository


class StockStRiskRepository(BaseRepository[StockStRisk]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, StockStRisk)
