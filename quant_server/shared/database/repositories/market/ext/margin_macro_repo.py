# -*- coding: utf-8 -*-
"""两融、改名、新股、指数月线与宏观仓储。"""

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models_ext_margin_macro import (
    IndexMonthly,
    MacroMoney,
    MacroPmi,
    MacroRate,
    MacroSf,
    StockMarginDetail,
    StockMarginSecs,
    StockNamechange,
    StockNewShare,
)
from shared.database.repositories.base import BaseRepository


class StockMarginDetailRepository(BaseRepository[StockMarginDetail]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StockMarginDetail)


class StockMarginSecsRepository(BaseRepository[StockMarginSecs]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StockMarginSecs)


class StockNamechangeRepository(BaseRepository[StockNamechange]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StockNamechange)


class StockNewShareRepository(BaseRepository[StockNewShare]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StockNewShare)


class IndexMonthlyRepository(BaseRepository[IndexMonthly]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, IndexMonthly)


class MacroRateRepository(BaseRepository[MacroRate]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, MacroRate)


class MacroSfRepository(BaseRepository[MacroSf]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, MacroSf)


class MacroMoneyRepository(BaseRepository[MacroMoney]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, MacroMoney)


class MacroPmiRepository(BaseRepository[MacroPmi]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, MacroPmi)
