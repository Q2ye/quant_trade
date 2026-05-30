# quant_server/utils/api_utils/pagination_decorator.py
"""
分页装饰器工具
用于自动处理分页参数的配置化和值转换
"""

import inspect
from typing import Callable, Any, Dict
from functools import wraps

from .pagination_config import PaginationParams


def with_pagination_config(
    page_param_name: str = "page",
    page_size_param_name: str = "page_size"
):
    """
    装饰器：自动处理分页参数的配置化和值转换

    仅对接受 page/page_size 关键字参数的函数生效；
    若函数签名不包含这些参数（如分页已由请求模型处理），则透传调用。

    Args:
        page_param_name: 页码参数名称
        page_size_param_name: 每页大小参数名称

    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)
        accepts_page = page_param_name in sig.parameters
        accepts_page_size = page_size_param_name in sig.parameters

        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not accepts_page and not accepts_page_size:
                return await func(*args, **kwargs)

            page = kwargs.get(page_param_name)
            page_size = kwargs.get(page_size_param_name)

            pagination_params = PaginationParams(
                page=page,
                page_size=page_size
            )

            if accepts_page:
                kwargs[page_param_name] = pagination_params.get_effective_page()
            if accepts_page_size:
                kwargs[page_size_param_name] = pagination_params.get_effective_page_size()

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
