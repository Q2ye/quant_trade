# account_rules.py      # 账户规则

from typing import Dict, Any, Tuple
from .base_rule import RiskRule


class AccountBalanceRule(RiskRule):
    """账户余额规则"""
    
    def __init__(self):
        """
        初始化账户余额规则
        """
        super().__init__(
            name="account_balance",
            description="检查账户余额是否充足"
        )
    
    async def check(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        检查账户余额是否充足
        
        Args:
            data: 检查数据，包含 direction, trade_amount, available_cash
            
        Returns:
            (是否通过, 消息)
        """
        direction = data.get("direction")
        trade_amount = data.get("trade_amount", 0)
        available_cash = data.get("available_cash", 0)
        
        if direction == "buy":
            if trade_amount > available_cash:
                return False, f"账户余额不足: 需要 {trade_amount:.2f}, 可用 {available_cash:.2f}"
        
        return True, "账户余额检查通过"


class LossLimitRule(RiskRule):
    """亏损限制规则"""
    
    def __init__(self, max_loss_percent: float = 0.05):
        """
        初始化亏损限制规则
        
        Args:
            max_loss_percent: 最大亏损比例
        """
        super().__init__(
            name="loss_limit",
            description="检查账户亏损是否超过限制"
        )
        self.max_loss_percent = max_loss_percent
    
    async def check(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        检查账户亏损是否超过限制
        
        Args:
            data: 检查数据，包含 total_asset, initial_capital
            
        Returns:
            (是否通过, 消息)
        """
        total_asset = data.get("total_asset", 0)
        initial_capital = data.get("initial_capital", total_asset)
        
        if initial_capital <= 0:
            return True, "初始资金为0，跳过亏损检查"
        
        loss_percent = (initial_capital - total_asset) / initial_capital
        
        if loss_percent > self.max_loss_percent:
            return False, f"账户亏损已达到上限: {loss_percent:.2f} > {self.max_loss_percent:.2f}"
        
        return True, "亏损限制检查通过"


class DrawdownLimitRule(RiskRule):
    """回撤限制规则"""
    
    def __init__(self, max_drawdown_percent: float = 0.1):
        """
        初始化回撤限制规则
        
        Args:
            max_drawdown_percent: 最大回撤比例
        """
        super().__init__(
            name="drawdown_limit",
            description="检查账户回撤是否超过限制"
        )
        self.max_drawdown_percent = max_drawdown_percent
    
    async def check(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        检查账户回撤是否超过限制
        
        Args:
            data: 检查数据，包含 total_asset, peak_asset
            
        Returns:
            (是否通过, 消息)
        """
        total_asset = data.get("total_asset", 0)
        peak_asset = data.get("peak_asset", total_asset)
        
        if peak_asset <= 0:
            return True, "峰值资产为0，跳过回撤检查"
        
        drawdown_percent = (peak_asset - total_asset) / peak_asset
        
        if drawdown_percent > self.max_drawdown_percent:
            return False, f"账户回撤已达到上限: {drawdown_percent:.2f} > {self.max_drawdown_percent:.2f}"
        
        return True, "回撤限制检查通过"


class TradeCountRule(RiskRule):
    """日交易次数限制规则"""

    def __init__(self, max_daily_trades: int = 10):
        super().__init__(
            name="trade_count",
            description="检查日内交易次数是否超过限制"
        )
        self.max_daily_trades = max_daily_trades

    async def check(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        daily_trade_count = data.get("daily_trade_count", 0)
        if daily_trade_count >= self.max_daily_trades:
            return False, f"日交易次数已达上限: {daily_trade_count} >= {self.max_daily_trades}"
        return True, "交易次数检查通过"


class CapitalChangeRule(RiskRule):
    """资金变化规则"""
    
    def __init__(self, max_daily_change_percent: float = 0.15):
        """
        初始化资金变化规则
        
        Args:
            max_daily_change_percent: 每日最大资金变化比例
        """
        super().__init__(
            name="capital_change",
            description="检查资金变化是否超过限制"
        )
        self.max_daily_change_percent = max_daily_change_percent
    
    async def check(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        检查资金变化是否超过限制
        
        Args:
            data: 检查数据，包含 total_asset, previous_asset
            
        Returns:
            (是否通过, 消息)
        """
        total_asset = data.get("total_asset", 0)
        previous_asset = data.get("previous_asset", total_asset)
        
        if previous_asset <= 0:
            return True, "之前资产为0，跳过资金变化检查"
        
        change_percent = abs(total_asset - previous_asset) / previous_asset
        
        if change_percent > self.max_daily_change_percent:
            return False, f"资金变化已达到上限: {change_percent:.2f} > {self.max_daily_change_percent:.2f}"
        
        return True, "资金变化检查通过"