# position_service.py    # 持仓服务

from typing import Dict, Any, Optional, List
from quant_server.modules.trade.engines.position_engine import PositionEngine


class PositionService:
    """持仓服务"""
    
    def __init__(self, position_engine: PositionEngine):
        self.position_engine = position_engine
    
    async def get_position(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取持仓"""
        return await self.position_engine.get_position(symbol)
    
    async def get_account(self) -> Dict[str, Any]:
        """获取账户信息"""
        return await self.position_engine.get_account()
    
    async def update_position(self) -> bool:
        """更新持仓"""
        return await self.position_engine.update_position()
    
    def get_position_by_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """根据股票代码获取持仓"""
        return self.position_engine.get_position_by_symbol(symbol)
    
    def get_total_asset(self) -> float:
        """获取总资产"""
        return self.position_engine.get_total_asset()
    
    def get_available_cash(self) -> float:
        """获取可用资金"""
        return self.position_engine.get_available_cash()
    
    def get_position_value(self) -> float:
        """获取持仓市值"""
        return self.position_engine.get_position_value()