# -*- coding: utf-8 -*-
"""期权、可转债与北向十大仓储。"""

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models_ext_options_bonds import (
    CbBasic,
    CbCall,
    CbDaily,
    CbIssue,
    CbRating,
    CbShare,
    OptBasic,
    OptDaily,
    StockHsgtTop10,
)
from shared.database.repositories.base import BaseRepository


class OptBasicRepository(BaseRepository[OptBasic]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, OptBasic)


class OptDailyRepository(BaseRepository[OptDaily]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, OptDaily)


class CbBasicRepository(BaseRepository[CbBasic]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, CbBasic)


class CbIssueRepository(BaseRepository[CbIssue]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, CbIssue)


class CbCallRepository(BaseRepository[CbCall]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, CbCall)


class CbDailyRepository(BaseRepository[CbDaily]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, CbDaily)


class CbShareRepository(BaseRepository[CbShare]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, CbShare)


class CbRatingRepository(BaseRepository[CbRating]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, CbRating)


class StockHsgtTop10Repository(BaseRepository[StockHsgtTop10]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StockHsgtTop10)
