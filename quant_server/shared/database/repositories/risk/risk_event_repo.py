# quant_server/shared/database/repositories/risk/risk_event_repo.py
"""
风险事件Repository
"""
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from quant_server.shared.database.models.business_models import RiskEvent, RiskRule, Strategy, SysUser
from quant_server.shared.database.repositories.base import RepositoryBase


class RiskEventRepository(RepositoryBase):
	"""
	风险事件仓库
	用于记录和管理风控事件
	"""

	def __init__ (self, session: Session):
		super().__init__(session)

	def create (self, event_data: Dict[str, Any]) -> RiskEvent:
		"""
		创建风险事件记录

		Args:
			event_data: 风险事件数据

		Returns:
			RiskEvent: 创建的风险事件
		"""
		event = RiskEvent(**event_data)
		self.session.add(event)
		self.session.flush()
		return event

	def get_by_id (self, event_id: int) -> Optional[RiskEvent]:
		"""
		根据ID获取风险事件

		Args:
			event_id: 事件ID

		Returns:
			Optional[RiskEvent]: 风险事件，如果不存在返回None
		"""
		return self.session.query(RiskEvent).filter(
			RiskEvent.id == event_id
		).first()

	def get_recent_events (
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
		query = self.session.query(RiskEvent)

		# 时间过滤
		start_date = datetime.now() - timedelta(days=days)
		query = query.filter(RiskEvent.created_at >= start_date)

		# 其他过滤条件
		if user_id:
			query = query.filter(RiskEvent.user_id == user_id)

		if strategy_id:
			query = query.filter(RiskEvent.strategy_id == strategy_id)

		if rule_id:
			query = query.filter(RiskEvent.rule_id == rule_id)

		if event_type:
			query = query.filter(RiskEvent.event_type == event_type)

		return query.order_by(
			desc(RiskEvent.created_at)
		).limit(limit).all()

	def get_events_by_user (self, user_id: int, limit: int = 50) -> List[RiskEvent]:
		"""
		获取指定用户的风险事件

		Args:
			user_id: 用户ID
			limit: 返回数量限制

		Returns:
			List[RiskEvent]: 用户的风险事件列表
		"""
		return self.session.query(RiskEvent).filter(
			RiskEvent.user_id == user_id
		).order_by(
			desc(RiskEvent.created_at)
		).limit(limit).all()

	def get_events_by_strategy (self, strategy_id: str, limit: int = 50) -> List[RiskEvent]:
		"""
		获取指定策略的风险事件

		Args:
			strategy_id: 策略ID
			limit: 返回数量限制

		Returns:
			List[RiskEvent]: 策略的风险事件列表
		"""
		return self.session.query(RiskEvent).filter(
			RiskEvent.strategy_id == strategy_id
		).order_by(
			desc(RiskEvent.created_at)
		).limit(limit).all()

	def search_events (
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
		query = self.session.query(RiskEvent)

		# 时间范围过滤
		if start_date:
			query = query.filter(RiskEvent.created_at >= start_date)
		if end_date:
			query = query.filter(RiskEvent.created_at <= end_date)

		# 其他过滤条件
		if user_id:
			query = query.filter(RiskEvent.user_id == user_id)

		if strategy_id:
			query = query.filter(RiskEvent.strategy_id == strategy_id)

		if rule_id:
			query = query.filter(RiskEvent.rule_id == rule_id)

		if event_type:
			query = query.filter(RiskEvent.event_type == event_type)

		if action_taken:
			query = query.filter(RiskEvent.action_taken == action_taken)

		total = query.count()
		events = query.order_by(
			desc(RiskEvent.created_at)
		).offset(offset).limit(limit).all()

		return {
			"events": events,
			"total": total,
			"offset": offset,
			"limit": limit
		}

	def get_event_statistics (
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
		total_events = self.session.query(func.count(RiskEvent.id)).filter(
			RiskEvent.created_at.between(start_date, end_date)
		).scalar()

		# 按事件类型分组统计
		type_stats = self.session.query(
			RiskEvent.event_type,
			func.count(RiskEvent.id).label('count')
		).filter(
			RiskEvent.created_at.between(start_date, end_date)
		).group_by(RiskEvent.event_type).all()

		# 按规则分组统计
		rule_stats = self.session.query(
			RiskRule.rule_name,
			func.count(RiskEvent.id).label('count')
		).join(
			RiskRule, RiskEvent.rule_id == RiskRule.id
		).filter(
			RiskEvent.created_at.between(start_date, end_date)
		).group_by(RiskRule.rule_name).all()

		# 按用户分组统计
		user_stats = self.session.query(
			SysUser.username,
			func.count(RiskEvent.id).label('count')
		).join(
			SysUser, RiskEvent.user_id == SysUser.id
		).filter(
			RiskEvent.created_at.between(start_date, end_date)
		).group_by(SysUser.username).limit(10).all()

		# 按策略分组统计
		strategy_stats = self.session.query(
			Strategy.name,
			func.count(RiskEvent.id).label('count')
		).join(
			Strategy, RiskEvent.strategy_id == Strategy.id
		).filter(
			RiskEvent.created_at.between(start_date, end_date)
		).group_by(Strategy.name).limit(10).all()

		return {
			"total_events": total_events or 0,
			"event_types": [{"type": s[0], "count": s[1]} for s in type_stats],
			"rules": [{"rule_name": s[0], "count": s[1]} for s in rule_stats],
			"top_users": [{"username": s[0], "count": s[1]} for s in user_stats],
			"top_strategies": [{"strategy_name": s[0], "count": s[1]} for s in strategy_stats],
			"date_range": {
				"start": start_date,
				"end": end_date
			}
		}

	def delete_old_events (self, days: int = 90) -> int:
		"""
		删除旧的风险事件记录

		Args:
			days: 保留天数

		Returns:
			int: 删除的记录数
		"""
		cutoff_date = datetime.now() - timedelta(days=days)

		result = self.session.query(RiskEvent).filter(
			RiskEvent.created_at < cutoff_date
		).delete(synchronize_session=False)

		return result