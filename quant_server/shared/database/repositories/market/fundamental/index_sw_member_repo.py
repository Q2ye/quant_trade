# -*- coding: utf-8 -*-
"""申万行业成分数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import IndexSwMember
from shared.database.repositories.base import BaseRepository


class IndexSwMemberRepository(BaseRepository[IndexSwMember]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, IndexSwMember)
