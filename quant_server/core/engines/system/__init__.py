"""
系统引擎模块
quant_server/core/engines/system/__init__.py
此模块包含系统级别的引擎实现，如事件引擎、监控引擎、配置引擎等，
这些引擎为整个系统提供基础服务支持。

"""

# 根据实际文件内容导入相应的类
from .event_engine import EventEngine
from .main_engine import MainEngine
from .engine_registry import EngineRecord,EngineRegistry

__all__ = [
    # 导出所有系统引擎类
    'EventEngine',
    'MainEngine',
    'EngineRecord',
    'EngineRegistry',
]

__version__ = '1.0.0'
__author__ = '量化交易系统团队'
__description__ = '系统级引擎实现'