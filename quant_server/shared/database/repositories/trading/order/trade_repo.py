# -*- coding: utf-8 -*-
"""
成交记录仓库 - 提供成交记录数据的统一访问接口

基于BaseRepository实现，提供成交记录相关的CRUD操作和业务查询方法
位置：quant_server/shared/database/repositories/trading/order/trade_repository.py

设计原则：
1. 纯数据访问：只做CRUD，不做业务逻辑
2. 继承BaseRepository：复用基础CRUD操作
3. 时序数据优化：支持时间范围查询和统计
4. 关联查询：支持与订单表的关联查询
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, asc, text, case

from quant_server.shared.database.repositories.base import BaseRepository,RepositoryError
from quant_server.shared.database.models.business_models import Trade, Order, Account, Strategy, SysUser
from quant_server.shared.database.repositories.types import (
	PaginationParams,
	PaginationResult,
	FilterCondition,
	SortCondition,
)


class TradeRepository(BaseRepository[Trade]):
	"""成交记录仓库 - 成交数据访问层"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化成交记录仓库

		Args:
			session: 数据库会话
		"""
		super().__init__(session, Trade)

	# ==================== 业务查询方法 ====================

	async def get_by_trade_id (self, trade_id: str, with_order: bool = False) -> Optional[Trade]:
		"""
		根据成交ID获取成交记录

		Args:
			trade_id: 成交ID
			with_order: 是否加载订单信息

		Returns:
			成交记录对象或None
		"""
		try:
			query = select(Trade).where(Trade.trade_id == trade_id)

			if with_order:
				query = query.options(joinedload(Trade.order))

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"获取成交记录失败: {str(e)}")

	async def get_by_order_id (
			self,
			order_id: str,
			skip: int = 0,
			limit: int = 100,
			order_by: str = "trade_time_asc"
	) -> List[Trade]:
		"""
		根据订单ID获取成交记录

		Args:
			order_id: 订单ID
			skip: 跳过记录数
			limit: 限制记录数
			order_by: 排序方式

		Returns:
			成交记录列表
		"""
		try:
			# 构建排序
			order_clause = self._build_order_by(order_by)

			query = (
				select(Trade)
				.where(Trade.order_id == order_id)
				.order_by(*order_clause)
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取订单成交记录失败: {str(e)}")

	async def get_by_ts_code (
			self,
			ts_code: str,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			skip: int = 0,
			limit: int = 100,
			order_by: str = "trade_time_desc"
	) -> List[Trade]:
		"""
		根据股票代码获取成交记录

		Args:
			ts_code: 股票代码
			start_time: 开始时间
			end_time: 结束时间
			skip: 跳过记录数
			limit: 限制记录数
			order_by: 排序方式

		Returns:
			成交记录列表
		"""
		try:
			filters = [Trade.ts_code == ts_code]

			if start_time:
				filters.append(Trade.trade_time >= start_time)
			if end_time:
				filters.append(Trade.trade_time <= end_time)

			# 构建排序
			order_clause = self._build_order_by(order_by)

			query = (
				select(Trade)
				.where(and_(*filters))
				.order_by(*order_clause)
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取股票成交记录失败: {str(e)}")

	async def get_by_user_id (
			self,
			user_id: int,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			skip: int = 0,
			limit: int = 100
	) -> List[Trade]:
		"""
		根据用户ID获取成交记录（需要关联订单表）

		Args:
			user_id: 用户ID
			start_time: 开始时间
			end_time: 结束时间
			skip: 跳过记录数
			limit: 限制记录数

		Returns:
			成交记录列表
		"""
		try:
			# 构建子查询：获取用户的订单ID
			order_subquery = (
				select(Order.order_id)
				.where(Order.user_id == user_id)
				.subquery()
			)

			filters = [Trade.order_id.in_(select(order_subquery.c.order_id))]

			if start_time:
				filters.append(Trade.trade_time >= start_time)
			if end_time:
				filters.append(Trade.trade_time <= end_time)

			query = (
				select(Trade)
				.where(and_(*filters))
				.order_by(desc(Trade.trade_time))
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取用户成交记录失败: {str(e)}")

	async def get_by_strategy_id (
			self,
			strategy_id: str,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			skip: int = 0,
			limit: int = 100
	) -> List[Trade]:
		"""
		根据策略ID获取成交记录（需要关联订单表）

		Args:
			strategy_id: 策略ID
			start_time: 开始时间
			end_time: 结束时间
			skip: 跳过记录数
			limit: 限制记录数

		Returns:
			成交记录列表
		"""
		try:
			# 构建子查询：获取策略的订单ID
			order_subquery = (
				select(Order.order_id)
				.where(Order.strategy_id == strategy_id)
				.subquery()
			)

			filters = [Trade.order_id.in_(select(order_subquery.c.order_id))]

			if start_time:
				filters.append(Trade.trade_time >= start_time)
			if end_time:
				filters.append(Trade.trade_time <= end_time)

			query = (
				select(Trade)
				.where(and_(*filters))
				.order_by(desc(Trade.trade_time))
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取策略成交记录失败: {str(e)}")

	async def get_by_trade_date (
			self,
			trade_date: date,
			ts_codes: Optional[List[str]] = None,
			user_id: Optional[int] = None,
			skip: int = 0,
			limit: int = 1000
	) -> List[Trade]:
		"""
		根据交易日期获取成交记录

		Args:
			trade_date: 交易日期
			ts_codes: 股票代码列表过滤
			user_id: 用户ID过滤
			skip: 跳过记录数
			limit: 限制记录数

		Returns:
			成交记录列表
		"""
		try:
			start_of_day = datetime.combine(trade_date, datetime.min.time())
			end_of_day = datetime.combine(trade_date, datetime.max.time())

			filters = [
				Trade.trade_time >= start_of_day,
				Trade.trade_time <= end_of_day
			]

			if ts_codes:
				filters.append(Trade.ts_code.in_(ts_codes))

			if user_id:
				# 需要关联订单表
				order_subquery = (
					select(Order.order_id)
					.where(Order.user_id == user_id)
					.subquery()
				)
				filters.append(Trade.order_id.in_(select(order_subquery.c.order_id)))

			query = (
				select(Trade)
				.where(and_(*filters))
				.order_by(asc(Trade.trade_time))
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取交易日成交记录失败: {str(e)}")

	async def get_today_trades (
			self,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None,
			ts_code: Optional[str] = None
	) -> List[Trade]:
		"""
		获取今日成交记录

		Args:
			user_id: 用户ID过滤
			strategy_id: 策略ID过滤
			ts_code: 股票代码过滤

		Returns:
			今日成交记录列表
		"""
		try:
			today = datetime.now().date()
			return await self.get_by_trade_date(today, [ts_code] if ts_code else None, user_id, 1000)

		except Exception as e:
			raise RepositoryError(f"获取今日成交记录失败: {str(e)}")

	async def get_recent_trades (
			self,
			days: int = 7,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None,
			ts_code: Optional[str] = None
	) -> List[Trade]:
		"""
		获取最近N天的成交记录

		Args:
			days: 天数
			user_id: 用户ID过滤
			strategy_id: 策略ID过滤
			ts_code: 股票代码过滤

		Returns:
			最近成交记录列表
		"""
		try:
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
					and_(
						Trade.trade_time >= start_time,
						Trade.trade_time <= end_time
					),
					limit=1000,
					order_by="trade_time_desc"
				)

		except Exception as e:
			raise RepositoryError(f"获取最近成交记录失败: {str(e)}")

	# ==================== 统计分析方法 ====================

	async def get_trade_statistics (
			self,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None,
			ts_code: Optional[str] = None,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None
	) -> Dict[str, Any]:
		"""
		获取成交统计信息

		Args:
			user_id: 用户ID过滤
			strategy_id: 策略ID过滤
			ts_code: 股票代码过滤
			start_time: 开始时间
			end_time: 结束时间

		Returns:
			成交统计信息字典
		"""
		try:
			# 构建过滤条件
			filters = []

			if ts_code:
				filters.append(Trade.ts_code == ts_code)

			if start_time:
				filters.append(Trade.trade_time >= start_time)
			if end_time:
				filters.append(Trade.trade_time <= end_time)

			# 处理用户或策略过滤
			if user_id or strategy_id:
				order_filters = []
				if user_id:
					order_filters.append(Order.user_id == user_id)
				if strategy_id:
					order_filters.append(Order.strategy_id == strategy_id)

				order_subquery = (
					select(Order.order_id)
					.where(and_(*order_filters))
					.subquery()
				)
				filters.append(Trade.order_id.in_(select(order_subquery.c.order_id)))

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

			return {
				'total_count': row.total_count or 0,
				'total_volume': row.total_volume or 0,
				'total_amount': float(row.total_amount) if row.total_amount else 0,
				'total_commission': float(row.total_commission) if row.total_commission else 0,
				'total_tax': float(row.total_tax) if row.total_tax else 0,
				'avg_price': float(row.avg_price) if row.avg_price else 0,
				'total_cost': float((row.total_amount or 0) + (row.total_commission or 0) + (row.total_tax or 0))
			}

		except Exception as e:
			raise RepositoryError(f"获取成交统计失败: {str(e)}")

	async def get_trade_summary_by_date (
			self,
			start_date: date,
			end_date: date,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None
	) -> List[Dict[str, Any]]:
		"""
		按日期汇总成交统计

		Args:
			start_date: 开始日期
			end_date: 结束日期
			user_id: 用户ID过滤
			strategy_id: 策略ID过滤

		Returns:
			按日期汇总的成交统计列表
		"""
		try:
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

				order_subquery = (
					select(Order.order_id)
					.where(and_(*order_filters))
					.subquery()
				)
				query = query.where(Trade.order_id.in_(select(order_subquery.c.order_id)))

			query = query.group_by(
				func.date(Trade.trade_time)
			).order_by(
				desc(func.date(Trade.trade_time))
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

		except Exception as e:
			raise RepositoryError(f"获取按日期成交汇总失败: {str(e)}")

	async def get_trade_summary_by_stock (
			self,
			start_time: datetime,
			end_time: datetime,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None,
			top_n: int = 20
	) -> List[Dict[str, Any]]:
		"""
		按股票汇总成交统计

		Args:
			start_time: 开始时间
			end_time: 结束时间
			user_id: 用户ID过滤
			strategy_id: 策略ID过滤
			top_n: 返回前N个

		Returns:
			按股票汇总的成交统计列表
		"""
		try:
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

				order_subquery = (
					select(Order.order_id)
					.where(and_(*order_filters))
					.subquery()
				)
				query = query.where(Trade.order_id.in_(select(order_subquery.c.order_id)))

			query = query.group_by(
				Trade.ts_code
			).order_by(
				desc(func.sum(Trade.price * Trade.volume))
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

		except Exception as e:
			raise RepositoryError(f"获取按股票成交汇总失败: {str(e)}")

	async def get_trade_flow (
			self,
			ts_code: str,
			start_time: datetime,
			end_time: datetime,
			interval_minutes: int = 5
	) -> List[Dict[str, Any]]:
		"""
		获取交易流量（按时间间隔）

		Args:
			ts_code: 股票代码
			start_time: 开始时间
			end_time: 结束时间
			interval_minutes: 时间间隔（分钟）

		Returns:
			交易流量列表
		"""
		try:
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
				asc(func.date_trunc(f'{interval_minutes} minutes', Trade.trade_time))
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

		except Exception as e:
			raise RepositoryError(f"获取交易流量失败: {str(e)}")

	# ==================== 高级查询方法 ====================

	async def get_trade_with_order_info (
			self,
			trade_id: str
	) -> Optional[Dict[str, Any]]:
		"""
		获取成交记录及其订单信息

		Args:
			trade_id: 成交ID

		Returns:
			成交记录及订单信息字典或None
		"""
		try:
			trade = await self.get_by_trade_id(trade_id, with_order=True)
			if not trade:
				return None

			return {
				'trade': trade,
				'order': trade.order
			}

		except Exception as e:
			raise RepositoryError(f"获取成交及订单信息失败: {str(e)}")

	async def get_trades_with_order_info (
			self,
			order_ids: List[str],
			skip: int = 0,
			limit: int = 100
	) -> List[Dict[str, Any]]:
		"""
		批量获取成交记录及其订单信息

		Args:
			order_ids: 订单ID列表
			skip: 跳过记录数
			limit: 限制记录数

		Returns:
			成交记录及订单信息列表
		"""
		try:
			if not order_ids:
				return []

			# 使用JOIN查询
			query = (
				select(Trade, Order)
				.join(Order, Trade.order_id == Order.order_id)
				.where(Trade.order_id.in_(order_ids))
				.order_by(desc(Trade.trade_time))
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			rows = result.all()

			trades = []
			for trade, order in rows:
				trades.append({
					'trade': trade,
					'order': order
				})

			return trades

		except Exception as e:
			raise RepositoryError(f"批量获取成交及订单信息失败: {str(e)}")

	async def search_trades (
			self,
			query_params: Dict[str, Any],
			pagination: PaginationParams
	) -> PaginationResult[Trade]:
		"""
		搜索成交记录

		Args:
			query_params: 查询参数
			pagination: 分页参数

		Returns:
			分页结果
		"""
		try:
			filters = []

			# 构建过滤条件
			if 'ts_code' in query_params:
				filters.append(Trade.ts_code == query_params['ts_code'])
			if 'order_id' in query_params:
				filters.append(Trade.order_id == query_params['order_id'])

			# 价格范围
			if 'min_price' in query_params:
				filters.append(Trade.price >= query_params['min_price'])
			if 'max_price' in query_params:
				filters.append(Trade.price <= query_params['max_price'])

			# 数量范围
			if 'min_volume' in query_params:
				filters.append(Trade.volume >= query_params['min_volume'])
			if 'max_volume' in query_params:
				filters.append(Trade.volume <= query_params['max_volume'])

			# 时间范围
			if 'start_time' in query_params:
				filters.append(Trade.trade_time >= query_params['start_time'])
			if 'end_time' in query_params:
				filters.append(Trade.trade_time <= query_params['end_time'])

			# 费用范围
			if 'min_commission' in query_params:
				filters.append(Trade.commission >= query_params['min_commission'])
			if 'max_commission' in query_params:
				filters.append(Trade.commission <= query_params['max_commission'])

			if 'min_tax' in query_params:
				filters.append(Trade.tax >= query_params['min_tax'])
			if 'max_tax' in query_params:
				filters.append(Trade.tax <= query_params['max_tax'])

			# 用户或策略过滤
			if 'user_id' in query_params or 'strategy_id' in query_params:
				order_filters = []
				if 'user_id' in query_params:
					order_filters.append(Order.user_id == query_params['user_id'])
				if 'strategy_id' in query_params:
					order_filters.append(Order.strategy_id == query_params['strategy_id'])

				order_subquery = (
					select(Order.order_id)
					.where(and_(*order_filters))
					.subquery()
				)
				filters.append(Trade.order_id.in_(select(order_subquery.c.order_id)))

			# 构建过滤条件对象
			filter_conditions = []
			for field, value in query_params.items():
				if hasattr(Trade, field) and field not in ['user_id', 'strategy_id']:
					filter_conditions.append(
						FilterCondition(field=field, operator="eq", value=value)
					)

			# 执行分页查询
			return await self.paginate(
				pagination=pagination,
				filters=filter_conditions,
				sorts=[SortCondition(field="trade_time", descending=True)]
			)

		except Exception as e:
			raise RepositoryError(f"搜索成交记录失败: {str(e)}")

	# ==================== 批量操作方法 ====================

	async def batch_create_trades (
			self,
			trades_data: List[Dict[str, Any]]
	) -> List[Trade]:
		"""
		批量创建成交记录

		Args:
			trades_data: 成交记录数据列表

		Returns:
			创建的成交记录列表
		"""
		try:
			if not trades_data:
				return []

			# 准备批量插入数据
			now = datetime.now()
			for trade_data in trades_data:
				if 'created_at' not in trade_data:
					trade_data['created_at'] = now

			return await self.batch_create(trades_data)

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"批量创建成交记录失败: {str(e)}")

	async def batch_upsert_trades (
			self,
			trades_data: List[Dict[str, Any]],
			match_fields: List[str] = ['trade_id']
	) -> List[Trade]:
		"""
		批量插入或更新成交记录

		Args:
			trades_data: 成交记录数据列表
			match_fields: 匹配字段

		Returns:
			插入或更新的成交记录列表
		"""
		try:
			if not trades_data:
				return []

			return await self.batch_upsert(trades_data, match_fields)

		except Exception as e:
			raise RepositoryError(f"批量插入或更新成交记录失败: {str(e)}")

	async def delete_old_trades (self, days: int = 365) -> int:
		"""
		删除旧的成交记录

		Args:
			days: 保留天数

		Returns:
			删除的记录数
		"""
		try:
			cutoff_time = datetime.now() - timedelta(days=days)

			# 获取要删除的记录ID
			query = select(Trade.id).where(
				Trade.trade_time < cutoff_time
			)

			result = await self.session.execute(query)
			old_trade_ids = [row[0] for row in result.all()]

			# 批量删除
			deleted_count = 0
			for trade_id in old_trade_ids:
				success = await self.delete(trade_id, soft=False)
				if success:
					deleted_count += 1

			return deleted_count

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"删除旧成交记录失败: {str(e)}")

	# ==================== 辅助方法 ====================

	def _build_order_by (self, order_by: str) -> List:
		"""
		构建排序子句

		Args:
			order_by: 排序字符串，格式：field_[asc/desc]

		Returns:
			排序子句列表
		"""
		order_mappings = {
			'trade_time_asc': [asc(Trade.trade_time)],
			'trade_time_desc': [desc(Trade.trade_time)],
			'price_asc': [asc(Trade.price)],
			'price_desc': [desc(Trade.price)],
			'volume_asc': [asc(Trade.volume)],
			'volume_desc': [desc(Trade.volume)],
			'commission_asc': [asc(Trade.commission)],
			'commission_desc': [desc(Trade.commission)],
		}

		return order_mappings.get(order_by, [desc(Trade.trade_time)])

	async def get_trade_summary (self) -> Dict[str, Any]:
		"""
		获取成交数据摘要

		Returns:
			成交数据摘要字典
		"""
		try:
			# 总成交记录数
			total_trades = await self.count()

			# 今日成交记录数
			today = datetime.now().date()
			today_trades = await self.count(
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

			# 成交总额统计
			amount_stats = await self.session.execute(
				select(
					func.sum(Trade.price * Trade.volume).label('total_amount'),
					func.sum(Trade.commission).label('total_commission'),
					func.sum(Trade.tax).label('total_tax')
				)
			)

			amount_row = amount_stats.first()
			amount_dict = {
				'total_amount': float(amount_row.total_amount) if amount_row.total_amount else 0,
				'total_commission': float(amount_row.total_commission) if amount_row.total_commission else 0,
				'total_tax': float(amount_row.total_tax) if amount_row.total_tax else 0
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
				'total_trades': total_trades,
				'today_trades': today_trades,
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

		except Exception as e:
			raise RepositoryError(f"获取成交摘要失败: {str(e)}")