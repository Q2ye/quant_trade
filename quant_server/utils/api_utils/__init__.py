# quant_server/utils/api_utils/__init__.py
"""
API工具模块

统一导出API层的所有工具函数和类，为FastAPI应用提供完整的工具支持。
基于设计文档的混合架构设计，确保API层的一致性和可维护性。

Author: 量化交易系统团队
Version: 1.0.0
"""

# 从各子模块导入
from .response_formatter import (
    # 响应格式化
    APIResponse,
    ResponseFormatter,
    success_response,
    error_response,
    paginated_response,
    _formatter as response_formatter,
)

from .pagination import (
    # 分页工具
    PaginationResult,
    PaginationResponse,
)


class APIUtilsManager:
    """API工具管理器"""

    @staticmethod
    def get_response_formatter() -> ResponseFormatter:
        """
        获取响应格式化器

        Returns:
            ResponseFormatter: 响应格式化器实例
        """
        return response_formatter


# 导出所有工具
__all__ = [
    # 响应格式化
    "APIResponse",
    "ResponseFormatter",
    "success_response",
    "error_response",
    "paginated_response",
    "response_formatter",

    # 分页工具
    "PaginationResult",
    "PaginationResponse",

    # 管理器
    "APIUtilsManager",
]

# 模块元数据
__version__ = "1.0.0"
__author__ = "量化交易系统团队"
__description__ = "API层工具模块，提供响应格式化、请求验证、分页、OpenAPI定制、限流等功能"
__license__ = "MIT"
