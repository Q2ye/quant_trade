# position_rules.py    # 仓位规则

from typing import Dict, Any, Tuple
from .base_rule import RiskRule


class PositionLimitRule(RiskRule):
    """仓位限制规则"""
    
    def __init__(self, max_position_ratio: float = 0.8):
        """
        初始化仓位限制规则
        
        Args:
            max_position_ratio: 最大仓位比例
        """
        super().__init__(
            name="position_limit",
            description="检查总仓位是否超过限制"
        )
        self.max_position_ratio = max_position_ratio
    
    async def check(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        检查总仓位是否超过限制
        
        Args:
            data: 检查数据，包含 total_asset, position_value
            
        Returns:
            (是否通过, 消息)
        """
        total_asset = data.get("total_asset", 0)
        position_value = data.get("position_value", 0)
        
        if total_asset <= 0:
            return True, "资产为0，跳过仓位检查"
        
        position_ratio = position_value / total_asset
        
        if position_ratio > self.max_position_ratio:
            return False, f"总仓位已达到上限: {position_ratio:.2f} > {self.max_position_ratio:.2f}"
        
        return True, "仓位限制检查通过"


class SinglePositionLimitRule(RiskRule):
    """单个仓位限制规则"""
    
    def __init__(self, max_single_position_ratio: float = 0.3):
        """
        初始化单个仓位限制规则
        
        Args:
            max_single_position_ratio: 单个股票最大仓位比例
        """
        super().__init__(
            name="single_position_limit",
            description="检查单个股票仓位是否超过限制"
        )
        self.max_single_position_ratio = max_single_position_ratio
    
    async def check(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        检查单个股票仓位是否超过限制
        
        Args:
            data: 检查数据，包含 total_asset, trade_amount
            
        Returns:
            (是否通过, 消息)
        """
        total_asset = data.get("total_asset", 0)
        trade_amount = data.get("trade_amount", 0)
        
        if total_asset <= 0:
            return True, "资产为0，跳过单个仓位检查"
        
        position_ratio = trade_amount / total_asset
        
        if position_ratio > self.max_single_position_ratio:
            return False, f"单个股票仓位已达到上限: {position_ratio:.2f} > {self.max_single_position_ratio:.2f}"
        
        return True, "单个仓位限制检查通过"


class PositionConcentrationRule(RiskRule):
    """仓位集中度规则"""
    
    def __init__(self, max_top_n_ratio: float = 0.6, top_n: int = 3):
        """
        初始化仓位集中度规则
        
        Args:
            max_top_n_ratio: 前N只股票最大仓位比例
            top_n: 前N只股票
        """
        super().__init__(
            name="position_concentration",
            description="检查仓位集中度是否超过限制"
        )
        self.max_top_n_ratio = max_top_n_ratio
        self.top_n = top_n
    
    async def check(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        检查仓位集中度是否超过限制
        
        Args:
            data: 检查数据，包含 positions, total_asset
            
        Returns:
            (是否通过, 消息)
        """
        positions = data.get("positions", [])
        total_asset = data.get("total_asset", 0)
        
        if total_asset <= 0 or not positions:
            return True, "资产为0或无持仓，跳过集中度检查"
        
        # 计算每个持仓的市值
        position_values = []
        for pos in positions:
            quantity = pos.get("quantity", pos.get("volume", 0))
            price = pos.get("current_price", 0)
            position_values.append(quantity * price)
        
        # 计算前N只股票的总市值
        position_values.sort(reverse=True)
        top_n_value = sum(position_values[:self.top_n])
        top_n_ratio = top_n_value / total_asset
        
        if top_n_ratio > self.max_top_n_ratio:
            return False, f"仓位集中度已达到上限: {top_n_ratio:.2f} > {self.max_top_n_ratio:.2f}"
        
        return True, "仓位集中度检查通过"