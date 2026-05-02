# -*- coding: utf-8 -*-
"""
配置依赖模块 — 薄接线层

对 shared/config 的 Depends() 包装，不自行创建或管理配置实例。
数据模块如需直接访问配置，应直接使用 shared.config.config_manager.get_config()。
"""

import logging
from typing import Any

from quant_server.shared.config.config_manager import get_config, ConfigSettings

logger = logging.getLogger(__name__)


async def get_settings() -> ConfigSettings:
    """获取全局配置设置（FastAPI Depends 兼容）"""
    return get_config().settings


def get_config_by_path(path: str) -> Any:
    """通过路径获取配置值，委托给 shared/config"""
    settings = get_config().settings
    parts = path.split(".")
    value = settings.model_dump()
    for part in parts:
        if part not in value:
            raise KeyError(f"配置路径不存在: {path}")
        value = value[part]
    return value
