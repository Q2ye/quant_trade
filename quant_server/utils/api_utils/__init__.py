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
    ResponseMiddleware,
    success_response,
    error_response,
    paginated_response,
    _formatter as response_formatter,
)

from .request_validator import (
    # 请求验证
    RequestValidator,
    ValidationRules,
    validate_request,
    validate_query,
    validate_path,
    ValidatedQuery,
    ValidatedPath,
    ValidatedBody,
    _validator as request_validator,
)

from .pagination import (
    # 分页工具
    PaginationResult,
    PaginationResponse,
)

from .rate_limit import (
    # 限流工具
    RateLimitStrategy,
    RateLimitScope,
    RateLimitConfig,
    RateLimitResult,
    RateLimiter,
    RedisRateLimiter,
    MemoryRateLimiter,
    RateLimitManager,
    rate_limit,
    create_rate_limit_middleware,
    initialize_rate_limit_manager,
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

    @staticmethod
    def get_request_validator() -> RequestValidator:
        """
        获取请求验证器

        Returns:
            RequestValidator: 请求验证器实例
        """
        return request_validator


    @staticmethod
    def create_rate_limit_middleware():
        """
        创建限流中间件

        Returns:
            Callable: 限流中间件函数
        """
        return create_rate_limit_middleware()


# 导出所有工具
__all__ = [
    # 响应格式化
    "APIResponse",
    "ResponseFormatter",
    "ResponseMiddleware",
    "success_response",
    "error_response",
    "paginated_response",
    "response_formatter",

    # 请求验证
    "RequestValidator",
    "ValidationRules",
    "validate_request",
    "validate_query",
    "validate_path",
    "ValidatedQuery",
    "ValidatedPath",
    "ValidatedBody",
    "request_validator",

    # 分页工具
    "PaginationResult",
    "PaginationResponse",

    # 限流工具
    "RateLimitStrategy",
    "RateLimitScope",
    "RateLimitConfig",
    "RateLimitResult",
    "RateLimiter",
    "RedisRateLimiter",
    "MemoryRateLimiter",
    "RateLimitManager",
    "rate_limit",
    "create_rate_limit_middleware",
    "initialize_rate_limit_manager",

    # 管理器
    "APIUtilsManager",
]

# 模块元数据
__version__ = "1.0.0"
__author__ = "量化交易系统团队"
__description__ = "API层工具模块，提供响应格式化、请求验证、分页、OpenAPI定制、限流等功能"
__license__ = "MIT"