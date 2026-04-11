# risk_manager.py       # 风险管理器

from typing import Dict, Any, Optional, List
from quant_server.core.engines.system import EventEngine


class RiskManager:
    """风险管理器"""
    
    def __init__(
        self,
        config: Dict[str, Any],
        event_engine: Optional[EventEngine] = None
    ):
        self.config = config
        self.event_engine = event_engine
        self.risk_events = []
        self.risk_rules = {
            "position_limit": config.get("position_limit", True),
            "loss_limit": config.get("loss_limit", True),
            "blacklist": config.get("blacklist", True),
            "liquidity": config.get("liquidity", True),
            "account_balance": config.get("account_balance", True)
        }
    
    def get_risk_rules(self) -> Dict[str, bool]:
        """获取风险规则配置"""
        return self.risk_rules
    
    def update_risk_rule(self, rule_name: str, enabled: bool) -> bool:
        """更新风险规则状态"""
        if rule_name in self.risk_rules:
            self.risk_rules[rule_name] = enabled
            return True
        return False
    
    def add_risk_event(self, event: Dict[str, Any]):
        """添加风险事件"""
        self.risk_events.append(event)
        # 发布风险事件
        if self.event_engine:
            # 这里可以发布风险事件
            pass
    
    def get_risk_events(self, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取风险事件"""
        events = self.risk_events
        if level:
            events = [event for event in events if event.get("level") == level]
        return events
    
    def clear_risk_events(self):
        """清除风险事件"""
        self.risk_events.clear()
    
    def is_rule_enabled(self, rule_name: str) -> bool:
        """检查风险规则是否启用"""
        return self.risk_rules.get(rule_name, False)