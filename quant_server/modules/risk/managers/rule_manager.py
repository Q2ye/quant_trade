# -*- coding: utf-8 -*-
"""
风控规则管理器 — 规则启用/禁用、参数热更新、状态查询

规则数据模型使用 shared.database.models.business_models.RiskRule (ORM)。
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class RuleManager:
    """风控规则管理器 — 管理规则的运行时状态与参数

    规则实例来自 shared.database.models.business_models.RiskRule。
    """

    def __init__(self):
        self._rules: Dict[str, Any] = {}  # rule_name -> RiskRule ORM instance
        self._events: List[Dict[str, Any]] = []

    def register_rule(self, rule) -> None:
        """注册规则到管理器（rule 为 RiskRule ORM 实例）"""
        self._rules[rule.rule_name] = rule
        logger.debug("规则已注册: %s (type=%s)", rule.rule_name, getattr(rule, 'rule_type', ''))

    def get_risk_rules(self) -> Dict[str, bool]:
        """获取所有规则启用状态"""
        return {name: r.enabled for name, r in self._rules.items()}

    def update_risk_rule(self, rule_name: str, enabled: bool, params: Optional[Dict] = None) -> bool:
        """更新规则状态和参数"""
        rule = self._rules.get(rule_name)
        if rule is None:
            logger.warning("规则不存在: %s", rule_name)
            return False
        rule.enabled = enabled
        if params:
            rule.params.update(params)
        logger.info("规则已更新: %s, enabled=%s", rule_name, enabled)
        return True

    def is_rule_enabled(self, rule_name: str) -> bool:
        """检查规则是否启用"""
        rule = self._rules.get(rule_name)
        return rule.enabled if rule else False

    def get_rule(self, rule_name: str) -> Optional[Any]:
        """获取指定规则（返回 RiskRule ORM 实例或 None）"""
        return self._rules.get(rule_name)

    def get_all_rules(self) -> List[Any]:
        """获取所有规则（返回 RiskRule ORM 实例列表）"""
        return list(self._rules.values())

    def record_event(self, event_type: str, rule_name: str, message: str,
                     level: str = "warning", signal_data: Optional[Dict] = None) -> None:
        """记录风控事件"""
        import uuid
        from datetime import datetime
        event = {
            "id": str(uuid.uuid4())[:8],
            "rule_name": rule_name,
            "event_type": event_type,
            "level": level,
            "message": message,
            "signal_data": signal_data,
            "created_at": datetime.now().isoformat(),
            "acknowledged": False,
        }
        self._events.insert(0, event)
        # 保留最近 500 条
        if len(self._events) > 500:
            self._events = self._events[:500]
        # 更新规则违规计数（如果 ORM 模型有此字段）
        if rule_name in self._rules:
            rule = self._rules[rule_name]
            if hasattr(rule, 'violation_count'):
                rule.violation_count += 1

    def get_risk_events(self, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取风控事件列表"""
        if level:
            return [e for e in self._events if e["level"] == level]
        return self._events[:100]

    def clear_risk_events(self) -> None:
        """清除所有风控事件"""
        self._events.clear()
