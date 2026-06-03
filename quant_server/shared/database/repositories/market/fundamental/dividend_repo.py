# -*- coding: utf-8 -*-
"""分红送股数据仓库"""
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models import StockDividend
from shared.database.repositories.base import BaseRepository, RepositoryError


class StockDividendRepository(BaseRepository[StockDividend]):
	"""上市公司分红送股数据仓库"""

	def __init__(self, session: AsyncSession):
		super().__init__(session, StockDividend)

	async def get_by_ts_code(self, ts_code: str, limit: int = 100) -> List[StockDividend]:
		"""根据股票代码获取分红送股"""
		try:
			return await self.get_many(limit=limit, ts_code=ts_code)
		except Exception as e:
			raise RepositoryError(f"获取分红送股失败: {e}")
