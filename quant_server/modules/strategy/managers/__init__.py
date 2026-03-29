# -*- coding: utf-8 -*-
"""
策略管理器模块
提供生命周期管理和依赖管理
"""

from .lifecycle_manager import (
    LifecycleState,
    LifecycleEvent,
    LifecycleManager,
)
from .dependency_manager import (
    DependencyType,
    DependencyState,
    Dependency,
    DependencyManager,
)

__all__ = [
    # 生命周期管理
    "LifecycleState",
    "LifecycleEvent",
    "LifecycleManager",
    # 依赖管理
    "DependencyType",
    "DependencyState",
    "Dependency",
    "DependencyManager",
]
