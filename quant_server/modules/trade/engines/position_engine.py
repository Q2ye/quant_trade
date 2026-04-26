# position_engine.py    # 持仓管理引擎

from typing import Dict, Any, Optional, List
from datetime import datetime

from quant_server.core.engines import EngineConfigEntity
from quant_server.core.engines.base.engine_base import EngineBase
from quant_server.core.engines.system import EventEngine
from quant_server.core.engines.types.enums import EngineType
from quant_server.modules.trade.adapters.broker_adapter import BrokerAdapter


class PositionEngine(EngineBase):
    """持仓管理引擎"""
    
    def __init__(
        self,
        config: Dict[str, Any],
        broker_adapter: BrokerAdapter,
        event_engine: Optional[EventEngine] = None
    ):
        # 导入 EngineConfig 类

        # 创建 EngineConfig 实例
        config_obj = EngineConfigEntity(
            name=config.get("name", "position_engine"),
            engine_type="position_engine",
            dependencies=config.get("dependencies", []),
            max_retries=config.get("max_retries", 3),
            retry_delay=config.get("retry_delay", 1.0),
            config=config
        )
        
        super().__init__(config=config_obj, event_engine=event_engine)
        self.broker_adapter = broker_adapter
        self.positions = {}
        self.account = {}
        self.last_update_time = None
    
    @property
    def engine_type(self) -> EngineType:
        """获取引擎类型"""
        return EngineType.POSITION_ENGINE
    
    async def _on_initialize(self) -> None:
        """引擎特定的初始化逻辑"""
        pass
    
    async def _on_start(self) -> None:
        """引擎特定的启动逻辑"""
        await self._update_position()
        await self._update_account()
        print("持仓引擎启动成功")
    
    async def _on_stop(self) -> None:
        """引擎特定的停止逻辑"""
        print("持仓引擎停止成功")
    
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
        """启动持仓引擎"""
        return await super().start()
    
    async def stop(self, force: bool = False, timeout: float = 30.0) -> bool:
        """停止持仓引擎"""
        return await super().stop(force=force, timeout=timeout)
    
    async def get_position(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取持仓"""
        positions = await self.broker_adapter.get_position(symbol)
        # 确保使用正确的键来存储持仓
        self.positions = {pos.get("symbol", pos.get("ts_code")): pos for pos in positions}
        return positions
    
    async def get_account(self) -> Dict[str, Any]:
        """获取账户信息"""
        account = await self.broker_adapter.get_account()
        self.account = account
        return account
    
    async def update_position(self) -> bool:
        """更新持仓"""
        try:
            await self._update_position()
            await self._update_account()
            return True
        except Exception as e:
            print(f"更新持仓失败: {str(e)}")
            return False
    
    async def _update_position(self):
        """内部更新持仓"""
        positions = await self.broker_adapter.get_position()
        # 确保使用正确的键来存储持仓
        self.positions = {pos.get("symbol", pos.get("ts_code")): pos for pos in positions}
        self.last_update_time = datetime.now()
    
    async def _update_account(self):
        """内部更新账户"""
        account = await self.broker_adapter.get_account()
        self.account = account
    
    def get_position_by_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """根据股票代码获取持仓"""
        return self.positions.get(symbol)
    
    def get_total_asset(self) -> float:
        """获取总资产"""
        return self.account.get("total_asset", 0)
    
    def get_available_cash(self) -> float:
        """获取可用资金"""
        return self.account.get("cash", self.account.get("available", 0))
    
    def get_position_value(self) -> float:
        """获取持仓市值"""
        total_value = 0
        for pos in self.positions.values():
            quantity = pos.get("quantity", pos.get("volume", 0))
            current_price = pos.get("current_price", 0)
            total_value += quantity * current_price
        return total_value