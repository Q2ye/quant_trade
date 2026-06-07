# -*- coding: utf-8 -*-
"""财报披露日期数据仓库"""
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import FinancialDisclosureDate
from shared.database.repositories.base import BaseRepository


class DisclosureDateRepository(BaseRepository[FinancialDisclosureDate]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, FinancialDisclosureDate)
