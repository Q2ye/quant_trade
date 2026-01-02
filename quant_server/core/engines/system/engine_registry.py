"""
引擎注册表
统一管理所有引擎实例，提供引擎的注册、查找、分类和统计功能

核心功能：
1. 引擎实例的全局注册和管理
2. 引擎的分类和标签管理
3. 引擎依赖关系跟踪
4. 引擎状态聚合和统计
5. 引擎发现和查询接口

注册表作为引擎的"电话簿"，提供便捷的引擎查找和管理功能。
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# 导入统一类型定义
from ..types.enums import (
    EngineType,
    EngineCategory,
    ComponentStatus,
    HealthStatus,
    PriorityLevel
)

# 导入引擎基类
from ..base.engine_base import EngineBase

logger = logging.getLogger(__name__)


@dataclass
class EngineRecord:
    """引擎注册记录

    存储引擎实例的注册信息和元数据，支持快速查询和索引。

    Attributes:
        engine: 引擎实例
        category: 引擎分类
        tags: 标签集合
        metadata: 元数据
        registered_at: 注册时间
        last_updated: 最后更新时间
    """

    engine: EngineBase
    category: EngineCategory
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    def update_metadata(self, metadata: Dict[str, Any]) -> None:
        """更新元数据

        Args:
            metadata: 新的元数据
        """
        self.metadata.update(metadata)
        self.last_updated = datetime.now()

    def add_tag(self, tag: str) -> None:
        """添加标签

        Args:
            tag: 标签
        """
        if tag not in self.tags:
            self.tags.add(tag)
            self.last_updated = datetime.now()

    def remove_tag(self, tag: str) -> bool:
        """移除标签

        Args:
            tag: 标签

        Returns:
            bool: 是否成功移除
        """
        if tag in self.tags:
            self.tags.remove(tag)
            self.last_updated = datetime.now()
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            Dict[str, Any]: 字典表示
        """
        status_info = self.engine.get_status_info()

        return {
            "engine_id": self.engine.engine_id,
            "engine_name": self.engine.config.name,
            "engine_type": self.engine.record.engine_type.value,
            "category": self.category.value,
            "tags": list(self.tags),
            "metadata": self.metadata,
            "registered_at": self.registered_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "status": status_info.get("status"),
            "health": status_info.get("health"),
            "uptime": status_info.get("uptime", 0),
            "config": status_info.get("config", {}),
            "metrics": status_info.get("metrics", {})
        }


class EngineRegistry:
    """引擎注册表

    单例模式的引擎注册表，负责管理所有引擎实例的注册和查找。
    支持引擎分类、标签管理、状态聚合和统计查询。

    Attributes:
        _instance: 单例实例
        _engines: 引擎记录字典 {engine_name: EngineRecord}
        _category_index: 分类索引 {category: Set[engine_name]}
        _tag_index: 标签索引 {tag: Set[engine_name]}
        _status_index: 状态索引 {status: Set[engine_name]}
        _health_index: 健康索引 {health: Set[engine_name]}
        _type_index: 类型索引 {engine_type: Set[engine_name]}
        _lock: 异步锁
    """

    _instance: Optional['EngineRegistry'] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化引擎注册表"""
        if not hasattr(self, '_initialized'):
            self._engines: Dict[str, EngineRecord] = {}
            self._category_index: Dict[EngineCategory, Set[str]] = {}
            self._tag_index: Dict[str, Set[str]] = {}
            self._status_index: Dict[ComponentStatus, Set[str]] = {}
            self._health_index: Dict[HealthStatus, Set[str]] = {}
            self._type_index: Dict[EngineType, Set[str]] = {}
            self._initialized = True

            logger.info("引擎注册表初始化完成")

    async def register_engine(self,
                             engine: EngineBase,
                             category: EngineCategory = EngineCategory.BUSINESS,
                             tags: Optional[List[str]] = None,
                             metadata: Optional[Dict[str, Any]] = None) -> bool:
        """注册引擎

        Args:
            engine: 引擎实例
            category: 引擎分类
            tags: 标签列表
            metadata: 元数据

        Returns:
            bool: 注册是否成功

        Raises:
            ValueError: 引擎已注册或参数无效
        """
        async with self._lock:
            engine_name = engine.config.name

            # 检查引擎是否已注册
            if engine_name in self._engines:
                logger.warning(f"引擎已注册: {engine_name}")
                return False

            # 创建引擎记录
            engine_record = EngineRecord(
                engine=engine,
                category=category,
                tags=set(tags or []),
                metadata=metadata or {}
            )

            # 保存引擎记录
            self._engines[engine_name] = engine_record

            # 更新索引
            self._update_indexes(engine_name, engine_record)

            logger.info(f"引擎注册成功: {engine_name} ({category.value})")
            return True

    async def unregister_engine(self, engine_name: str) -> bool:
        """注销引擎

        Args:
            engine_name: 引擎名称

        Returns:
            bool: 注销是否成功
        """
        async with self._lock:
            if engine_name not in self._engines:
                logger.warning(f"引擎不存在: {engine_name}")
                return False

            # 从索引中移除
            self._remove_from_indexes(engine_name)

            # 从注册表中移除
            del self._engines[engine_name]

            logger.info(f"引擎注销成功: {engine_name}")
            return True

    async def update_engine_metadata(self,
                                    engine_name: str,
                                    metadata: Dict[str, Any]) -> bool:
        """更新引擎元数据

        Args:
            engine_name: 引擎名称
            metadata: 元数据

        Returns:
            bool: 更新是否成功
        """
        async with self._lock:
            if engine_name not in self._engines:
                logger.warning(f"引擎不存在: {engine_name}")
                return False

            engine_record = self._engines[engine_name]
            engine_record.update_metadata(metadata)

            logger.debug(f"引擎元数据更新: {engine_name}")
            return True

    async def add_engine_tag(self, engine_name: str, tag: str) -> bool:
        """添加引擎标签

        Args:
            engine_name: 引擎名称
            tag: 标签

        Returns:
            bool: 添加是否成功
        """
        async with self._lock:
            if engine_name not in self._engines:
                logger.warning(f"引擎不存在: {engine_name}")
                return False

            engine_record = self._engines[engine_name]

            # 标签已存在则直接返回成功
            if tag in engine_record.tags:
                return True

            # 添加到标签索引
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(engine_name)

            # 添加到引擎记录
            engine_record.add_tag(tag)

            logger.debug(f"引擎标签添加: {engine_name} -> {tag}")
            return True

    async def remove_engine_tag(self, engine_name: str, tag: str) -> bool:
        """移除引擎标签

        Args:
            engine_name: 引擎名称
            tag: 标签

        Returns:
            bool: 移除是否成功
        """
        async with self._lock:
            if engine_name not in self._engines:
                logger.warning(f"引擎不存在: {engine_name}")
                return False

            engine_record = self._engines[engine_name]

            # 从标签索引中移除
            if tag in self._tag_index and engine_name in self._tag_index[tag]:
                self._tag_index[tag].remove(engine_name)
                if not self._tag_index[tag]:
                    del self._tag_index[tag]

            # 从引擎记录中移除
            return engine_record.remove_tag(tag)

    async def change_engine_category(self,
                                    engine_name: str,
                                    category: EngineCategory) -> bool:
        """更改引擎分类

        Args:
            engine_name: 引擎名称
            category: 新分类

        Returns:
            bool: 更改是否成功
        """
        async with self._lock:
            if engine_name not in self._engines:
                logger.warning(f"引擎不存在: {engine_name}")
                return False

            engine_record = self._engines[engine_name]

            # 从旧分类索引中移除
            old_category = engine_record.category
            if (old_category in self._category_index and
                engine_name in self._category_index[old_category]):
                self._category_index[old_category].remove(engine_name)
                if not self._category_index[old_category]:
                    del self._category_index[old_category]

            # 添加到新分类索引
            if category not in self._category_index:
                self._category_index[category] = set()
            self._category_index[category].add(engine_name)

            # 更新引擎记录
            engine_record.category = category
            engine_record.last_updated = datetime.now()

            logger.debug(f"引擎分类更改: {engine_name} -> {category.value}")
            return True

    async def update_engine_indexes(self, engine_name: str) -> bool:
        """更新引擎索引（用于引擎状态变化时）

        Args:
            engine_name: 引擎名称

        Returns:
            bool: 更新是否成功
        """
        async with self._lock:
            if engine_name not in self._engines:
                logger.warning(f"引擎不存在: {engine_name}")
                return False

            engine_record = self._engines[engine_name]

            # 从状态和健康索引中移除
            for status in ComponentStatus:
                if status in self._status_index and engine_name in self._status_index[status]:
                    self._status_index[status].remove(engine_name)
                    if not self._status_index[status]:
                        del self._status_index[status]

            for health in HealthStatus:
                if health in self._health_index and engine_name in self._health_index[health]:
                    self._health_index[health].remove(engine_name)
                    if not self._health_index[health]:
                        del self._health_index[health]

            # 重新添加状态和健康索引
            engine_status = engine_record.engine.record.status
            engine_health = engine_record.engine.record.health

            if engine_status not in self._status_index:
                self._status_index[engine_status] = set()
            self._status_index[engine_status].add(engine_name)

            if engine_health not in self._health_index:
                self._health_index[engine_health] = set()
            self._health_index[engine_health].add(engine_name)

            logger.debug(f"引擎索引更新: {engine_name}")
            return True

    def get_engine(self, engine_name: str) -> Optional[EngineBase]:
        """获取引擎实例

        Args:
            engine_name: 引擎名称

        Returns:
            Optional[EngineBase]: 引擎实例
        """
        engine_record = self._engines.get(engine_name)
        return engine_record.engine if engine_record else None

    def get_engine_record(self, engine_name: str) -> Optional[EngineRecord]:
        """获取引擎记录

        Args:
            engine_name: 引擎名称

        Returns:
            Optional[EngineRecord]: 引擎记录
        """
        return self._engines.get(engine_name)

    def get_all_engines(self) -> List[EngineBase]:
        """获取所有引擎实例

        Returns:
            List[EngineBase]: 引擎实例列表
        """
        return [record.engine for record in self._engines.values()]

    def get_all_engine_records(self) -> List[EngineRecord]:
        """获取所有引擎记录

        Returns:
            List[EngineRecord]: 引擎记录列表
        """
        return list(self._engines.values())

    def get_engines_by_category(self, category: EngineCategory) -> List[EngineBase]:
        """按分类获取引擎

        Args:
            category: 引擎分类

        Returns:
            List[EngineBase]: 引擎实例列表
        """
        engine_names = self._category_index.get(category, set())
        return [self._engines[name].engine for name in engine_names if name in self._engines]

    def get_engines_by_tag(self, tag: str) -> List[EngineBase]:
        """按标签获取引擎

        Args:
            tag: 标签

        Returns:
            List[EngineBase]: 引擎实例列表
        """
        engine_names = self._tag_index.get(tag, set())
        return [self._engines[name].engine for name in engine_names if name in self._engines]

    def get_engines_by_status(self, status: ComponentStatus) -> List[EngineBase]:
        """按状态获取引擎

        Args:
            status: 引擎状态

        Returns:
            List[EngineBase]: 引擎实例列表
        """
        engine_names = self._status_index.get(status, set())
        return [self._engines[name].engine for name in engine_names if name in self._engines]

    def get_engines_by_health(self, health: HealthStatus) -> List[EngineBase]:
        """按健康状态获取引擎

        Args:
            health: 引擎健康状态

        Returns:
            List[EngineBase]: 引擎实例列表
        """
        engine_names = self._health_index.get(health, set())
        return [self._engines[name].engine for name in engine_names if name in self._engines]

    def get_engines_by_type(self, engine_type: EngineType) -> List[EngineBase]:
        """按引擎类型获取引擎

        Args:
            engine_type: 引擎类型

        Returns:
            List[EngineBase]: 引擎实例列表
        """
        engine_names = self._type_index.get(engine_type, set())
        return [self._engines[name].engine for name in engine_names if name in self._engines]

    def search_engines(self, query: str) -> List[EngineBase]:
        """搜索引擎

        Args:
            query: 搜索关键词

        Returns:
            List[EngineBase]: 引擎实例列表
        """
        query_lower = query.lower()
        results = []

        for engine_record in self._engines.values():
            engine_name = engine_record.engine.config.name.lower()
            engine_type = engine_record.engine.record.engine_type.value.lower()

            # 匹配引擎名称
            if query_lower in engine_name:
                results.append(engine_record.engine)
                continue

            # 匹配引擎类型
            if query_lower in engine_type:
                results.append(engine_record.engine)
                continue

            # 匹配分类
            if query_lower in engine_record.category.value.lower():
                results.append(engine_record.engine)
                continue

            # 匹配标签
            for tag in engine_record.tags:
                if query_lower in tag.lower():
                    results.append(engine_record.engine)
                    break

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """获取注册表统计

        Returns:
            Dict[str, Any]: 统计信息
        """
        total_engines = len(self._engines)

        # 分类统计
        category_counts = {
            category.value: len(names)
            for category, names in self._category_index.items()
        }

        # 标签统计
        tag_counts = {
            tag: len(names)
            for tag, names in self._tag_index.items()
        }

        # 状态统计
        status_counts = {
            status.value: len(names)
            for status, names in self._status_index.items()
        }

        # 健康统计
        health_counts = {
            health.value: len(names)
            for health, names in self._health_index.items()
        }

        # 类型统计
        type_counts = {
            engine_type.value: len(names)
            for engine_type, names in self._type_index.items()
        }

        # 计算平均标签数
        total_tags = sum(len(record.tags) for record in self._engines.values())
        avg_tags = total_tags / total_engines if total_engines > 0 else 0

        # 引擎状态分布
        running_count = len(self._status_index.get(ComponentStatus.RUNNING, set()))
        stopped_count = len(self._status_index.get(ComponentStatus.STOPPED, set()))
        error_count = len(self._status_index.get(ComponentStatus.ERROR, set()))

        return {
            "total_engines": total_engines,
            "running_engines": running_count,
            "stopped_engines": stopped_count,
            "error_engines": error_count,
            "category_counts": category_counts,
            "tag_counts": tag_counts,
            "status_counts": status_counts,
            "health_counts": health_counts,
            "type_counts": type_counts,
            "avg_tags_per_engine": round(avg_tags, 2),
            "index_sizes": {
                "category_index": len(self._category_index),
                "tag_index": len(self._tag_index),
                "status_index": len(self._status_index),
                "health_index": len(self._health_index),
                "type_index": len(self._type_index)
            },
            "timestamp": datetime.now().isoformat()
        }

    def get_category_list(self) -> List[str]:
        """获取分类列表

        Returns:
            List[str]: 分类名称列表
        """
        return [category.value for category in self._category_index.keys()]

    def get_tag_list(self) -> List[str]:
        """获取标签列表

        Returns:
            List[str]: 标签列表
        """
        return list(self._tag_index.keys())

    def get_type_list(self) -> List[str]:
        """获取引擎类型列表

        Returns:
            List[str]: 引擎类型列表
        """
        return [engine_type.value for engine_type in self._type_index.keys()]

    async def refresh_indexes(self) -> None:
        """刷新索引"""
        async with self._lock:
            logger.debug("开始刷新引擎索引")

            # 清空所有索引
            self._category_index.clear()
            self._tag_index.clear()
            self._status_index.clear()
            self._health_index.clear()
            self._type_index.clear()

            # 重新构建索引
            for engine_name, engine_record in self._engines.items():
                self._update_indexes(engine_name, engine_record)

            logger.debug(f"引擎索引刷新完成，共索引 {len(self._engines)} 个引擎")

    def _update_indexes(self, engine_name: str, engine_record: EngineRecord) -> None:
        """更新索引

        Args:
            engine_name: 引擎名称
            engine_record: 引擎记录
        """
        # 分类索引
        category = engine_record.category
        if category not in self._category_index:
            self._category_index[category] = set()
        self._category_index[category].add(engine_name)

        # 标签索引
        for tag in engine_record.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(engine_name)

        # 状态索引
        engine = engine_record.engine
        status = engine.record.status
        if status not in self._status_index:
            self._status_index[status] = set()
        self._status_index[status].add(engine_name)

        # 健康索引
        health = engine.record.health
        if health not in self._health_index:
            self._health_index[health] = set()
        self._health_index[health].add(engine_name)

        # 类型索引
        engine_type = engine.record.engine_type
        if engine_type not in self._type_index:
            self._type_index[engine_type] = set()
        self._type_index[engine_type].add(engine_name)

    def _remove_from_indexes(self, engine_name: str) -> None:
        """从索引中移除

        Args:
            engine_name: 引擎名称
        """
        # 分类索引
        for category, engine_names in list(self._category_index.items()):
            if engine_name in engine_names:
                engine_names.remove(engine_name)
                if not engine_names:
                    del self._category_index[category]

        # 标签索引
        for tag, engine_names in list(self._tag_index.items()):
            if engine_name in engine_names:
                engine_names.remove(engine_name)
                if not engine_names:
                    del self._tag_index[tag]

        # 状态索引
        for status, engine_names in list(self._status_index.items()):
            if engine_name in engine_names:
                engine_names.remove(engine_name)
                if not engine_names:
                    del self._status_index[status]

        # 健康索引
        for health, engine_names in list(self._health_index.items()):
            if engine_name in engine_names:
                engine_names.remove(engine_name)
                if not engine_names:
                    del self._health_index[health]

        # 类型索引
        for engine_type, engine_names in list(self._type_index.items()):
            if engine_name in engine_names:
                engine_names.remove(engine_name)
                if not engine_names:
                    del self._type_index[engine_type]

    def __str__(self) -> str:
        """字符串表示

        Returns:
            str: 注册表的字符串表示
        """
        return (f"EngineRegistry("
                f"engines={len(self._engines)}, "
                f"categories={len(self._category_index)})")


async def get_engine_registry() -> EngineRegistry:
    """获取全局引擎注册表实例

    Returns:
        EngineRegistry: 引擎注册表实例
    """
    return EngineRegistry()