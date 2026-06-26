# -*- coding: utf-8 -*-
"""
配置管理器

负责系统配置的缓存、版本管理和热更新通知。

v2.0 新增：
- ConfigUpdatedEvent 发布（set 时通知订阅方）
- start_watcher / stop_watcher（轻量配置监听，供未来 DB NOTIFY 使用）
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from shared.database.repositories.system.config.config_repo import ConfigRepository

logger = logging.getLogger(__name__)


class ConfigManager:
    """系统配置管理器 — 带缓存的配置读写 + 热更新事件推送"""

    def __init__(self, session_factory, event_engine=None):
        self._session_factory = session_factory
        self._event_engine = event_engine  # v2.0: 事件引擎（可选）
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._last_refresh: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 缓存 5 分钟
        self._watching = False

    # ==================== 读取 ====================

    async def get(self, key: str, default: Any = None) -> Any:
        """读取配置值（优先从缓存）"""
        await self._maybe_refresh()
        item = self._cache.get(key)
        if item is None:
            return default
        return item.get("config_value", default)

    async def get_int(self, key: str, default: int = 0) -> int:
        val = await self.get(key, default)
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    async def get_float(self, key: str, default: float = 0.0) -> float:
        val = await self.get(key, default)
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    async def get_bool(self, key: str, default: bool = False) -> bool:
        val = await self.get(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes", "on")
        return default

    async def get_all(self, prefix: str = "") -> Dict[str, Any]:
        """获取所有配置（可选前缀过滤）"""
        await self._maybe_refresh()
        if not prefix:
            return {k: v.get("config_value") for k, v in self._cache.items()}
        return {
            k: v.get("config_value")
            for k, v in self._cache.items()
            if k.startswith(prefix)
        }

    # ==================== 写入（含事件推送） ====================

    async def set(
        self,
        key: str,
        value: Any,
        config_type: str = "string",
        updated_by: str = "system",
    ) -> None:
        """写入配置并刷新缓存，v2.0 同步发布 ConfigUpdatedEvent"""
        old_value = self._cache.get(key, {}).get("config_value")

        async with self._session_factory() as session:
            repo = ConfigRepository(session)
            existing = await repo.get_by_key(key)
            if existing:
                await repo.update_config(
                    config_key=key,
                    config_value=str(value),
                    config_type=config_type,
                    updated_by=updated_by,
                )
            else:
                await repo.create_config(
                    config_key=key,
                    config_value=str(value),
                    config_type=config_type,
                    created_by=updated_by,
                    updated_by=updated_by,
                )

        # 更新缓存
        self._cache[key] = {
            "config_key": key,
            "config_value": value,
            "config_type": config_type,
        }

        # v2.0: 发布热更新事件
        await self._notify_change(key, new_value=value, old_value=old_value or "")

        logger.info("配置已更新: %s", key)

    async def delete(self, key: str, deleted_by: str = "system") -> bool:
        """删除配置"""
        async with self._session_factory() as session:
            repo = ConfigRepository(session)
            result = await repo.delete_config(key)
        if result:
            self._cache.pop(key, None)
            # 发布删除事件
            if self._event_engine:
                from modules.system.events.config_events import ConfigDeletedEvent
                event = ConfigDeletedEvent(
                    config_key=key,
                    deleted_by=deleted_by,
                )
                await self._event_engine.put(event)
            logger.info("配置已删除: %s", key)
        return result

    # ==================== 缓存管理 ====================

    async def refresh(self) -> None:
        """强制刷新缓存"""
        self._cache.clear()
        async with self._session_factory() as session:
            repo = ConfigRepository(session)
            configs = await repo.get_all_configs()
            for c in configs:
                self._cache[c.config_key] = {
                    "config_key": c.config_key,
                    "config_value": self._parse_value(c.config_value, c.config_type),
                    "config_type": c.config_type,
                }
        self._last_refresh = datetime.now()
        logger.debug("配置缓存已刷新，共 %d 项", len(self._cache))

    async def _maybe_refresh(self) -> None:
        """按需刷新过期缓存"""
        if self._last_refresh is None:
            await self.refresh()
            return
        elapsed = (datetime.now() - self._last_refresh).total_seconds()
        if elapsed > self._cache_ttl_seconds:
            await self.refresh()

    @staticmethod
    def _parse_value(raw: str, config_type: str) -> Any:
        if config_type == "int":
            return int(raw)
        elif config_type == "float":
            return float(raw)
        elif config_type == "bool":
            return raw.lower() in ("true", "1", "yes", "on")
        return raw

    # ==================== v2.0: 热更新事件 ====================

    async def _notify_change(
        self, key: str, new_value: Any, old_value: Any = ""
    ) -> None:
        """发布配置变更事件到 EventEngine"""
        if not self._event_engine:
            return
        try:
            from modules.system.events.config_events import ConfigUpdatedEvent
            event = ConfigUpdatedEvent(
                config_key=key,
                old_value=str(old_value) if old_value else "",
                new_value=str(new_value),
                updated_by="system",
            )
            await self._event_engine.put(event)
            logger.debug("已发布 ConfigUpdatedEvent: %s", key)
        except Exception as e:
            logger.warning("发布配置变更事件失败: %s", e)

    async def start_watcher(self) -> None:
        """
        启动配置热加载监听。

        当前实现：依赖 _maybe_refresh 的 TTL 过期机制 + set() 时的主动推送。
        未来可扩展为 PostgreSQL LISTEN/NOTIFY 或文件监听。
        """
        if self._watching:
            return
        self._watching = True
        logger.info("配置热加载监听已启动（TTL=%ds + 事件推送）", self._cache_ttl_seconds)

    async def stop_watcher(self) -> None:
        """停止配置热加载监听"""
        self._watching = False
        logger.info("配置热加载监听已停止")
