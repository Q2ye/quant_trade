# -*- coding: utf-8 -*-
"""
策略类注册表

单例注册表，统一管理策略类型→策略类的映射。
替代 scattered 的 _strategy_registry dict（StrategyManager）和
_engine_registry dict（EngineFactory）。

使用场景:
- 应用启动时扫描 strategies/ 目录自动注册
- StrategyManager 通过 registry.get(type) 获取策略类列表
- 前端查询可用策略类型列表（API 端点）
"""
import importlib
import inspect
import logging
from typing import Dict, List, Type, Optional

from modules.strategy.constants import StrategyType
from modules.strategy.strategies.base.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """
    策略类注册表 — 单例

    v1.1 重构说明:
    - 内部存储改为 Dict[StrategyType, List[Type[BaseStrategy]]]，
      支持一个类型注册多个策略类（修复原 Dict key 覆盖 Bug）
    - 提供 auto_discover() 使用 importlib + inspect 自动扫描
    - 参照 VN.PY 策略扫描机制
    """

    _instance: Optional["StrategyRegistry"] = None

    def __new__(cls) -> "StrategyRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._registry: Dict[StrategyType, List[Type[BaseStrategy]]] = {}
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._registry: Dict[StrategyType, List[Type[BaseStrategy]]] = {}
        self._initialized = True

    # ---- 注册 / 查询 ----

    def register(
        self,
        strategy_type: StrategyType,
        strategy_class: Type[BaseStrategy],
    ) -> None:
        """
        注册策略类

        Args:
            strategy_type: 策略类型枚举
            strategy_class: BaseStrategy 子类

        Raises:
            TypeError: strategy_class 不是 BaseStrategy 子类
        """
        if not issubclass(strategy_class, BaseStrategy):
            raise TypeError(
                f"{strategy_class.__name__} 必须是 BaseStrategy 的子类"
            )

        if strategy_type not in self._registry:
            self._registry[strategy_type] = []

        # 避免重复注册
        existing_names = [cls.__name__ for cls in self._registry[strategy_type]]
        if strategy_class.__name__ not in existing_names:
            self._registry[strategy_type].append(strategy_class)
            logger.info(
                f"注册策略: {strategy_type.value} -> {strategy_class.__name__}"
            )
        else:
            logger.debug(
                f"策略 {strategy_class.__name__} 已在 {strategy_type.value} 中注册，跳过"
            )

    def get(self, strategy_type: StrategyType) -> List[Type[BaseStrategy]]:
        """
        获取指定类型的所有已注册策略类

        Args:
            strategy_type: 策略类型枚举

        Returns:
            策略类列表（可能为空）
        """
        return self._registry.get(strategy_type, [])

    def get_first(self, strategy_type: StrategyType) -> Optional[Type[BaseStrategy]]:
        """
        获取指定类型的第一个已注册策略类（便捷方法）

        Args:
            strategy_type: 策略类型枚举

        Returns:
            策略类，未注册返回 None
        """
        classes = self._registry.get(strategy_type, [])
        return classes[0] if classes else None

    def list_all(self) -> List[Dict]:
        """
        返回所有已注册策略的元信息（名称/类型/参数说明）

        Returns:
            [{"type": "technical", "class": "MACDStrategy", "name": "MACD 信号策略"}, ...]
        """
        result = []
        for strategy_type, classes in self._registry.items():
            for cls in classes:
                # 从策略类中提取元信息
                instance_hint = getattr(cls, "name", cls.__name__)
                result.append({
                    "strategy_type": strategy_type.value,
                    "class_name": cls.__name__,
                    "display_name": instance_hint,
                    "module": cls.__module__,
                })
        return result

    def get_registered_types(self) -> List[StrategyType]:
        """返回所有已注册的策略类型"""
        return list(self._registry.keys())

    def get_class_count(self) -> int:
        """返回已注册的策略类总数"""
        return sum(len(classes) for classes in self._registry.values())

    # ---- 自动扫描 ----

    def auto_discover(
        self,
        package_path: str = "modules.strategy.strategies",
    ) -> int:
        """
        自动扫描 strategies/ 目录，注册所有 BaseStrategy 子类

        实现方式: importlib + inspect，类似 VN.PY 的策略扫描机制。
        扫描以下子包:
          - strategies.technical  → StrategyType.TECHNICAL
          - strategies.alpha      → StrategyType.ALPHA
          - strategies.ai         → StrategyType.ML / DL（按类名推断）

        Args:
            package_path: 策略包的 Python 导入路径

        Returns:
            注册的策略类数量
        """
        # 子包名 → 默认策略类型映射
        subpackage_type_map = {
            "technical": StrategyType.TECHNICAL,
            "alpha": StrategyType.ALPHA,
            "ai": StrategyType.ML,  # AI 子包中的类可能需要更细分的类型推断
        }

        registered_count = 0

        for subpackage, default_type in subpackage_type_map.items():
            try:
                full_path = f"{package_path}.{subpackage}"
                module = importlib.import_module(full_path)

                for name, obj in inspect.getmembers(module, inspect.isclass):
                    # 只注册 BaseStrategy 的子类，排除 BaseStrategy 本身
                    if (
                        issubclass(obj, BaseStrategy)
                        and obj is not BaseStrategy
                        and obj.__module__.startswith(package_path)
                    ):
                        # 尝试从策略类推断更精确的类型
                        inferred_type = self._infer_strategy_type(
                            obj, default_type
                        )
                        self.register(inferred_type, obj)
                        registered_count += 1

            except ImportError as e:
                logger.warning(f"无法导入策略子包 {subpackage}: {e}")
            except Exception as e:
                logger.error(f"扫描 {subpackage} 时出错: {e}")

        logger.info(
            f"策略自动扫描完成 — 共注册 {registered_count} 个策略类"
        )
        return registered_count

    def _infer_strategy_type(
        self,
        strategy_class: Type[BaseStrategy],
        default_type: StrategyType,
    ) -> StrategyType:
        """
        从策略类推断其 StrategyType

        推断规则（按优先级）:
        1. 类属性 strategy_type（如果定义了）
        2. 类名关键字匹配: "ML" → ML, "DL" → DL, "MACD"/"MACross" → TECHNICAL,
           "Factor" → ALPHA, "MeanRev" → MEAN_REVERSION
        3. 使用子包对应的默认类型

        Args:
            strategy_class: 策略类
            default_type: 子包默认类型

        Returns:
            推断的策略类型
        """
        # 规则 1: 类属性
        if hasattr(strategy_class, "strategy_type"):
            return strategy_class.strategy_type

        # 规则 2: 类名关键字匹配
        name = strategy_class.__name__.lower()
        if "ml" in name:
            return StrategyType.ML
        if "dl" in name:
            return StrategyType.DL
        if "macd" in name or "macross" in name:
            return StrategyType.TECHNICAL
        if "factor" in name:
            return StrategyType.ALPHA
        if "meanrev" in name:
            return StrategyType.MEAN_REVERSION

        # 规则 3: 默认类型
        return default_type

    # ---- 工具方法 ----

    def clear(self) -> None:
        """清空注册表（主要用于测试）"""
        self._registry.clear()
        logger.debug("策略注册表已清空")

    def is_empty(self) -> bool:
        """检查注册表是否为空"""
        return len(self._registry) == 0

    def __contains__(self, strategy_type: StrategyType) -> bool:
        return strategy_type in self._registry

    def __len__(self) -> int:
        return self.get_class_count()

    def __repr__(self) -> str:
        return (
            f"StrategyRegistry(types={len(self._registry)}, "
            f"classes={self.get_class_count()})"
        )
