# -*- coding: utf-8 -*-
"""大宗交易、全球指数与期货仓储。"""

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models_ext_futures import (
    FutBasic,
    FutDaily,
    FutHolding,
    FutIndexDaily,
    FutMapping,
    FutSettle,
    FutWsr,
    IndexGlobalDaily,
    StockBlockTrade,
)
from shared.database.repositories.base import BaseRepository


class StockBlockTradeRepository(BaseRepository[StockBlockTrade]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StockBlockTrade)


class IndexGlobalDailyRepository(BaseRepository[IndexGlobalDaily]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, IndexGlobalDaily)


class FutBasicRepository(BaseRepository[FutBasic]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FutBasic)


class FutDailyRepository(BaseRepository[FutDaily]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FutDaily)


class FutHoldingRepository(BaseRepository[FutHolding]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FutHolding)


class FutWsrRepository(BaseRepository[FutWsr]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FutWsr)


class FutSettleRepository(BaseRepository[FutSettle]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FutSettle)


class FutMappingRepository(BaseRepository[FutMapping]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FutMapping)


class FutIndexDailyRepository(BaseRepository[FutIndexDaily]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FutIndexDaily)
