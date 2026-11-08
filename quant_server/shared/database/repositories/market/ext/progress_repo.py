# -*- coding: utf-8 -*-
"""回填进度表仓储。"""

from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models_ext_progress import DataBackfillProgress
from shared.database.repositories.base import BaseRepository


class DataBackfillProgressRepository(BaseRepository[DataBackfillProgress]):
    """data_backfill_progress 表仓储。"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, DataBackfillProgress)

    async def get_status_map(self, data_type: str) -> Dict[str, str]:
        """返回 {period_key 或日期字符串: status}，供断点续传使用。"""
        stmt = select(
            self.model.trade_date, self.model.period_key, self.model.status
        ).where(self.model.data_type == data_type)
        rows = (await self.session.execute(stmt)).all()
        out: Dict[str, str] = {}
        for trade_date, period_key, status in rows:
            key = (period_key or (trade_date.isoformat() if trade_date else ""))
            out[key] = status
        return out

    async def mark(self, data_type: str, trade_date, period_key: str,
                   status: str, rows_written: int = 0,
                   error: str = "") -> int:
        """写入/更新一条进度；幂等。"""
        record: Dict[str, Any] = {
            "data_type": data_type,
            "trade_date": trade_date,
            "period_key": period_key or "",
            "status": status,
            "rows_written": rows_written,
            "error": error or None,
        }
        return await self.bulk_upsert([record])
