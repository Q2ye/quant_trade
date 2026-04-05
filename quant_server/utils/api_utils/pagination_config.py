# quant_server/utils/api_utils/pagination_config.py
"""
分页和排序配置工具
用于从配置中获取分页和排序参数，支持Swagger文档定制
"""

from typing import Optional, List
from enum import Enum
from pydantic import Field, BaseModel
from functools import lru_cache

from quant_server.shared.config.constants import PAGINATION_DEFAULTS
from quant_server.shared.config.config_manager import get_config


class SortOrder(str, Enum):
    """排序方向枚举"""
    ASC = "asc"
    DESC = "desc"


class PaginationParams(BaseModel):
    """分页参数基类（配置化版本）"""

    page: Optional[int] = Field(
        default=None,
        ge=1,
        description="页码，从1开始。如果未提供则使用配置的默认值",
        json_schema_extra={"include_in_schema": False}
    )

    page_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="每页记录数。如果未提供则使用配置的默认值，最大值受配置限制",
        json_schema_extra={"include_in_schema": False}
    )

    def get_effective_page(self) -> int:
        """获取有效的页码（优先使用参数，其次使用配置）"""
        if self.page is not None:
            return self.page
        return get_pagination_defaults()["DEFAULT_PAGE"]

    def get_effective_page_size(self) -> int:
        """获取有效的每页大小（优先使用参数，其次使用配置，并限制最大值）"""
        if self.page_size is not None:
            return min(self.page_size, get_pagination_defaults()["MAX_PAGE_SIZE"])
        return get_pagination_defaults()["PAGE_SIZE"]


class SortParams(BaseModel):
    """排序参数基类（配置化版本）"""

    sort_by: Optional[str] = Field(
        default=None,
        description="排序字段。如果未提供则使用配置的默认值",
        json_schema_extra={"include_in_schema": False}
    )
    sort_order: Optional[SortOrder] = Field(
        default=None,
        description="排序顺序。如果未提供则使用配置的默认值",
        json_schema_extra={"include_in_schema": False}
    )

    def get_effective_sort_by(self, default_field: str = "created_at") -> str:
        """获取有效的排序字段（优先使用参数，其次使用配置）"""
        if self.sort_by is not None and self.sort_by != "":
            return self.sort_by
        return get_sort_defaults()["DEFAULT_SORT_FIELD"]

    def get_effective_sort_order(self) -> str:
        """获取有效的排序方向（优先使用参数，其次使用配置）"""
        if self.sort_order is not None:
            return self.sort_order.value
        return get_sort_defaults()["DEFAULT_SORT_ORDER"]


# ==================== 配置管理 ====================

SORT_DEFAULTS = {
    "DEFAULT_SORT_FIELD": "created_at",
    "DEFAULT_SORT_ORDER": "desc",
    "ALLOWED_SORT_FIELDS": ["created_at", "updated_at", "name", "id"]
}


@lru_cache(maxsize=1)
def get_pagination_defaults() -> dict:
    """
    获取分页默认配置（带缓存）

    Returns:
        dict: 分页默认配置字典
    """
    settings = get_config().settings
    return PAGINATION_DEFAULTS


@lru_cache(maxsize=1)
def get_sort_defaults() -> dict:
    """
    获取排序默认配置（带缓存）

    Returns:
        dict: 排序默认配置字典
    """
    settings = get_config().settings
    return SORT_DEFAULTS


def get_allowed_sort_fields() -> List[str]:
    """获取允许的排序字段列表"""
    return SORT_DEFAULTS.get("ALLOWED_SORT_FIELDS", ["created_at"])


def is_valid_sort_field(field: str) -> bool:
    """验证排序字段是否合法"""
    return field in get_allowed_sort_fields()


def exclude_pagination_params_from_openapi() -> dict:
    """
    生成用于Swagger文档的排除参数配置

    Returns:
        dict: 用于FastAPI Depends的配置，排除分页和排序参数从Swagger文档
    """
    return {
        "include_in_schema": False
    }