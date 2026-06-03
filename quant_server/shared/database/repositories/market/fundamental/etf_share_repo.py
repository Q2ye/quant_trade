# -*- coding: utf-8 -*-
"""ETF份额数据仓库"""
from datetime import date, datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from shared.database.models.data_models import EtfShare
from shared.database.repositories.base import BaseRepository, RepositoryError


class EtfShareRepository(BaseRepository[EtfShare]):
    """上市公司ETF份额数据仓库"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, EtfShare)

    async def get_by_ts_code(self, ts_code: str, limit: int = 100) -> List[EtfShare]:
        """根据股票代码获取ETF份额"""
        try:
            return await self.get_many(limit=limit, ts_code=ts_code)
        except Exception as e:
            raise RepositoryError(f"获取ETF份额失败: {e}")
