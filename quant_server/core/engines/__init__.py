"""
量化交易引擎模块

此模块包含量化交易系统的所有引擎组件，提供统一的引擎管理框架。
包括基础引擎、事件引擎、交易引擎、策略引擎等各种类型的引擎实现。

模块结构：
- base: 引擎基类和核心框架
- events: 系统引擎（事件引擎、监控引擎等）
- trading: 交易相关引擎
- events: 策略相关引擎
- utils: 引擎工具类
"""

from .base import EngineBase, EngineRecord, EngineStatusValidator

__all__ = [
    # 基础类
    'EngineBase',
    'EngineRecord',
    'EngineStatusValidator',
]

__version__ = '1.0.0'
__author__ = '量化交易系统团队'
__description__ = '量化交易引擎系统'