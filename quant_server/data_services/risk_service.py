# risk_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import func, desc
from quant_server.data_services.base_service import BaseService
from quant_server.db.models.business_models import RiskRule, RiskEvent


class RiskRuleService(BaseService):
    """风控规则信息服务"""

    def create(self, data: Dict[str, Any]) -> RiskRule:
        """创建新风控规则记录"""
        with self.session_scope() as session:
            rule = RiskRule(**data)
            session.add(rule)
            session.flush()
            return rule

    def get(self, rule_id: int) -> Optional[RiskRule]:
        """根据规则ID获取规则信息"""
        with self.session_scope() as session:
            return session.query(RiskRule).filter_by(id=rule_id).first()

    def get_active_rules(self) -> List[RiskRule]:
        """获取活跃规则列表"""
        with self.session_scope() as session:
            return session.query(RiskRule).filter_by(is_active=True).all()

    def get_rules_by_type(self, rule_type: str) -> List[RiskRule]:
        """根据类型获取规则列表"""
        with self.session_scope() as session:
            return session.query(RiskRule).filter_by(rule_type=rule_type).all()

    def update(self, rule_id: int, update_data: Dict[str, Any]) -> Optional[RiskRule]:
        """更新规则信息"""
        with self.session_scope() as session:
            rule = session.query(RiskRule).filter_by(id=rule_id).first()
            if rule:
                for key, value in update_data.items():
                    setattr(rule, key, value)
                return rule
            return None

    def toggle_active(self, rule_id: int) -> Optional[RiskRule]:
        """切换规则激活状态"""
        with self.session_scope() as session:
            rule = session.query(RiskRule).filter_by(id=rule_id).first()
            if rule:
                rule.is_active = not rule.is_active
                return rule
            return None

    def delete(self, rule_id: int) -> bool:
        """删除规则记录"""
        with self.session_scope() as session:
            rule = session.query(RiskRule).filter_by(id=rule_id).first()
            if rule:
                session.delete(rule)
                return True
            return False

    def count_by_type(self) -> Dict[str, int]:
        """统计各类型的规则数量"""
        with self.session_scope() as session:
            result = session.query(
                RiskRule.rule_type,
                func.count(RiskRule.id)
            ).group_by(RiskRule.rule_type).all()
            return {rule_type: count for rule_type, count in result}

    def count_by_status(self) -> Dict[bool, int]:
        """统计激活状态的规则数量"""
        with self.session_scope() as session:
            result = session.query(
                RiskRule.is_active,
                func.count(RiskRule.id)
            ).group_by(RiskRule.is_active).all()
            return {is_active: count for is_active, count in result}


class RiskEventService(BaseService):
    """风控事件信息服务"""

    def create(self, data: Dict[str, Any]) -> RiskEvent:
        """创建新风控事件记录"""
        with self.session_scope() as session:
            event = RiskEvent(**data)
            session.add(event)
            session.flush()
            return event

    def get(self, event_id: int) -> Optional[RiskEvent]:
        """根据事件ID获取事件信息"""
        with self.session_scope() as session:
            return session.query(RiskEvent).filter_by(id=event_id).first()

    def get_recent_events(self, days: int = 7) -> List[RiskEvent]:
        """获取最近N天的事件记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        with self.session_scope() as session:
            return session.query(RiskEvent).filter(
                RiskEvent.created_at >= cutoff_date
            ).order_by(desc(RiskEvent.created_at)).all()

    def get_strategy_events(self, strategy_id: str) -> List[RiskEvent]:
        """获取策略的所有事件记录"""
        with self.session_scope() as session:
            return session.query(RiskEvent).filter_by(strategy_id=strategy_id).all()

    def get_user_events(self, user_id: int) -> List[RiskEvent]:
        """获取用户的所有事件记录"""
        with self.session_scope() as session:
            return session.query(RiskEvent).filter_by(user_id=user_id).all()

    def get_rule_events(self, rule_id: int) -> List[RiskEvent]:
        """获取规则的所有事件记录"""
        with self.session_scope() as session:
            return session.query(RiskEvent).filter_by(rule_id=rule_id).all()

    def update(self, event_id: int, update_data: Dict[str, Any]) -> Optional[RiskEvent]:
        """更新事件信息"""
        with self.session_scope() as session:
            event = session.query(RiskEvent).filter_by(id=event_id).first()
            if event:
                for key, value in update_data.items():
                    setattr(event, key, value)
                return event
            return None

    def delete(self, event_id: int) -> bool:
        """删除事件记录"""
        with self.session_scope() as session:
            event = session.query(RiskEvent).filter_by(id=event_id).first()
            if event:
                session.delete(event)
                return True
            return False

    def delete_old_events(self, days: int = 30) -> int:
        """删除指定天数前的事件记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        with self.session_scope() as session:
            result = session.query(RiskEvent).filter(
                RiskEvent.created_at < cutoff_date
            ).delete()
            return result

    def count_by_type(self) -> Dict[str, int]:
        """统计各类型的事件数量"""
        with self.session_scope() as session:
            result = session.query(
                RiskEvent.event_type,
                func.count(RiskEvent.id)
            ).group_by(RiskEvent.event_type).all()
            return {event_type: count for event_type, count in result}

    def count_by_rule(self) -> Dict[int, int]:
        """统计各规则的事件数量"""
        with self.session_scope() as session:
            result = session.query(
                RiskEvent.rule_id,
                func.count(RiskEvent.id)
            ).group_by(RiskEvent.rule_id).all()
            return {rule_id: count for rule_id, count in result}