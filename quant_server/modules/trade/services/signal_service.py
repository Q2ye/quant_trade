# signal_service.py      # 信号服务

from typing import Dict, Any, Optional, List
from modules.trade.engines.signal_engine import SignalEngine


class SignalService:
    """信号服务"""
    
    def __init__(self, signal_engine: SignalEngine):
        self.signal_engine = signal_engine
    
    async def process_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理信号"""
        return await self.signal_engine.process_signal(signal_data)
    
    async def batch_process_signals(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量处理信号"""
        return await self.signal_engine.batch_process_signals(signals)
    
    def get_signal(self, signal_id: str) -> Optional[Dict[str, Any]]:
        """获取信号信息"""
        return self.signal_engine.get_signal(signal_id)
    
    def get_signals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取信号列表"""
        return self.signal_engine.get_signals(status)
    
    def get_processed_signals(self) -> List[Dict[str, Any]]:
        """获取已处理的信号"""
        return self.signal_engine.get_processed_signals()
    
    def get_signals_by_strategy(self, strategy_id: str) -> List[Dict[str, Any]]:
        """根据策略ID获取信号"""
        return self.signal_engine.get_signals_by_strategy(strategy_id)