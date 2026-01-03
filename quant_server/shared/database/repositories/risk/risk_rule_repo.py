# quant_server/shared/database/repositories/risk/risk_rule_repo.py
"""
风控规则Repository
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

from quant_server.shared.database.models.business_models import RiskRule
from quant_server.shared.database.repositories.base import RepositoryBase


class RiskRuleRepository(RepositoryBase):
	"""
	风控规则仓库
	用于管理风控规则的创建、查询、更新和删除
	"""

	def __init__ (self, session: Session):
		super().__init__(session)

	def create (self, rule_data: Dict[str, Any]) -> RiskRule:
		"""
		创建风控规则

		Args:
			rule_data: 风控规则数据

		Returns:
			RiskRule: 创建的风控规则
		"""
		rule = RiskRule(**rule_data)
		self.session.add(rule)
		self.session.flush()
		return rule

	def get_by_id (self, rule_id: int) -> Optional[RiskRule]:
		"""
		根据ID获取风控规则

		Args:
			rule_id: 规则ID

		Returns:
			Optional[RiskRule]: 风控规则，如果不存在返回None
		"""
		return self.session.query(RiskRule).filter(
			RiskRule.id == rule_id
		).first()

	def get_by_name (self, rule_name: str) -> Optional[RiskRule]:
		"""
		根据规则名称获取风控规则

		Args:
			rule_name: 规则名称

		Returns:
			Optional[RiskRule]: 风控规则，如果不存在返回None
		"""
		return self.session.query(RiskRule).filter(
			RiskRule.rule_name == rule_name
		).first()

	def get_active_rules (self, rule_type: Optional[str] = None) -> List[RiskRule]:
		"""
		获取所有活跃的风控规则

		Args:
			rule_type: 规则类型过滤

		Returns:
			List[RiskRule]: 活跃的风控规则列表
		"""
		query = self.session.query(RiskRule).filter(
			RiskRule.is_active == True
		)

		if rule_type:
			query = query.filter(RiskRule.rule_type == rule_type)

		return query.order_by(RiskRule.created_at.desc()).all()

	def get_rules_by_type (self, rule_type: str) -> List[RiskRule]:
		"""
		根据类型获取风控规则

		Args:
			rule_type: 规则类型

		Returns:
			List[RiskRule]: 指定类型的风控规则列表
		"""
		return self.session.query(RiskRule).filter(
			RiskRule.rule_type == rule_type,
			RiskRule.is_active == True
		).order_by(RiskRule.created_at.desc()).all()

	def update (self, rule_id: int, update_data: Dict[str, Any]) -> Optional[RiskRule]:
		"""
		更新风控规则

		Args:
			rule_id: 规则ID
			update_data: 更新数据

		Returns:
			Optional[RiskRule]: 更新后的风控规则，如果不存在返回None
		"""
		rule = self.get_by_id(rule_id)
		if not rule:
			return None

		for key, value in update_data.items():
			setattr(rule, key, value)

		rule.updated_at = datetime.now()
		self.session.flush()
		return rule

	def delete (self, rule_id: int) -> bool:
		"""
		删除风控规则（软删除）

		Args:
			rule_id: 规则ID

		Returns:
			bool: 是否成功删除
		"""
		rule = self.get_by_id(rule_id)
		if not rule:
			return False

		rule.is_active = False
		rule.updated_at = datetime.now()
		self.session.flush()
		return True

	def enable_rule (self, rule_id: int) -> bool:
		"""
		启用风控规则

		Args:
			rule_id: 规则ID

		Returns:
			bool: 是否成功启用
		"""
		rule = self.get_by_id(rule_id)
		if not rule:
			return False

		rule.is_active = True
		rule.updated_at = datetime.now()
		self.session.flush()
		return True

	def disable_rule (self, rule_id: int) -> bool:
		"""
		禁用风控规则

		Args:
			rule_id: 规则ID

		Returns:
			bool: 是否成功禁用
		"""
		rule = self.get_by_id(rule_id)
		if not rule:
			return False

		rule.is_active = False
		rule.updated_at = datetime.now()
		self.session.flush()
		return True

	def search_rules (
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
		query = self.session.query(RiskRule)

		if rule_type:
			query = query.filter(RiskRule.rule_type == rule_type)

		if is_active is not None:
			query = query.filter(RiskRule.is_active == is_active)

		if rule_name:
			query = query.filter(RiskRule.rule_name.ilike(f"%{rule_name}%"))

		total = query.count()
		rules = query.order_by(
			RiskRule.is_active.desc(),
			RiskRule.updated_at.desc()
		).offset(offset).limit(limit).all()

		return {
			"rules": rules,
			"total": total,
			"offset": offset,
			"limit": limit
		}

	def get_rule_types (self) -> List[str]:
		"""
		获取所有风控规则类型

		Returns:
			List[str]: 规则类型列表
		"""
		results = self.session.query(
			RiskRule.rule_type
		).distinct().all()

		return [r[0] for r in results if r[0]]