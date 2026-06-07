# -*- coding: utf-8 -*-
"""前十大流通股东数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import StockTop10FloatHolders
from shared.database.repositories.base import BaseRepository


class StockTop10FloatHoldersRepository(BaseRepository[StockTop10FloatHolders]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, StockTop10FloatHolders)
