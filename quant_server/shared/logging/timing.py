# -*- coding: utf-8 -*-
"""函数耗时装饰器 — 一行 @log_duration() 自动记录耗时和异常"""
import time
import functools
import logging
from typing import Callable


def log_duration(level: int = logging.INFO) -> Callable:
    """异步函数耗时装饰器

    用法:
        from shared.logging.timing import log_duration

        @log_duration()
        async def get_stock_full(session, ts_code):
            ...

    输出:
        INFO  modules.market.services.stock_service: get_stock_full 完成 (118ms)
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)
            t0 = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                ms = (time.perf_counter() - t0) * 1000
                logger.log(level, f"{func.__name__} 完成 ({ms:.0f}ms)")
                return result
            except Exception:
                ms = (time.perf_counter() - t0) * 1000
                logger.error(f"{func.__name__} 失败 ({ms:.0f}ms)", exc_info=True)
                raise

        return wrapper

    return decorator
