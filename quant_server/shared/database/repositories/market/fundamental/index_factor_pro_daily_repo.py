# -*- coding: utf-8 -*-
"""指数技术因子专业版数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import IndexFactorProDaily
from shared.database.repositories.base import BaseRepository


class IndexFactorProDailyRepository(BaseRepository[IndexFactorProDaily]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, IndexFactorProDaily)
