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

    async def get_latest_trade_date(self, ts_code: str) -> Optional[date]:
        """获取指定ETF份额的最新数据日期。"""
        from sqlalchemy import desc
        from datetime import date as d
        query = select(self.model.trade_date).where(
            self.model.ts_code == ts_code
        ).order_by(desc(self.model.trade_date)).limit(1)
        result = await self.session.execute(query)
        row = result.first()
        return row.trade_date if row else None

    async def get_latest_trade_dates_batch(self, ts_codes: list) -> dict:
        """批量获取多只ETF份额的最新数据日期（一次 SQL 查询）。"""
        from sqlalchemy import func

        if not ts_codes:
            return {}

        query = (
            select(self.model.ts_code, func.max(self.model.trade_date))
            .where(self.model.ts_code.in_(ts_codes))
            .group_by(self.model.ts_code)
        )
        result = await self.session.execute(query)
        mapping = {row[0]: row[1] for row in result.fetchall()}
        for code in ts_codes:
            if code not in mapping:
                mapping[code] = None
        return mapping
