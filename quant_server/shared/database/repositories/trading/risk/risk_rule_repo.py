# -*- coding: utf-8 -*-
"""
风控规则数据仓库
提供风控规则数据的统一访问接口
位置：shared/database/repositories/trading/risk/risk_rule_repo.py
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, func, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import AuthenticationException
from shared.database.models.business_models import RiskRule, RiskEvent
from shared.database.repositories import RepositoryError
from shared.database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

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
		return await self.get_by(rule_name=rule_name)

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
		filters: Dict[str, Any] = {'is_active': True}

		if rule_type:
			filters['rule_type'] = rule_type

		# 直接使用自定义查询
		query = select(RiskRule).where(
			and_(*[getattr(RiskRule, k) == v for k, v in filters.items()])
		).order_by(RiskRule.created_at.desc())

		result = await self.session.execute(query)
		return result.scalars().all()

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
		filters: Dict[str, Any] = {'rule_type': rule_type}

		if active_only:
			filters['is_active'] = True

		# 直接使用自定义查询
		query = select(RiskRule).where(
			and_(*[getattr(RiskRule, k) == v for k, v in filters.items()])
		).order_by(RiskRule.created_at.desc())

		result = await self.session.execute(query)
		return result.scalars().all()

	async def enable_rule (self, rule_id: str) -> bool:
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

	async def disable_rule (self, rule_id: str) -> bool:
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

	async def toggle_rule_status (self, rule_id: str) -> Optional[bool]:
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


		# 直接使用自定义查询获取总数
		total_query = select(func.count()).select_from(RiskRule).where(and_(*conditions))
		total_result = await self.session.execute(total_query)
		total = total_result.scalar() or 0

		# 获取分页数据
		query = select(RiskRule).where(
			and_(*conditions)
		).order_by(
			RiskRule.is_active.desc(),
			RiskRule.updated_at.desc()
		).offset(offset).limit(limit)

		result = await self.session.execute(query)
		rules = result.scalars().all()

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

		# 最常用规则类型 — 最近30天触发次数排名
		try:
			popular_types_query = select(
				RiskRule.rule_type,
				func.count(RiskEvent.id).label('trigger_count')
			).join(
				RiskEvent, RiskRule.id == RiskEvent.rule_id
			).where(
				RiskEvent.created_at >= datetime.now() - timedelta(days=30)
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
		except Exception as e:
			logger.warning(f"查询最常用规则类型失败: {e}")
			popular_types = []

		return {
			'total_rules': sum(stat['total'] for stat in type_stats),
			'active_rules': sum(stat['active'] for stat in type_stats),
			'inactive_rules': sum(stat['inactive'] for stat in type_stats),
			'by_type': type_stats,
			'popular_types': popular_types,
			'recent_rules': [
				{
					'id': rule.id,
					'rule_name': rule.rule_name,
					'rule_type': rule.rule_type,
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
			except AuthenticationException:
				failed_count += 1

		return {
			'success': success_count,
			'failed': failed_count,
			'total': len(updates)
		}

	async def get_rules_by_action (
			self,
			action: str,
			active_only: bool = True
	) -> List[RiskRule]:
		"""
		根据触发动作获取风控规则

		Args:
			action: 触发动作（reject, alert, pause_strategy）
			active_only: 是否只返回活跃规则

		Returns:
			List[RiskRule]: 指定动作的风控规则列表
		"""
		conditions = [RiskRule.action == action]

		if active_only:
			conditions.append(RiskRule.is_active == True)

		return await self.get_many(
			*conditions,
			order_by=RiskRule.updated_at.desc()
		)

	@staticmethod
	async def validate_rule_condition (
			condition_data: Dict[str, Any]
	) -> Dict[str, Any]:
		"""
		验证规则条件数据有效性

		Args:
			condition_data: 规则条件数据

		Returns:
			Dict[str, Any]: 验证结果
		"""
		try:
			# 基本验证：检查必要字段
			if not condition_data:
				return {'valid': False, 'error': '条件数据不能为空'}

			# 验证条件类型
			if 'type' not in condition_data:
				return {'valid': False, 'error': '条件类型不能为空'}

			# 验证阈值参数
			if 'threshold' in condition_data:
				threshold = condition_data['threshold']
				if not isinstance(threshold, (int, float)) or threshold < 0:
					return {'valid': False, 'error': '阈值必须为非负数'}

			return {'valid': True, 'error': None}
		except Exception as e:
			return {'valid': False, 'error': f'条件验证失败: {str(e)}'}

	async def duplicate_rule (
			self,
			rule_id: str,
			new_rule_name: str
	) -> Optional[RiskRule]:
		"""
		复制风控规则

		Args:
			rule_id: 原规则ID
			new_rule_name: 新规则名称

		Returns:
			Optional[RiskRule]: 新创建的规则，如果失败返回None
		"""
		try:
			# 获取原规则
			original_rule = await self.get(rule_id)
			if not original_rule:
				return None

			# 检查新规则名称是否已存在
			existing_rule = await self.get_by_name(new_rule_name)
			if existing_rule:
				return None

			# 创建新规则
			new_rule_data = {
				'rule_name': new_rule_name,
				'rule_type': original_rule.rule_type,
				'condition': original_rule.condition,
				'action': original_rule.action,
				'is_active': False,  # 新规则默认禁用
				'created_at': datetime.now(),
				'updated_at': datetime.now()
			}

			return await self.create(new_rule_data)
		except AuthenticationException:
			return None

	async def export_rules (
			self,
			rule_type: Optional[str] = None,
			format_type: str = 'json'
	) -> str:
		"""
		导出风控规则

		Args:
			rule_type: 规则类型过滤
			format_type: 导出格式（json/csv）

		Returns:
			str: 导出文件路径或数据
		"""
		try:
			rules = await self.get_rules_by_type(rule_type) if rule_type else await self.get_all()

			if not rules:
				return "" if format_type == 'csv' else "[]"

			records = []
			for r in rules:
				records.append({
					"id": r.id,
					"rule_name": r.rule_name,
					"rule_type": r.rule_type,
					"condition": r.condition,
					"action": r.action,
					"is_active": r.is_active,
					"created_at": r.created_at.isoformat() if r.created_at else "",
					"updated_at": r.updated_at.isoformat() if r.updated_at else ""
				})

			if format_type == 'json':
				import json
				return json.dumps(records, ensure_ascii=False, indent=2, default=str)
			else:
				import csv
				import io
				output = io.StringIO()
				fieldnames = list(records[0].keys())
				writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
				writer.writeheader()
				writer.writerows(records)
				return output.getvalue()
		except Exception as e:
			raise RepositoryError(f"导出风控规则失败: {str(e)}")

	async def import_rules (
			self,
			import_data: List[Dict[str, Any]]
	) -> Dict[str, int]:
		"""
		导入风控规则

		Args:
			import_data: 导入数据列表

		Returns:
			Dict[str, int]: 导入结果统计
		"""
		success_count = 0
		failed_count = 0

		for rule_data in import_data:
			try:
				# 验证必要字段
				if not all(key in rule_data for key in ['rule_name', 'rule_type', 'condition', 'action']):
					failed_count += 1
					continue

				# 检查规则名称是否已存在
				existing_rule = await self.get_by_name(rule_data['rule_name'])
				if existing_rule:
					failed_count += 1
					continue

				# 创建规则
				rule_data['created_at'] = datetime.now()
				rule_data['updated_at'] = datetime.now()
				
				result = await self.create(rule_data)
				if result:
					success_count += 1
				else:
					failed_count += 1
			except AuthenticationException:
				failed_count += 1

		return {
			'success': success_count,
			'failed': failed_count,
			'total': len(import_data)
		}

	async def get_rule_usage (
			self,
			rule_id: str
	) -> Dict[str, Any]:
		"""
		获取风控规则使用情况

		Args:
			rule_id: 规则ID

		Returns:
			Dict[str, Any]: 规则使用情况统计
		"""
		try:
			# 获取规则信息
			rule = await self.get(rule_id)
			if not rule:
				return {'error': '规则不存在'}

			# 统计触发次数（需要关联RiskEvent表）
			from shared.database.models.business_models import RiskEvent

			try:
				trigger_count_query = select(
					func.count(RiskEvent.id)
				).where(RiskEvent.rule_id == rule_id)

				trigger_count_result = await self.session.execute(trigger_count_query)
				trigger_count = trigger_count_result.scalar() or 0
			except AuthenticationException:
				trigger_count = 0

			return {
				'rule_id': rule_id,
				'rule_name': rule.rule_name,
				'rule_type': rule.rule_type,
				'is_active': rule.is_active,
				'trigger_count': trigger_count,
				'last_triggered': None,  # 需要从RiskEvent表中获取
				'created_at': rule.created_at,
				'updated_at': rule.updated_at
			}
		except Exception as e:
			return {'error': f"获取规则使用情况失败: {str(e)}"}

	async def cleanup_inactive_rules (
			self,
			days_threshold: int = 90
	) -> int:
		"""
		清理长时间未启用的风控规则

		Args:
			days_threshold: 天数阈值（默认90天）

		Returns:
			int: 清理的规则数量
		"""
		try:
			# 计算截止日期
			cutoff_date = datetime.now() - timedelta(days=days_threshold)

			# 查找长时间未启用的规则
			query = select(RiskRule).where(
				and_(
					RiskRule.is_active == False,
					RiskRule.updated_at < cutoff_date
				)
			)

			result = await self.session.execute(query)
			rules_to_delete = result.scalars().all()

			# 删除规则
			deleted_count = 0
			for rule in rules_to_delete:
				try:
					await self.delete(rule.id)
					deleted_count += 1
				except AuthenticationException:
					pass

			return deleted_count
		except AuthenticationException:
			return 0

	async def get_rule_actions (self) -> List[str]:
		"""
		获取所有风控规则动作类型

		Returns:
			List[str]: 动作类型列表
		"""
		query = select(
			RiskRule.action
		).distinct().order_by(
			RiskRule.action
		)

		result = await self.session.execute(query)
		return [row[0] for row in result.all() if row[0]]

	async def validate_rule_data (
			self,
			rule_data: Dict[str, Any]
	) -> Dict[str, Any]:
		"""
		验证风控规则数据有效性

		Args:
			rule_data: 规则数据

		Returns:
			Dict[str, Any]: 验证结果
		"""
		try:
			# 检查必要字段
			required_fields = ['rule_name', 'rule_type', 'condition', 'action']
			for field in required_fields:
				if field not in rule_data:
					return {'valid': False, 'error': f'缺少必要字段: {field}'}

			# 验证规则名称
			if not isinstance(rule_data['rule_name'], str) or len(rule_data['rule_name']) == 0:
				return {'valid': False, 'error': '规则名称不能为空'}

			# 验证规则类型
			valid_rule_types = ['position', 'account', 'market', 'blacklist']
			if rule_data['rule_type'] not in valid_rule_types:
				return {'valid': False, 'error': f'无效的规则类型: {rule_data["rule_type"]}'}

			# 验证动作类型
			valid_actions = ['reject', 'alert', 'pause_strategy']
			if rule_data['action'] not in valid_actions:
				return {'valid': False, 'error': f'无效的动作类型: {rule_data["action"]}'}

			# 验证条件数据
			condition_validation = await self.validate_rule_condition(rule_data.get('condition', {}))
			if not condition_validation['valid']:
				return condition_validation

			return {'valid': True, 'error': None}
		except Exception as e:
			return {'valid': False, 'error': f'数据验证失败: {str(e)}'}