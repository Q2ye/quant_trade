# quant_server/utils/api_utils/pagination.py

import logging
from datetime import datetime, timezone
from typing import (
	TypeVar, Generic, Optional, Dict, Any, List,
)

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

T = TypeVar('T')
M = TypeVar('M', bound=BaseModel)

# 直接定义 PaginationResult，避免循环导入
class PaginationResult(BaseModel, Generic[T]):
    """分页结果模型"""
    items: List[T] = Field(..., description="数据列表")
    page: int = Field(..., description="当前页码")
    size: int = Field(..., description="每页大小")
    total: int = Field(..., description="总记录数")
    pages: int = Field(..., description="总页数")
    has_prev: bool = Field(..., description="是否有上一页")
    has_next: bool = Field(..., description="是否有下一页")
    prev_page: Optional[int] = Field(None, description="上一页页码")
    next_page: Optional[int] = Field(None, description="下一页页码")


# 添加本地定义的APIResponse基类
class APIResponse(BaseModel):
    """API响应基类（本地定义，避免循环导入）"""
    code: str = Field(..., description="响应代码")
    message: str = Field(..., description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": "SUCCESS",
                "message": "操作成功",
                "data": None,
                "timestamp": "2023-01-01T00:00:00Z"
            }
        }
    }


# 删除或修改PaginationResponse类，不继承APIResponse
class PaginationResponse(BaseModel, Generic[T]):
    """分页响应模型（独立定义）"""

    code: str = Field(default="SUCCESS", description="响应代码")
    message: str = Field(default="查询成功", description="响应消息")
    data: Dict[str, Any] = Field(..., description="分页数据")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_pagination_result(
            cls,
            result: PaginationResult[T],
            message: str = "查询成功"
    ) -> 'PaginationResponse':
        """从分页结果创建响应"""
        return cls(
            code="SUCCESS",
            message=message,
            data={
                "items": result.items,
                "pagination": {
                    "page": result.page,
                    "size": result.size,
                    "total": result.total,
                    "pages": result.pages,
                    "has_prev": result.has_prev,
                    "has_next": result.has_next,
                    "prev_page": result.prev_page,
                    "next_page": result.next_page
                }
            },
            timestamp=datetime.now(timezone.utc)
        )

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": "SUCCESS",
                "message": "查询成功",
                "data": {
                    "items": [],
                    "pagination": {
                        "page": 1,
                        "size": 20,
                        "total": 0,
                        "pages": 0,
                        "has_prev": False,
                        "has_next": False,
                        "prev_page": None,
                        "next_page": None
                    }
                },
                "timestamp": "2023-01-01T00:00:00Z"
            }
        }
    }