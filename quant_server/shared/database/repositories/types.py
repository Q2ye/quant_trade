# -*- coding: utf-8 -*-
"""
自定义数据库类型定义

位置：quant_server/shared/database/repositories/types.py

设计目的：
1. 提供统一的数据类型定义，确保类型一致性
2. 封装复杂的查询参数和结果类型
3. 支持强类型检查和IDE智能提示
4. 提供数据验证和转换功能
"""

from typing import TypeVar, Generic, Dict, Any, List, Optional, Union
from datetime import date, datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

# 异常类 - 在types中定义以便跨模块使用
class RepositoryError(Exception):
    """Repository基础异常类"""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(message)

# 泛型类型变量
T = TypeVar('T')
R = TypeVar('R')


class RepositoryResult(Generic[T]):
    """Repository操作结果基类"""

    def __init__(
            self,
            success: bool,
            data: Optional[T] = None,
            error: Optional[str] = None,
            total: Optional[int] = None,
            id: Optional[int] = None,
            created_at: Optional[datetime] = None
    ):
        """
        初始化操作结果

        Args:
            success: 是否成功
            data: 返回数据
            error: 错误信息
            total: 数据总数（用于分页）
            id: 记录ID（用于创建操作）
            created_at: 创建时间（用于创建操作）
        """
        self.success = success
        self.data = data
        self.error = error
        self.total = total
        self.id = id
        self.created_at = created_at

    @classmethod
    def success_result(cls, data: T, total: Optional[int] = None) -> 'RepositoryResult[T]':
        """创建成功结果"""
        return cls(success=True, data=data, total=total)

    @classmethod
    def error_result(cls, error: str) -> 'RepositoryResult[T]':
        """创建错误结果"""
        return cls(success=False, error=error)

    def is_success(self) -> bool:
        """是否成功"""
        return self.success

    def get_data(self) -> Optional[T]:
        """获取数据"""
        return self.data

    def get_error(self) -> Optional[str]:
        """获取错误信息"""
        return self.error

    def get_total(self) -> Optional[int]:
        """获取总数"""
        return self.total

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "total": self.total
        }


@dataclass
class PaginationParams:
    """分页参数"""
    page: int = 1
    page_size: int = 20
    order_by: Optional[str] = None
    order_desc: bool = True

    def get_offset(self) -> int:
        """计算偏移量"""
        return (self.page - 1) * self.page_size

    def get_limit(self) -> int:
        """获取限制数量"""
        return self.page_size

    def validate(self) -> bool:
        """验证参数有效性"""
        return self.page > 0 and self.page_size > 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "page": self.page,
            "page_size": self.page_size,
            "order_by": self.order_by,
            "order_desc": self.order_desc
        }


@dataclass
class PaginationResult(Generic[T]):
    """分页结果"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def create(cls, items: List[T], total: int, page: int,
               page_size: int) -> 'PaginationResult[T]':
        """创建分页结果"""
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

    def has_previous(self) -> bool:
        """是否有上一页"""
        return self.page > 1

    def has_next(self) -> bool:
        """是否有下一页"""
        return self.page < self.total_pages

    def get_previous_page(self) -> Optional[int]:
        """获取上一页页码"""
        return self.page - 1 if self.has_previous() else None

    def get_next_page(self) -> Optional[int]:
        """获取下一页页码"""
        return self.page + 1 if self.has_next() else None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
            "has_previous": self.has_previous(),
            "has_next": self.has_next(),
            "previous_page": self.get_previous_page(),
            "next_page": self.get_next_page()
        }


@dataclass
class DateRange:
    """日期范围"""
    start_date: date
    end_date: date

    def validate(self) -> bool:
        """验证日期范围是否有效"""
        return self.start_date <= self.end_date

    def days(self) -> int:
        """获取天数"""
        return (self.end_date - self.start_date).days + 1

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "days": self.days()
        }


@dataclass
class DateTimeRange:
    """日期时间范围"""
    start_time: datetime
    end_time: datetime

    def validate(self) -> bool:
        """验证时间范围是否有效"""
        return self.start_time <= self.end_time

    def seconds(self) -> float:
        """获取秒数"""
        return (self.end_time - self.start_time).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "seconds": self.seconds()
        }


# ==================== 查询过滤器类型 ====================

class FilterOperator(str, Enum):
    """过滤操作符枚举"""
    EQ = "eq"  # 等于
    NE = "ne"  # 不等于
    GT = "gt"  # 大于
    GE = "ge"  # 大于等于
    LT = "lt"  # 小于
    LE = "le"  # 小于等于
    LIKE = "like"  # 模糊匹配
    ILIKE = "ilike"  # 不区分大小写的模糊匹配
    IN = "in"  # 在列表中
    NOT_IN = "not_in"  # 不在列表中
    IS_NULL = "is_null"  # 为空
    NOT_NULL = "not_null"  # 不为空
    BETWEEN = "between"  # 在范围内
    CONTAINS = "contains"  # 包含（用于JSON/数组字段）


@dataclass
class FilterCondition:
    """过滤条件"""
    field: str
    operator: FilterOperator
    value: Any

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "field": self.field,
            "operator": self.operator.value,
            "value": self.value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FilterCondition':
        """从字典创建"""
        return cls(
            field=data.get("field", ""),
            operator=FilterOperator(data.get("operator", "eq")),
            value=data.get("value")
        )


@dataclass
class SortCondition:
    """排序条件"""
    field: str
    descending: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "field": self.field,
            "descending": self.descending
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SortCondition':
        """从字典创建"""
        return cls(
            field=data.get("field", ""),
            descending=data.get("descending", False)
        )


@dataclass
class QueryParams:
    """查询参数"""
    filters: List[FilterCondition] = field(default_factory=list)
    sorts: List[SortCondition] = field(default_factory=list)
    pagination: PaginationParams = field(default_factory=lambda: PaginationParams())

    def add_filter(self, filter_cond: FilterCondition) -> 'QueryParams':
        """添加过滤条件"""
        self.filters.append(filter_cond)
        return self

    def add_sort(self, sort_cond: SortCondition) -> 'QueryParams':
        """添加排序条件"""
        self.sorts.append(sort_cond)
        return self

    @classmethod
    def create(cls, page: int = 1, page_size: int = 20) -> 'QueryParams':
        """创建查询参数"""
        return cls(
            filters=[],
            sorts=[],
            pagination=PaginationParams(page=page, page_size=page_size)
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "filters": [f.to_dict() for f in self.filters],
            "sorts": [s.to_dict() for s in self.sorts],
            "pagination": self.pagination.to_dict()
        }


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
    ssl_mode: Optional[str] = None

    @property
    def connection_string(self) -> str:
        """获取连接字符串"""
        ssl_part = f"?sslmode={self.ssl_mode}" if self.ssl_mode else ""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}{ssl_part}"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "echo": self.echo,
            "ssl_mode": self.ssl_mode
        }


class TransactionIsolationLevel(str, Enum):
    """事务隔离级别枚举"""
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

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "isolation_level": self.isolation_level.value,
            "read_only": self.read_only,
            "deferrable": self.deferrable
        }


# ==================== 数据模型相关类型 ====================

class ModelFieldType(str, Enum):
    """模型字段类型枚举"""
    INTEGER = "integer"
    BIGINT = "bigint"
    STRING = "string"
    TEXT = "text"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    DECIMAL = "decimal"
    JSON = "json"
    JSONB = "jsonb"
    FLOAT = "float"
    DOUBLE = "double"
    UUID = "uuid"
    ARRAY = "array"
    ENUM = "enum"


@dataclass
class ModelField:
    """模型字段定义"""
    name: str
    field_type: ModelFieldType  # 修改为 field_type 避免与内置type冲突
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False
    index: bool = False
    default: Any = None
    foreign_key: Optional[str] = None
    comment: Optional[str] = None
    max_length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "type": self.field_type.value,
            "nullable": self.nullable,
            "primary_key": self.primary_key,
            "unique": self.unique,
            "index": self.index,
            "default": self.default,
            "foreign_key": self.foreign_key,
            "comment": self.comment,
            "max_length": self.max_length,
            "precision": self.precision,
            "scale": self.scale
        }


@dataclass
class ModelDefinition:
    """模型定义"""
    name: str
    table_name: str
    fields: List[ModelField]
    indexes: List[List[str]] = field(default_factory=list)
    unique_constraints: List[List[str]] = field(default_factory=list)
    comment: Optional[str] = None

    def get_primary_key_fields(self) -> List[ModelField]:
        """获取主键字段"""
        return [keyField for keyField in self.fields if keyField.primary_key]

    def get_foreign_key_fields(self) -> List[ModelField]:
        """获取外键字段"""
        return [keyField for keyField in self.fields if keyField.foreign_key]

    def get_index_fields(self) -> List[ModelField]:
        """获取索引字段"""
        return [keyField for keyField in self.fields if keyField.index]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "table_name": self.table_name,
            "fields": [keyField.to_dict() for keyField in self.fields],
            "indexes": self.indexes,
            "unique_constraints": self.unique_constraints,
            "comment": self.comment
        }


# ==================== Repository特定类型 ====================

@dataclass
class BulkOperationResult:
    """批量操作结果"""
    success_count: int
    failed_count: int
    total_count: int
    errors: List[Dict[str, Any]] = field(default_factory=list)

    def success_rate(self) -> float:
        """计算成功率"""
        return (self.success_count / self.total_count * 100) if self.total_count > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
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

    def total(self) -> int:
        """获取总数"""
        return len(self.created) + len(self.updated) + len(self.skipped)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "created_count": len(self.created),
            "updated_count": len(self.updated),
            "skipped_count": len(self.skipped),
            "total_count": self.total()
        }


class CacheStrategy(str, Enum):
    """缓存策略枚举"""
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

    def get_key(self, *parts) -> str:
        """生成缓存键"""
        key_parts = [self.prefix] + [str(part) for part in parts]
        return ":".join(key_parts)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "strategy": self.strategy.value,
            "ttl": self.ttl,
            "max_size": self.max_size,
            "prefix": self.prefix
        }


# ==================== 高级查询类型 ====================

@dataclass
class JoinCondition:
    """关联查询条件"""
    model: Any  # 关联模型
    join_type: str = "inner"  # join类型：inner, left, right, full
    on_clause: Optional[Any] = None  # 关联条件
    eager_load: bool = False  # 是否立即加载


@dataclass
class AggregationResult:
    """聚合结果"""
    count: Optional[int] = None
    sum: Optional[float] = None
    avg: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "count": self.count,
            "sum": self.sum,
            "avg": self.avg,
            "min": self.min,
            "max": self.max
        }


@dataclass
class TimeRange:
    """时间范围 - 通用时间间隔表示"""

    start: datetime = field(default_factory=datetime.now)
    end: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """初始化后验证时间范围"""
        if self.end < self.start:
            raise ValueError("结束时间不能早于开始时间")

    @classmethod
    def create_from_dates(cls, start_date: date, end_date: date) -> 'TimeRange':
        """
        从日期创建时间范围（时间为当天的开始和结束）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            TimeRange 实例
        """
        start = datetime.combine(start_date, datetime.min.time())
        end = datetime.combine(end_date, datetime.max.time())
        return cls(start=start, end=end)

    @classmethod
    def create_from_datetimes(cls, start_time: datetime, end_time: datetime) -> 'TimeRange':
        """
        从 datetime 创建时间范围

        Args:
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            TimeRange 实例
        """
        return cls(start=start_time, end=end_time)

    @classmethod
    def create_last_n_days(cls, days: int, end_date: Optional[date] = None) -> 'TimeRange':
        """
        创建过去 N 天的时间范围

        Args:
            days: 天数
            end_date: 结束日期（默认为今天）

        Returns:
            TimeRange 实例
        """
        if end_date is None:
            end_date = date.today()

        start_date = end_date - timedelta(days=days - 1)
        return cls.create_from_dates(start_date, end_date)

    @classmethod
    def create_last_n_hours(cls, hours: int, end_time: Optional[datetime] = None) -> 'TimeRange':
        """
        创建过去 N 小时的时间范围

        Args:
            hours: 小时数
            end_time: 结束时间（默认为现在）

        Returns:
            TimeRange 实例
        """
        if end_time is None:
            end_time = datetime.now()

        start_time = end_time - timedelta(hours=hours)
        return cls(start=start_time, end=end_time)

    @classmethod
    def create_today(cls) -> 'TimeRange':
        """创建今天的时间范围"""
        today = date.today()
        return cls.create_from_dates(today, today)

    @classmethod
    def create_this_week(cls) -> 'TimeRange':
        """创建本周的时间范围"""
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())  # 周一
        end_of_week = start_of_week + timedelta(days=6)  # 周日
        return cls.create_from_dates(start_of_week, end_of_week)

    @classmethod
    def create_this_month(cls) -> 'TimeRange':
        """创建本月的时间范围"""
        today = date.today()
        start_of_month = date(today.year, today.month, 1)

        # 计算下个月的第一天，然后减一天得到本月的最后一天
        if today.month == 12:
            next_month = date(today.year + 1, 1, 1)
        else:
            next_month = date(today.year, today.month + 1, 1)

        end_of_month = next_month - timedelta(days=1)
        return cls.create_from_dates(start_of_month, end_of_month)

    @classmethod
    def create_this_year(cls) -> 'TimeRange':
        """创建本年的时间范围"""
        today = date.today()
        start_of_year = date(today.year, 1, 1)
        end_of_year = date(today.year, 12, 31)
        return cls.create_from_dates(start_of_year, end_of_year)

    def validate(self) -> bool:
        """验证时间范围是否有效"""
        return self.start <= self.end

    def contains(self, time_point: Union[datetime, date]) -> bool:
        """
        检查时间点是否在时间范围内

        Args:
            time_point: 时间点（datetime 或 date）

        Returns:
            是否在范围内
        """
        if isinstance(time_point, date):
            # 如果是 date 类型，转换为 datetime 进行比较
            return self.start.date() <= time_point <= self.end.date()
        elif isinstance(time_point, datetime):
            return self.start <= time_point <= self.end
        else:
            raise TypeError("time_point 必须是 datetime 或 date 类型")

    def overlaps(self, other: 'TimeRange') -> bool:
        """
        检查两个时间范围是否有重叠

        Args:
            other: 另一个时间范围

        Returns:
            是否有重叠
        """
        return not (self.end < other.start or self.start > other.end)

    def intersection(self, other: 'TimeRange') -> Optional['TimeRange']:
        """
        计算两个时间范围的交集

        Args:
            other: 另一个时间范围

        Returns:
            交集时间范围，如果没有交集则返回 None
        """
        if not self.overlaps(other):
            return None

        start = max(self.start, other.start)
        end = min(self.end, other.end)
        return TimeRange(start=start, end=end)

    def union(self, other: 'TimeRange') -> 'TimeRange':
        """
        计算两个时间范围的并集

        Args:
            other: 另一个时间范围

        Returns:
            并集时间范围
        """
        start = min(self.start, other.start)
        end = max(self.end, other.end)
        return TimeRange(start=start, end=end)

    def duration(self) -> timedelta:
        """获取时间范围的长度"""
        return self.end - self.start

    def days(self) -> int:
        """获取天数（包括小数部分）"""
        return self.duration().days

    def hours(self) -> float:
        """获取小时数"""
        return self.duration().total_seconds() / 3600

    def minutes(self) -> float:
        """获取分钟数"""
        return self.duration().total_seconds() / 60

    def split_by_days(self) -> List['TimeRange']:
        """
        按天分割时间范围

        Returns:
            按天分割的时间范围列表
        """
        ranges = []
        current_date = self.start.date()
        end_date = self.end.date()

        while current_date <= end_date:
            day_start = datetime.combine(current_date, datetime.min.time())
            day_end = datetime.combine(current_date, datetime.max.time())

            # 调整第一天和最后一天的开始和结束时间
            if current_date == self.start.date():
                day_start = self.start

            if current_date == self.end.date():
                day_end = self.end

            ranges.append(TimeRange(start=day_start, end=day_end))
            current_date += timedelta(days=1)

        return ranges

    def split_by_hours(self, hours_per_interval: int = 1) -> List['TimeRange']:
        """
        按小时间隔分割时间范围

        Args:
            hours_per_interval: 每个间隔的小时数

        Returns:
            按小时间隔分割的时间范围列表
        """
        if hours_per_interval <= 0:
            raise ValueError("hours_per_interval 必须大于 0")

        ranges = []
        current_start = self.start

        while current_start < self.end:
            current_end = min(current_start + timedelta(hours=hours_per_interval), self.end)
            ranges.append(TimeRange(start=current_start, end=current_end))
            current_start = current_end

        return ranges

    def to_date_range(self) -> 'DateRange':
        """
        转换为 DateRange（只保留日期部分）

        Returns:
            DateRange 实例
        """
        return DateRange(
            start_date=self.start.date(),
            end_date=self.end.date()
        )

    def to_datetime_range(self) -> 'DateTimeRange':
        """
        转换为 DateTimeRange

        Returns:
            DateTimeRange 实例
        """
        return DateTimeRange(
            start_time=self.start,
            end_time=self.end
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "duration_seconds": self.duration().total_seconds() if self.start and self.end else 0,
            "duration_days": self.days(),
            "duration_hours": self.hours(),
            "duration_minutes": self.minutes(),
            "is_valid": self.validate()
        }

    def __str__(self) -> str:
        """字符串表示"""
        start_str = self.start.strftime("%Y-%m-%d %H:%M:%S")
        end_str = self.end.strftime("%Y-%m-%d %H:%M:%S")
        return f"TimeRange({start_str} to {end_str})"

    def __repr__(self) -> str:
        """表示形式"""
        return f"TimeRange(start={self.start!r}, end={self.end!r})"


# ==================== 导出所有类型 ====================

__all__ = [
    # 基础类型
    "RepositoryResult",
    "RepositoryError",
    "PaginationParams",
    "PaginationResult",
    "DateRange",
    "DateTimeRange",
    "TimeRange",

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

    # 高级查询类型
    "JoinCondition",
    "AggregationResult"
]