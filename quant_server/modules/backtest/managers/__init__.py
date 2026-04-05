"""
管理器模块

负责回测任务管理和资源管理

主要组件：
1. TaskManager：任务管理器，负责回测任务的创建、执行和监控
2. ResourceManager：资源管理器，负责回测资源的分配和管理
"""

from .task_manager import TaskManager
from .resource_manager import ResourceManager

__all__ = [
    "TaskManager",
    "ResourceManager"
]