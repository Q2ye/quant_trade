# -*- coding: utf-8 -*-
"""前十大股东数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import StockTop10Holders
from shared.database.repositories.base import BaseRepository


class StockTop10HoldersRepository(BaseRepository[StockTop10Holders]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, StockTop10Holders)
