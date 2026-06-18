# 交易模块

from typing import Optional, Dict, Any
from core.engines.base.engine_base import EngineBase
from core.engines.system import MainEngine, EventEngine

# 导入子模块
from .adapters import *
from .engines import *
from .events import *
from .managers import *
from .rules import *
from .services import *
from .tasks import *
from .utils import *

from .constants import *
from .schemas import *
from .handlers import (
    # TradeHandler 包装函数
    get_order_list,
    get_order_detail,
    create_order,
    cancel_order,
    get_position_list,
    get_position_detail,
    execute_signal,
    get_trade_history,
    get_account_summary,
    check_trade_module_health,
    # BasketHandler 包装函数
    get_basket_list,
    get_basket_detail,
    create_basket_item,
    update_basket_item,
    delete_basket_item,
    add_basket_item,
    adjust_basket_weight,
    remove_basket_item,
    get_basket_performance,
)

# 交易模块版本
__version__ = "1.0.0"

# 模块初始化函数
async def initialize(
    main_engine: Optional[MainEngine] = None,
    event_engine: Optional[EventEngine] = None,
    config: Optional[Dict[str, Any]] = None
) -> bool:
    """
    初始化交易模块
    
    Args:
        main_engine: 主引擎实例
        event_engine: 事件引擎实例
        config: 模块配置
    
    Returns:
        bool: 初始化是否成功
    """
    try:
        from modules.trade.engines.signal_engine import SignalEngine
        from modules.trade.engines.risk_engine import RiskEngine
        from modules.trade.engines.execution_engine import ExecutionEngine
        from modules.trade.engines.position_engine import PositionEngine
        from modules.trade.managers.trade_manager import TradeManager
        from modules.trade.managers.risk_manager import RiskManager
        from modules.trade.adapters.sim_adapter import SimBrokerAdapter
        
        # 从配置中获取交易设置
        trade_config = config or {}
        simulated_trading = trade_config.get("simulated_trading", True)
        initial_capital = trade_config.get("initial_capital", 1000000)
        broker = trade_config.get("broker", "sim")
        
        # 初始化交易管理器
        trade_manager = TradeManager(
            config=trade_config,
            event_engine=event_engine
        )
        
        # 初始化风险管理器
        risk_manager = RiskManager(
            config=trade_config,
            event_engine=event_engine
        )
        
        # 初始化券商适配器
        if simulated_trading or broker == "sim":
            broker_adapter = SimBrokerAdapter(
                config={
                    "initial_capital": initial_capital,
                    "simulated": True
                }
            )
        else:
            # 这里可以添加其他券商适配器的初始化
            broker_adapter = SimBrokerAdapter(
                config={
                    "initial_capital": initial_capital,
                    "simulated": True
                }
            )
        
        # 初始化持仓引擎
        position_engine = PositionEngine(
            config=trade_config,
            broker_adapter=broker_adapter,
            event_engine=event_engine
        )
        
        # 初始化风险引擎
        risk_engine = RiskEngine(
            config=trade_config,
            risk_manager=risk_manager,
            position_engine=position_engine,
            event_engine=event_engine
        )
        
        # 初始化执行引擎
        execution_engine = ExecutionEngine(
            config=trade_config,
            broker_adapter=broker_adapter,
            position_engine=position_engine,
            risk_engine=risk_engine,
            event_engine=event_engine
        )
        
        # 初始化信号引擎
        signal_engine = SignalEngine(
            config=trade_config,
            execution_engine=execution_engine,
            risk_engine=risk_engine,
            event_engine=event_engine
        )
        
        # 注册引擎到主引擎
        if main_engine:
            main_engine.register_engine("signal_engine", signal_engine)
            main_engine.register_engine("risk_engine", risk_engine)
            main_engine.register_engine("execution_engine", execution_engine)
            main_engine.register_engine("position_engine", position_engine)
            main_engine.register_engine("trade_manager", trade_manager)
            main_engine.register_engine("risk_manager", risk_manager)
        
        # 启动引擎
        await signal_engine.start()
        await risk_engine.start()
        await execution_engine.start()
        await position_engine.start()
        
        print("交易模块初始化成功")
        return True
        
    except Exception as e:
        print(f"交易模块初始化失败: {str(e)}")
        return False

# 模块关闭函数
async def shutdown() -> bool:
    """
    关闭交易模块
    
    Returns:
        bool: 关闭是否成功
    """
    try:
        # 这里可以添加关闭逻辑
        print("交易模块关闭成功")
        return True
    except Exception as e:
        print(f"交易模块关闭失败: {str(e)}")
        return False

# 导出所有组件
__all__ = [
    # 适配器
    "BrokerAdapter",
    "SimBrokerAdapter",
    "XTPBrokerAdapter",
    # 引擎
    "SignalEngine",
    "RiskEngine",
    "ExecutionEngine",
    "PositionEngine",
    # 事件
    "EventType",
    "OrderStatus",
    "TradeDirection",
    "RiskLevel",
    "OrderEvent",
    "OrderUpdateEvent",
    "ExecutionEvent",
    "ExecutionResultEvent",
    "PositionEvent",
    "PositionUpdateEvent",
    "RiskEvent",
    "RiskAlertEvent",
    # 管理器
    "TradeManager",
    "RiskManager",
    # 规则
    "BaseRule",
    "PositionLimitRule",
    "LossLimitRule",
    "BalanceRule",
    "BlacklistRule",
    "LiquidityRule",
    # 服务
    "SignalService",
    "OrderService",
    "ExecutionService",
    "PositionService",
    "RiskService",
    # 任务
    "ExecutionTask",
    "RiskTask",
    # 工具
    "CostCalculator",
    "OrderValidator",
    # Handler 包装函数 — 订单/持仓/信号
    "get_order_list",
    "get_order_detail",
    "create_order",
    "cancel_order",
    "get_position_list",
    "get_position_detail",
    "execute_signal",
    "get_trade_history",
    "get_account_summary",
    "check_trade_module_health",
    # Handler 包装函数 — 篮子管理
    "get_basket_list",
    "get_basket_detail",
    "create_basket_item",
    "update_basket_item",
    "delete_basket_item",
    "add_basket_item",
    "adjust_basket_weight",
    "remove_basket_item",
    "get_basket_performance",
    # 其他
    "initialize",
    "shutdown",
    "__version__"
]