# -*- coding: utf-8 -*-
"""港股、美股与港股通仓储。"""

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models_ext_overseas import (
    GgtDaily,
    HkBasic,
    HkDaily,
    UsBasic,
    UsDaily,
)
from shared.database.repositories.base import BaseRepository


class HkBasicRepository(BaseRepository[HkBasic]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, HkBasic)


class HkDailyRepository(BaseRepository[HkDaily]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, HkDaily)


class UsBasicRepository(BaseRepository[UsBasic]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, UsBasic)


class UsDailyRepository(BaseRepository[UsDaily]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, UsDaily)


class GgtDailyRepository(BaseRepository[GgtDaily]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, GgtDaily)
