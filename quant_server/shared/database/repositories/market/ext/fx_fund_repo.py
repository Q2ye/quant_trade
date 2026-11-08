# -*- coding: utf-8 -*-
"""外汇与基金仓储（一表一 Repository 类）。"""

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models_ext_fx_fund import (
    FundBasic,
    FundCompany,
    FundDailyEx,
    FundDiv,
    FundManager,
    FundNav,
    FundShare,
    FxBasic,
    FxDaily,
)
from shared.database.repositories.base import BaseRepository


class FxBasicRepository(BaseRepository[FxBasic]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FxBasic)


class FxDailyRepository(BaseRepository[FxDaily]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FxDaily)


class FundNavRepository(BaseRepository[FundNav]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FundNav)


class FundBasicRepository(BaseRepository[FundBasic]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FundBasic)


class FundCompanyRepository(BaseRepository[FundCompany]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FundCompany)


class FundManagerRepository(BaseRepository[FundManager]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FundManager)


class FundDivRepository(BaseRepository[FundDiv]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FundDiv)


class FundShareRepository(BaseRepository[FundShare]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FundShare)


class FundDailyExRepository(BaseRepository[FundDailyEx]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FundDailyEx)
