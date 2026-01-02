# core/main_engine.py
import logging
from typing import Dict, Any

from .engines.alpha_engine import AlphaEngine
from .engines.backtest_engine import BacktestEngine
from .engines.cta_engine import CtaEngine
from .engines.risk_engine import RiskEngine
from .engines.selection_engine import SelectionEngine
from .engines.signal_engine import SignalEngine
from .engines.strategy_manager_engine import StrategyManagerEngine
from .event_engine import EventEngine, Event
from .strategy_engine import StrategyEngine

logger = logging.getLogger(__name__)


class MainEngine:
    """主引擎（系统协调中心）- 优化后版本"""

    def __init__(self):
        # 初始化事件引擎（系统的中枢神经）
        self.event_engine = EventEngine()

        # 引擎容器
        self.engines: Dict[str, Any] = {}

        # 注册通用事件处理
        self.event_engine.register_general(self._handle_event)

        logger.info("主引擎初始化完成")

    async def initialize(self):
        """异步初始化主引擎"""
        logger.info("初始化主引擎")

        # 初始化所有子引擎
        await self._init_engines()

        # 启动事件引擎
        self.event_engine.start()

        logger.info("主引擎初始化完成")

    async def _init_engines(self):
        """初始化所有子引擎"""
        # 初始化策略管理引擎
        self.engines["strategy_manager"] = StrategyManagerEngine(self, self.event_engine)
        await self.engines["strategy_manager"].initialize()
        logger.info("策略管理引擎初始化完成")

        # 初始化策略执行引擎
        self.engines["alpha"] = AlphaEngine(self, self.event_engine)
        logger.info("Alpha引擎初始化完成")

        self.engines["events"] = BacktestEngine(self, self.event_engine)
        logger.info("回测引擎初始化完成")

        self.engines["cta"] = CtaEngine(self, self.event_engine)
        logger.info("CTA引擎初始化完成")

        # 初始化其他引擎
        self.engines["selection"] = SelectionEngine(self, self.event_engine)
        logger.info("选股引擎初始化完成")

        self.engines["signal"] = SignalEngine(self, self.event_engine)
        logger.info("信号引擎初始化完成")

        self.engines["risk"] = RiskEngine(self, self.event_engine)
        logger.info("风控引擎初始化完成")

    def get_engine(self, engine_type: str) -> StrategyEngine:
        """获取指定类型的引擎"""
        return self.engines.get(engine_type)

    def broadcast_event(self, event: Event):
        """广播事件到所有引擎"""
        self.event_engine.put(event)

    def _handle_event(self, event: Event):
        """处理事件（用于WebSocket广播）"""
        # 这里会将事件发送到WebSocket管理器
        # 实际实现需要在WebSocketManager中处理
        pass

    async def shutdown(self):
        """关闭主引擎"""
        logger.info("关闭主引擎")

        # 停止事件引擎
        self.event_engine.stop()

        # 停止所有子引擎
        for engine_name, engine in self.engines.items():
            if hasattr(engine, "stop_engine"):
                logger.info(f"停止{engine_name}引擎")
                engine.stop_engine()