# -*- coding: utf-8 -*-
"""
数据加载器

负责加载回测所需的数据
"""
import logging
from typing import Dict, Any

import pandas as pd
from quant_server.modules.data.services.market_service import MarketDataService
from quant_server.shared.database.models.business_models import Strategy
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class DataLoader:
	"""
	数据加载器

	负责加载回测所需的数据
	"""

	def __init__ (self, db: AsyncSession):
		"""
		初始化数据加载器

		Args:
			db: 数据库会话
		"""
		self.db = db
		self.data_service = MarketDataService(db)

	async def load_market_data (self, symbol: str, start_date: str, end_date: str,
	                            interval: str = "1d") -> pd.DataFrame:
		"""
		加载市场数据

		Args:
			symbol: 标的符号
			start_date: 开始日期
			end_date: 结束日期
			interval: 时间间隔

		Returns:
			市场数据
		"""
		try:
			logger.info(f"加载市场数据: {symbol}, {start_date} - {end_date}, {interval}")

			# 从数据服务获取数据
			# 注意：这里需要根据实际的 MarketDataService 方法调整
			# 暂时返回空 DataFrame，需要根据实际实现修改
			data = []

			# 转换为DataFrame
			df = pd.DataFrame(data)

			# 处理时间列
			if "timestamp" in df.columns:
				df["datetime"] = pd.to_datetime(df["timestamp"])
				df.set_index("datetime", inplace=True)

			logger.info(f"加载市场数据完成，共 {len(df)} 条记录")

			return df
		except Exception as e:
			logger.error(f"加载市场数据失败: {str(e)}")
			return pd.DataFrame()

	async def load_strategy_data (self, strategy_id: str) -> Dict[str, Any]:
		"""
		加载策略数据

		Args:
			strategy_id: 策略ID

		Returns:
			策略数据
		"""
		try:
			logger.info(f"加载策略数据: {strategy_id}")

			# 从数据库获取策略信息
			strategy = await self.db.get(Strategy, strategy_id)
			if not strategy:
				raise ValueError(f"策略不存在: {strategy_id}")

			# 构建策略数据
			strategy_data = {
				"id": strategy.id,
				"name": strategy.name,
				"description": strategy.description,
				"parameters": {},
				"code": strategy.code,
				"created_at": strategy.created_at
			}

			logger.info(f"加载策略数据完成")

			return strategy_data
		except Exception as e:
			logger.error(f"加载策略数据失败: {str(e)}")
			return {}