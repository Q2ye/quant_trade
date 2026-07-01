# -*- coding: utf-8 -*-
"""
AI策略模块
提供基于机器学习和深度学习的策略

注意：torch 为深度学习策略的可选依赖，
未安装时 MLStrategy 仍可用，DLStrategy 不可用。
"""

import logging
logger = logging.getLogger(__name__)

from .ml_strategy import MLStrategy

try:
    from .dl_strategy import DLStrategy
except Exception as _e:
    logger.warning("DLStrategy 导入失败（torch 不可用）: %s", _e)
    DLStrategy = None  # type: ignore

__all__ = [
    "MLStrategy",
    "DLStrategy",
]