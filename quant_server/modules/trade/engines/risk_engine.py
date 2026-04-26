# risk_engine.py        # 风险控制引擎

from typing import Dict, Any, Optional, List, Tuple

from quant_server.core.engines import EngineConfigEntity
from quant_server.core.engines.base.engine_base import EngineBase
from quant_server.core.engines.system import EventEngine
from quant_server.core.engines.types.enums import EngineType
from quant_server.modules.trade.engines.position_engine import PositionEngine
from quant_server.modules.trade.managers.risk_manager import RiskManager


async def _check_liquidity(signal_data: Dict[str, Any]) -> Tuple[bool, str]:
    """检查流动性"""
    # 这里可以添加流动性检查逻辑
    # 例如检查股票的成交量、市值等
    _ = signal_data  # 避免未使用参数的警告
    return True, "流动性检查通过"


class RiskEngine(EngineBase):
    """风险控制引擎"""
    
    def __init__(
        self,
        config: Dict[str, Any],
        risk_manager: RiskManager,
        position_engine: PositionEngine,
        event_engine: Optional[EventEngine] = None
    ):

        # 创建 EngineConfig 实例
        config_obj = EngineConfigEntity(
            name=config.get("name", "risk_engine"),
            engine_type="risk_engine",
            dependencies=config.get("dependencies", []),
            max_retries=config.get("max_retries", 3),
            retry_delay=config.get("retry_delay", 1.0),
            config=config
        )
        
        super().__init__(config=config_obj, event_engine=event_engine)
        self.risk_manager = risk_manager
        self.position_engine = position_engine
        self.risk_check_enabled = config.get("risk_check_enabled", True)
    
    @property
    def engine_type(self) -> EngineType:
        """获取引擎类型"""
        return EngineType.RISK_ENGINE
    
    async def _on_initialize(self) -> None:
        """引擎特定的初始化逻辑"""
        pass
    
    async def _on_start(self) -> None:
        """引擎特定的启动逻辑"""
        print("风险引擎启动成功")
    
    async def _on_stop(self) -> None:
        """引擎特定的停止逻辑"""
        print("风险引擎停止成功")
    
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
        """启动风险引擎"""
        return await super().start()
    
    async def stop(self, force: bool = False, timeout: float = 30.0) -> bool:
        """停止风险引擎"""
        return await super().stop(force=force, timeout=timeout)
    
    async def check_signal(self, signal_data: Dict[str, Any]) -> Tuple[bool, str]:
        """检查信号是否符合风控规则"""
        if not self.risk_check_enabled:
            return True, "风控检查已禁用"
        
        # 执行各类风控规则检查
        checks = [
            self._check_position_limit,
            self._check_loss_limit,
            self._check_blacklist,
            _check_liquidity,
            self._check_account_balance
        ]
        
        for check_func in checks:
            is_valid, message = await check_func(signal_data)
            if not is_valid:
                return False, message
        
        return True, "风控检查通过"
    
    async def _check_position_limit(self, signal_data: Dict[str, Any]) -> Tuple[bool, str]:
        """检查仓位限制"""
        ts_code = signal_data.get("ts_code")
        direction = signal_data.get("direction")
        quantity = signal_data.get("quantity")
        price = signal_data.get("price")
        
        # 计算交易金额
        trade_amount = price * quantity
        
        # 获取当前持仓
        positions = await self.position_engine.get_position()
        total_asset = self.position_engine.get_total_asset()
        
        # 计算当前持仓比例
        current_position_value = self.position_engine.get_position_value()
        current_position_ratio = current_position_value / total_asset if total_asset > 0 else 0
        
        # 检查总仓位限制
        max_position_ratio = self.config.config.get("max_position_ratio", 0.8)
        if current_position_ratio > max_position_ratio:
            return False, f"总仓位已达到上限: {current_position_ratio:.2f} > {max_position_ratio:.2f}"
        
        # 检查单个股票仓位限制
        max_single_position_ratio = self.config.config.get("max_single_position_ratio", 0.3)
        if ts_code in [pos.get("symbol", pos.get("ts_code")) for pos in positions]:
            current_pos = self.position_engine.get_position_by_symbol(ts_code)
            if current_pos:
                quantity = current_pos.get("quantity", current_pos.get("volume", 0))
                current_price = current_pos.get("current_price", 0)
                current_pos_value = quantity * current_price
                if direction == "buy":
                    new_pos_value = current_pos_value + trade_amount
                    if new_pos_value / total_asset > max_single_position_ratio:
                        return False, f"单个股票仓位已达到上限"
        else:
            if direction == "buy" and trade_amount / total_asset > max_single_position_ratio:
                return False, f"单个股票仓位已达到上限"
        
        return True, "仓位限制检查通过"
    
    async def _check_loss_limit(self, signal_data: Dict[str, Any]) -> Tuple[bool, str]:
        """检查亏损限制"""
        total_asset = self.position_engine.get_total_asset()
        initial_capital = self.config.config.get("initial_capital", 1000000)
        
        # 计算当前亏损比例
        loss_percent = (initial_capital - total_asset) / initial_capital
        max_loss_percent = self.config.config.get("stop_loss_percent", 0.05)
        
        if loss_percent > max_loss_percent:
            return False, f"账户亏损已达到上限: {loss_percent:.2f} > {max_loss_percent:.2f}"
        
        return True, "亏损限制检查通过"
    
    async def _check_blacklist(self, signal_data: Dict[str, Any]) -> Tuple[bool, str]:
        """检查黑名单"""
        ts_code = signal_data.get("ts_code")
        blacklist = self.config.config.get("blacklist", [])
        
        if ts_code in blacklist:
            return False, f"股票 {ts_code} 在黑名单中"
        
        return True, "黑名单检查通过"

    async def _check_account_balance(self, signal_data: Dict[str, Any]) -> Tuple[bool, str]:
        """检查账户余额"""
        direction = signal_data.get("direction")
        quantity = signal_data.get("quantity")
        price = signal_data.get("price")
        
        if direction == "buy":
            trade_amount = price * quantity
            available_cash = self.position_engine.get_available_cash()
            if trade_amount > available_cash:
                return False, f"账户余额不足: 需要 {trade_amount:.2f}, 可用 {available_cash:.2f}"
        
        return True, "账户余额检查通过"
    
    async def check_position_risk(self) -> List[Dict[str, Any]]:
        """检查持仓风险"""
        risks = []
        positions = await self.position_engine.get_position()
        
        for pos in positions:
            # 检查单个持仓风险
            pnl_percent = (pos.get("current_price", 0) - pos.get("cost_price", 0)) / pos.get("cost_price", 1) if pos.get("cost_price", 0) > 0 else 0
            if abs(pnl_percent) > self.config.config.get("position_risk_threshold", 0.1):
                risks.append({
                    "ts_code": pos.get("symbol", pos.get("ts_code")),
                    "risk_type": "position_pnl",
                    "message": f"持仓盈亏比例过大: {pnl_percent:.2f}",
                    "level": "warning" if pnl_percent > 0 else "danger"
                })
        
        return risks