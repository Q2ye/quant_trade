# -*- coding: utf-8 -*-
"""
订单仓库 - 提供订单数据的统一访问接口

基于BaseRepository实现，提供订单相关的CRUD操作和业务查询方法
位置：quant_server/shared/database/repositories/trading/order/order_repository.py

设计原则：
1. 纯数据访问：只做CRUD，不做业务逻辑
2. 继承BaseRepository：复用基础CRUD操作
3. 订单专用查询：提供订单特有的业务查询方法
4. 类型安全：使用SQLAlchemy类型提示
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, update, and_, func, desc, asc, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.testing.schema import Column

from shared.database.models.business_models import Order, Trade, Account, Strategy, SysUser
from shared.database.repositories.base import BaseRepository, RepositoryError
from shared.database.repositories.types import (
	PaginationParams,
	PaginationResult,
	FilterCondition,
	SortCondition, FilterOperator
)


class OrderRepository(BaseRepository[Order]):
	"""订单仓库 - 订单数据访问层"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化订单仓库

		Args:
			session: 数据库会话
		"""
		super().__init__(session, Order)

	# ==================== 业务查询方法 ====================

	async def get_by_order_id (self, order_id: str, with_trades: bool = False) -> Optional[Order]:
		"""
		根据订单ID获取订单

		Args:
			order_id: 订单ID
			with_trades: 是否加载成交记录

		Returns:
			订单对象或None
		"""
		try:
			query = select(Order).where(Order.order_id == order_id)

			if with_trades:
				query = query.options(joinedload(Order.trades))

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"获取订单失败: {str(e)}")

	async def get_by_user_id (
			self,
			user_id: str,
			status: Optional[str] = None,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			skip: int = 0,
			limit: int = 100,
			order_by: str = "submitted_at_desc"
	) -> List[Order]:
		"""
		根据用户ID获取订单

		Args:
			user_id: 用户ID
			status: 订单状态过滤
			start_date: 开始时间
			end_date: 结束时间
			skip: 跳过记录数
			limit: 限制记录数
			order_by: 排序方式

		Returns:
			订单列表
		"""
		try:
			filters = [Order.user_id == user_id]

			if status:
				filters.append(Order.status == status)
			if start_date:
				filters.append(Order.submitted_at >= start_date)
			if end_date:
				filters.append(Order.submitted_at <= end_date)

			# 构建排序
			order_clause = self._build_order_by(order_by)

			query = (
				select(Order)
				.where(and_(*filters))
				.order_by(*order_clause)
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取用户订单失败: {str(e)}")

	async def get_by_account_id (
			self,
			account_id: str,
			status: Optional[str] = None,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			skip: int = 0,
			limit: int = 100
	) -> List[Order]:
		"""
		根据账户ID获取订单

		Args:
			account_id: 账户ID
			status: 订单状态过滤
			start_date: 开始时间
			end_date: 结束时间
			skip: 跳过记录数
			limit: 限制记录数

		Returns:
			订单列表
		"""
		try:
			filters = [Order.account_id == account_id]

			if status:
				filters.append(Order.status == status)
			if start_date:
				filters.append(Order.submitted_at >= start_date)
			if end_date:
				filters.append(Order.submitted_at <= end_date)

			query = (
				select(Order)
				.where(and_(*filters))
				.order_by(desc(Order.submitted_at))
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取账户订单失败: {str(e)}")

	async def get_by_strategy_id (
			self,
			strategy_id: str,
			status: Optional[str] = None,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			skip: int = 0,
			limit: int = 100
	) -> List[Order]:
		"""
		根据策略ID获取订单

		Args:
			strategy_id: 策略ID
			status: 订单状态过滤
			start_date: 开始时间
			end_date: 结束时间
			skip: 跳过记录数
			limit: 限制记录数

		Returns:
			订单列表
		"""
		try:
			filters = [Order.strategy_id == strategy_id]

			if status:
				filters.append(Order.status == status)
			if start_date:
				filters.append(Order.submitted_at >= start_date)
			if end_date:
				filters.append(Order.submitted_at <= end_date)

			query = (
				select(Order)
				.where(and_(*filters))
				.order_by(desc(Order.submitted_at))
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取策略订单失败: {str(e)}")

	async def get_by_strategy_and_account (
			self,
			strategy_id: str,
			account_id: str,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			skip: int = 0,
			limit: int = 100
		) -> List[Order]:
		"""
		根据策略ID和账户ID获取订单

		Args:
			strategy_id: 策略ID
			account_id: 账户ID
			start_date: 开始时间
			end_date: 结束时间
			skip: 跳过记录数
			limit: 限制记录数

		Returns:
			订单列表
		"""
		try:
			filters = [
				Order.strategy_id == strategy_id,
				Order.account_id == account_id
			]

			if start_date:
				filters.append(Order.submitted_at >= start_date)
			if end_date:
				filters.append(Order.submitted_at <= end_date)

			query = (
				select(Order)
				.where(and_(*filters))
				.order_by(desc(Order.submitted_at))
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取策略账户订单失败: {str(e)}")

	async def get_by_ts_code (
			self,
			ts_code: str,
			user_id: Optional[str] = None,
			status: Optional[str] = None,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			skip: int = 0,
			limit: int = 100
	) -> List[Order]:
		"""
		根据股票代码获取订单

		Args:
			ts_code: 股票代码
			user_id: 用户ID过滤
			status: 订单状态过滤
			start_date: 开始时间
			end_date: 结束时间
			skip: 跳过记录数
			limit: 限制记录数

		Returns:
			订单列表
		"""
		try:
			filters = [Order.ts_code == ts_code]

			if user_id:
				filters.append(Order.user_id == user_id)
			if status:
				filters.append(Order.status == status)
			if start_date:
				filters.append(Order.submitted_at >= start_date)
			if end_date:
				filters.append(Order.submitted_at <= end_date)

			query = (
				select(Order)
				.where(and_(*filters))
				.order_by(desc(Order.submitted_at))
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取股票订单失败: {str(e)}")

	async def get_active_orders (
			self,
			user_id: Optional[str] = None,
			account_id: Optional[str] = None,
			strategy_id: Optional[str] = None,
			ts_code: Optional[str] = None
	) -> List[Order]:
		"""
		获取活动订单（未完成订单）

		Args:
			user_id: 用户ID过滤
			account_id: 账户ID过滤
			strategy_id: 策略ID过滤
			ts_code: 股票代码过滤

		Returns:
			活动订单列表
		"""
		try:
			# 活动状态：submitted, partial_filled
			active_statuses = ['submitted', 'partial_filled']

			filters: List[Column] = [Order.status.in_(active_statuses)]

			if user_id:
				filters.append(Order.user_id == user_id)
			if account_id:
				filters.append(Order.account_id == account_id)
			if strategy_id:
				filters.append(Order.strategy_id == strategy_id)
			if ts_code:
				filters.append(Order.ts_code == ts_code)

			query = (
				select(Order)
				.where(and_(*filters))
				.order_by(asc(Order.submitted_at))
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取活动订单失败: {str(e)}")

	async def get_today_orders (
			self,
			user_id: Optional[str] = None,
			account_id: Optional[str] = None,
			strategy_id: Optional[str] = None
	) -> List[Order]:
		"""
		获取今日订单

		Args:
			user_id: 用户ID过滤
			account_id: 账户ID过滤
			strategy_id: 策略ID过滤

		Returns:
			今日订单列表
		"""
		try:
			today = datetime.now().date()
			start_of_day = datetime.combine(today, datetime.min.time())
			end_of_day = datetime.combine(today, datetime.max.time())

			filters = [
				Order.submitted_at >= start_of_day,
				Order.submitted_at <= end_of_day
			]

			if user_id:
				filters.append(Order.user_id == user_id)
			if account_id:
				filters.append(Order.account_id == account_id)
			if strategy_id:
				filters.append(Order.strategy_id == strategy_id)

			query = (
				select(Order)
				.where(and_(*filters))
				.order_by(desc(Order.submitted_at))
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取今日订单失败: {str(e)}")

	# ==================== 订单统计方法 ====================

	async def get_order_statistics (
			self,
			user_id: Optional[str] = None,
			account_id: Optional[str] = None,
			strategy_id: Optional[str] = None,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None
	) -> Dict[str, Any]:
		"""
		获取订单统计信息

		Args:
			user_id: 用户ID过滤
			account_id: 账户ID过滤
			strategy_id: 策略ID过滤
			start_date: 开始时间
			end_date: 结束时间

		Returns:
			订单统计信息字典
		"""
		try:
			filters = []

			if user_id:
				filters.append(Order.user_id == user_id)
			if account_id:
				filters.append(Order.account_id == account_id)
			if strategy_id:
				filters.append(Order.strategy_id == strategy_id)
			if start_date:
				filters.append(Order.submitted_at >= start_date)
			if end_date:
				filters.append(Order.submitted_at <= end_date)

			where_clause = and_(*filters) if filters else True

			# 执行统计查询
			result = await self.session.execute(
				select(
					func.count(Order.order_id).label('total_orders'),
					func.sum(case((Order.direction == 'buy', Order.volume), else_=0)).label('buy_volume'),
					func.sum(case((Order.direction == 'sell', Order.volume), else_=0)).label('sell_volume'),
					func.sum(case((Order.direction == 'buy', Order.price * Order.volume), else_=0)).label('buy_amount'),
					func.sum(case((Order.direction == 'sell', Order.price * Order.volume), else_=0)).label(
						'sell_amount'),
					func.avg(Order.price).label('avg_price'),
					func.sum(Order.filled_volume).label('total_filled_volume'),
					func.sum(Order.filled_amount).label('total_filled_amount')
				).where(where_clause)
			)

			row = result.first()

			return {
				'total_orders': row.total_orders or 0,
				'buy_volume': row.buy_volume or 0,
				'sell_volume': row.sell_volume or 0,
				'buy_amount': float(row.buy_amount) if row.buy_amount else 0,
				'sell_amount': float(row.sell_amount) if row.sell_amount else 0,
				'avg_price': float(row.avg_price) if row.avg_price else 0,
				'total_filled_volume': row.total_filled_volume or 0,
				'total_filled_volume_ratio': (row.total_filled_volume or 0) / (row.buy_volume + row.sell_volume) if (
							                                                                                                    row.buy_volume + row.sell_volume) > 0 else 0,
				'total_filled_amount': float(row.total_filled_amount) if row.total_filled_amount else 0
			}

		except Exception as e:
			raise RepositoryError(f"获取订单统计失败: {str(e)}")

	async def get_order_status_summary (
			self,
			user_id: Optional[str] = None,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None
	) -> Dict[str, int]:
		"""
		获取订单状态汇总

		Args:
			user_id: 用户ID过滤
			start_date: 开始时间
			end_date: 结束时间

		Returns:
			订单状态统计字典
		"""
		try:
			filters = []

			if user_id:
				filters.append(Order.user_id == user_id)
			if start_date:
				filters.append(Order.submitted_at >= start_date)
			if end_date:
				filters.append(Order.submitted_at <= end_date)

			where_clause = and_(*filters) if filters else True

			# 按状态分组统计
			result = await self.session.execute(
				select(
					Order.status,
					func.count(Order.order_id).label('count')
				)
				.where(where_clause)
				.group_by(Order.status)
			)

			status_summary = {}
			for row in result.all():
				status_summary[row.status] = row.count

			return status_summary

		except Exception as e:
			raise RepositoryError(f"获取订单状态汇总失败: {str(e)}")

	async def get_order_summary_by_date (
			self,
			start_date: date,
			end_date: date,
			user_id: Optional[str] = None,
			account_id: Optional[str] = None
	) -> List[Dict[str, Any]]:
		"""
		按日期汇总订单统计

		Args:
			start_date: 开始日期
			end_date: 结束日期
			user_id: 用户ID过滤
			account_id: 账户ID过滤

		Returns:
			按日期汇总的订单统计列表
		"""
		try:
			filters = [
				Order.submitted_at >= start_date,
				Order.submitted_at <= end_date + timedelta(days=1)
			]

			if user_id:
				filters.append(Order.user_id == user_id)
			if account_id:
				filters.append(Order.account_id == account_id)

			query = (
				select(
					func.date(Order.submitted_at).label('order_date'),
					func.count(Order.order_id).label('order_count'),
					func.sum(case((Order.direction == 'buy', Order.volume), else_=0)).label('buy_volume'),
					func.sum(case((Order.direction == 'sell', Order.volume), else_=0)).label('sell_volume'),
					func.sum(case((Order.direction == 'buy', Order.price * Order.volume), else_=0)).label('buy_amount'),
					func.sum(case((Order.direction == 'sell', Order.price * Order.volume), else_=0)).label(
						'sell_amount')
				)
				.where(and_(*filters))
				.group_by(func.date(Order.submitted_at))
				.order_by(desc(func.date(Order.submitted_at)))
			)

			result = await self.session.execute(query)
			rows = result.all()

			summary = []
			for row in rows:
				summary.append({
					'order_date': row.order_date,
					'order_count': row.order_count or 0,
					'buy_volume': row.buy_volume or 0,
					'sell_volume': row.sell_volume or 0,
					'buy_amount': float(row.buy_amount) if row.buy_amount else 0,
					'sell_amount': float(row.sell_amount) if row.sell_amount else 0,
					'net_volume': (row.buy_volume or 0) - (row.sell_volume or 0),
					'net_amount': float((row.buy_amount or 0) - (row.sell_amount or 0))
				})

			return summary

		except Exception as e:
			raise RepositoryError(f"获取按日期订单汇总失败: {str(e)}")

	async def get_order_summary_by_stock (
			self,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			user_id: Optional[str] = None,
			top_n: int = 20
	) -> List[Dict[str, Any]]:
		"""
		按股票汇总订单统计

		Args:
			start_date: 开始时间
			end_date: 结束时间
			user_id: 用户ID过滤
			top_n: 返回前N个

		Returns:
			按股票汇总的订单统计列表
		"""
		try:
			filters = []

			if user_id:
				filters.append(Order.user_id == user_id)
			if start_date:
				filters.append(Order.submitted_at >= start_date)
			if end_date:
				filters.append(Order.submitted_at <= end_date)

			where_clause = and_(*filters) if filters else True

			query = (
				select(
					Order.ts_code,
					func.count(Order.order_id).label('order_count'),
					func.sum(Order.volume).label('total_volume'),
					func.sum(Order.price * Order.volume).label('total_amount'),
					func.avg(Order.price).label('avg_price')
				)
				.where(where_clause)
				.group_by(Order.ts_code)
				.order_by(desc(func.sum(Order.price * Order.volume)))
				.limit(top_n)
			)

			result = await self.session.execute(query)
			rows = result.all()

			summary = []
			for row in rows:
				summary.append({
					'ts_code': row.ts_code,
					'order_count': row.order_count or 0,
					'total_volume': row.total_volume or 0,
					'total_amount': float(row.total_amount) if row.total_amount else 0,
					'avg_price': float(row.avg_price) if row.avg_price else 0
				})

			return summary

		except Exception as e:
			raise RepositoryError(f"获取按股票订单汇总失败: {str(e)}")

	# ==================== 高级查询方法 ====================

	async def get_orders_with_trades (
			self,
			order_ids: List[str],
			skip: int = 0,
			limit: int = 100
	) -> List[Dict[str, Any]]:
		"""
		获取订单及其成交记录

		Args:
			order_ids: 订单ID列表
			skip: 跳过记录数
			limit: 限制记录数

		Returns:
			订单及其成交记录列表
		"""
		try:
			if not order_ids:
				return []

			# 使用JOIN查询订单和成交记录
			query = (
				select(Order, Trade)
				.join(Trade, Order.order_id == Trade.order_id, isouter=True)
				.where(Order.order_id.in_(order_ids))
				.order_by(desc(Order.submitted_at), asc(Trade.trade_time))
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			rows = result.all()

			# 组织结果
			orders_dict = {}
			for order, trade in rows:
				if order.order_id not in orders_dict:
					orders_dict[order.order_id] = {
						'order': order,
						'trades': []
					}
				if trade:
					orders_dict[order.order_id]['trades'].append(trade)

			return list(orders_dict.values())

		except Exception as e:
			raise RepositoryError(f"获取订单及成交记录失败: {str(e)}")

	async def get_order_with_details (
			self,
			order_id: str
	) -> Optional[Dict[str, Any]]:
		"""
		获取订单详情（包含关联信息）

		Args:
			order_id: 订单ID

		Returns:
			订单详情字典或None
		"""
		try:
			# 获取订单及关联的用户、账户、策略信息
			query = (
				select(Order, SysUser, Account, Strategy)
				.join(SysUser, Order.user_id == SysUser.id)
				.join(Account, Order.account_id == Account.id)
				.outerjoin(Strategy, Order.strategy_id == Strategy.id)
				.where(Order.order_id == order_id)
			)

			result = await self.session.execute(query)
			row = result.first()

			if not row:
				return None

			order, user, account, strategy = row

			# 获取成交记录
			trades = await self.session.execute(
				select(Trade)
				.where(Trade.order_id == order_id)
				.order_by(asc(Trade.trade_time))
			)

			return {
				'order': order,
				'user': user,
				'account': account,
				'strategy': strategy,
				'trades': trades.scalars().all()
			}

		except Exception as e:
			raise RepositoryError(f"获取订单详情失败: {str(e)}")

	async def search_orders (
			self,
			query_params: Dict[str, Any],
			pagination: PaginationParams
	) -> PaginationResult[Order]:
		"""
		搜索订单

		Args:
			query_params: 查询参数
			pagination: 分页参数

		Returns:
			分页结果
		"""
		try:
			filters = []

			# 构建过滤条件
			if 'user_id' in query_params:
				filters.append(Order.user_id == query_params['user_id'])
			if 'account_id' in query_params:
				filters.append(Order.account_id == query_params['account_id'])
			if 'strategy_id' in query_params:
				filters.append(Order.strategy_id == query_params['strategy_id'])
			if 'ts_code' in query_params:
				filters.append(Order.ts_code == query_params['ts_code'])
			if 'status' in query_params:
				filters.append(Order.status == query_params['status'])
			if 'direction' in query_params:
				filters.append(Order.direction == query_params['direction'])
			if 'order_type' in query_params:
				filters.append(Order.order_type == query_params['order_type'])

			# 时间范围
			if 'start_time' in query_params:
				filters.append(Order.submitted_at >= query_params['start_time'])
			if 'end_time' in query_params:
				filters.append(Order.submitted_at <= query_params['end_time'])

			# 价格范围
			if 'min_price' in query_params:
				filters.append(Order.price >= query_params['min_price'])
			if 'max_price' in query_params:
				filters.append(Order.price <= query_params['max_price'])

			# 数量范围
			if 'min_volume' in query_params:
				filters.append(Order.volume >= query_params['min_volume'])
			if 'max_volume' in query_params:
				filters.append(Order.volume <= query_params['max_volume'])

			# 执行分页查询
			return await self.paginate(
				pagination=pagination,
				filters=[FilterCondition(field=field, operator=FilterOperator.EQ, value=value)
				         for field, value in query_params.items()
				         if hasattr(Order, field)],
				sorts=[SortCondition(field="submitted_at", descending=True)]
			)

		except Exception as e:
			raise RepositoryError(f"搜索订单失败: {str(e)}")

	# ==================== 批量操作方法 ====================

	async def batch_update_status (
			self,
			order_ids: List[str],
			status: str,
			update_time: Optional[datetime] = None
	) -> int:
		"""
		批量更新订单状态

		Args:
			order_ids: 订单ID列表
			status: 新状态
			update_time: 更新时间

		Returns:
			更新的记录数
		"""
		try:
			if not order_ids:
				return 0

			update_data: Dict[str, Any] = {'status': status}
			if update_time:
				update_data['updated_at'] = update_time
			else:
				update_data['updated_at'] = datetime.now()

			# 如果是成交状态，设置成交时间
			if status == 'filled':
				update_data['filled_at'] = update_data['updated_at']
			# 如果是取消状态，设置取消时间
			elif status == 'cancelled':
				update_data['cancelled_at'] = update_data['updated_at']

			query = (
				update(self.model)
				.where(self.model.order_id.in_(order_ids))
				.values(**update_data)
			)

			result = await self.session.execute(query)
			return result.rowcount or 0

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"批量更新订单状态失败: {str(e)}")

	async def batch_update_filled_info (
			self,
			order_updates: List[Dict[str, Any]]
	) -> int:
		"""
		批量更新订单成交信息 — v2.4: 单条 SQL 批量更新，消除 N+1

		Args:
			order_updates: 订单更新列表，每个元素包含order_id, filled_volume, filled_amount, avg_price

		Returns:
			更新的记录数
		"""
		try:
			if not order_updates:
				return 0

			from sqlalchemy import case, select
			now = datetime.now()

			# 提取所有 order_id 并做有效性过滤
			valid_updates = [u for u in order_updates if u.get('order_id')]
			if not valid_updates:
				return 0
			order_ids = [u['order_id'] for u in valid_updates]

			# 第一步：批量查询订单原始成交量（一次 SQL）
			orders_map = {}
			stmt = select(self.model).where(self.model.order_id.in_(order_ids))
			result = await self.session.execute(stmt)
			for row in result.scalars():
				orders_map[row.order_id] = row

			# 第二步：构建批量 UPDATE 的 CASE WHEN 表达式
			status_case_data = {}
			filled_at_case_data = {}
			volume_case_data = {}
			amount_case_data = {}
			price_case_data = {}

			for u in valid_updates:
				oid = u['order_id']
				filled_vol = u.get('filled_volume', 0)
				order = orders_map.get(oid)

				# 根据原始成交量判断状态
				if order and order.volume == filled_vol:
					status_case_data[oid] = 'filled'
					filled_at_case_data[oid] = now
				elif order and filled_vol > 0:
					status_case_data[oid] = 'partial_filled'

				volume_case_data[oid] = filled_vol
				amount_case_data[oid] = u.get('filled_amount', 0)
				if u.get('avg_price') is not None:
					price_case_data[oid] = u['avg_price']

			# 第三步：单条 SQL 批量 UPDATE
			values = {'updated_at': now}
			if status_case_data:
				values['status'] = case(status_case_data, value=self.model.order_id)
			if filled_at_case_data:
				values['filled_at'] = case(filled_at_case_data, value=self.model.order_id)
			if volume_case_data:
				values['filled_volume'] = case(volume_case_data, value=self.model.order_id)
			if amount_case_data:
				values['filled_amount'] = case(amount_case_data, value=self.model.order_id)
			if price_case_data:
				values['avg_price'] = case(price_case_data, value=self.model.order_id)

			stmt = (
				update(self.model)
				.where(self.model.order_id.in_(order_ids))
				.values(**values)
			)
			result = await self.session.execute(stmt)
			return result.rowcount or 0

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"批量更新订单成交信息失败: {str(e)}")

	# ==================== 辅助方法 ====================

	@staticmethod
	def _build_order_by (order_by: str) -> List:
		"""
		构建排序子句

		Args:
			order_by: 排序字符串，格式：field_[asc/desc]

		Returns:
			排序子句列表
		"""
		order_mappings = {
			'submitted_at_asc': [asc(Order.submitted_at)],
			'submitted_at_desc': [desc(Order.submitted_at)],
			'price_asc': [asc(Order.price)],
			'price_desc': [desc(Order.price)],
			'volume_asc': [asc(Order.volume)],
			'volume_desc': [desc(Order.volume)],
			'status_asc': [asc(Order.status)],
			'status_desc': [desc(Order.status)],
		}

		return order_mappings.get(order_by, [desc(Order.submitted_at)])

	async def get_order_summary (self) -> Dict[str, Any]:
		"""
		获取订单数据摘要

		Returns:
			订单数据摘要字典
		"""
		try:
			# 总订单数
			total_orders = await self.count()

			# 今日订单数
			today = datetime.now().date()
			today_query = select(func.count()).select_from(Order).where(
				and_(
					Order.submitted_at >= today,
					Order.submitted_at < today + timedelta(days=1)
				)
			)
			today_result = await self.session.execute(today_query)
			today_orders = today_result.scalar() or 0

			# 活动订单数
			active_query = select(func.count()).select_from(Order).where(
				Order.status.in_(['submitted', 'partial_filled'])
			)
			active_result = await self.session.execute(active_query)
			active_orders = active_result.scalar() or 0

			# 涉及用户数
			user_count = await self.session.execute(
				select(func.count(func.distinct(Order.user_id)))
			)
			user_count_value = user_count.scalar() or 0

			# 涉及账户数
			account_count = await self.session.execute(
				select(func.count(func.distinct(Order.account_id)))
			)
			account_count_value = account_count.scalar() or 0

			# 涉及策略数
			strategy_count = await self.session.execute(
				select(func.count(func.distinct(Order.strategy_id)))
				.where(Order.strategy_id.isnot(None))
			)
			strategy_count_value = strategy_count.scalar() or 0

			# 涉及股票数
			stock_count = await self.session.execute(
				select(func.count(func.distinct(Order.ts_code)))
			)
			stock_count_value = stock_count.scalar() or 0

			# 订单总额统计
			amount_stats = await self.session.execute(
				select(
					func.sum(case((Order.direction == 'buy', Order.price * Order.volume), else_=0)).label('buy_amount'),
					func.sum(case((Order.direction == 'sell', Order.price * Order.volume), else_=0)).label(
						'sell_amount')
				)
			)

			amount_row = amount_stats.first()
			amount_dict = {
				'buy_amount': float(amount_row[0]) if amount_row[0] else 0,
				'sell_amount': float(amount_row[1]) if amount_row[1] else 0,
				'net_amount': float((amount_row[0] or 0) - (amount_row[1] or 0))
			}

			# 日期范围
			date_range = await self.session.execute(
				select(
					func.min(Order.submitted_at),
					func.max(Order.submitted_at)
				)
			)
			min_time, max_time = date_range.first()

			return {
				'total_orders': total_orders,
				'today_orders': today_orders,
				'active_orders': active_orders,
				'user_count': user_count_value,
				'account_count': account_count_value,
				'strategy_count': strategy_count_value,
				'stock_count': stock_count_value,
				'amount_stats': amount_dict,
				'date_range': {
					'min_time': min_time,
					'max_time': max_time
				}
			}

		except Exception as e:
			raise RepositoryError(f"获取订单摘要失败: {str(e)}")


class RepositoryError(Exception):
	"""Repository异常基类"""

	def __init__ (self, message: str, code: str = "ORDER_REPOSITORY_ERROR"):
		"""
		初始化异常

		Args:
			message: 错误信息
			code: 错误码
		"""
		self.message = message
		self.code = code
		super().__init__(self.message)