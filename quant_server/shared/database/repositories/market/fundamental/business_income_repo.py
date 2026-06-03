# -*- coding: utf-8 -*-
"""主营业务收入数据仓库"""
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models import StockBusinessIncome
from shared.database.repositories.base import BaseRepository, RepositoryError


class StockBusinessIncomeRepository(BaseRepository[StockBusinessIncome]):
	"""上市公司主营业务收入数据仓库"""

	def __init__(self, session: AsyncSession):
		super().__init__(session, StockBusinessIncome)

	async def get_by_ts_code(self, ts_code: str, limit: int = 100) -> List[StockBusinessIncome]:
		"""根据股票代码获取主营业务收入"""
		try:
			return await self.get_many(limit=limit, ts_code=ts_code)
		except Exception as e:
			raise RepositoryError(f"获取主营业务收入失败: {e}")
