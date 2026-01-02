"""
引擎工厂
提供统一的引擎创建、配置和管理服务，遵循工厂模式设计原则

设计目标：
1. 统一引擎创建流程，简化引擎初始化
2. 集中管理引擎配置，支持动态配置更新
3. 提供引擎依赖注入和生命周期管理
4. 支持引擎的懒加载和缓存
5. 提供引擎的配置验证和预检

工厂模式确保所有引擎的创建过程一致，便于管理和维护。
"""

import asyncio
import logging
import inspect
from typing import Dict, Any, List, Optional, Type, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime

# 导入统一类型定义
from ..types.entities import EngineConfig as EngineConfigEntity
from ..types.enums import (
    EngineType,
    EngineCategory,
    ComponentStatus,
    HealthStatus
)

# 导入引擎基类
from ..base.engine_base import EngineBase
from ..system.event_engine import EventEngine
from ..system.engine_registry import EngineRegistry

logger = logging.getLogger(__name__)


@dataclass
class EngineDescriptor:
    """引擎描述符

    描述引擎的元数据，用于引擎注册和发现。

    Attributes:
        engine_type: 引擎类型
        engine_class: 引擎类
        name: 引擎名称
        description: 引擎描述
        version: 引擎版本
        category: 引擎分类
        dependencies: 依赖的引擎类型
        config_schema: 配置模式
        tags: 标签（用于分类）
    """

    engine_type: EngineType
    engine_class: Type[EngineBase]
    name: str
    description: str = ""
    version: str = "1.0.0"
    category: EngineCategory = EngineCategory.UTILITY
    dependencies: List[EngineType] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """验证配置

        Args:
            config: 引擎配置

        Returns:
            List[str]: 验证错误信息列表，空列表表示配置有效
        """
        errors = []

        # 这里可以实现基于config_schema的配置验证
        # 简化的验证：检查必要字段
        required_fields = self.config_schema.get("required", [])
        for field_name in required_fields:
            if field_name not in config:
                errors.append(f"缺少必要字段: {field_name}")

        return errors

    def get_default_config(self) -> Dict[str, Any]:
        """获取默认配置

        Returns:
            Dict[str, Any]: 默认配置字典
        """
        return self.config_schema.get("default", {})

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            Dict[str, Any]: 字典表示
        """
        return {
            "engine_type": self.engine_type.value,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "category": self.category.value,
            "dependencies": [dep.value for dep in self.dependencies],
            "tags": self.tags,
            "config_schema": self.config_schema
        }


class EngineFactory:
    """引擎工厂

    单例模式的引擎工厂，负责创建和管理所有引擎实例。
    支持引擎注册、创建、配置注入、依赖解析和生命周期管理。

    Attributes:
        _instance: 单例实例
        _engine_descriptors: 引擎描述符注册表
        _engine_instances: 引擎实例缓存
        _event_engine: 共享事件引擎实例
        _engine_registry: 引擎注册表
        _initialized: 工厂是否已初始化
    """

    _instance: Optional['EngineFactory'] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化引擎工厂"""
        if not hasattr(self, '_initialized'):
            self._engine_descriptors: Dict[EngineType, EngineDescriptor] = {}
            self._engine_instances: Dict[str, EngineBase] = {}
            self._event_engine: Optional[EventEngine] = None
            self._engine_registry: Optional[EngineRegistry] = None
            self._initialized = False

            # 注册内置引擎类型
            self._register_builtin_engines()

            logger.info("引擎工厂初始化完成")

    def _register_builtin_engines(self):
        """注册内置引擎类型"""
        # 动态导入以避免循环依赖
        from ..system.main_engine import MainEngine
        from ..system.event_engine import EventEngine

        # 主引擎
        self.register_engine(
            EngineDescriptor(
                engine_type=EngineType.MAIN,
                engine_class=MainEngine,
                name="main_engine",
                description="系统主引擎，协调所有子引擎",
                category=EngineCategory.CORE,
                dependencies=[],
                config_schema={
                    "required": [],
                    "default": {
                        "system_name": "量化交易系统",
                        "version": "1.0.0",
                        "auto_start": True,
                        "max_retries": 3,
                        "health_check_interval": 60
                    }
                },
                tags=["core", "events"]
            )
        )

        # 事件引擎
        self.register_engine(
            EngineDescriptor(
                engine_type=EngineType.EVENT,
                engine_class=EventEngine,
                name="event_engine",
                description="事件驱动引擎，系统通信总线",
                category=EngineCategory.CORE,
                dependencies=[],
                config_schema={
                    "required": ["max_workers"],
                    "default": {
                        "max_workers": 10,
                        "queue_size": 10000,
                        "auto_start": True,
                        "max_retries": 3,
                        "health_check_interval": 30
                    }
                },
                tags=["core", "communication"]
            )
        )

        logger.debug(f"注册了 {len(self._engine_descriptors)} 个内置引擎类型")

    def register_engine(self, descriptor: EngineDescriptor):
        """注册引擎类型

        Args:
            descriptor: 引擎描述符

        Raises:
            ValueError: 引擎类型已注册或描述符无效
        """
        if descriptor.engine_type in self._engine_descriptors:
            raise ValueError(f"引擎类型已注册: {descriptor.engine_type}")

        # 验证引擎类
        if not inspect.isclass(descriptor.engine_class):
            raise ValueError(f"引擎类必须是类对象: {descriptor.engine_class}")

        if not issubclass(descriptor.engine_class, EngineBase):
            raise ValueError(f"引擎类必须继承自 EngineBase: {descriptor.engine_class}")

        self._engine_descriptors[descriptor.engine_type] = descriptor
        logger.info(f"注册引擎类型: {descriptor.engine_type.value} ({descriptor.name})")

    def unregister_engine(self, engine_type: EngineType):
        """注销引擎类型

        Args:
            engine_type: 引擎类型

        Raises:
            KeyError: 引擎类型不存在
        """
        if engine_type not in self._engine_descriptors:
            raise KeyError(f"引擎类型不存在: {engine_type}")

        descriptor = self._engine_descriptors[engine_type]
        del self._engine_descriptors[engine_type]

        logger.info(f"注销引擎类型: {engine_type.value} ({descriptor.name})")

    async def create_engine(self,
                           engine_type: EngineType,
                           config: Optional[Dict[str, Any]] = None,
                           instance_name: Optional[str] = None,
                           lazy_init: bool = False) -> EngineBase:
        """创建引擎实例

        Args:
            engine_type: 引擎类型
            config: 引擎配置（可选）
            instance_name: 实例名称（可选，默认使用描述符名称）
            lazy_init: 是否延迟初始化（只创建不启动）

        Returns:
            EngineBase: 创建的引擎实例

        Raises:
            KeyError: 引擎类型未注册
            ValueError: 配置验证失败或引擎创建失败
        """
        async with self._lock:
            # 检查引擎类型是否已注册
            if engine_type not in self._engine_descriptors:
                raise KeyError(f"引擎类型未注册: {engine_type}")

            descriptor = self._engine_descriptors[engine_type]

            # 生成实例名称
            if not instance_name:
                instance_name = descriptor.name
                # 如果已有同名实例，添加后缀
                suffix = 1
                while instance_name in self._engine_instances:
                    instance_name = f"{descriptor.name}_{suffix}"
                    suffix += 1

            # 检查是否已有该实例
            if instance_name in self._engine_instances:
                logger.warning(f"引擎实例已存在: {instance_name}")
                return self._engine_instances[instance_name]

            # 准备配置
            engine_config = self._prepare_engine_config(descriptor, config or {})

            # 验证配置
            config_errors = descriptor.validate_config(engine_config)
            if config_errors:
                raise ValueError(f"引擎配置验证失败: {config_errors}")

            # 创建引擎配置实体
            engine_config_entity = EngineConfigEntity(
                name=instance_name,
                engine_type=descriptor.engine_type.value,
                auto_start=engine_config.get("auto_start", True),
                max_retries=engine_config.get("max_retries", 3),
                retry_delay=engine_config.get("retry_delay", 1.0),
                config=engine_config,
                dependencies=[dep.value for dep in descriptor.dependencies],
                health_check_interval=engine_config.get("health_check_interval", 60.0),
                graceful_shutdown_timeout=engine_config.get("graceful_shutdown_timeout", 30.0)
            )

            # 创建引擎实例
            try:
                logger.info(f"创建引擎实例: {instance_name} ({engine_type.value})")

                # 获取共享事件引擎
                event_engine = await self._get_shared_event_engine()

                # 创建引擎实例
                engine_instance = descriptor.engine_class(engine_config_entity, event_engine)

                # 设置引擎类型
                engine_instance.record.engine_type = engine_type

                # 保存到缓存
                self._engine_instances[instance_name] = engine_instance

                # 初始化引擎依赖
                await self._resolve_dependencies(engine_instance, descriptor)

                # 如果不是延迟初始化，启动引擎
                if not lazy_init:
                    await engine_instance.start()

                # 注册到引擎注册表
                if self._engine_registry:
                    await self._engine_registry.register_engine(engine_instance)

                logger.info(f"引擎实例创建成功: {instance_name}")
                return engine_instance

            except Exception as e:
                logger.error(f"创建引擎实例失败: {instance_name}, 错误: {e}")
                # 清理失败的实例
                if instance_name in self._engine_instances:
                    del self._engine_instances[instance_name]
                raise

    async def get_engine(self, instance_name: str) -> Optional[EngineBase]:
        """获取引擎实例

        Args:
            instance_name: 引擎实例名称

        Returns:
            Optional[EngineBase]: 引擎实例，不存在时返回None
        """
        return self._engine_instances.get(instance_name)

    async def get_or_create_engine(self,
                                  engine_type: EngineType,
                                  config: Optional[Dict[str, Any]] = None,
                                  instance_name: Optional[str] = None) -> EngineBase:
        """获取或创建引擎实例

        Args:
            engine_type: 引擎类型
            config: 引擎配置（可选）
            instance_name: 实例名称（可选）

        Returns:
            EngineBase: 引擎实例
        """
        if not instance_name:
            descriptor = self._engine_descriptors[engine_type]
            instance_name = descriptor.name

        engine = await self.get_engine(instance_name)
        if engine:
            return engine

        return await self.create_engine(engine_type, config, instance_name)

    async def destroy_engine(self, instance_name: str, force: bool = False) -> bool:
        """销毁引擎实例

        Args:
            instance_name: 引擎实例名称
            force: 是否强制销毁（不执行优雅停止）

        Returns:
            bool: 销毁是否成功
        """
        async with self._lock:
            if instance_name not in self._engine_instances:
                logger.warning(f"引擎实例不存在: {instance_name}")
                return False

            engine = self._engine_instances[instance_name]

            try:
                # 从注册表注销
                if self._engine_registry:
                    await self._engine_registry.unregister_engine(instance_name)

                # 停止引擎
                if not force:
                    await engine.stop()

                # 从缓存移除
                del self._engine_instances[instance_name]

                logger.info(f"引擎实例销毁成功: {instance_name}")
                return True

            except Exception as e:
                logger.error(f"销毁引擎实例失败: {instance_name}, 错误: {e}")
                if force:
                    # 强制移除
                    del self._engine_instances[instance_name]
                    return True
                return False

    async def initialize_factory(self,
                                event_engine: Optional[EventEngine] = None,
                                engine_registry: Optional[EngineRegistry] = None):
        """初始化工厂

        Args:
            event_engine: 共享事件引擎实例（可选）
            engine_registry: 引擎注册表实例（可选）
        """
        if self._initialized:
            logger.warning("引擎工厂已经初始化")
            return

        # 设置共享事件引擎
        if event_engine:
            self._event_engine = event_engine

        # 设置引擎注册表
        if engine_registry:
            self._engine_registry = engine_registry
        else:
            # 创建默认注册表
            from ..system.engine_registry import EngineRegistry
            self._engine_registry = EngineRegistry()

        self._initialized = True
        logger.info("引擎工厂初始化完成")

    def get_engine_descriptor(self, engine_type: EngineType) -> Optional[EngineDescriptor]:
        """获取引擎描述符

        Args:
            engine_type: 引擎类型

        Returns:
            Optional[EngineDescriptor]: 引擎描述符，不存在时返回None
        """
        return self._engine_descriptors.get(engine_type)

    def list_engine_types(self) -> List[EngineType]:
        """获取所有已注册的引擎类型

        Returns:
            List[EngineType]: 引擎类型列表
        """
        return list(self._engine_descriptors.keys())

    def list_engine_instances(self) -> List[str]:
        """获取所有引擎实例名称

        Returns:
            List[str]: 引擎实例名称列表
        """
        return list(self._engine_instances.keys())

    async def get_engine_status(self, instance_name: str) -> Optional[Dict[str, Any]]:
        """获取引擎状态

        Args:
            instance_name: 引擎实例名称

        Returns:
            Optional[Dict[str, Any]]: 引擎状态信息，不存在时返回None
        """
        engine = await self.get_engine(instance_name)
        if not engine:
            return None

        return engine.get_status_info()

    async def get_all_engine_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有引擎状态

        Returns:
            Dict[str, Dict[str, Any]]: 引擎状态字典 {instance_name: status_info}
        """
        status_dict = {}

        for instance_name, engine in self._engine_instances.items():
            try:
                status_dict[instance_name] = engine.get_status_info()
            except Exception as e:
                logger.error(f"获取引擎状态失败: {instance_name}, 错误: {e}")
                status_dict[instance_name] = {
                    "error": str(e),
                    "status": "unknown"
                }

        return status_dict

    async def restart_engine(self, instance_name: str) -> bool:
        """重启引擎

        Args:
            instance_name: 引擎实例名称

        Returns:
            bool: 重启是否成功
        """
        engine = await self.get_engine(instance_name)
        if not engine:
            logger.error(f"引擎实例不存在: {instance_name}")
            return False

        try:
            await engine.restart()
            logger.info(f"引擎重启成功: {instance_name}")
            return True
        except Exception as e:
            logger.error(f"引擎重启失败: {instance_name}, 错误: {e}")
            return False

    async def shutdown_all_engines(self, force: bool = False) -> Dict[str, bool]:
        """关闭所有引擎

        Args:
            force: 是否强制关闭

        Returns:
            Dict[str, bool]: 关闭结果字典 {instance_name: success}
        """
        logger.info(f"开始关闭所有引擎 (force={force})")

        results = {}

        # 按照依赖关系的逆序关闭
        sorted_engines = await self._sort_engines_by_dependency(reverse=True)

        for instance_name in sorted_engines:
            try:
                success = await self.destroy_engine(instance_name, force)
                results[instance_name] = success
            except Exception as e:
                logger.error(f"关闭引擎失败: {instance_name}, 错误: {e}")
                results[instance_name] = False

        logger.info(f"所有引擎关闭完成，成功: {sum(results.values())}/{len(results)}")
        return results

    def _prepare_engine_config(self, descriptor: EngineDescriptor,
                              config: Dict[str, Any]) -> Dict[str, Any]:
        """准备引擎配置

        Args:
            descriptor: 引擎描述符
            config: 用户提供的配置

        Returns:
            Dict[str, Any]: 合并后的配置
        """
        # 获取默认配置
        default_config = descriptor.get_default_config()

        # 合并配置
        merged_config = {**default_config, **config}

        return merged_config

    async def _get_shared_event_engine(self) -> Optional[EventEngine]:
        """获取共享事件引擎

        Returns:
            Optional[EventEngine]: 事件引擎实例
        """
        if self._event_engine:
            return self._event_engine

        # 尝试获取事件引擎实例
        event_engine = await self.get_engine("event_engine")
        if event_engine:
            self._event_engine = event_engine

        return self._event_engine

    async def _resolve_dependencies(self, engine: EngineBase,
                                   descriptor: EngineDescriptor):
        """解析引擎依赖

        Args:
            engine: 引擎实例
            descriptor: 引擎描述符
        """
        for dep_type in descriptor.dependencies:
            try:
                dep_descriptor = self.get_engine_descriptor(dep_type)

                if not dep_descriptor:
                    logger.warning(f"依赖引擎类型未注册: {dep_type.value}")
                    continue

                # 获取或创建依赖引擎
                dep_engine = await self.get_or_create_engine(
                    dep_type,
                    instance_name=dep_descriptor.name
                )

                # 添加依赖
                engine.add_dependency(dep_engine)

                logger.debug(f"引擎 {engine.config.name} 添加依赖: {dep_engine.config.name}")

            except Exception as e:
                logger.error(f"解析依赖失败: {dep_type.value}, 错误: {e}")

    async def _sort_engines_by_dependency(self, reverse: bool = False) -> List[str]:
        """按照依赖关系排序引擎

        Args:
            reverse: 是否逆序排序（True: 依赖多的在前，False: 依赖少的在前）

        Returns:
            List[str]: 排序后的引擎实例名称列表
        """
        # 构建依赖图
        dependency_graph = {}

        for instance_name, engine in self._engine_instances.items():
            dependencies = []

            # 获取引擎的依赖
            for dep_name in engine.dependencies.keys():
                if dep_name in self._engine_instances:
                    dependencies.append(dep_name)

            dependency_graph[instance_name] = dependencies

        # 拓扑排序
        def topological_sort(graph: Dict[str, List[str]]) -> List[str]:
            """拓扑排序"""
            in_degree = {node: 0 for node in graph}
            for node in graph:
                for neighbor in graph[node]:
                    if neighbor in in_degree:
                        in_degree[neighbor] += 1

            queue = [node for node in graph if in_degree[node] == 0]
            result = []

            while queue:
                node = queue.pop(0)
                result.append(node)

                for neighbor in graph.get(node, []):
                    if neighbor in in_degree:
                        in_degree[neighbor] -= 1
                        if in_degree[neighbor] == 0:
                            queue.append(neighbor)

            # 检查是否有环
            if len(result) != len(graph):
                logger.warning("依赖图中存在环，无法完全排序")
                # 将未排序的节点添加到结果末尾
                for node in graph:
                    if node not in result:
                        result.append(node)

            return result

        sorted_engines = topological_sort(dependency_graph)

        if reverse:
            sorted_engines = list(reversed(sorted_engines))

        return sorted_engines

    def __str__(self) -> str:
        """字符串表示

        Returns:
            str: 引擎工厂的字符串表示
        """
        return (f"EngineFactory("
                f"engines={len(self._engine_instances)}, "
                f"types={len(self._engine_descriptors)})")


# 全局工厂实例
_factory: Optional[EngineFactory] = None


async def get_engine_factory() -> EngineFactory:
    """获取全局引擎工厂实例

    Returns:
        EngineFactory: 引擎工厂实例
    """
    global _factory
    if _factory is None:
        _factory = EngineFactory()
        await _factory.initialize_factory()
    return _factory


async def create_engine(engine_type: EngineType,
                       config: Optional[Dict[str, Any]] = None,
                       instance_name: Optional[str] = None) -> EngineBase:
    """创建引擎（便捷函数）

    Args:
        engine_type: 引擎类型
        config: 引擎配置
        instance_name: 实例名称

    Returns:
        EngineBase: 创建的引擎实例
    """
    factory = await get_engine_factory()
    return await factory.create_engine(engine_type, config, instance_name)


async def get_engine(instance_name: str) -> Optional[EngineBase]:
    """获取引擎实例（便捷函数）

    Args:
        instance_name: 引擎实例名称

    Returns:
        Optional[EngineBase]: 引擎实例
    """
    factory = await get_engine_factory()
    return await factory.get_engine(instance_name)