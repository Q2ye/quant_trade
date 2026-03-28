# quant_server/utils/api_utils/pagination_decorator.py
"""
分页装饰器工具
用于自动处理分页参数的配置化和值转换
"""

from typing import Callable, Any, Dict
from functools import wraps
from fastapi import Depends
from pydantic import Field

from .pagination_config import PaginationParams


def with_pagination_config(
    page_param_name: str = "page",
    page_size_param_name: str = "page_size"
):
    """
    装饰器：自动处理分页参数的配置化和值转换

    Args:
        page_param_name: 页码参数名称
        page_size_param_name: 每页大小参数名称

    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从参数中提取分页参数
            page = kwargs.get(page_param_name)
            page_size = kwargs.get(page_size_param_name)

            # 创建分页参数对象
            pagination_params = PaginationParams(
                page=page,
                page_size=page_size
            )

            # 替换原始参数为配置化后的值
            kwargs[page_param_name] = pagination_params.get_effective_page()
            kwargs[page_size_param_name] = pagination_params.get_effective_page_size()

            # 调用原始函数
            return await func(*args, **kwargs)

        return wrapper
    return decorator


def get_pagination_dependency() -> Dict[str, Any]:
    """
    获取分页参数依赖项配置

    Returns:
        dict: 分页参数依赖项配置
    """
    return {}
