# execution_service.py  # 执行服务

from typing import Dict, Any
from modules.trade.engines.execution_engine import ExecutionEngine


class ExecutionService:
    """执行服务"""
    
    def __init__(self, execution_engine: ExecutionEngine):
        self.execution_engine = execution_engine
    
    async def execute_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行信号"""
        return await self.execution_engine.execute_signal(signal_data)
    
    async def execute_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行订单"""
        return await self.execution_engine.execute_order(order_data)
    
    async def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        return await self.execution_engine.cancel_order(order_id)
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """获取订单状态"""
        return await self.execution_engine.get_order_status(order_id)