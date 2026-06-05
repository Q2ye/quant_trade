"""
数据模块工具包

提供数据模块专用的工具函数和类，包括：
1. 数据格式化工具
2. 因子计算工具
3. 质量检查工具
4. 数据处理辅助函数

设计原则：
1. 模块专用：只包含数据模块特有的工具，通用工具放在顶级utils目录
2. 功能单一：每个工具类/函数只解决一个特定问题
3. 易于测试：工具函数应该是纯函数或无状态的类
4. 类型安全：使用类型提示确保代码健壮性
"""

from .data_formatter import DataFormatter
from .factor_calculator import FactorCalculator
from .quality_checker import DataQualityChecker
from .timing import SyncTimingLogger

__all__ = [
    "DataFormatter",
    "FactorCalculator",
    "DataQualityChecker",
    "SyncTimingLogger",
]

# 版本信息
__version__ = "1.0.0"
__description__ = "数据模块专用工具包"
__author__ = "QuantServer Team"