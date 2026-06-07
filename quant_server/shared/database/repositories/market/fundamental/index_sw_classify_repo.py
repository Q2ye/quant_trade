# -*- coding: utf-8 -*-
"""申万行业分类数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import IndexSwClassify
from shared.database.repositories.base import BaseRepository


class IndexSwClassifyRepository(BaseRepository[IndexSwClassify]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, IndexSwClassify)
