# -*- coding: utf-8 -*-
"""
信号数据仓库 - 交易信号数据访问
继承自BaseRepository，提供策略交易信号的CRUD操作和业务查询

设计原则：
1. 纯数据访问：只做CRUD，不包含业务逻辑
2. 统一接口：继承BaseRepository，提供标准数据访问方法
3. 异步支持：完全异步化设计，支持高并发访问
4. 类型安全：使用SQLAlchemy模型确保类型一致性

位置：shared/database/repositories/strategy/signal/signal_repository.py
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, asc, text, distinct
from sqlalchemy.orm import joinedload

from quant_server.shared.database.repositories.base import BaseRepository, RepositoryError
from quant_server.shared.database.models.business_models import Signal


class SignalRepository(BaseRepository[Signal]):
	"""
	交易信号数据仓库
	继承BaseRepository，提供Signal模型的专用数据访问方法
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化信号仓库

		Args:
			session: 数据库会话，提供数据访问上下文
		"""
		super().__init__(session, Signal)

	# ==================== 专用查询方法 ====================

	async def get_by_strategy (
			self,
			strategy_id: str,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			signal_type: Optional[str] = None,
			ts_code: Optional[str] = None,
			skip: int = 0,
			limit: int = 100,
			order_by_desc: bool = True
	) -> List[Signal]:
		"""
		根据策略ID获取交易信号

		Args:
			strategy_id: 策略ID
			start_time: 开始时间（可选）
			end_time: 结束时间（可选）
			signal_type: 信号类型：buy/sell/hold（可选）
			ts_code: 股票代码（可选）
			skip: 跳过的记录数
			limit: 返回的最大记录数
			order_by_desc: 是否按时间降序排列

		Returns:
			交易信号列表

		Raises:
			RepositoryError: 查询失败时抛出
		"""
		try:
			# 构建查询条件
			filters = {"strategy_id": strategy_id}

			# 构建时间范围条件
			time_filters = []
			if start_time:
				time_filters.append(Signal.signal_time >= start_time)
			if end_time:
				time_filters.append(Signal.signal_time <= end_time)

			# 构建额外条件
			if signal_type:
				filters["signal_type"] = signal_type
			if ts_code:
				filters["ts_code"] = ts_code

			# 执行查询
			query = self.build_query()

			# 应用基本过滤条件
			for attr, value in filters.items():
				if hasattr(Signal, attr):
					query = query.where(getattr(Signal, attr) == value)

			# 应用时间过滤条件
			if time_filters:
				query = query.where(and_(*time_filters))

			# 应用排序
			order_by_field = desc(Signal.signal_time) if order_by_desc else asc(Signal.signal_time)
			query = query.order_by(order_by_field)

			# 应用分页
			query = query.offset(skip).limit(limit)

			return await self.execute_query(query)

		except Exception as e:
			raise RepositoryError(f"按策略查询信号失败: {str(e)}")

	async def get_by_stock (
			self,
			ts_code: str,
			strategy_id: Optional[str] = None,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			signal_type: Optional[str] = None,
			skip: int = 0,
			limit: int = 100
	) -> List[Signal]:
		"""
		根据股票代码获取交易信号

		Args:
			ts_code: 股票代码
			strategy_id: 策略ID（可选）
			start_time: 开始时间（可选）
			end_time: 结束时间（可选）
			signal_type: 信号类型（可选）
			skip: 跳过的记录数
			limit: 返回的最大记录数

		Returns:
			交易信号列表
		"""
		try:
			# 构建查询条件
			filters = {"ts_code": ts_code}
			if strategy_id:
				filters["strategy_id"] = strategy_id
			if signal_type:
				filters["signal_type"] = signal_type

			# 构建时间范围条件
			time_filters = []
			if start_time:
				time_filters.append(Signal.signal_time >= start_time)
			if end_time:
				time_filters.append(Signal.signal_time <= end_time)

			# 执行查询
			query = self.build_query()

			# 应用基本过滤条件
			for attr, value in filters.items():
				if hasattr(Signal, attr):
					query = query.where(getattr(Signal, attr) == value)

			# 应用时间过滤条件
			if time_filters:
				query = query.where(and_(*time_filters))

			# 应用排序和分页
			query = query.order_by(desc(Signal.signal_time)).offset(skip).limit(limit)

			return await self.execute_query(query)

		except Exception as e:
			raise RepositoryError(f"按股票查询信号失败: {str(e)}")

	async def get_by_time_range (
			self,
			start_time: datetime,
			end_time: datetime,
			strategy_ids: Optional[List[str]] = None,
			ts_codes: Optional[List[str]] = None,
			signal_types: Optional[List[str]] = None,
			min_strength: Optional[float] = None
	) -> List[Signal]:
		"""
		根据时间范围获取交易信号

		Args:
			start_time: 开始时间
			end_time: 结束时间
			strategy_ids: 策略ID列表（可选）
			ts_codes: 股票代码列表（可选）
			signal_types: 信号类型列表（可选）
			min_strength: 最小信号强度（可选）

		Returns:
			交易信号列表
		"""
		try:
			# 构建基础查询
			query = self.build_query().where(
				and_(
					Signal.signal_time >= start_time,
					Signal.signal_time <= end_time
				)
			)

			# 添加策略过滤条件
			if strategy_ids:
				query = query.where(Signal.strategy_id.in_(strategy_ids))

			# 添加股票过滤条件
			if ts_codes:
				query = query.where(Signal.ts_code.in_(ts_codes))

			# 添加信号类型过滤条件
			if signal_types:
				query = query.where(Signal.signal_type.in_(signal_types))

			# 添加信号强度过滤条件
			if min_strength is not None:
				query = query.where(Signal.strength >= min_strength)

			# 按时间排序
			query = query.order_by(asc(Signal.signal_time))

			return await self.execute_query(query)

		except Exception as e:
			raise RepositoryError(f"按时间范围查询信号失败: {str(e)}")

	async def get_latest_signals (
			self,
			strategy_id: Optional[str] = None,
			ts_code: Optional[str] = None,
			signal_type: Optional[str] = None,
			hours: int = 24,
			limit: int = 100
	) -> List[Signal]:
		"""
		获取最近N小时的交易信号

		Args:
			strategy_id: 策略ID（可选）
			ts_code: 股票代码（可选）
			signal_type: 信号类型（可选）
			hours: 小时数
			limit: 最大返回记录数

		Returns:
			交易信号列表
		"""
		try:
			cutoff_time = datetime.now() - timedelta(hours=hours)

			filters = {"signal_time": (">=", cutoff_time)}
			if strategy_id:
				filters["strategy_id"] = strategy_id
			if ts_code:
				filters["ts_code"] = ts_code
			if signal_type:
				filters["signal_type"] = signal_type

			return await self.get_many(
				skip=0,
				limit=limit,
				order_by="signal_time DESC",
				**filters
			)

		except Exception as e:
			raise RepositoryError(f"获取最新信号失败: {str(e)}")

	async def get_today_signals (
			self,
			strategy_id: Optional[str] = None,
			ts_code: Optional[str] = None
	) -> List[Signal]:
		"""
		获取今日交易信号

		Args:
			strategy_id: 策略ID（可选）
			ts_code: 股票代码（可选）

		Returns:
			今日交易信号列表
		"""
		try:
			today = datetime.now().date()
			tomorrow = today + timedelta(days=1)

			filters = {
				"signal_time": (">=", today),
				"signal_time": ("<", tomorrow)
			}
			if strategy_id:
				filters["strategy_id"] = strategy_id
			if ts_code:
				filters["ts_code"] = ts_code

			return await self.get_many(
				skip=0,
				limit=1000,
				order_by="signal_time DESC",
				**filters
			)

		except Exception as e:
			raise RepositoryError(f"获取今日信号失败: {str(e)}")

	async def get_signal_statistics (
			self,
			strategy_id: Optional[str] = None,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None
	) -> Dict[str, Any]:
		"""
		获取交易信号统计信息

		Args:
			strategy_id: 策略ID（可选）
			start_time: 开始时间（可选）
			end_time: 结束时间（可选）

		Returns:
			统计信息字典，包含：
			- total_count: 总信号数
			- by_type: 按类型统计
			- by_strategy: 按策略统计
			- by_stock: 按股票统计
			- strength_stats: 信号强度统计
		"""
		try:
			# 构建基础查询条件
			conditions = []
			if strategy_id:
				conditions.append(Signal.strategy_id == strategy_id)
			if start_time:
				conditions.append(Signal.signal_time >= start_time)
			if end_time:
				conditions.append(Signal.signal_time <= end_time)

			where_clause = and_(*conditions) if conditions else True

			# 统计总信号数
			total_query = select(func.count()).select_from(Signal).where(where_clause)
			total_result = await self.session.execute(total_query)
			total_count = total_result.scalar() or 0

			# 按信号类型统计
			type_query = (
				select(Signal.signal_type, func.count().label("count"))
				.where(where_clause)
				.group_by(Signal.signal_type)
				.order_by(func.count().desc())
			)
			type_result = await self.session.execute(type_query)
			type_stats = {row[0]: row[1] for row in type_result.all()}

			# 按策略统计（如果未指定策略）
			strategy_stats = []
			if not strategy_id:
				strategy_query = (
					select(Signal.strategy_id, func.count().label("count"))
					.where(where_clause)
					.group_by(Signal.strategy_id)
					.order_by(func.count().desc())
					.limit(10)
				)
				strategy_result = await self.session.execute(strategy_query)
				strategy_stats = [
					{"strategy_id": row[0], "count": row[1]}
					for row in strategy_result.all()
				]

			# 按股票统计
			stock_query = (
				select(Signal.ts_code, func.count().label("count"))
				.where(where_clause)
				.group_by(Signal.ts_code)
				.order_by(func.count().desc())
				.limit(10)
			)
			stock_result = await self.session.execute(stock_query)
			stock_stats = [
				{"ts_code": row[0], "count": row[1]}
				for row in stock_result.all()
			]

			# 信号强度统计
			strength_query = (
				select(
					func.avg(Signal.strength).label("avg_strength"),
					func.min(Signal.strength).label("min_strength"),
					func.max(Signal.strength).label("max_strength")
				)
				.where(and_(where_clause, Signal.strength.isnot(None)))
			)
			strength_result = await self.session.execute(strength_query)
			strength_row = strength_result.first()

			strength_stats = {
				"avg_strength": float(strength_row.avg_strength) if strength_row.avg_strength else 0,
				"min_strength": float(strength_row.min_strength) if strength_row.min_strength else 0,
				"max_strength": float(strength_row.max_strength) if strength_row.max_strength else 0
			}

			return {
				"total_count": total_count,
				"by_type": type_stats,
				"by_strategy": strategy_stats,
				"by_stock": stock_stats,
				"strength_stats": strength_stats,
				"time_range": {
					"start_time": start_time,
					"end_time": end_time
				}
			}

		except Exception as e:
			raise RepositoryError(f"获取信号统计失败: {str(e)}")

	async def get_strong_signals (
			self,
			min_strength: float = 0.7,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			limit: int = 100
	) -> List[Signal]:
		"""
		获取强信号（信号强度大于阈值）

		Args:
			min_strength: 最小信号强度阈值
			start_time: 开始时间（可选）
			end_time: 结束时间（可选）
			limit: 最大返回记录数

		Returns:
			强信号列表
		"""
		try:
			filters = {"strength": (">=", min_strength)}
			if start_time:
				filters["signal_time"] = (">=", start_time)
			if end_time:
				filters["signal_time"] = ("<=", end_time)

			return await self.get_many(
				skip=0,
				limit=limit,
				order_by="strength DESC",
				**filters
			)

		except Exception as e:
			raise RepositoryError(f"获取强信号失败: {str(e)}")

	async def get_signal_trend (
			self,
			strategy_id: Optional[str] = None,
			days: int = 30
	) -> List[Dict[str, Any]]:
		"""
		获取信号生成趋势

		Args:
			strategy_id: 策略ID（可选）
			days: 天数

		Returns:
			趋势数据列表，每个元素包含：
			- date: 日期
			- total: 总信号数
			- by_type: 按类型统计
		"""
		try:
			end_date = datetime.now().date()
			start_date = end_date - timedelta(days=days - 1)

			# 构建基础查询
			query = (
				select(
					func.date(Signal.signal_time).label("date"),
					Signal.signal_type,
					func.count().label("count")
				)
				.where(
					and_(
						Signal.signal_time >= start_date,
						Signal.signal_time < end_date + timedelta(days=1)
					)
				)
				.group_by(func.date(Signal.signal_time), Signal.signal_type)
				.order_by(func.date(Signal.signal_time).asc())
			)

			# 添加策略过滤条件
			if strategy_id:
				query = query.where(Signal.strategy_id == strategy_id)

			# 执行查询
			result = await self.session.execute(query)
			rows = result.all()

			# 按日期组织数据
			date_dict = {}
			for row in rows:
				date_str = row.date.strftime('%Y-%m-%d')
				if date_str not in date_dict:
					date_dict[date_str] = {
						'date': row.date,
						'total': 0,
						'by_type': {}
					}

				date_dict[date_str]['by_type'][row.signal_type] = row.count
				date_dict[date_str]['total'] += row.count

			# 转换为有序列表
			trend_list = []
			current_date = start_date
			while current_date <= end_date:
				date_str = current_date.strftime('%Y-%m-%d')
				if date_str in date_dict:
					trend_list.append(date_dict[date_str])
				else:
					trend_list.append({
						'date': current_date,
						'total': 0,
						'by_type': {}
					})
				current_date += timedelta(days=1)

			return trend_list

		except Exception as e:
			raise RepositoryError(f"获取信号趋势失败: {str(e)}")

	async def get_signals_with_price (
			self,
			strategy_id: str,
			ts_code: str,
			start_time: datetime,
			end_time: datetime
	) -> List[Dict[str, Any]]:
		"""
		获取信号及其对应的价格信息（需要关联行情数据）

		Args:
			strategy_id: 策略ID
			ts_code: 股票代码
			start_time: 开始时间
			end_time: 结束时间

		Returns:
			信号数据列表，每个元素包含：
			- 信号基本信息
			- 关联的价格信息（TODO: 需要实现行情数据关联）
		"""
		try:
			# 获取信号数据
			signals = await self.get_by_time_range(
				start_time=start_time,
				end_time=end_time,
				strategy_ids=[strategy_id],
				ts_codes=[ts_code]
			)

			# 转换为字典格式
			signal_list = []
			for signal in signals:
				signal_data = {
					'id': signal.id,
					'strategy_id': signal.strategy_id,
					'ts_code': signal.ts_code,
					'signal_type': signal.signal_type,
					'signal_time': signal.signal_time,
					'price': float(signal.price) if signal.price else None,
					'strength': float(signal.strength) if signal.strength else 0,
					'reason': signal.reason,
					'created_at': signal.created_at
				}

				# TODO: 这里可以添加关联查询价格信息的逻辑
				# 例如：查询信号发出时的最新行情价格
				# signal_data['market_price'] = await market_service.get_price_at_time(ts_code, signal.signal_time)

				signal_list.append(signal_data)

			return signal_list

		except Exception as e:
			raise RepositoryError(f"获取信号价格信息失败: {str(e)}")

	async def get_signal_accuracy (
			self,
			strategy_id: str,
			days: int = 30
	) -> Dict[str, Any]:
		"""
		获取信号准确率统计（需要关联交易数据）

		Args:
			strategy_id: 策略ID
			days: 统计天数

		Returns:
			准确率统计信息，包含：
			- strategy_id: 策略ID
			- total_signals: 总信号数
			- accuracy_rate: 准确率
			- profitable_signals: 盈利信号数
			- unprofitable_signals: 亏损信号数
		"""
		try:
			end_date = datetime.now().date()
			start_date = end_date - timedelta(days=days - 1)

			# 获取该策略在指定时间范围内的信号
			signals = await self.get_by_strategy(
				strategy_id=strategy_id,
				start_time=start_date,
				end_time=end_date + timedelta(days=1)
			)

			total_signals = len(signals)

			if total_signals == 0:
				return {
					'strategy_id': strategy_id,
					'total_signals': 0,
					'accuracy_rate': 0,
					'profitable_signals': 0,
					'unprofitable_signals': 0,
					'start_date': start_date,
					'end_date': end_date
				}

			# TODO: 这里需要实现信号准确率分析逻辑
			# 需要关联交易记录来判断信号是否盈利
			# 暂时返回基础统计信息

			profitable_count = 0
			unprofitable_count = 0

			return {
				'strategy_id': strategy_id,
				'total_signals': total_signals,
				'accuracy_rate': profitable_count / total_signals if total_signals > 0 else 0,
				'profitable_signals': profitable_count,
				'unprofitable_signals': unprofitable_count,
				'start_date': start_date,
				'end_date': end_date
			}

		except Exception as e:
			raise RepositoryError(f"获取信号准确率失败: {str(e)}")

	async def get_signal_summary (self) -> Dict[str, Any]:
		"""
		获取交易信号数据摘要

		Returns:
			摘要信息，包含：
			- total_count: 总信号数
			- today_count: 今日信号数
			- strategy_count: 涉及策略数
			- stock_count: 涉及股票数
			- type_stats: 信号类型分布
			- recent_strategies: 最近活跃的策略
		"""
		try:
			# 总信号数
			total_count = await self.count()

			# 今日信号数
			today = datetime.now().date()
			tomorrow = today + timedelta(days=1)
			today_count = await self.count(
				signal_time=(">=", today)
			)

			# 涉及策略数
			strategy_count_query = select(func.count(func.distinct(Signal.strategy_id)))
			strategy_count_result = await self.session.execute(strategy_count_query)
			strategy_count = strategy_count_result.scalar() or 0

			# 涉及股票数
			stock_count_query = select(func.count(func.distinct(Signal.ts_code)))
			stock_count_result = await self.session.execute(stock_count_query)
			stock_count = stock_count_result.scalar() or 0

			# 信号类型分布
			type_dist_query = (
				select(Signal.signal_type, func.count().label('count'))
				.group_by(Signal.signal_type)
				.order_by(func.count().desc())
			)
			type_dist_result = await self.session.execute(type_dist_query)
			type_stats = {row[0]: row[1] for row in type_dist_result.all()}

			# 最近活跃的策略（最近7天有信号的策略）
			recent_days = 7
			cutoff_time = datetime.now() - timedelta(days=recent_days)

			recent_strategies_query = (
				select(
					Signal.strategy_id,
					func.max(Signal.signal_time).label('last_signal_time'),
					func.count().label('signal_count')
				)
				.where(Signal.signal_time >= cutoff_time)
				.group_by(Signal.strategy_id)
				.order_by(func.max(Signal.signal_time).desc())
				.limit(10)
			)
			recent_strategies_result = await self.session.execute(recent_strategies_query)

			recent_strategies = [
				{
					'strategy_id': row.strategy_id,
					'last_signal_time': row.last_signal_time,
					'signal_count': row.signal_count
				}
				for row in recent_strategies_result.all()
			]

			return {
				'total_count': total_count,
				'today_count': today_count,
				'strategy_count': strategy_count,
				'stock_count': stock_count,
				'type_stats': type_stats,
				'recent_strategies': recent_strategies,
				'summary_time': datetime.now()
			}

		except Exception as e:
			raise RepositoryError(f"获取信号摘要失败: {str(e)}")

	async def delete_old_signals (
			self,
			days: int = 365
	) -> int:
		"""
		删除旧信号记录

		Args:
			days: 保留天数，超过此天数的记录将被删除

		Returns:
			删除的记录数
		"""
		try:
			cutoff_time = datetime.now() - timedelta(days=days)

			# 执行删除
			deleted_count = await self.delete_by(
				signal_time=("<", cutoff_time)
			)

			return deleted_count

		except Exception as e:
			raise RepositoryError(f"删除旧信号失败: {str(e)}")

	# ==================== 批量操作扩展 ====================

	async def batch_create_signals (
			self,
			signal_data_list: List[Dict[str, Any]]
	) -> List[Signal]:
		"""
		批量创建交易信号记录（优化版）

		Args:
			signal_data_list: 信号数据列表

		Returns:
			创建的信号记录列表
		"""
		try:
			# 添加时间戳
			now = datetime.now()
			for data in signal_data_list:
				data['created_at'] = data.get('created_at', now)

			return await self.batch_create(signal_data_list)

		except Exception as e:
			raise RepositoryError(f"批量创建信号失败: {str(e)}")

	async def batch_upsert_signals (
			self,
			signal_data_list: List[Dict[str, Any]],
			match_fields: List[str] = ['strategy_id', 'ts_code', 'signal_time']
	) -> List[Signal]:
		"""
		批量插入或更新交易信号记录

		Args:
			signal_data_list: 信号数据列表
			match_fields: 匹配字段，用于检查记录是否存在

		Returns:
			插入或更新的信号记录列表
		"""
		try:
			return await self.batch_upsert(match_fields, signal_data_list)

		except Exception as e:
			raise RepositoryError(f"批量插入或更新信号失败: {str(e)}")