# shared/database/repositories/strategy/backtest/trade_repo.py
from datetime import datetime, date
from typing import List, Dict, Any

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import literal

from quant_server.shared.database.models.business_models import BacktestTrade
from quant_server.shared.database.repositories.base import BaseRepository


class BacktestTradeRepository(BaseRepository[BacktestTrade]):
	"""回测成交数据仓库"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, BacktestTrade)

	async def get_by_task_id (self, task_id: str, skip: int = 0, limit: int = 1000) -> List[BacktestTrade]:
		"""获取回测任务的成交记录"""
		query = (
			select(self.model)
			.where(self.model.task_id == task_id)
			.order_by(desc(self.model.trade_time))
			.offset(skip)
			.limit(limit)
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_task_trades_summary (self, task_id: str) -> Dict[str, Any]:
		"""获取回测任务成交汇总统计"""
		# 总成交统计
		total_query = (
			select(
				func.count().label('total_trades'),
				func.sum(self.model.volume).label('total_volume'),
				func.sum(self.model.value).label('total_value'),
				func.avg(self.model.commission).label('avg_commission'),
				func.sum(self.model.commission).label('total_commission')
			)
			.where(self.model.task_id == task_id)
		)

		total_result = await self.session.execute(total_query)
		total_stats = total_result.first()

		# 买入/卖出统计
		direction_query = (
			select(
				self.model.direction,
				func.count().label('count'),
				func.sum(self.model.volume).label('volume'),
				func.sum(self.model.value).label('value')
			)
			.where(self.model.task_id == task_id)
			.group_by(self.model.direction)
		)

		direction_result = await self.session.execute(direction_query)
		direction_stats = {row.direction: dict(row) for row in direction_result.all()}

		# 按股票代码统计
		stock_query = (
			select(
				self.model.ts_code,
				func.count().label('count'),
				func.sum(
					func.case(
						[(self.model.direction == 'buy', self.model.volume)],
						else_=literal(0)
					)
				).label('buy_volume'),
				func.sum(
					func.case(
						[(self.model.direction == 'sell', self.model.volume)],
						else_=literal(0)
					)
				).label('sell_volume'),
				func.sum(self.model.commission).label('total_commission')
			)
			.where(self.model.task_id == task_id)
			.group_by(self.model.ts_code)
			.order_by(desc(func.count()))
			.limit(20)
		)

		stock_result = await self.session.execute(stock_query)
		top_stocks = [dict(row) for row in stock_result.all()]

		return {
			"total_trades": total_stats.total_trades or 0,
			"total_volume": total_stats.total_volume or 0,
			"total_value": total_stats.total_value or 0,
			"avg_commission": float(total_stats.avg_commission or 0),
			"total_commission": total_stats.total_commission or 0,
			"direction_stats": direction_stats,
			"top_stocks": top_stocks
		}

	async def get_trades_by_date_range (self, task_id: str, start_date: date,
	                                    end_date: date) -> List[BacktestTrade]:
		"""获取指定日期范围内的成交记录"""
		query = (
			select(self.model)
			.where(
				and_(
					self.model.task_id == task_id,
					func.date(self.model.trade_time) >= start_date,
					func.date(self.model.trade_time) <= end_date
				)
			)
			.order_by(self.model.trade_time)
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_trades_by_stock (self, task_id: str, ts_code: str) -> List[BacktestTrade]:
		"""获取指定股票的成交记录"""
		query = (
			select(self.model)
			.where(
				and_(
					self.model.task_id == task_id,
					self.model.ts_code == ts_code
				)
			)
			.order_by(self.model.trade_time)
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_trade_distribution_by_hour (self, task_id: str) -> Dict[int, int]:
		"""获取成交时间分布（按小时）"""
		query = (
			select(
				func.extract('hour', self.model.trade_time).label('hour'),
				func.count().label('count')
			)
			.where(self.model.task_id == task_id)
			.group_by(func.extract('hour', self.model.trade_time))
			.order_by('hour')
		)

		result = await self.session.execute(query)
		distribution = {}
		for row in result.all():
			distribution[int(row.hour)] = row.count

		return distribution

	async def batch_create_trades (self, task_id: str, trades_data: List[Dict[str, Any]]) -> int:
		"""批量创建回测成交记录"""
		now = datetime.now()
		instances = []

		for data in trades_data:
			# 确保task_id一致
			data['task_id'] = task_id
			data['created_at'] = now

			instance = self.model(**data)
			instances.append(instance)

		self.session.add_all(instances)
		await self.session.flush()
		return len(instances)