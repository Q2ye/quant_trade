# -*- coding: utf-8 -*-
"""审计意见数据仓库"""
from datetime import date, datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from shared.database.models.data_models import StockAuditOpinion
from shared.database.repositories.base import BaseRepository, RepositoryError


class StockAuditOpinionRepository(BaseRepository[StockAuditOpinion]):
    """上市公司审计意见数据仓库"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, StockAuditOpinion)

    async def get_by_ts_code(self, ts_code: str, limit: int = 100) -> List[StockAuditOpinion]:
        """根据股票代码获取审计意见"""
        try:
            return await self.get_many(limit=limit, ts_code=ts_code)
        except Exception as e:
            raise RepositoryError(f"获取审计意见失败: {e}")
