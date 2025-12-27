# -*- coding: utf-8 -*-
"""
交易信号数据仓库
提供策略交易信号数据的统一访问接口
位置：shared/database/repositories/signal_repo.py
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, between

from .base import BaseRepository
from quant_server.shared.database.models.business_models import Signal


class SignalRepository:
	"""交易信号数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.base_repo = BaseRepository(session, Signal)

	# ==================== 基础CRUD操作 ====================

	async def create (self, data: Dict[str, Any]) -> Signal:
		"""创建交易信号记录"""
		return await self.base_repo.create(data)

	async def get (self, id: int) -> Optional[Signal]:
		"""根据ID获取交易信号记录"""
		return await self.base_repo.get(id)

	async def update (self, id: int, data: Dict[str, Any]) -> Optional[Signal]:
		"""更新交易信号记录"""
		return await self.base_repo.update(id, data)

	async def delete (self, id: int, soft: bool = True) -> bool:
		"""删除交易信号记录"""
		return await self.base_repo.delete(id, soft)

	async def get_one (self, *filters) -> Optional[Signal]:
		"""根据条件获取单个交易信号记录"""
		return await self.base_repo.get_one(*filters)

	async def get_many (
			self,
			*filters,
			skip: int = 0,
			limit: int = 100,
			order_by: str = None
	) -> List[Signal]:
		"""根据条件获取多个交易信号记录"""
		return await self.base_repo.get_many(*filters, skip=skip, limit=limit, order_by=order_by)

	async def count (self, *filters) -> int:
		"""统计交易信号记录数"""
		return await self.base_repo.count(*filters)

	# ==================== 业务查询方法 ====================

	async def get_by_strategy (
			self,
			strategy_id: str,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			signal_type: Optional[str] = None,
			limit: int = 100
	) -> List[Signal]:
		"""根据策略ID获取交易信号"""
		filters = [Signal.strategy_id == strategy_id]

		if start_time:
			filters.append(Signal.signal_time >= start_time)
		if end_time:
			filters.append(Signal.signal_time <= end_time)
		if signal_type:
			filters.append(Signal.signal_type == signal_type)

		return await self.get_many(
			*filters,
			limit=limit,
			order_by=Signal.signal_time.desc()
		)

	async def get_by_stock (
			self,
			ts_code: str,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			signal_type: Optional[str] = None,
			limit: int = 100
	) -> List[Signal]:
		"""根据股票代码获取交易信号"""
		filters = [Signal.ts_code == ts_code]

		if start_time:
			filters.append(Signal.signal_time >= start_time)
		if end_time:
			filters.append(Signal.signal_time <= end_time)
		if signal_type:
			filters.append(Signal.signal_type == signal_type)

		return await self.get_many(
			*filters,
			limit=limit,
			order_by=Signal.signal_time.desc()
		)

	async def get_by_strategy_and_stock (
			self,
			strategy_id: str,
			ts_code: str,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			signal_type: Optional[str] = None
	) -> List[Signal]:
		"""根据策略和股票获取交易信号"""
		filters = [
			Signal.strategy_id == strategy_id,
			Signal.ts_code == ts_code
		]

		if start_time:
			filters.append(Signal.signal_time >= start_time)
		if end_time:
			filters.append(Signal.signal_time <= end_time)
		if signal_type:
			filters.append(Signal.signal_type == signal_type)

		return await self.get_many(
			*filters,
			order_by=Signal.signal_time.desc()
		)

	async def get_latest_signals (
			self,
			strategy_id: Optional[str] = None,
			ts_code: Optional[str] = None,
			hours: int = 24,
			limit: int = 100
	) -> List[Signal]:
		"""获取最近N小时的交易信号"""
		cutoff_time = datetime.now() - timedelta(hours=hours)

		filters = [Signal.signal_time >= cutoff_time]

		if strategy_id:
			filters.append(Signal.strategy_id == strategy_id)
		if ts_code:
			filters.append(Signal.ts_code == ts_code)

		return await self.get_many(
			*filters,
			limit=limit,
			order_by=Signal.signal_time.desc()
		)

	async def get_today_signals (
			self,
			strategy_id: Optional[str] = None,
			ts_code: Optional[str] = None
	) -> List[Signal]:
		"""获取今日交易信号"""
		today = datetime.now().date()
		tomorrow = today + timedelta(days=1)

		filters = [
			Signal.signal_time >= today,
			Signal.signal_time < tomorrow
		]

		if strategy_id:
			filters.append(Signal.strategy_id == strategy_id)
		if ts_code:
			filters.append(Signal.ts_code == ts_code)

		return await self.get_many(
			*filters,
			order_by=Signal.signal_time.desc()
		)

	async def get_signal_statistics (
			self,
			strategy_id: Optional[str] = None,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None
	) -> Dict[str, Any]:
		"""获取交易信号统计信息"""
		filters = []
		if strategy_id:
			filters.append(Signal.strategy_id == strategy_id)
		if start_time:
			filters.append(Signal.signal_time >= start_time)
		if end_time:
			filters.append(Signal.signal_time <= end_time)

		where_clause = and_(*filters) if filters else True

		# 总信号数
		total_count = await self.count(*filters) if filters else await self.count()

		# 按信号类型统计
		type_stats = await self.session.execute(
			select(
				Signal.signal_type,
				func.count(Signal.id).label('count')
			).where(
				where_clause
			).group_by(
				Signal.signal_type
			).order_by(
				func.count(Signal.id).desc()
			)
		)

		type_stats_dict = {row[0]: row[1] for row in type_stats.all()}

		# 按策略统计
		if not strategy_id:
			strategy_stats = await self.session.execute(
				select(
					Signal.strategy_id,
					func.count(Signal.id).label('count')
				).where(
					where_clause
				).group_by(
					Signal.strategy_id
				).order_by(
					func.count(Signal.id).desc()
				).limit(10)
			)

			strategy_stats_list = [
				{'strategy_id': row[0], 'count': row[1]}
				for row in strategy_stats.all()
			]
		else:
			strategy_stats_list = []

		# 按股票统计
		stock_stats = await self.session.execute(
			select(
				Signal.ts_code,
				func.count(Signal.id).label('count')
			).where(
				where_clause
			).group_by(
				Signal.ts_code
			).order_by(
				func.count(Signal.id).desc()
			).limit(10)
		)

		stock_stats_list = [
			{'ts_code': row[0], 'count': row[1]}
			for row in stock_stats.all()
		]

		# 信号强度统计
		strength_stats = await self.session.execute(
			select(
				func.avg(Signal.strength).label('avg_strength'),
				func.min(Signal.strength).label('min_strength'),
				func.max(Signal.strength).label('max_strength')
			).where(
				and_(
					where_clause,
					Signal.strength.isnot(None)
				)
			)
		)

		strength_row = strength_stats.first()
		strength_dict = {
			'avg_strength': float(strength_row[0]) if strength_row[0] else 0,
			'min_strength': float(strength_row[1]) if strength_row[1] else 0,
			'max_strength': float(strength_row[2]) if strength_row[2] else 0
		}

		return {
			'total_count': total_count,
			'type_stats': type_stats_dict,
			'strategy_stats': strategy_stats_list,
			'stock_stats': stock_stats_list,
			'strength_stats': strength_dict
		}

	async def get_signal_trend (
			self,
			strategy_id: Optional[str] = None,
			days: int = 30
	) -> List[Dict[str, Any]]:
		"""获取信号生成趋势"""
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=days - 1)

		query = select(
			func.date(Signal.signal_time).label('date'),
			Signal.signal_type,
			func.count(Signal.id).label('count')
		).where(
			and_(
				Signal.signal_time >= start_date,
				Signal.signal_time < end_date + timedelta(days=1)
			)
		)

		if strategy_id:
			query = query.where(Signal.strategy_id == strategy_id)

		query = query.group_by(
			func.date(Signal.signal_time),
			Signal.signal_type
		).order_by(
			func.date(Signal.signal_time).asc()
		)

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

		# 转换为列表
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

	async def get_strong_signals (
			self,
			min_strength: float = 0.7,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			limit: int = 100
	) -> List[Signal]:
		"""获取强信号"""
		filters = [Signal.strength >= min_strength]

		if start_time:
			filters.append(Signal.signal_time >= start_time)
		if end_time:
			filters.append(Signal.signal_time <= end_time)

		return await self.get_many(
			*filters,
			limit=limit,
			order_by=Signal.strength.desc()
		)

	async def get_signals_with_price (
			self,
			strategy_id: str,
			ts_code: str,
			start_time: datetime,
			end_time: datetime
	) -> List[Dict[str, Any]]:
		"""获取信号及其对应的价格信息（需要关联行情数据）"""
		# 这里需要关联行情表查询信号发出时的价格
		# 实际实现需要根据数据库设计调整

		# 先获取信号
		signals = await self.get_by_strategy_and_stock(
			strategy_id, ts_code, start_time, end_time
		)

		signal_list = []
		for signal in signals:
			signal_data = {
				'id': signal.id,
				'signal_time': signal.signal_time,
				'signal_type': signal.signal_type,
				'strength': float(signal.strength) if signal.strength else 0,
				'price': float(signal.price) if signal.price else None,
				'reason': signal.reason
			}

			# 这里可以添加关联查询价格信息的逻辑
			# 例如：查询信号发出时的最新行情价格

			signal_list.append(signal_data)

		return signal_list

	async def get_signal_accuracy (
			self,
			strategy_id: str,
			days: int = 30
	) -> Dict[str, Any]:
		"""获取信号准确率统计（需要关联交易数据）"""
		# 这里需要关联交易表来分析信号准确率
		# 实际实现需要根据数据库设计调整

		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=days - 1)

		# 获取该策略在指定时间范围内的信号
		signals = await self.get_by_strategy(
			strategy_id, start_date, end_date
		)

		total_signals = len(signals)
		if total_signals == 0:
			return {
				'strategy_id': strategy_id,
				'total_signals': 0,
				'accuracy_rate': 0,
				'profitable_signals': 0,
				'unprofitable_signals': 0
			}

		# 这里假设有方法可以判断信号是否盈利
		# 实际需要关联交易记录进行分析

		profitable_count = 0
		unprofitable_count = 0

		for signal in signals:
			# 判断信号是否盈利的逻辑
			# 这里只是示例，实际需要实现
			pass

		accuracy_rate = profitable_count / total_signals if total_signals > 0 else 0

		return {
			'strategy_id': strategy_id,
			'total_signals': total_signals,
			'accuracy_rate': accuracy_rate,
			'profitable_signals': profitable_count,
			'unprofitable_signals': unprofitable_count,
			'start_date': start_date,
			'end_date': end_date
		}

	async def batch_create (
			self,
			data_list: List[Dict[str, Any]]
	) -> List[Signal]:
		"""批量创建交易信号记录"""
		return await self.base_repo.batch_create(data_list)

	async def batch_upsert (
			self,
			data_list: List[Dict[str, Any]],
			match_fields: List[str] = ['strategy_id', 'ts_code', 'signal_time']
	) -> List[Signal]:
		"""批量插入或更新交易信号记录"""
		return await self.base_repo.batch_upsert(data_list, match_fields)

	async def delete_old_signals (
			self,
			days: int = 365
	) -> int:
		"""删除旧信号记录"""
		cutoff_time = datetime.now() - timedelta(days=days)

		# 获取要删除的记录
		query = select(Signal.id).where(
			Signal.signal_time < cutoff_time
		)

		result = await self.session.execute(query)
		old_signal_ids = [row[0] for row in result.all()]

		# 批量删除
		deleted_count = 0
		for signal_id in old_signal_ids:
			success = await self.delete(signal_id, soft=False)
			if success:
				deleted_count += 1

		return deleted_count

	async def get_signal_summary (self) -> Dict[str, Any]:
		"""获取交易信号数据摘要"""
		# 总信号数
		total_count = await self.count()

		# 今日信号数
		today = datetime.now().date()
		tomorrow = today + timedelta(days=1)
		today_count = await self.count(
			and_(
				Signal.signal_time >= today,
				Signal.signal_time < tomorrow
			)
		)

		# 涉及策略数
		strategy_count = await self.session.execute(
			select(func.count(func.distinct(Signal.strategy_id)))
		)
		strategy_count_value = strategy_count.scalar() or 0

		# 涉及股票数
		stock_count = await self.session.execute(
			select(func.count(func.distinct(Signal.ts_code)))
		)
		stock_count_value = stock_count.scalar() or 0

		# 信号类型分布
		type_dist = await self.session.execute(
			select(
				Signal.signal_type,
				func.count(Signal.id).label('count')
			).group_by(
				Signal.signal_type
			).order_by(
				func.count(Signal.id).desc()
			)
		)

		type_stats = {row[0]: row[1] for row in type_dist.all()}

		# 最近活跃的策略
		recent_strategies = await self.session.execute(
			select(
				Signal.strategy_id,
				func.max(Signal.signal_time).label('last_signal_time'),
				func.count(Signal.id).label('signal_count')
			).group_by(
				Signal.strategy_id
			).order_by(
				func.max(Signal.signal_time).desc()
			).limit(10)
		)

		strategy_stats = [
			{
				'strategy_id': row[0],
				'last_signal_time': row[1],
				'signal_count': row[2]
			}
			for row in recent_strategies.all()
		]

		return {
			'total_count': total_count,
			'today_count': today_count,
			'strategy_count': strategy_count_value,
			'stock_count': stock_count_value,
			'type_stats': type_stats,
			'recent_strategies': strategy_stats
		}