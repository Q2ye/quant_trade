# -*- coding: utf-8 -*-
"""沪深港通股票列表数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import StockHsgt
from shared.database.repositories.base import BaseRepository


class StockHsgtRepository(BaseRepository[StockHsgt]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, StockHsgt)
