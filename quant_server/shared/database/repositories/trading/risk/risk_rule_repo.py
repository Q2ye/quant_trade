# -*- coding: utf-8 -*-
"""
风控规则数据仓库
提供风控规则数据的统一访问接口
位置：shared/database/repositories/trading/risk/risk_rule_repo.py
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.business_models import RiskRule


class RiskRuleRepository(BaseRepository):
	"""风控规则数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, RiskRule)

	async def get_by_name (self, rule_name: str) -> Optional[RiskRule]:
		"""
		根据规则名称获取风控规则

		Args:
			rule_name: 规则名称

		Returns:
			Optional[RiskRule]: 风控规则，如果不存在返回None
		"""
		return await self.get_one(RiskRule.rule_name == rule_name)

	async def get_active_rules (
			self,
			rule_type: Optional[str] = None
	) -> List[RiskRule]:
		"""
		获取所有活跃的风控规则

		Args:
			rule_type: 规则类型过滤

		Returns:
			List[RiskRule]: 活跃的风控规则列表
		"""
		conditions = [RiskRule.is_active == True]

		if rule_type:
			conditions.append(RiskRule.rule_type == rule_type)

		return await self.get_many(
			*conditions,
			order_by=RiskRule.created_at.desc()
		)

	async def get_rules_by_type (
			self,
			rule_type: str,
			active_only: bool = True
	) -> List[RiskRule]:
		"""
		根据类型获取风控规则

		Args:
			rule_type: 规则类型
			active_only: 是否只返回活跃规则

		Returns:
			List[RiskRule]: 指定类型的风控规则列表
		"""
		conditions = [RiskRule.rule_type == rule_type]

		if active_only:
			conditions.append(RiskRule.is_active == True)

		return await self.get_many(
			*conditions,
			order_by=RiskRule.created_at.desc()
		)

	async def enable_rule (self, rule_id: int) -> bool:
		"""
		启用风控规则

		Args:
			rule_id: 规则ID

		Returns:
			bool: 是否成功启用
		"""
		update_data = {
			'is_active': True,
			'updated_at': datetime.now()
		}

		result = await self.update(rule_id, update_data)
		return result is not None

	async def disable_rule (self, rule_id: int) -> bool:
		"""
		禁用风控规则

		Args:
			rule_id: 规则ID

		Returns:
			bool: 是否成功禁用
		"""
		update_data = {
			'is_active': False,
			'updated_at': datetime.now()
		}

		result = await self.update(rule_id, update_data)
		return result is not None

	async def toggle_rule_status (self, rule_id: int) -> Optional[bool]:
		"""
		切换规则状态

		Args:
			rule_id: 规则ID

		Returns:
			Optional[bool]: 切换后的状态，如果规则不存在返回None
		"""
		rule = await self.get(rule_id)
		if not rule:
			return None

		new_status = not rule.is_active

		update_data = {
			'is_active': new_status,
			'updated_at': datetime.now()
		}

		await self.update(rule_id, update_data)
		return new_status

	async def search_rules (
			self,
			rule_type: Optional[str] = None,
			is_active: Optional[bool] = None,
			rule_name: Optional[str] = None,
			limit: int = 100,
			offset: int = 0
	) -> Dict[str, Any]:
		"""
		搜索风控规则

		Args:
			rule_type: 规则类型过滤
			is_active: 是否活跃过滤
			rule_name: 规则名称模糊搜索
			limit: 每页数量
			offset: 偏移量

		Returns:
			Dict[str, Any]: 包含规则列表和总数的字典
		"""
		conditions = []

		if rule_type:
			conditions.append(RiskRule.rule_type == rule_type)

		if is_active is not None:
			conditions.append(RiskRule.is_active == is_active)

		if rule_name:
			conditions.append(RiskRule.rule_name.ilike(f"%{rule_name}%"))

		# 获取总数
		total = await self.count(*conditions)

		# 获取分页数据
		rules = await self.get_many(
			*conditions,
			order_by=[RiskRule.is_active.desc(), RiskRule.updated_at.desc()],
			skip=offset,
			limit=limit
		)

		return {
			"rules": rules,
			"total": total,
			"offset": offset,
			"limit": limit,
			"has_more": offset + len(rules) < total
		}

	async def get_rule_types (self) -> List[str]:
		"""
		获取所有风控规则类型

		Returns:
			List[str]: 规则类型列表
		"""
		query = select(
			RiskRule.rule_type
		).distinct().order_by(
			RiskRule.rule_type
		)

		result = await self.session.execute(query)
		return [row[0] for row in result.all() if row[0]]

	async def get_rule_statistics (self) -> Dict[str, Any]:
		"""
		获取风控规则统计信息

		Returns:
			Dict[str, Any]: 统计信息
		"""
		# 按类型统计
		type_stats_query = select(
			RiskRule.rule_type,
			func.count(RiskRule.id).label('total'),
			func.sum(func.cast(RiskRule.is_active, Integer)).label('active')
		).group_by(
			RiskRule.rule_type
		)

		type_stats_result = await self.session.execute(type_stats_query)
		type_stats = [
			{
				'rule_type': row[0],
				'total': row[1],
				'active': row[2] or 0,
				'inactive': row[1] - (row[2] or 0)
			}
			for row in type_stats_result.all()
		]

		# 最近更新的规则
		recent_rules = await self.get_many(
			order_by=RiskRule.updated_at.desc(),
			limit=10
		)

		# 最常用的规则类型（需要关联RiskEvent表，这里暂时简化）
		from quant_server.shared.database.models.business_models import RiskEvent

		popular_types_query = select(
			RiskRule.rule_type,
			func.count(RiskEvent.id).label('trigger_count')
		).join(
			RiskEvent, RiskRule.id == RiskEvent.rule_id
		).group_by(
			RiskRule.rule_type
		).order_by(
			func.count(RiskEvent.id).desc()
		).limit(5)

		popular_types_result = await self.session.execute(popular_types_query)
		popular_types = [
			{'rule_type': row[0], 'trigger_count': row[1]}
			for row in popular_types_result.all()
		]

		return {
			'total_rules': sum(stat['total'] for stat in type_stats),
			'active_rules': sum(stat['active'] for stat in type_stats),
			'inactive_rules': sum(stat['inactive'] for stat in type_stats),
			'by_type': type_stats,
			'popular_types': popular_types,
			'recent_updates': [
				{
					'id': rule.id,
					'name': rule.rule_name,
					'type': rule.rule_type,
					'is_active': rule.is_active,
					'updated_at': rule.updated_at
				}
				for rule in recent_rules
			]
		}

	async def batch_update_rules (
			self,
			updates: List[Dict[str, Any]]
	) -> Dict[str, int]:
		"""
		批量更新风控规则

		Args:
			updates: 更新数据列表，每个元素包含rule_id和更新数据

		Returns:
			Dict[str, int]: 更新结果统计
		"""
		success_count = 0
		failed_count = 0

		for update in updates:
			rule_id = update.get('rule_id')
			update_data = update.get('data', {})

			if not rule_id or not update_data:
				failed_count += 1
				continue

			# 确保更新时间
			if 'updated_at' not in update_data:
				update_data['updated_at'] = datetime.now()

			try:
				result = await self.update(rule_id, update_data)
				if result:
					success_count += 1
				else:
					failed_count += 1
			except Exception:
				failed_count += 1

		return {
			'success': success_count,
			'failed': failed_count,
			'total': len(updates)
		}