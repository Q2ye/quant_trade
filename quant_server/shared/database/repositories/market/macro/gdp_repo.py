# -*- coding: utf-8 -*-
"""GDP 国内生产总值数据仓库"""
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from shared.database.models.data_models import MacroGdp
from shared.database.repositories.base import BaseRepository


class MacroGdpRepository(BaseRepository[MacroGdp]):
    """GDP 国内生产总值 Repository"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, MacroGdp)

    async def bulk_upsert(self, records: List[Dict[str, Any]]) -> int:
        """批量 upsert GDP 数据（按 quarter 去重）。"""
        if not records:
            return 0
        stmt = pg_insert(self.model).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=['quarter'],
            set_={k: stmt.excluded[k] for k in records[0] if k != 'quarter'}
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0
