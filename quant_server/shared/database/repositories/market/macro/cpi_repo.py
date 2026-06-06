# -*- coding: utf-8 -*-
"""CPI 居民消费价格指数数据仓库"""
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from shared.database.models.data_models import MacroCpi
from shared.database.repositories.base import BaseRepository


class MacroCpiRepository(BaseRepository[MacroCpi]):
    """CPI 居民消费价格指数 Repository"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, MacroCpi)

    async def bulk_upsert(self, records: List[Dict[str, Any]]) -> int:
        """批量 upsert CPI 数据（按 month 去重）。"""
        if not records:
            return 0
        stmt = pg_insert(self.model).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=['month'],
            set_={k: stmt.excluded[k] for k in records[0] if k != 'month'}
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0
