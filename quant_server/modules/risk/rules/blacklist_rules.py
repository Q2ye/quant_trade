# blacklist_rules.py     # 黑名单规则

from typing import Dict, Any, Tuple
from .base_rule import RiskRule


class BlacklistRule(RiskRule):
    """黑名单规则"""
    
    def __init__(self, blacklist: list = None):
        """
        初始化黑名单规则
        
        Args:
            blacklist: 黑名单列表
        """
        super().__init__(
            name="blacklist",
            description="检查股票是否在黑名单中"
        )
        self.blacklist = blacklist or []
    
    async def check(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        检查股票是否在黑名单中
        
        Args:
            data: 检查数据，包含 ts_code 或 symbol
            
        Returns:
            (是否通过, 消息)
        """
        symbol = data.get("ts_code", data.get("symbol"))
        
        if not symbol:
            return True, "未提供股票代码，跳过黑名单检查"
        
        if symbol in self.blacklist:
            return False, f"股票 {symbol} 在黑名单中"
        
        return True, "黑名单检查通过"


class MarketBlacklistRule(RiskRule):
    """市场黑名单规则"""
    
    def __init__(self, market_blacklist: list = None):
        """
        初始化市场黑名单规则
        
        Args:
            market_blacklist: 市场黑名单列表
        """
        super().__init__(
            name="market_blacklist",
            description="检查市场是否在黑名单中"
        )
        self.market_blacklist = market_blacklist or []
    
    async def check(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        检查市场是否在黑名单中
        
        Args:
            data: 检查数据，包含 market
            
        Returns:
            (是否通过, 消息)
        """
        market = data.get("market")
        
        if not market:
            return True, "未提供市场信息，跳过市场黑名单检查"
        
        if market in self.market_blacklist:
            return False, f"市场 {market} 在黑名单中"
        
        return True, "市场黑名单检查通过"


class SectorBlacklistRule(RiskRule):
    """行业黑名单规则"""
    
    def __init__(self, sector_blacklist: list = None):
        """
        初始化行业黑名单规则
        
        Args:
            sector_blacklist: 行业黑名单列表
        """
        super().__init__(
            name="sector_blacklist",
            description="检查行业是否在黑名单中"
        )
        self.sector_blacklist = sector_blacklist or []
    
    async def check(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        检查行业是否在黑名单中
        
        Args:
            data: 检查数据，包含 sector
            
        Returns:
            (是否通过, 消息)
        """
        sector = data.get("sector")
        
        if not sector:
            return True, "未提供行业信息，跳进行业黑名单检查"
        
        if sector in self.sector_blacklist:
            return False, f"行业 {sector} 在黑名单中"
        
        return True, "行业黑名单检查通过"