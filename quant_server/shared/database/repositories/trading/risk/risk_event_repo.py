# -*- coding: utf-8 -*-
"""
风险事件数据仓库
提供风险事件数据的统一访问接口（超表）
位置：shared/database/repositories/trading/risk/risk_event_repo.py
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.business_models import RiskEvent, RiskRule, Strategy, SysUser
from quant_server.shared.database.repositories.base.hyper_repository_base import HyperRepositoryBase


class RiskEventRepository(HyperRepositoryBase):
	"""风险事件数据Repository - 超表，继承HyperRepositoryBase"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, RiskEvent)

	async def get_recent_events (
			self,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None,
			rule_id: Optional[int] = None,
			event_type: Optional[str] = None,
			days: int = 7,
			limit: int = 100
	) -> List[RiskEvent]:
		"""
		获取最近的风险事件

		Args:
			user_id: 用户ID过滤
			strategy_id: 策略ID过滤
			rule_id: 规则ID过滤
			event_type: 事件类型过滤
			days: 查询天数
			limit: 返回数量限制

		Returns:
			List[RiskEvent]: 风险事件列表
		"""
		# 时间过滤
		start_date = datetime.now() - timedelta(days=days)

		conditions = [RiskEvent.created_at >= start_date]

		if user_id:
			conditions.append(RiskEvent.user_id == user_id)

		if strategy_id:
			conditions.append(RiskEvent.strategy_id == strategy_id)

		if rule_id:
			conditions.append(RiskEvent.rule_id == rule_id)

		if event_type:
			conditions.append(RiskEvent.event_type == event_type)

		return await self.get_many(
			*conditions,
			order_by=RiskEvent.created_at.desc(),
			limit=limit
		)

	async def get_events_by_user (
			self,
			user_id: str,
			limit: int = 50
	) -> List[RiskEvent]:
		"""
		获取指定用户的风险事件

		Args:
			user_id: 用户ID
			limit: 返回数量限制

		Returns:
			List[RiskEvent]: 用户的风险事件列表
		"""
		# 先获取数据，然后手动排序
		events = await self.get_many(limit=limit, user_id=user_id)
		return sorted(events, key=lambda x: x.created_at, reverse=True)

	async def get_events_by_strategy (
			self,
			strategy_id: str,
			limit: int = 50
	) -> List[RiskEvent]:
		"""
		获取指定策略的风险事件

		Args:
			strategy_id: 策略ID
			limit: 返回数量限制

		Returns:
			List[RiskEvent]: 策略的风险事件列表
		"""
		query = select(RiskEvent).where(
			RiskEvent.strategy_id == strategy_id
		).order_by(
			RiskEvent.created_at.desc()
		).limit(limit)
		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_events_by_rule (
			self,
			rule_id: int,
			limit: int = 50
	) -> List[RiskEvent]:
		"""
		获取指定规则的风险事件

		Args:
			rule_id: 规则ID
			limit: 返回数量限制

		Returns:
			List[RiskEvent]: 规则的风险事件列表
		"""
		query = select(RiskEvent).where(
			RiskEvent.rule_id == rule_id
		).order_by(
			RiskEvent.created_at.desc()
		).limit(limit)
		result = await self.session.execute(query)
		return result.scalars().all()

	async def search_events (
			self,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None,
			rule_id: Optional[int] = None,
			event_type: Optional[str] = None,
			action_taken: Optional[str] = None,
			limit: int = 100,
			offset: int = 0
	) -> Dict[str, Any]:
		"""
		搜索风险事件

		Args:
			start_date: 开始日期
			end_date: 结束日期
			user_id: 用户ID
			strategy_id: 策略ID
			rule_id: 规则ID
			event_type: 事件类型
			action_taken: 采取的行动
			limit: 每页数量
			offset: 偏移量

		Returns:
			Dict[str, Any]: 包含事件列表和总数的字典
		"""
		conditions = []

		# 时间范围过滤
		if start_date:
			conditions.append(RiskEvent.created_at >= start_date)
		if end_date:
			conditions.append(RiskEvent.created_at <= end_date)

		# 其他过滤条件
		if user_id:
			conditions.append(RiskEvent.user_id == user_id)

		if strategy_id:
			conditions.append(RiskEvent.strategy_id == strategy_id)

		if rule_id:
			conditions.append(RiskEvent.rule_id == rule_id)

		if event_type:
			conditions.append(RiskEvent.event_type == event_type)

		if action_taken:
			conditions.append(RiskEvent.action_taken == action_taken)

		# 获取总数
		count_query = select(func.count()).select_from(RiskEvent)
		if conditions:
			count_query = count_query.where(and_(*conditions))
		total_result = await self.session.execute(count_query)
		total = total_result.scalar() or 0

		# 获取分页数据
		query = select(RiskEvent)
		if conditions:
			query = query.where(and_(*conditions))
		query = query.order_by(RiskEvent.created_at.desc()).offset(offset).limit(limit)
		result = await self.session.execute(query)
		events = result.scalars().all()

		return {
			"events": events,
			"total": total,
			"offset": offset,
			"limit": limit,
			"has_more": offset + len(events) < total
		}

	async def get_event_statistics (
			self,
			start_date: datetime,
			end_date: datetime
	) -> Dict[str, Any]:
		"""
		获取风险事件统计信息

		Args:
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			Dict[str, Any]: 统计信息
		"""
		# 查询事件总数
		total_query = select(func.count()).select_from(RiskEvent).where(
			RiskEvent.created_at.between(start_date, end_date)
		)
		total_result = await self.session.execute(total_query)
		total_events = total_result.scalar() or 0

		# 按事件类型分组统计
		type_stats_query = select(
			RiskEvent.event_type,
			func.count(RiskEvent.id).label('count')
		).where(
			RiskEvent.created_at.between(start_date, end_date)
		).group_by(
			RiskEvent.event_type
		)

		type_stats_result = await self.session.execute(type_stats_query)
		type_stats = [
			{"type": row[0], "count": row[1]}
			for row in type_stats_result.all()
		]

		# 按规则分组统计（需要关联查询）
		rule_stats_query = select(
			RiskRule.rule_name,
			func.count(RiskEvent.id).label('count')
		).join(
			RiskRule, RiskEvent.rule_id == RiskRule.id
		).where(
			RiskEvent.created_at.between(start_date, end_date)
		).group_by(
			RiskRule.rule_name
		)

		rule_stats_result = await self.session.execute(rule_stats_query)
		rule_stats = [
			{"rule_name": row[0], "count": row[1]}
			for row in rule_stats_result.all()
		]

		# 按用户分组统计
		user_stats_query = select(
			SysUser.username,
			func.count(RiskEvent.id).label('count')
		).join(
			SysUser, RiskEvent.user_id == SysUser.id
		).where(
			RiskEvent.created_at.between(start_date, end_date)
		).group_by(
			SysUser.username
		).order_by(
			func.count(RiskEvent.id).desc()
		).limit(10)

		user_stats_result = await self.session.execute(user_stats_query)
		user_stats = [
			{"username": row[0], "count": row[1]}
			for row in user_stats_result.all()
		]

		# 按策略分组统计
		strategy_stats_query = select(
			Strategy.name,
			func.count(RiskEvent.id).label('count')
		).join(
			Strategy, RiskEvent.strategy_id == Strategy.id
		).where(
			RiskEvent.created_at.between(start_date, end_date)
		).group_by(
			Strategy.name
		).order_by(
			func.count(RiskEvent.id).desc()
		).limit(10)

		strategy_stats_result = await self.session.execute(strategy_stats_query)
		strategy_stats = [
			{"strategy_name": row[0], "count": row[1]}
			for row in strategy_stats_result.all()
		]

		# 获取事件趋势（按小时/天）
		hourly_trend_query = select(
			func.date_trunc('hour', RiskEvent.created_at).label('hour'),
			func.count(RiskEvent.id).label('count')
		).where(
			RiskEvent.created_at.between(start_date, end_date)
		).group_by(
			func.date_trunc('hour', RiskEvent.created_at)
		).order_by(
			func.date_trunc('hour', RiskEvent.created_at)
		)

		hourly_trend_result = await self.session.execute(hourly_trend_query)
		hourly_trend = [
			{"hour": row[0], "count": row[1]}
			for row in hourly_trend_result.all()
		]

		return {
			"total_events": total_events or 0,
			"event_types": type_stats,
			"rules": rule_stats,
			"top_users": user_stats,
			"top_strategies": strategy_stats,
			"hourly_trend": hourly_trend,
			"date_range": {
				"start": start_date,
				"end": end_date
			}
		}

	async def get_event_trend (
			self,
			days: int = 30,
			group_by: str = 'day'  # 'hour', 'day', 'week', 'month'
	) -> List[Dict[str, Any]]:
		"""
		获取风险事件趋势

		Args:
			days: 查询天数
			group_by: 分组方式

		Returns:
			List[Dict[str, Any]]: 趋势数据
		"""
		start_date = datetime.now() - timedelta(days=days)

		# 根据分组方式选择时间函数
		if group_by == 'hour':
			time_func = func.date_trunc('hour', RiskEvent.created_at)
		elif group_by == 'day':
			time_func = func.date_trunc('day', RiskEvent.created_at)
		elif group_by == 'week':
			time_func = func.date_trunc('week', RiskEvent.created_at)
		elif group_by == 'month':
			time_func = func.date_trunc('month', RiskEvent.created_at)
		else:
			time_func = func.date_trunc('day', RiskEvent.created_at)

		trend_query = select(
			time_func.label('time_period'),
			func.count(RiskEvent.id).label('event_count'),
			RiskEvent.event_type,
			func.count(RiskEvent.id).filter(RiskEvent.action_taken.is_not(None)).label('action_count')
		).where(
			RiskEvent.created_at >= start_date
		).group_by(
			time_func, RiskEvent.event_type
		).order_by(
			time_func
		)

		trend_result = await self.session.execute(trend_query)

		trend_data = {}
		for row in trend_result.all():
			period = row[0]
			if period not in trend_data:
				trend_data[period] = {
					'period': period,
					'total_events': 0,
					'event_types': {},
					'action_taken': 0
				}

			trend_data[period]['total_events'] += row[1]
			trend_data[period]['event_types'][row[2]] = row[1]
			trend_data[period]['action_taken'] += row[3]

		return list(trend_data.values())

	async def cleanup_old_events (self, days: int = 90) -> int:
		"""
		清理旧的风险事件记录（超表专用方法）

		Args:
			days: 保留天数

		Returns:
			int: 删除的记录数
		"""
		cutoff_date = datetime.now() - timedelta(days=days)

		# 使用超表的分区删除功能
		return await self.delete_by_time_range(
			start_time=cutoff_date,
			end_time=datetime.now()
		)