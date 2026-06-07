# -*- coding: utf-8 -*-
"""大盘指数每日指标数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import IndexDailyBasic
from shared.database.repositories.base import BaseRepository


class IndexDailyBasicRepository(BaseRepository[IndexDailyBasic]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, IndexDailyBasic)
