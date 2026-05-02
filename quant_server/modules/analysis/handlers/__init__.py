"""分析模块事件处理器

同名 handlers.py（模块文件）与 handlers/（本包）存在命名冲突，
Python 优先解析本包，因此通过 SourceFileLoader 显式加载顶层 handlers.py。
"""
import os as _os
from importlib.machinery import SourceFileLoader as _SourceFileLoader

from .event_handler import AnalysisEventHandler

# 加载顶层 handlers.py（模块文件），绕过 package 优先解析
_analysis_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_top_handlers = _SourceFileLoader(
    "quant_server.modules.analysis._top_handlers",
    _os.path.join(_analysis_dir, "handlers.py"),
).load_module()

AnalysisHandler = _top_handlers.AnalysisHandler
check_analysis_module_health = _top_handlers.check_analysis_module_health

__all__ = ["AnalysisEventHandler", "AnalysisHandler", "check_analysis_module_health"]