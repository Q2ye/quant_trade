# shared/database/repositories/strategy/backtest/position_repo.py
from datetime import date, datetime
from typing import List, Dict, Any

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import literal_column

from shared.database.models.business_models import BacktestPosition
from shared.database.repositories.base import BaseRepository


class BacktestPositionRepository(BaseRepository[BacktestPosition]):
	"""回测持仓数据仓库"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, BacktestPosition)

	async def get_by_task_id (self, task_id: str, skip: int = 0, limit: int = 1000) -> List[BacktestPosition]:
		"""根据任务ID获取持仓记录"""
		query = (
			select(self.model)
			.where(self.model.task_id == task_id)
			.order_by(desc(self.model.trade_date))
			.offset(skip)
			.limit(limit)
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_daily_positions (self, task_id: str, trade_date: date) -> List[BacktestPosition]:
		"""获取指定日期的持仓快照"""
		query = (
			select(self.model)
			.where(
				and_(
					self.model.task_id == task_id,
					func.date(self.model.trade_date) == trade_date
				)
			)
			.order_by(desc(self.model.market_value))
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_position_history (self, task_id: str, ts_code: str) -> List[BacktestPosition]:
		"""获取指定股票的历史持仓记录"""
		query = (
			select(self.model)
			.where(
				and_(
					self.model.task_id == task_id,
					self.model.ts_code == ts_code
				)
			)
			.order_by(self.model.trade_date)
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_position_summary (self, task_id: str, trade_date: date) -> Dict[str, Any]:
		"""获取持仓汇总统计"""
		# 总持仓统计
		total_query = (
			select(
				func.count().label('total_positions'),
				func.sum(self.model.volume).label('total_volume'),
				func.sum(self.model.market_value).label('total_market_value'),
				func.avg(self.model.cost_price).label('avg_cost_price')
			)
			.where(
				and_(
					self.model.task_id == task_id,
					func.date(self.model.trade_date) == trade_date
				)
			)
		)

		total_result = await self.session.execute(total_query)
		total_stats = total_result.first()

		# 持仓市值排名
		top_positions_query = (
			select(self.model)
			.where(
				and_(
					self.model.task_id == task_id,
					func.date(self.model.trade_date) == trade_date
				)
			)
			.order_by(desc(self.model.market_value))
			.limit(10)
		)

		top_result = await self.session.execute(top_positions_query)
		top_positions = top_result.scalars().all()

		return {
			"total_positions": total_stats.total_positions or 0,
			"total_volume": total_stats.total_volume or 0,
			"total_market_value": total_stats.total_market_value or 0,
			"avg_cost_price": float(total_stats.avg_cost_price or 0),
			"top_positions": [self._position_to_dict(pos) for pos in top_positions]
		}

	async def get_position_timeline (self, task_id: str) -> List[Dict[str, Any]]:
		"""获取持仓时间线数据（按日汇总）"""
		query = (
			select(
				func.date(self.model.trade_date).label('trade_date'),
				func.count().label('position_count'),
				func.sum(self.model.volume).label('total_volume'),
				func.sum(self.model.market_value).label('total_market_value')
			)
			.where(self.model.task_id == task_id)
			.group_by(func.date(self.model.trade_date))
			.order_by(func.date(self.model.trade_date))
		)

		result = await self.session.execute(query)
		timeline = []
		for row in result.all():
			timeline.append({
				"trade_date": row.trade_date,
				"position_count": row.position_count,
				"total_volume": row.total_volume,
				"total_market_value": row.total_market_value
			})

		return timeline

	async def get_top_holdings_by_duration (self, task_id: str, top_n: int = 10) -> List[Dict[str, Any]]:
		"""获取持仓时间最长的股票"""
		# 获取每只股票的最早和最晚持仓日期
		query = (
			select(
				self.model.ts_code,
				func.min(func.date(self.model.trade_date)).label('first_held'),
				func.max(func.date(self.model.trade_date)).label('last_held'),
				func.count().label('holding_days'),
				func.avg(self.model.volume).label('avg_volume'),
				func.avg(self.model.market_value).label('avg_market_value')
			)
			.where(self.model.task_id == task_id)
			.group_by(self.model.ts_code)
			.order_by(desc(literal_column('holding_days')))
			.limit(top_n)
		)

		result = await self.session.execute(query)
		holdings = []
		for row in result.all():
			holdings.append({
				"ts_code": row.ts_code,
				"first_held": row.first_held,
				"last_held": row.last_held,
				"holding_days": row.holding_days,
				"avg_volume": float(row.avg_volume or 0),
				"avg_market_value": float(row.avg_market_value or 0)
			})

		return holdings

	async def batch_create_positions (self, task_id: str, positions_data: List[Dict[str, Any]]) -> int:
		"""批量创建持仓快照"""
		now = datetime.now()
		instances = []

		for data in positions_data:
			# 确保task_id一致
			data['task_id'] = task_id
			data['created_at'] = now

			instance = self.model(**data)
			instances.append(instance)

		self.session.add_all(instances)
		await self.session.flush()
		return len(instances)

	@staticmethod
	def _position_to_dict (position: BacktestPosition) -> Dict[str, Any]:
		"""将持仓对象转换为字典"""
		return {
			"ts_code": position.ts_code,
			"trade_date": position.trade_date,
			"volume": position.volume,
			"cost_price": float(position.cost_price),
			"market_value": float(position.market_value)
		}
