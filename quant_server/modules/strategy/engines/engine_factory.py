# -*- coding: utf-8 -*-
"""
引擎工厂
根据策略类型创建对应的策略引擎
"""
import logging
from typing import Dict, Type, Optional

from modules.strategy.constants import StrategyType
from modules.strategy.engines.strategy_manager import StrategyManager

logger = logging.getLogger(__name__)


class EngineFactory:
    """
    策略引擎工厂

    负责根据策略类型创建对应的引擎实例
    """

    def __init__(self, event_engine=None):
        """
        初始化工厂

        Args:
            event_engine: 事件引擎
        """
        self.event_engine = event_engine

        # 引擎类注册表
        self._engine_registry: Dict[StrategyType, Type] = {}

        # 注册默认引擎
        self._register_default_engines()

    def _register_default_engines(self) -> None:
        """
        注册默认引擎

        v1.1 重构: CTAEngine/AlphaEngine/AIEngine 已删除（功能被 StrategyManager
        + BaseStrategy 子类覆盖）。所有策略类型统一使用 StrategyManager 驱动。
        EngineFactory 保留以支持向后兼容的 create_engine() 接口。
        """
        logger.info(
            "引擎工厂已初始化 — 所有策略类型统一由 StrategyManager 驱动"
        )

    def register_engine(
        self,
        strategy_type: StrategyType,
        engine_class: Type
    ) -> None:
        """
        注册引擎类

        Args:
            strategy_type: 策略类型
            engine_class: 引擎类
        """
        self._engine_registry[strategy_type] = engine_class
        logger.info(f"注册引擎: {strategy_type.value} -> {engine_class.__name__}")

    def create_engine(
        self,
        strategy_type: StrategyType,
        **kwargs
    ):
        """
        创建引擎实例

        Args:
            strategy_type: 策略类型
            **kwargs: 引擎初始化参数

        Returns:
            引擎实例

        Raises:
            ValueError: 未注册的策略类型
        """
        engine_class = self._engine_registry.get(strategy_type)

        if not engine_class:
            # 如果没有专用引擎，使用默认的策略管理器
            logger.warning(
                f"未找到策略类型 {strategy_type} 的专用引擎，"
                f"使用默认的 StrategyManager"
            )
            return StrategyManager(event_engine=self.event_engine)

        # 创建引擎实例
        engine = engine_class(
            event_engine=self.event_engine,
            **kwargs
        )

        logger.info(f"创建引擎: {strategy_type.value} -> {engine_class.__name__}")

        return engine

    def get_engine_class(
        self,
        strategy_type: StrategyType
    ) -> Optional[Type]:
        """
        获取引擎类

        Args:
            strategy_type: 策略类型

        Returns:
            引擎类，如果未注册返回None
        """
        return self._engine_registry.get(strategy_type)

    def get_registered_engines(self) -> Dict[str, str]:
        """
        获取已注册的引擎列表

        Returns:
            引擎注册表
        """
        return {
            key.value: cls.__name__
            for key, cls in self._engine_registry.items()
        }
