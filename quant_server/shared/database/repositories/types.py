# -*- coding: utf-8 -*-
"""
自定义数据库类型定义
位置：shared/database/repositories/types.py

注意：这个文件主要用于定义Repository层使用的自定义类型
在实际使用中，可能需要根据具体数据库适配器调整
"""

from typing import TypeVar, Generic, Dict, Any, List, Optional, Union
from datetime import date, datetime
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

# ==================== 基础类型定义 ====================

T = TypeVar('T')
R = TypeVar('R')


class RepositoryResult(Generic[T]):
	"""Repository操作结果基类"""

	def __init__ (
			self,
			success: bool,
			data: Optional[T] = None,
			error: Optional[str] = None,
			total: Optional[int] = None
	):
		self.success = success
		self.data = data
		self.error = error
		self.total = total

	@classmethod
	def success_result (cls, data: T, total: Optional[int] = None) -> 'RepositoryResult[T]':
		"""成功结果"""
		return cls(success=True, data=data, total=total)

	@classmethod
	def error_result (cls, error: str) -> 'RepositoryResult[T]':
		"""错误结果"""
		return cls(success=False, error=error)

	def is_success (self) -> bool:
		"""是否成功"""
		return self.success

	def get_data (self) -> Optional[T]:
		"""获取数据"""
		return self.data

	def get_error (self) -> Optional[str]:
		"""获取错误信息"""
		return self.error

	def get_total (self) -> Optional[int]:
		"""获取总数"""
		return self.total


@dataclass
class PaginationParams:
	"""分页参数"""
	page: int = 1
	page_size: int = 20
	order_by: Optional[str] = None
	order_desc: bool = True

	def get_offset (self) -> int:
		"""计算偏移量"""
		return (self.page - 1) * self.page_size

	def get_limit (self) -> int:
		"""获取限制数量"""
		return self.page_size


@dataclass
class PaginationResult(Generic[T]):
	"""分页结果"""
	items: List[T]
	total: int
	page: int
	page_size: int
	total_pages: int

	@classmethod
	def create (
			cls,
			items: List[T],
			total: int,
			page: int,
			page_size: int
	) -> 'PaginationResult[T]':
		"""创建分页结果"""
		total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
		return cls(
			items=items,
			total=total,
			page=page,
			page_size=page_size,
			total_pages=total_pages
		)

	def has_previous (self) -> bool:
		"""是否有上一页"""
		return self.page > 1

	def has_next (self) -> bool:
		"""是否有下一页"""
		return self.page < self.total_pages

	def get_previous_page (self) -> Optional[int]:
		"""获取上一页页码"""
		return self.page - 1 if self.has_previous() else None

	def get_next_page (self) -> Optional[int]:
		"""获取下一页页码"""
		return self.page + 1 if self.has_next() else None


@dataclass
class DateRange:
	"""日期范围"""
	start_date: date
	end_date: date

	def validate (self) -> bool:
		"""验证日期范围是否有效"""
		return self.start_date <= self.end_date

	def days (self) -> int:
		"""获取天数"""
		return (self.end_date - self.start_date).days + 1


@dataclass
class DateTimeRange:
	"""日期时间范围"""
	start_time: datetime
	end_time: datetime

	def validate (self) -> bool:
		"""验证时间范围是否有效"""
		return self.start_time <= self.end_time

	def seconds (self) -> float:
		"""获取秒数"""
		return (self.end_time - self.start_time).total_seconds()


# ==================== 查询过滤器类型 ====================

class FilterOperator(str, Enum):
	"""过滤操作符"""
	EQ = "eq"  # 等于
	NE = "ne"  # 不等于
	GT = "gt"  # 大于
	GE = "ge"  # 大于等于
	LT = "lt"  # 小于
	LE = "le"  # 小于等于
	LIKE = "like"  # 模糊匹配
	IN = "in"  # 在列表中
	NOT_IN = "not_in"  # 不在列表中
	IS_NULL = "is_null"  # 为空
	NOT_NULL = "not_null"  # 不为空
	BETWEEN = "between"  # 在范围内


@dataclass
class FilterCondition:
	"""过滤条件"""
	field: str
	operator: FilterOperator
	value: Any

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"field": self.field,
			"operator": self.operator.value,
			"value": self.value
		}


@dataclass
class SortCondition:
	"""排序条件"""
	field: str
	descending: bool = False

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"field": self.field,
			"descending": self.descending
		}


@dataclass
class QueryParams:
	"""查询参数"""
	filters: List[FilterCondition]
	sorts: List[SortCondition]
	pagination: PaginationParams

	def add_filter (self, filter_cond: FilterCondition) -> 'QueryParams':
		"""添加过滤条件"""
		self.filters.append(filter_cond)
		return self

	def add_sort (self, sort_cond: SortCondition) -> 'QueryParams':
		"""添加排序条件"""
		self.sorts.append(sort_cond)
		return self

	@classmethod
	def create (
			cls,
			page: int = 1,
			page_size: int = 20
	) -> 'QueryParams':
		"""创建查询参数"""
		return cls(
			filters=[],
			sorts=[],
			pagination=PaginationParams(page=page, page_size=page_size)
		)


# ==================== 数据库相关类型 ====================

@dataclass
class DatabaseConfig:
	"""数据库配置"""
	host: str
	port: int
	database: str
	username: str
	password: str
	pool_size: int = 10
	max_overflow: int = 20
	pool_timeout: int = 30
	pool_recycle: int = 3600
	echo: bool = False

	@property
	def connection_string (self) -> str:
		"""获取连接字符串"""
		return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class TransactionIsolationLevel(str, Enum):
	"""事务隔离级别"""
	READ_COMMITTED = "READ COMMITTED"
	REPEATABLE_READ = "REPEATABLE READ"
	SERIALIZABLE = "SERIALIZABLE"
	READ_UNCOMMITTED = "READ UNCOMMITTED"


@dataclass
class TransactionOptions:
	"""事务选项"""
	isolation_level: TransactionIsolationLevel = TransactionIsolationLevel.READ_COMMITTED
	read_only: bool = False
	deferrable: bool = False


# ==================== 数据模型相关类型 ====================

class ModelFieldType(str, Enum):
	"""模型字段类型"""
	INTEGER = "integer"
	BIGINT = "bigint"
	STRING = "string"
	TEXT = "text"
	BOOLEAN = "boolean"
	DATE = "date"
	DATETIME = "datetime"
	DECIMAL = "decimal"
	JSON = "json"
	FLOAT = "float"


@dataclass
class ModelField:
	"""模型字段定义"""
	name: str
	type: ModelFieldType
	nullable: bool = True
	primary_key: bool = False
	unique: bool = False
	index: bool = False
	default: Any = None
	foreign_key: Optional[str] = None
	comment: Optional[str] = None

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"name": self.name,
			"type": self.type.value,
			"nullable": self.nullable,
			"primary_key": self.primary_key,
			"unique": self.unique,
			"index": self.index,
			"default": self.default,
			"foreign_key": self.foreign_key,
			"comment": self.comment
		}


@dataclass
class ModelDefinition:
	"""模型定义"""
	name: str
	table_name: str
	fields: List[ModelField]
	indexes: List[List[str]] = None
	unique_constraints: List[List[str]] = None

	def __post_init__ (self):
		if self.indexes is None:
			self.indexes = []
		if self.unique_constraints is None:
			self.unique_constraints = []

	def get_primary_key_fields (self) -> List[ModelField]:
		"""获取主键字段"""
		return [field for field in self.fields if field.primary_key]

	def get_foreign_key_fields (self) -> List[ModelField]:
		"""获取外键字段"""
		return [field for field in self.fields if field.foreign_key]

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"name": self.name,
			"table_name": self.table_name,
			"fields": [field.to_dict() for field in self.fields],
			"indexes": self.indexes,
			"unique_constraints": self.unique_constraints
		}


# ==================== Repository特定类型 ====================

@dataclass
class BulkOperationResult:
	"""批量操作结果"""
	success_count: int
	failed_count: int
	total_count: int
	errors: List[Dict[str, Any]] = None

	def __post_init__ (self):
		if self.errors is None:
			self.errors = []

	def success_rate (self) -> float:
		"""成功率"""
		return self.success_count / self.total_count * 100 if self.total_count > 0 else 0

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"success_count": self.success_count,
			"failed_count": self.failed_count,
			"total_count": self.total_count,
			"success_rate": self.success_rate(),
			"errors": self.errors
		}


@dataclass
class UpsertResult(Generic[T]):
	"""插入或更新结果"""
	created: List[T]
	updated: List[T]
	skipped: List[T]

	def total (self) -> int:
		"""总数"""
		return len(self.created) + len(self.updated) + len(self.skipped)

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"created_count": len(self.created),
			"updated_count": len(self.updated),
			"skipped_count": len(self.skipped),
			"total_count": self.total()
		}


class CacheStrategy(str, Enum):
	"""缓存策略"""
	NONE = "none"  # 不缓存
	MEMORY = "memory"  # 内存缓存
	REDIS = "redis"  # Redis缓存
	TWO_LEVEL = "two_level"  # 二级缓存（内存+Redis）


@dataclass
class CacheConfig:
	"""缓存配置"""
	strategy: CacheStrategy = CacheStrategy.NONE
	ttl: int = 300  # 生存时间（秒）
	max_size: int = 1000  # 最大缓存数量（仅内存缓存有效）
	prefix: str = "repo:"  # 缓存键前缀

	def get_key (self, *parts) -> str:
		"""获取缓存键"""
		key_parts = [self.prefix] + [str(part) for part in parts]
		return ":".join(key_parts)


# ==================== 导出所有类型 ====================

__all__ = [
	# 基础类型
	"RepositoryResult",
	"PaginationParams",
	"PaginationResult",
	"DateRange",
	"DateTimeRange",

	# 查询过滤器类型
	"FilterOperator",
	"FilterCondition",
	"SortCondition",
	"QueryParams",

	# 数据库相关类型
	"DatabaseConfig",
	"TransactionIsolationLevel",
	"TransactionOptions",

	# 数据模型相关类型
	"ModelFieldType",
	"ModelField",
	"ModelDefinition",

	# Repository特定类型
	"BulkOperationResult",
	"UpsertResult",
	"CacheStrategy",
	"CacheConfig",
]