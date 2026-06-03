# -*- coding: utf-8 -*-
"""财务指标数据仓库"""
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models import StockFinaIndicator
from shared.database.repositories.base import BaseRepository, RepositoryError


class StockFinaIndicatorRepository(BaseRepository[StockFinaIndicator]):
	"""上市公司财务指标数据仓库"""

	def __init__(self, session: AsyncSession):
		super().__init__(session, StockFinaIndicator)

	async def get_by_ts_code(self, ts_code: str, limit: int = 100) -> List[StockFinaIndicator]:
		"""根据股票代码获取财务指标"""
		try:
			return await self.get_many(limit=limit, ts_code=ts_code)
		except Exception as e:
			raise RepositoryError(f"获取财务指标失败: {e}")
