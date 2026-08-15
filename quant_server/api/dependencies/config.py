# -*- coding: utf-8 -*-
"""
配置依赖模块 — 薄接线层

对 shared/config 的 Depends() 包装，不自行创建或管理配置实例。
数据模块如需直接访问配置，应直接使用 shared.config.config_manager.get_config()。
"""

import logging

from shared.config.config_manager import get_config, ConfigSettings

logger = logging.getLogger(__name__)


async def get_settings() -> ConfigSettings:
    """获取全局配置设置（FastAPI Depends 兼容）"""
    return get_config().settings
