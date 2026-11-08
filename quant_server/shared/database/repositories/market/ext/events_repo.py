# -*- coding: utf-8 -*-
"""质押、回购、调研、榜单、游资与财经日历仓储。"""

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models_ext_events import (
    MacroEcoCal,
    StockHmList,
    StockKplList,
    StockPledgeDetail,
    StockRepurchase,
    StockSurv,
)
from shared.database.repositories.base import BaseRepository


class StockPledgeDetailRepository(BaseRepository[StockPledgeDetail]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StockPledgeDetail)


class StockRepurchaseRepository(BaseRepository[StockRepurchase]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StockRepurchase)


class StockSurvRepository(BaseRepository[StockSurv]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StockSurv)


class StockKplListRepository(BaseRepository[StockKplList]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StockKplList)


class StockHmListRepository(BaseRepository[StockHmList]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StockHmList)


class MacroEcoCalRepository(BaseRepository[MacroEcoCal]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, MacroEcoCal)
