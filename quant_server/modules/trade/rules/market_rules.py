# market_rules.py        # 市场规则

from typing import Dict, Any, Tuple
from .base_rule import RiskRule


class LiquidityRule(RiskRule):
    """流动性规则"""
    
    def __init__(self, min_liquidity: float = 1000000):
        """
        初始化流动性规则
        
        Args:
            min_liquidity: 最小流动性（成交额）
        """
        super().__init__(
            name="liquidity",
            description="检查股票流动性是否充足"
        )
        self.min_liquidity = min_liquidity
    
    async def check(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        检查股票流动性是否充足
        
        Args:
            data: 检查数据，包含 liquidity 或 volume, price
            
        Returns:
            (是否通过, 消息)
        """
        liquidity = data.get("liquidity")
        
        if not liquidity:
            volume = data.get("volume", 0)
            price = data.get("price", 0)
            liquidity = volume * price
        
        if liquidity < self.min_liquidity:
            return False, f"股票流动性不足: {liquidity:.2f} < {self.min_liquidity:.2f}"
        
        return True, "流动性检查通过"


class PriceRule(RiskRule):
    """价格规则"""
    
    def __init__(self, min_price: float = 1.0, max_price: float = 1000.0):
        """
        初始化价格规则
        
        Args:
            min_price: 最小价格
            max_price: 最大价格
        """
        super().__init__(
            name="price",
            description="检查股票价格是否在合理范围内"
        )
        self.min_price = min_price
        self.max_price = max_price
    
    async def check(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        检查股票价格是否在合理范围内
        
        Args:
            data: 检查数据，包含 price
            
        Returns:
            (是否通过, 消息)
        """
        price = data.get("price", 0)
        
        if price < self.min_price:
            return False, f"股票价格过低: {price:.2f} < {self.min_price:.2f}"
        
        if price > self.max_price:
            return False, f"股票价格过高: {price:.2f} > {self.max_price:.2f}"
        
        return True, "价格检查通过"


class VolatilityRule(RiskRule):
    """波动率规则"""
    
    def __init__(self, max_volatility: float = 0.1):
        """
        初始化波动率规则
        
        Args:
            max_volatility: 最大波动率
        """
        super().__init__(
            name="volatility",
            description="检查股票波动率是否超过限制"
        )
        self.max_volatility = max_volatility
    
    async def check(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        检查股票波动率是否超过限制
        
        Args:
            data: 检查数据，包含 volatility 或 high, low, close
            
        Returns:
            (是否通过, 消息)
        """
        volatility = data.get("volatility")
        
        if not volatility:
            high = data.get("high", 0)
            low = data.get("low", 0)
            close = data.get("close", 1)
            if close > 0:
                volatility = (high - low) / close
        
        if volatility and volatility > self.max_volatility:
            return False, f"股票波动率过高: {volatility:.2f} > {self.max_volatility:.2f}"
        
        return True, "波动率检查通过"


class MarketStatusRule(RiskRule):
    """市场状态规则"""
    
    def __init__(self):
        """
        初始化市场状态规则
        """
        super().__init__(
            name="market_status",
            description="检查市场状态是否正常"
        )
    
    async def check(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        检查市场状态是否正常
        
        Args:
            data: 检查数据，包含 market_status
            
        Returns:
            (是否通过, 消息)
        """
        market_status = data.get("market_status", "normal")
        
        if market_status != "normal":
            return False, f"市场状态异常: {market_status}"
        
        return True, "市场状态检查通过"