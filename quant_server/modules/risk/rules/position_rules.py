# position_rules.py    # 仓位规则

from typing import Dict, Any, Tuple
from .base_rule import RiskRule, RiskCheckResult


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

    async def check_with_severity(self, data: Dict[str, Any]) -> RiskCheckResult:
        total_asset = data.get("total_asset", 0)
        position_value = data.get("position_value", 0)
        if total_asset <= 0:
            return RiskCheckResult(True, "info", "资产为0，跳过仓位检查", "allow", self.name)
        ratio = position_value / total_asset
        if ratio > self.max_position_ratio * 1.1:
            return RiskCheckResult(False, "error",
                f"总仓位严重超限: {ratio:.2%} > {self.max_position_ratio * 1.1:.2%}", "block", self.name)
        if ratio > self.max_position_ratio:
            return RiskCheckResult(True, "warning",
                f"总仓位接近上限: {ratio:.2%} > {self.max_position_ratio:.2%}", "reduce_size", self.name)
        if ratio > self.max_position_ratio * 0.8:
            return RiskCheckResult(True, "info",
                f"总仓位偏高: {ratio:.2%}（上限 {self.max_position_ratio:.2%}）", "allow", self.name)
        return RiskCheckResult(True, "info", "仓位检查通过", "allow", self.name)


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


class StockStopLossRule(RiskRule):
    """个股止损规则"""

    def __init__(self, max_loss_percent: float = 0.08):
        super().__init__(
            name="stock_stop_loss",
            description="检查单只股票亏损是否超过止损线"
        )
        self.max_loss_percent = max_loss_percent

    async def check(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        ts_code = data.get("ts_code", "")
        cost_price = data.get("cost_price", 0)
        current_price = data.get("current_price", data.get("close", 0))

        if cost_price <= 0 or current_price <= 0:
            return True, "缺少成本价或现价，跳过个股止损检查"

        loss_pct = (cost_price - current_price) / cost_price
        if loss_pct > self.max_loss_percent:
            return False, f"股票 {ts_code} 亏损已达止损线: {loss_pct:.2%} > {self.max_loss_percent:.2%}"

        return True, "个股止损检查通过"


class SectorConcentrationRule(RiskRule):
    """行业集中度规则"""

    def __init__(self, max_sector_ratio: float = 0.5):
        super().__init__(
            name="sector_concentration",
            description="检查单一行业持仓是否超过限制"
        )
        self.max_sector_ratio = max_sector_ratio

    async def check(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        sector = data.get("sector", "")
        positions = data.get("positions", [])
        total_asset = data.get("total_asset", 0)

        if not sector or total_asset <= 0 or not positions:
            return True, "无行业或持仓数据，跳过行业集中度检查"

        # 计算该行业总持仓
        sector_value = sum(
            p.get("quantity", 0) * p.get("current_price", 0)
            for p in positions
            if p.get("sector") == sector
        )
        sector_ratio = sector_value / total_asset

        if sector_ratio > self.max_sector_ratio:
            return False, f"行业 {sector} 集中度超限: {sector_ratio:.2%} > {self.max_sector_ratio:.2%}"

        return True, "行业集中度检查通过"

    async def check_with_severity(self, data: Dict[str, Any]) -> RiskCheckResult:
        sector = data.get("sector", "")
        positions = data.get("positions", [])
        total_asset = data.get("total_asset", 0)
        if not sector or total_asset <= 0 or not positions:
            return RiskCheckResult(True, "info", "无行业或持仓数据，跳过检查", "allow", self.name)
        sector_value = sum(
            p.get("quantity", 0) * p.get("current_price", 0)
            for p in positions if p.get("sector") == sector
        )
        ratio = sector_value / total_asset
        if ratio > self.max_sector_ratio * 1.25:
            return RiskCheckResult(False, "error",
                f"行业 {sector} 集中度严重超限: {ratio:.2%} > {self.max_sector_ratio * 1.25:.2%}", "block", self.name)
        if ratio > self.max_sector_ratio:
            return RiskCheckResult(True, "warning",
                f"行业 {sector} 集中度偏高: {ratio:.2%} > {self.max_sector_ratio:.2%}", "reduce_size", self.name)
        return RiskCheckResult(True, "info", "行业集中度检查通过", "allow", self.name)


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