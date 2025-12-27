# -*- coding: utf-8 -*-
"""
交易数据仓库
提供交易记录数据的统一访问接口
位置：shared/database/repositories/trade_repo.py
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, distinct, case

from .base import BaseRepository
from quant_server.shared.database.models.business_models import Trade, Order


class TradeRepository:
	"""交易数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.base_repo = BaseRepository(session, Trade)
		self.order_repo = BaseRepository(session, Order)

	# ==================== 基础CRUD操作 ====================

	async def create (self, data: Dict[str, Any]) -> Trade:
		"""创建交易记录"""
		return await self.base_repo.create(data)

	async def get (self, trade_id: str) -> Optional[Trade]:
		"""根据交易ID获取交易记录"""
		return await self.base_repo.get_one(Trade.trade_id == trade_id)

	async def update (self, trade_id: str, data: Dict[str, Any]) -> Optional[Trade]:
		"""更新交易记录"""
		trade = await self.get(trade_id)
		if trade:
			return await self.base_repo.update(trade.id, data)
		return None

	async def delete (self, trade_id: str, soft: bool = True) -> bool:
		"""删除交易记录"""
		trade = await self.get(trade_id)
		if trade:
			return await self.base_repo.delete(trade.id, soft)
		return False

	async def get_one (self, *filters) -> Optional[Trade]:
		"""根据条件获取单个交易记录"""
		return await self.base_repo.get_one(*filters)

	async def get_many (
			self,
			*filters,
			skip: int = 0,
			limit: int = 100,
			order_by: str = None
	) -> List[Trade]:
		"""根据条件获取多个交易记录"""
		return await self.base_repo.get_many(*filters, skip=skip, limit=limit, order_by=order_by)

	async def count (self, *filters) -> int:
		"""统计交易记录数"""
		return await self.base_repo.count(*filters)

	# ==================== 业务查询方法 ====================

	async def get_by_order_id (self, order_id: str) -> List[Trade]:
		"""根据订单ID获取交易记录"""
		return await self.get_many(
			Trade.order_id == order_id,
			order_by=Trade.trade_time.asc()
		)

	async def get_by_ts_code (
			self,
			ts_code: str,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			limit: int = 100
	) -> List[Trade]:
		"""根据股票代码获取交易记录"""
		filters = [Trade.ts_code == ts_code]

		if start_time:
			filters.append(Trade.trade_time >= start_time)
		if end_time:
			filters.append(Trade.trade_time <= end_time)

		return await self.get_many(
			*filters,
			limit=limit,
			order_by=Trade.trade_time.desc()
		)

	async def get_by_user_id (
			self,
			user_id: int,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			limit: int = 100
	) -> List[Trade]:
		"""根据用户ID获取交易记录（需要关联订单表）"""
		# 首先通过订单表找到用户的订单
		order_query = select(Order.order_id).where(Order.user_id == user_id)

		if start_time:
			order_query = order_query.where(Order.submitted_at >= start_time)
		if end_time:
			order_query = order_query.where(Order.submitted_at <= end_time)

		order_result = await self.session.execute(order_query)
		order_ids = [row[0] for row in order_result.all()]

		if not order_ids:
			return []

		# 根据订单ID获取交易记录
		filters = [Trade.order_id.in_(order_ids)]

		if start_time:
			filters.append(Trade.trade_time >= start_time)
		if end_time:
			filters.append(Trade.trade_time <= end_time)

		return await self.get_many(
			*filters,
			limit=limit,
			order_by=Trade.trade_time.desc()
		)

	async def get_by_strategy_id (
			self,
			strategy_id: str,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			limit: int = 100
	) -> List[Trade]:
		"""根据策略ID获取交易记录（需要关联订单表）"""
		# 首先通过订单表找到策略的订单
		order_query = select(Order.order_id).where(Order.strategy_id == strategy_id)

		if start_time:
			order_query = order_query.where(Order.submitted_at >= start_time)
		if end_time:
			order_query = order_query.where(Order.submitted_at <= end_time)

		order_result = await self.session.execute(order_query)
		order_ids = [row[0] for row in order_result.all()]

		if not order_ids:
			return []

		# 根据订单ID获取交易记录
		filters = [Trade.order_id.in_(order_ids)]

		if start_time:
			filters.append(Trade.trade_time >= start_time)
		if end_time:
			filters.append(Trade.trade_time <= end_time)

		return await self.get_many(
			*filters,
			limit=limit,
			order_by=Trade.trade_time.desc()
		)

	async def get_by_trade_date (
			self,
			trade_date: date,
			ts_codes: Optional[List[str]] = None,
			limit: int = 1000
	) -> List[Trade]:
		"""根据交易日期获取交易记录"""
		start_of_day = datetime.combine(trade_date, datetime.min.time())
		end_of_day = datetime.combine(trade_date, datetime.max.time())

		filters = [
			Trade.trade_time >= start_of_day,
			Trade.trade_time <= end_of_day
		]

		if ts_codes:
			filters.append(Trade.ts_code.in_(ts_codes))

		return await self.get_many(
			*filters,
			limit=limit,
			order_by=Trade.trade_time.asc()
		)

	async def get_today_trades (
			self,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None,
			ts_code: Optional[str] = None
	) -> List[Trade]:
		"""获取今日交易记录"""
		today = datetime.now().date()
		return await self.get_by_trade_date(today, [ts_code] if ts_code else None, 1000)

	async def get_recent_trades (
			self,
			days: int = 7,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None,
			ts_code: Optional[str] = None
	) -> List[Trade]:
		"""获取最近N天的交易记录"""
		end_time = datetime.now()
		start_time = end_time - timedelta(days=days)

		if user_id:
			return await self.get_by_user_id(user_id, start_time, end_time, 1000)
		elif strategy_id:
			return await self.get_by_strategy_id(strategy_id, start_time, end_time, 1000)
		elif ts_code:
			return await self.get_by_ts_code(ts_code, start_time, end_time, 1000)
		else:
			return await self.get_many(
				Trade.trade_time >= start_time,
				Trade.trade_time <= end_time,
				limit=1000,
				order_by=Trade.trade_time.desc()
			)

	async def get_trade_statistics (
			self,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None,
			ts_code: Optional[str] = None,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None
	) -> Dict[str, Any]:
		"""获取交易统计信息"""
		# 构建查询条件
		filters = []

		if user_id or strategy_id:
			# 需要关联订单表
			order_filters = []
			if user_id:
				order_filters.append(Order.user_id == user_id)
			if strategy_id:
				order_filters.append(Order.strategy_id == strategy_id)

			order_query = select(Order.order_id).where(and_(*order_filters))
			order_result = await self.session.execute(order_query)
			order_ids = [row[0] for row in order_result.all()]

			if order_ids:
				filters.append(Trade.order_id.in_(order_ids))
			else:
				# 如果没有订单，返回空统计
				return {
					'total_count': 0,
					'total_volume': 0,
					'total_amount': 0,
					'total_commission': 0,
					'total_tax': 0,
					'avg_price': 0
				}

		if ts_code:
			filters.append(Trade.ts_code == ts_code)

		if start_time:
			filters.append(Trade.trade_time >= start_time)
		if end_time:
			filters.append(Trade.trade_time <= end_time)

		where_clause = and_(*filters) if filters else True

		# 执行统计查询
		result = await self.session.execute(
			select(
				func.count(Trade.trade_id).label('total_count'),
				func.sum(Trade.volume).label('total_volume'),
				func.sum(Trade.price * Trade.volume).label('total_amount'),
				func.sum(Trade.commission).label('total_commission'),
				func.sum(Trade.tax).label('total_tax'),
				func.avg(Trade.price).label('avg_price')
			).where(where_clause)
		)

		row = result.first()

		if not row:
			return {
				'total_count': 0,
				'total_volume': 0,
				'total_amount': 0,
				'total_commission': 0,
				'total_tax': 0,
				'avg_price': 0
			}

		return {
			'total_count': row.total_count or 0,
			'total_volume': row.total_volume or 0,
			'total_amount': float(row.total_amount) if row.total_amount else 0,
			'total_commission': float(row.total_commission) if row.total_commission else 0,
			'total_tax': float(row.total_tax) if row.total_tax else 0,
			'avg_price': float(row.avg_price) if row.avg_price else 0,
			'total_cost': float((row.total_amount or 0) + (row.total_commission or 0) + (row.total_tax or 0))
		}

	async def get_trade_summary_by_date (
			self,
			start_date: date,
			end_date: date,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None
	) -> List[Dict[str, Any]]:
		"""按日期汇总交易统计"""
		# 构建基础查询
		query = select(
			func.date(Trade.trade_time).label('trade_date'),
			func.count(Trade.trade_id).label('trade_count'),
			func.sum(Trade.volume).label('total_volume'),
			func.sum(Trade.price * Trade.volume).label('total_amount'),
			func.sum(Trade.commission).label('total_commission'),
			func.sum(Trade.tax).label('total_tax')
		).where(
			and_(
				Trade.trade_time >= start_date,
				Trade.trade_time <= end_date + timedelta(days=1)  # 包含结束日期
			)
		)

		# 添加过滤条件
		if user_id or strategy_id:
			order_filters = []
			if user_id:
				order_filters.append(Order.user_id == user_id)
			if strategy_id:
				order_filters.append(Order.strategy_id == strategy_id)

			order_query = select(Order.order_id).where(and_(*order_filters))
			order_result = await self.session.execute(order_query)
			order_ids = [row[0] for row in order_result.all()]

			if order_ids:
				query = query.where(Trade.order_id.in_(order_ids))
			else:
				return []

		query = query.group_by(
			func.date(Trade.trade_time)
		).order_by(
			func.date(Trade.trade_time).desc()
		)

		result = await self.session.execute(query)
		rows = result.all()

		summary = []
		for row in rows:
			summary.append({
				'trade_date': row.trade_date,
				'trade_count': row.trade_count or 0,
				'total_volume': row.total_volume or 0,
				'total_amount': float(row.total_amount) if row.total_amount else 0,
				'total_commission': float(row.total_commission) if row.total_commission else 0,
				'total_tax': float(row.total_tax) if row.total_tax else 0,
				'total_cost': float((row.total_amount or 0) + (row.total_commission or 0) + (row.total_tax or 0))
			})

		return summary

	async def get_trade_summary_by_stock (
			self,
			start_time: datetime,
			end_time: datetime,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None,
			top_n: int = 20
	) -> List[Dict[str, Any]]:
		"""按股票汇总交易统计"""
		# 构建基础查询
		query = select(
			Trade.ts_code,
			func.count(Trade.trade_id).label('trade_count'),
			func.sum(Trade.volume).label('total_volume'),
			func.sum(Trade.price * Trade.volume).label('total_amount'),
			func.avg(Trade.price).label('avg_price')
		).where(
			and_(
				Trade.trade_time >= start_time,
				Trade.trade_time <= end_time
			)
		)

		# 添加过滤条件
		if user_id or strategy_id:
			order_filters = []
			if user_id:
				order_filters.append(Order.user_id == user_id)
			if strategy_id:
				order_filters.append(Order.strategy_id == strategy_id)

			order_query = select(Order.order_id).where(and_(*order_filters))
			order_result = await self.session.execute(order_query)
			order_ids = [row[0] for row in order_result.all()]

			if order_ids:
				query = query.where(Trade.order_id.in_(order_ids))
			else:
				return []

		query = query.group_by(
			Trade.ts_code
		).order_by(
			func.sum(Trade.price * Trade.volume).desc()
		).limit(top_n)

		result = await self.session.execute(query)
		rows = result.all()

		summary = []
		for row in rows:
			summary.append({
				'ts_code': row.ts_code,
				'trade_count': row.trade_count or 0,
				'total_volume': row.total_volume or 0,
				'total_amount': float(row.total_amount) if row.total_amount else 0,
				'avg_price': float(row.avg_price) if row.avg_price else 0
			})

		return summary

	async def get_trade_flow (
			self,
			ts_code: str,
			start_time: datetime,
			end_time: datetime,
			interval_minutes: int = 5
	) -> List[Dict[str, Any]]:
		"""获取交易流量（按时间间隔）"""
		# 将时间按指定间隔分组
		query = select(
			func.date_trunc(f'{interval_minutes} minutes', Trade.trade_time).label('time_bucket'),
			func.sum(Trade.volume).label('total_volume'),
			func.sum(Trade.price * Trade.volume).label('total_amount'),
			func.avg(Trade.price).label('avg_price'),
			func.count(Trade.trade_id).label('trade_count')
		).where(
			and_(
				Trade.ts_code == ts_code,
				Trade.trade_time >= start_time,
				Trade.trade_time <= end_time
			)
		).group_by(
			func.date_trunc(f'{interval_minutes} minutes', Trade.trade_time)
		).order_by(
			func.date_trunc(f'{interval_minutes} minutes', Trade.trade_time).asc()
		)

		result = await self.session.execute(query)
		rows = result.all()

		flow = []
		for row in rows:
			flow.append({
				'time_bucket': row.time_bucket,
				'total_volume': row.total_volume or 0,
				'total_amount': float(row.total_amount) if row.total_amount else 0,
				'avg_price': float(row.avg_price) if row.avg_price else 0,
				'trade_count': row.trade_count or 0
			})

		return flow

	async def get_trade_with_order_info (
			self,
			trade_id: str
	) -> Optional[Dict[str, Any]]:
		"""获取交易记录及其订单信息"""
		trade = await self.get(trade_id)
		if not trade:
			return None

		# 获取订单信息
		order = await self.order_repo.get_one(Order.order_id == trade.order_id)

		result = {
			'trade': trade,
			'order': order
		}

		return result

	async def get_trades_with_order_info (
			self,
			order_ids: List[str],
			limit: int = 100
	) -> List[Dict[str, Any]]:
		"""批量获取交易记录及其订单信息"""
		if not order_ids:
			return []

		# 使用JOIN查询
		query = select(
			Trade,
			Order
		).join(
			Order,
			Trade.order_id == Order.order_id
		).where(
			Trade.order_id.in_(order_ids)
		).order_by(
			Trade.trade_time.desc()
		).limit(limit)

		result = await self.session.execute(query)
		rows = result.all()

		trades = []
		for row in rows:
			trades.append({
				'trade': row[0],
				'order': row[1]
			})

		return trades

	async def batch_create (
			self,
			data_list: List[Dict[str, Any]]
	) -> List[Trade]:
		"""批量创建交易记录"""
		return await self.base_repo.batch_create(data_list)

	async def batch_upsert (
			self,
			data_list: List[Dict[str, Any]],
			match_fields: List[str] = ['trade_id']
	) -> List[Trade]:
		"""批量插入或更新交易记录"""
		return await self.base_repo.batch_upsert(data_list, match_fields)

	async def delete_old_trades (
			self,
			days: int = 365
	) -> int:
		"""删除旧的交易记录"""
		cutoff_time = datetime.now() - timedelta(days=days)

		# 获取要删除的记录
		query = select(Trade.id).where(
			Trade.trade_time < cutoff_time
		)

		result = await self.session.execute(query)
		old_trade_ids = [row[0] for row in result.all()]

		# 批量删除
		deleted_count = 0
		for trade_id in old_trade_ids:
			success = await self.base_repo.delete(trade_id, soft=False)
			if success:
				deleted_count += 1

		return deleted_count

	async def get_trade_summary (self) -> Dict[str, Any]:
		"""获取交易数据摘要"""
		# 总交易记录数
		total_count = await self.count()

		# 今日交易记录数
		today = datetime.now().date()
		today_count = await self.count(
			and_(
				Trade.trade_time >= today,
				Trade.trade_time < today + timedelta(days=1)
			)
		)

		# 涉及订单数
		order_count = await self.session.execute(
			select(func.count(func.distinct(Trade.order_id)))
		)
		order_count_value = order_count.scalar() or 0

		# 涉及股票数
		stock_count = await self.session.execute(
			select(func.count(func.distinct(Trade.ts_code)))
		)
		stock_count_value = stock_count.scalar() or 0

		# 涉及用户数（通过订单）
		user_count = await self.session.execute(
			select(func.count(func.distinct(Order.user_id)))
			.select_from(Trade)
			.join(Order, Trade.order_id == Order.order_id)
		)
		user_count_value = user_count.scalar() or 0

		# 涉及策略数（通过订单）
		strategy_count = await self.session.execute(
			select(func.count(func.distinct(Order.strategy_id)))
			.select_from(Trade)
			.join(Order, Trade.order_id == Order.order_id)
			.where(Order.strategy_id.isnot(None))
		)
		strategy_count_value = strategy_count.scalar() or 0

		# 交易总额统计
		amount_stats = await self.session.execute(
			select(
				func.sum(Trade.price * Trade.volume).label('total_amount'),
				func.sum(Trade.commission).label('total_commission'),
				func.sum(Trade.tax).label('total_tax')
			)
		)

		amount_row = amount_stats.first()
		amount_dict = {
			'total_amount': float(amount_row[0]) if amount_row[0] else 0,
			'total_commission': float(amount_row[1]) if amount_row[1] else 0,
			'total_tax': float(amount_row[2]) if amount_row[2] else 0
		}

		# 日期范围
		date_range = await self.session.execute(
			select(
				func.min(Trade.trade_time),
				func.max(Trade.trade_time)
			)
		)
		min_time, max_time = date_range.first()

		return {
			'total_records': total_count,
			'today_records': today_count,
			'order_count': order_count_value,
			'stock_count': stock_count_value,
			'user_count': user_count_value,
			'strategy_count': strategy_count_value,
			'amount_stats': amount_dict,
			'date_range': {
				'min_time': min_time,
				'max_time': max_time
			}
		}