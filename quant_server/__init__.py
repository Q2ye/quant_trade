"""
quant_server/__init__.py
量化交易系统主包

提供统一的启动接口和工具函数
"""

__version__ = "1.0.0"
__author__ = "Quant Trading Team"

from .main import QuantServer, main

__all__ = ["QuantServer", "main"]