# -*- coding: utf-8 -*-
"""业绩预告数据仓库"""
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models import StockForecast
from shared.database.repositories.base import BaseRepository, RepositoryError


class StockForecastRepository(BaseRepository[StockForecast]):
	"""上市公司业绩预告数据仓库"""

	def __init__(self, session: AsyncSession):
		super().__init__(session, StockForecast)

	async def get_by_ts_code(self, ts_code: str, limit: int = 100) -> List[StockForecast]:
		"""根据股票代码获取业绩预告"""
		try:
			return await self.get_many(limit=limit, ts_code=ts_code)
		except Exception as e:
			raise RepositoryError(f"获取业绩预告失败: {e}")
