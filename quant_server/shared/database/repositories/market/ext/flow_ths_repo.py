# -*- coding: utf-8 -*-
"""龙虎榜、筹码、THS、资金流与市场统计仓储。"""

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models_ext_flow_ths import (
    IndexThs,
    IndexThsDaily,
    IndexThsMember,
    MarketDailyInfo,
    StockCyqPerf,
    StockMoneyflowExt,
    StockMoneyflowInd,
    StockTopInst,
    StockTopList,
)
from shared.database.repositories.base import BaseRepository


class StockTopListRepository(BaseRepository[StockTopList]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StockTopList)


class StockTopInstRepository(BaseRepository[StockTopInst]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StockTopInst)


class StockCyqPerfRepository(BaseRepository[StockCyqPerf]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StockCyqPerf)


class IndexThsRepository(BaseRepository[IndexThs]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, IndexThs)


class IndexThsDailyRepository(BaseRepository[IndexThsDaily]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, IndexThsDaily)


class IndexThsMemberRepository(BaseRepository[IndexThsMember]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, IndexThsMember)


class StockMoneyflowExtRepository(BaseRepository[StockMoneyflowExt]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StockMoneyflowExt)


class StockMoneyflowIndRepository(BaseRepository[StockMoneyflowInd]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StockMoneyflowInd)


class MarketDailyInfoRepository(BaseRepository[MarketDailyInfo]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, MarketDailyInfo)
