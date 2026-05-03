# signal_engine.py      # 信号处理引擎

import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

from core.engines import EngineConfigEntity
from core.engines.base.engine_base import EngineBase
from core.engines.system import EventEngine
from core.engines.types.enums import EngineType
from modules.trade.engines.execution_engine import ExecutionEngine
from modules.trade.engines.risk_engine import RiskEngine


class SignalEngine(EngineBase):
    """信号处理引擎"""
    
    def __init__(
        self,
        config: Dict[str, Any],
        execution_engine: ExecutionEngine,
        risk_engine: RiskEngine,
        event_engine: Optional[EventEngine] = None
    ):

        # 创建 EngineConfig 实例
        config_obj = EngineConfigEntity(
            name=config.get("name", "signal_engine"),
            engine_type="signal_engine",
            dependencies=config.get("dependencies", []),
            max_retries=config.get("max_retries", 3),
            retry_delay=config.get("retry_delay", 1.0),
            config=config
        )
        
        super().__init__(config=config_obj, event_engine=event_engine)
        self.execution_engine = execution_engine
        self.risk_engine = risk_engine
        self.signals = {}
        self.processed_signals = []
    
    @property
    def engine_type(self) -> EngineType:
        """获取引擎类型"""
        return EngineType.SIGNAL_ENGINE
    
    async def _on_initialize(self) -> None:
        """引擎特定的初始化逻辑"""
        pass
    
    async def _on_start(self) -> None:
        """引擎特定的启动逻辑"""
        if self.event_engine:
            from modules.strategy.events.signal_events import StrategySignalEvent
            self.event_engine.subscribe(StrategySignalEvent, self._on_strategy_signal)
        print("信号引擎启动成功")

    async def _on_strategy_signal(self, event) -> None:
        """处理策略信号事件，将信号送入风控→执行链路"""
        await self.process_signal(event.data)
    
    async def _on_stop(self) -> None:
        """引擎特定的停止逻辑"""
        print("信号引擎停止成功")
    
    async def _on_force_stop(self) -> None:
        """引擎特定的强制停止逻辑"""
        pass
    
    def _validate_config(self) -> None:
        """验证配置"""
        pass
    
    async def _check_dependencies(self) -> None:
        """检查依赖"""
        pass
    
    async def _start_background_tasks(self) -> None:
        """启动后台任务"""
        pass
    
    async def _stop_background_tasks(self) -> None:
        """停止后台任务"""
        pass
    
    async def _monitoring_loop(self) -> None:
        """监控循环"""
        pass
    
    async def start(self) -> bool:
        """启动信号引擎"""
        return await super().start()
    
    async def stop(self, force: bool = False, timeout: float = 30.0) -> bool:
        """停止信号引擎"""
        return await super().stop(force=force, timeout=timeout)
    
    async def process_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理信号"""
        # 生成信号ID
        signal_id = signal_data.get("signal_id", str(uuid.uuid4()))
        
        # 补充信号信息
        signal = {
            "signal_id": signal_id,
            "ts_code": signal_data.get("ts_code"),
            "direction": signal_data.get("direction"),
            "price": signal_data.get("price"),
            "quantity": signal_data.get("quantity"),
            "strategy_id": signal_data.get("strategy_id", "unknown"),
            "created_at": datetime.now().isoformat(),
            "status": "received",
            "message": "信号已接收"
        }
        
        # 保存信号
        self.signals[signal_id] = signal
        
        try:
            # 检查信号是否符合风控规则
            is_valid, message = await self.risk_engine.check_signal(signal)
            if not is_valid:
                signal["status"] = "rejected"
                signal["message"] = f"风控检查失败: {message}"
                self.processed_signals.append(signal)
                return signal
            
            # 执行信号
            execution_result = await self.execution_engine.execute_signal(signal)
            
            if execution_result["success"]:
                signal["status"] = "executed"
                signal["message"] = "信号执行成功"
                signal["order_id"] = execution_result["order"].get("order_id")
            else:
                signal["status"] = "failed"
                signal["message"] = f"信号执行失败: {execution_result.get('message')}"
            
        except Exception as e:
            signal["status"] = "error"
            signal["message"] = f"信号处理异常: {str(e)}"
        
        # 记录处理结果
        self.processed_signals.append(signal)
        
        # 发布信号处理完成事件
        if self.event_engine:
            # 这里可以发布信号处理完成事件
            pass
        
        return signal
    
    def get_signal(self, signal_id: str) -> Optional[Dict[str, Any]]:
        """获取信号信息"""
        return self.signals.get(signal_id)
    
    def get_signals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取信号列表"""
        signals = list(self.signals.values())
        if status:
            signals = [signal for signal in signals if signal.get("status") == status]
        return signals
    
    def get_processed_signals(self) -> List[Dict[str, Any]]:
        """获取已处理的信号"""
        return self.processed_signals
    
    def get_signals_by_strategy(self, strategy_id: str) -> List[Dict[str, Any]]:
        """根据策略ID获取信号"""
        return [signal for signal in self.signals.values() if signal.get("strategy_id") == strategy_id]
    
    async def batch_process_signals(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量处理信号"""
        results = []
        for signal_data in signals:
            result = await self.process_signal(signal_data)
            results.append(result)
        return results