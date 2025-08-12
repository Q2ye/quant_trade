import abc
from typing import Dict, Any, List


class StrategyEngine(abc.ABC):
    """策略引擎基类"""

    @property
    @abc.abstractmethod
    def strategies(self) -> Dict[str, Any]:
        """引擎管理的策略字典（名称->策略实例）"""
        pass


    @abc.abstractmethod
    def add_strategy(self, strategy: Any) -> Any:
        """添加策略实例"""
        pass

    @abc.abstractmethod
    def remove_strategy(self, strategy_name: str):
        """移除策略"""
        pass

    @abc.abstractmethod
    def start_strategy(self, strategy_name: str):
        """启动单个策略"""
        pass

    @abc.abstractmethod
    def stop_strategy(self, strategy_name: str):
        """停止单个策略"""
        pass

    @abc.abstractmethod
    def start_all_strategies(self):
        """启动所有策略"""
        pass

    @abc.abstractmethod
    def stop_all_strategies(self):
        """停止所有策略"""
        pass

    @abc.abstractmethod
    def run_engine(self, *args, **kwargs):
        """运行引擎主循环"""
        pass

    @abc.abstractmethod
    def stop_engine(self):
        """停止引擎"""
        pass

    @abc.abstractmethod
    def run_backtest(self, strategy_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """运行回测（统一接口）"""
        pass

    @abc.abstractmethod
    def get_strategies(self) -> List[Any]:
        """获取引擎中的所有策略实例列表"""
        pass