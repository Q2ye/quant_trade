# -*- coding: utf-8 -*-
"""
AI策略模块
提供基于机器学习和深度学习的策略

注意：torch 为深度学习策略的可选依赖，
未安装时 MLStrategy 仍可用，DLStrategy 不可用。
"""

from .ml_strategy import MLStrategy

try:
    from .dl_strategy import DLStrategy
except Exception:
    # torch 未安装或加载失败（如 DLL 缺失）时，DLStrategy 不可用
    DLStrategy = None  # type: ignore

__all__ = [
    "MLStrategy",
    "DLStrategy",
]