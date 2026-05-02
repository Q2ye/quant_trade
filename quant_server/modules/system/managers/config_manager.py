# -*- coding: utf-8 -*-
"""
配置管理器
负责系统配置的缓存、版本管理和热更新通知。
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from quant_server.shared.database.repositories.system.config.config_repo import ConfigRepository

logger = logging.getLogger(__name__)


class ConfigManager:
    """系统配置管理器 — 带缓存的配置读写"""

    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._last_refresh: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 缓存 5 分钟

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

    async def set(self, key: str, value: Any, config_type: str = "string") -> None:
        """写入配置并刷新缓存"""
        async with self._session_factory() as session:
            repo = ConfigRepository(session)
            existing = await repo.get_by_key(key)
            if existing:
                await repo.update_config(
                    config_key=key, config_value=str(value),
                    config_type=config_type, updated_by="system",
                )
            else:
                await repo.create_config(
                    config_key=key, config_value=str(value),
                    config_type=config_type, created_by="system", updated_by="system",
                )
        # 更新缓存
        self._cache[key] = {"config_key": key, "config_value": value, "config_type": config_type}
        logger.info(f"配置已更新: {key}")

    async def delete(self, key: str) -> bool:
        """删除配置"""
        async with self._session_factory() as session:
            repo = ConfigRepository(session)
            result = await repo.delete_config(key)
        if result:
            self._cache.pop(key, None)
            logger.info(f"配置已删除: {key}")
        return result

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
        logger.debug(f"配置缓存已刷新，共 {len(self._cache)} 项")

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
