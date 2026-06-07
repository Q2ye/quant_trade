# -*- coding: utf-8 -*-
"""申万行业日线行情数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import IndexSwDaily
from shared.database.repositories.base import BaseRepository

class IndexSwDailyRepository(BaseRepository[IndexSwDaily]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, IndexSwDaily)
