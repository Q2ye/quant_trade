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
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime

# 导入统一类型定义
from ..types.enums import (
    EngineType,
    EngineCategory,
    ComponentStatus,
    HealthStatus
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
                             category: EngineCategory,
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


    def get_engine(self, engine_name: str) -> Optional[EngineBase]:
        """获取引擎实例

        Args:
            engine_name: 引擎名称

        Returns:
            Optional[EngineBase]: 引擎实例
        """
        engine_record = self._engines.get(engine_name)
        return engine_record.engine if engine_record else None


    def get_all_engines(self) -> List[EngineBase]:
        """获取所有引擎实例

        Returns:
            List[EngineBase]: 引擎实例列表
        """
        return [record.engine for record in self._engines.values()]


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