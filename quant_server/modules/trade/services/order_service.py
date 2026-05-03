# order_service.py      # 订单服务

from typing import Dict, Any, Optional, List
from modules.trade.engines.execution_engine import ExecutionEngine


class OrderService:
    """订单服务"""
    
    def __init__(self, execution_engine: ExecutionEngine):
        self.execution_engine = execution_engine
    
    async def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建订单"""
        return await self.execution_engine.execute_order(order_data)
    
    async def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        return await self.execution_engine.cancel_order(order_id)
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """获取订单状态"""
        return await self.execution_engine.get_order_status(order_id)
    
    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """获取订单信息"""
        return self.execution_engine.get_order(order_id)
    
    def get_orders(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取订单列表"""
        return self.execution_engine.get_orders(status)
    
    def get_trades(self) -> List[Dict[str, Any]]:
        """获取交易记录"""
        return self.execution_engine.get_trades()
    
    def get_trades_by_symbol(self, ts_code: str) -> List[Dict[str, Any]]:
        """根据股票代码获取交易记录"""
        return self.execution_engine.get_trades_by_symbol(ts_code)