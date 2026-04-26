# quant_server/shared/database/repositories/base/pagination.py
"""
分页参数和结果模型 - 数据库层分页专用

注意：与API层的分页工具quant_server/utils/api_utils/pagination.py是独立的
- 此模块：数据库层分页参数和结果
- API模块：API层分页响应格式

设计原则：各层职责分离，避免循环依赖
"""

from typing import List, Any, Generic, TypeVar, Optional, Dict

from pydantic import BaseModel, Field

T = TypeVar('T')


class PaginationParams(BaseModel):
	"""分页参数模型"""

	page: int = Field(default=1, ge=1, description="页码，从1开始")
	page_size: int = Field(default=20, ge=1, le=1000, description="每页大小")
	offset: Optional[int] = Field(default=None, description="偏移量（优先使用page）")
	limit: Optional[int] = Field(default=None, description="限制数（优先使用page_size）")

	def get_offset (self) -> int:
		"""计算偏移量"""
		if self.offset is not None:
			return self.offset
		return (self.page - 1) * self.page_size

	def get_limit (self) -> int:
		"""计算限制数"""
		if self.limit is not None:
			return self.limit
		return self.page_size

	class Config:
		json_schema_extra = {
			"example": {
				"page": 1,
				"page_size": 20
			}
		}


class PaginationResult(BaseModel, Generic[T]):
	"""分页结果模型（数据库层）"""

	items: List[T] = Field(..., description="数据列表")
	total: int = Field(..., ge=0, description="总记录数")
	page: int = Field(..., ge=1, description="当前页码")
	page_size: int = Field(..., ge=1, le=1000, description="每页大小")
	pages: int = Field(..., ge=0, description="总页数")
	has_prev: bool = Field(..., description="是否有上一页")
	has_next: bool = Field(..., description="是否有下一页")
	prev_page: Optional[int] = Field(None, description="上一页页码")
	next_page: Optional[int] = Field(None, description="下一页页码")

	@classmethod
	def create (
			cls,
			items: List[T],
			total: int,
			page: int,
			page_size: int
	) -> 'PaginationResult[T]':
		"""创建分页结果实例"""
		if total == 0:
			pages = 0
		else:
			pages = (total + page_size - 1) // page_size

		has_prev = page > 1
		has_next = page < pages if pages > 0 else False
		prev_page = page - 1 if has_prev else None
		next_page = page + 1 if has_next else None

		return cls(
			items=items,
			total=total,
			page=page,
			page_size=page_size,
			pages=pages,
			has_prev=has_prev,
			has_next=has_next,
			prev_page=prev_page,
			next_page=next_page
		)

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典格式"""
		return {
			"items": self.items,
			"total": self.total,
			"page": self.page,
			"page_size": self.page_size,
			"pages": self.pages,
			"has_prev": self.has_prev,
			"has_next": self.has_next,
			"prev_page": self.prev_page,
			"next_page": self.next_page
		}

	class Config:
		arbitrary_types_allowed = True
		json_schema_extra = {
			"example": {
				"items": [],
				"total": 0,
				"page": 1,
				"page_size": 20,
				"pages": 0,
				"has_prev": False,
				"has_next": False,
				"prev_page": None,
				"next_page": None
			}
		}
