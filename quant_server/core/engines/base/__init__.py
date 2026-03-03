"""
quant_server/core/engines/base/__init__.py
引擎基类模块

此模块包含引擎系统的核心基类和基础组件，为所有引擎提供统一的
生命周期管理、状态监控和资源管理框架。

主要组件：
- EngineBase: 所有引擎的抽象基类
- EngineRecord: 引擎状态记录实体
- EngineStatusValidator: 引擎状态转换验证器
"""

from .engine_base import EngineBase, EngineRecord, EngineStatusValidator

__all__ = [
    'EngineBase',
    'EngineRecord',
    'EngineStatusValidator'
]

__version__ = '1.0.0'
__author__ = '量化交易系统团队'
__description__ = '引擎系统基础框架模块'