# risk_service.py       # 风控服务

from typing import Dict, Any, Optional, List
from quant_server.modules.trade.engines.risk_engine import RiskEngine
from quant_server.modules.trade.managers.risk_manager import RiskManager


class RiskService:
    """风控服务"""
    
    def __init__(self, risk_engine: RiskEngine, risk_manager: RiskManager):
        self.risk_engine = risk_engine
        self.risk_manager = risk_manager
    
    async def check_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """检查信号是否符合风控规则"""
        is_valid, message = await self.risk_engine.check_signal(signal_data)
        return {
            "valid": is_valid,
            "message": message
        }
    
    async def check_position_risk(self) -> List[Dict[str, Any]]:
        """检查持仓风险"""
        return await self.risk_engine.check_position_risk()
    
    def get_risk_rules(self) -> Dict[str, bool]:
        """获取风险规则配置"""
        return self.risk_manager.get_risk_rules()
    
    def update_risk_rule(self, rule_name: str, enabled: bool) -> bool:
        """更新风险规则状态"""
        return self.risk_manager.update_risk_rule(rule_name, enabled)
    
    def get_risk_events(self, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取风险事件"""
        return self.risk_manager.get_risk_events(level)
    
    def clear_risk_events(self):
        """清除风险事件"""
        self.risk_manager.clear_risk_events()
    
    def is_rule_enabled(self, rule_name: str) -> bool:
        """检查风险规则是否启用"""
        return self.risk_manager.is_rule_enabled(rule_name)