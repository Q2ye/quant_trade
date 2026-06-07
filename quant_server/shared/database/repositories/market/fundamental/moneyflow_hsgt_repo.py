# -*- coding: utf-8 -*-
"""沪深港通资金流向数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import StockMoneyflowHsgt
from shared.database.repositories.base import BaseRepository


class StockMoneyflowHsgtRepository(BaseRepository[StockMoneyflowHsgt]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, StockMoneyflowHsgt)
