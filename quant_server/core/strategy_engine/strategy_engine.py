# core/strategy_engine.py
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class StrategyEngine(ABC):
    """策略引擎基类 - 定义所有策略引擎的统一接口"""

    def __init__(self, main_engine, event_engine):
        self.main_engine = main_engine
        self.event_engine = event_engine
        self._strategies: Dict[str, Any] = {}

    @abstractmethod
    def add_strategy(self, strategy: Any) -> Any:
        """添加策略实例"""
        pass

    @abstractmethod
    def remove_strategy(self, strategy_name: str):
        """移除策略"""
        pass

    @abstractmethod
    def start_strategy(self, strategy_name: str, engine_type: str):
        """启动策略"""
        pass

    @abstractmethod
    def stop_strategy(self, strategy_name: str):
        """停止策略"""
        pass

    def get_strategies(self) -> List[Any]:
        """获取引擎中的所有策略实例列表"""
        return list(self._strategies.values())

    @property
    def strategies(self) -> Dict[str, Any]:
        """获取策略字典"""
        return self._strategies

    def get_strategy(self, strategy_name: str) -> Any:
        """获取指定策略"""
        return self._strategies.get(strategy_name)

    def has_strategy(self, strategy_name: str) -> bool:
        """检查策略是否存在"""
        return strategy_name in self._strategies

    def strategy_count(self) -> int:
        """获取策略数量"""
        return len(self._strategies)

    async def initialize(self):
        """初始化引擎"""
        pass