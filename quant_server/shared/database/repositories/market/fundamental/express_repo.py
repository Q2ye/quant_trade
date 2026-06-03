# -*- coding: utf-8 -*-
"""业绩快报数据仓库"""
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models import StockExpress
from shared.database.repositories.base import BaseRepository, RepositoryError


class StockExpressRepository(BaseRepository[StockExpress]):
	"""上市公司业绩快报数据仓库"""

	def __init__(self, session: AsyncSession):
		super().__init__(session, StockExpress)

	async def get_by_ts_code(self, ts_code: str, limit: int = 100) -> List[StockExpress]:
		"""根据股票代码获取业绩快报"""
		try:
			return await self.get_many(limit=limit, ts_code=ts_code)
		except Exception as e:
			raise RepositoryError(f"获取业绩快报失败: {e}")
