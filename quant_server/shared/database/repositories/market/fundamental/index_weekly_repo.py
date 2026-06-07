# -*- coding: utf-8 -*-
"""指数周线行情数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import IndexWeekly
from shared.database.repositories.base import BaseRepository


class IndexWeeklyRepository(BaseRepository[IndexWeekly]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, IndexWeekly)
