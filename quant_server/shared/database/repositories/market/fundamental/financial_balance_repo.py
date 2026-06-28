# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import FinancialBalance
from shared.database.repositories.base import BaseRepository

class FinancialBalanceRepository(BaseRepository[FinancialBalance]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FinancialBalance)
