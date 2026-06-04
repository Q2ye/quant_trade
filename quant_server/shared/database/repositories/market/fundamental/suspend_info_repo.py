# -*- coding: utf-8 -*-
"""停复牌信息数据仓库"""
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models import StockSuspendInfo
from shared.database.repositories.base import BaseRepository, RepositoryError


class StockSuspendInfoRepository(BaseRepository[StockSuspendInfo]):
    """股票停复牌信息数据仓库"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, StockSuspendInfo)

    async def get_by_ts_code(self, ts_code: str, limit: int = 100) -> List[StockSuspendInfo]:
        """根据股票代码获取停复牌信息"""
        try:
            return await self.get_many(limit=limit, ts_code=ts_code)
        except Exception as e:
            raise RepositoryError(f"获取停复牌信息失败: {e}")
