# -*- coding: utf-8 -*-
"""
API层异常处理器包

提供 FastAPI 全局异常处理器注册能力。
将业务异常（QuantBaseException 及其子类）转换为标准 HTTP JSON 响应。
"""

from .exception_handlers import setup_exception_handlers

__all__ = ["setup_exception_handlers"]
