# quant_server/shared/database/repositories/base/query_builder.py
"""
查询构建器 - 构建复杂的数据库查询

提供灵活的查询条件构建、排序、过滤等功能
支持链式调用，使查询构建更加直观
"""

from typing import List, Dict, Any, Optional, Union, Callable
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, or_, not_, desc, asc, func
from sqlalchemy.sql import Select, ColumnElement


class Operator(str, Enum):
	"""查询操作符枚举"""
	EQ = "eq"  # 等于
	NE = "ne"  # 不等于
	GT = "gt"  # 大于
	GE = "ge"  # 大于等于
	LT = "lt"  # 小于
	LE = "le"  # 小于等于
	IN = "in"  # 在列表中
	NOT_IN = "not_in"  # 不在列表中
	LIKE = "like"  # 模糊匹配
	ILIKE = "ilike"  # 不区分大小写模糊匹配
	IS_NULL = "is_null"  # 为空
	IS_NOT_NULL = "is_not_null"  # 不为空
	BETWEEN = "between"  # 在范围内


class LogicalOperator(str, Enum):
	"""逻辑操作符枚举"""
	AND = "and"
	OR = "or"
	NOT = "not"


class FilterCondition(BaseModel):
	"""过滤条件模型"""

	field: str = Field(..., description="字段名")
	operator: Operator = Field(..., description="操作符")
	value: Optional[Any] = Field(None, description="值")
	value2: Optional[Any] = Field(None, description="第二个值（用于BETWEEN操作）")

	class Config:
		use_enum_values = True
		json_schema_extra = {
			"example": {
				"field": "price",
				"operator": "gt",
				"value": 100
			}
		}


class SortCondition(BaseModel):
	"""排序条件模型"""

	field: str = Field(..., description="字段名")
	descending: bool = Field(default=False, description="是否降序")

	class Config:
		json_schema_extra = {
			"example": {
				"field": "created_at",
				"descending": True
			}
		}


class QueryParams(BaseModel):
	"""查询参数模型"""

	filters: List[FilterCondition] = Field(default_factory=list, description="过滤条件列表")
	sorts: List[SortCondition] = Field(default_factory=list, description="排序条件列表")
	logical_operator: LogicalOperator = Field(default=LogicalOperator.AND, description="逻辑操作符")
	include_deleted: bool = Field(default=False, description="是否包含已删除记录")

	class Config:
		use_enum_values = True


class QueryBuilder:
	"""查询构建器"""

	def __init__ (self, model):
		"""
		初始化查询构建器

		Args:
			model: SQLAlchemy模型类
		"""
		self.model = model
		self._query = select(model)
		self._conditions = []
		self._sort_conditions = []
		self._include_deleted = False

	def filter (self, **filters) -> 'QueryBuilder':
		"""
		添加简单过滤条件

		Args:
			**filters: 字段名=值形式的过滤条件

		Returns:
			查询构建器实例（支持链式调用）
		"""
		for field, value in filters.items():
			if hasattr(self.model, field):
				if value is None:
					self._conditions.append(getattr(self.model, field).is_(None))
				else:
					self._conditions.append(getattr(self.model, field) == value)
		return self

	def filter_by (self, condition: FilterCondition) -> 'QueryBuilder':
		"""
		添加复杂过滤条件

		Args:
			condition: 过滤条件对象

		Returns:
			查询构建器实例
		"""
		field = getattr(self.model, condition.field, None)
		if not field:
			return self

		if condition.operator == Operator.EQ:
			self._conditions.append(field == condition.value)
		elif condition.operator == Operator.NE:
			self._conditions.append(field != condition.value)
		elif condition.operator == Operator.GT:
			self._conditions.append(field > condition.value)
		elif condition.operator == Operator.GE:
			self._conditions.append(field >= condition.value)
		elif condition.operator == Operator.LT:
			self._conditions.append(field < condition.value)
		elif condition.operator == Operator.LE:
			self._conditions.append(field <= condition.value)
		elif condition.operator == Operator.IN:
			self._conditions.append(field.in_(condition.value))
		elif condition.operator == Operator.NOT_IN:
			self._conditions.append(field.not_in(condition.value))
		elif condition.operator == Operator.LIKE:
			self._conditions.append(field.like(f"%{condition.value}%"))
		elif condition.operator == Operator.ILIKE:
			self._conditions.append(field.ilike(f"%{condition.value}%"))
		elif condition.operator == Operator.IS_NULL:
			self._conditions.append(field.is_(None))
		elif condition.operator == Operator.IS_NOT_NULL:
			self._conditions.append(field.is_not(None))
		elif condition.operator == Operator.BETWEEN:
			self._conditions.append(field.between(condition.value, condition.value2))

		return self

	def filter_many (self, conditions: List[FilterCondition],
	                 logical_operator: LogicalOperator = LogicalOperator.AND) -> 'QueryBuilder':
		"""
		添加多个过滤条件

		Args:
			conditions: 过滤条件列表
			logical_operator: 逻辑操作符

		Returns:
			查询构建器实例
		"""
		condition_list = []
		for condition in conditions:
			field = getattr(self.model, condition.field, None)
			if not field:
				continue

			# 构建单个条件
			if condition.operator == Operator.EQ:
				condition_list.append(field == condition.value)
			elif condition.operator == Operator.NE:
				condition_list.append(field != condition.value)
		# ... 其他操作符类似处理

		if condition_list:
			if logical_operator == LogicalOperator.AND:
				self._conditions.append(and_(*condition_list))
			elif logical_operator == LogicalOperator.OR:
				self._conditions.append(or_(*condition_list))
			elif logical_operator == LogicalOperator.NOT:
				self._conditions.append(not_(and_(*condition_list)))

		return self

	def sort (self, field: str, descending: bool = False) -> 'QueryBuilder':
		"""
		添加排序条件

		Args:
			field: 字段名
			descending: 是否降序

		Returns:
			查询构建器实例
		"""
		if hasattr(self.model, field):
			if descending:
				self._sort_conditions.append(desc(getattr(self.model, field)))
			else:
				self._sort_conditions.append(asc(getattr(self.model, field)))
		return self

	def sort_by (self, condition: SortCondition) -> 'QueryBuilder':
		"""
		添加排序条件

		Args:
			condition: 排序条件对象

		Returns:
			查询构建器实例
		"""
		return self.sort(condition.field, condition.descending)

	def sort_many (self, conditions: List[SortCondition]) -> 'QueryBuilder':
		"""
		添加多个排序条件

		Args:
			conditions: 排序条件列表

		Returns:
			查询构建器实例
		"""
		for condition in conditions:
			self.sort_by(condition)
		return self

	def include_deleted (self, include: bool = True) -> 'QueryBuilder':
		"""
		设置是否包含已删除记录

		Args:
			include: 是否包含已删除记录

		Returns:
			查询构建器实例
		"""
		self._include_deleted = include
		return self

	def offset (self, offset: int) -> 'QueryBuilder':
		"""
		设置偏移量

		Args:
			offset: 偏移量

		Returns:
			查询构建器实例
		"""
		self._query = self._query.offset(offset)
		return self

	def limit (self, limit: int) -> 'QueryBuilder':
		"""
		设置限制数

		Args:
			limit: 限制数

		Returns:
			查询构建器实例
		"""
		self._query = self._query.limit(limit)
		return self

	def paginate (self, page: int = 1, page_size: int = 20) -> 'QueryBuilder':
		"""
		设置分页

		Args:
			page: 页码
			page_size: 每页大小

		Returns:
			查询构建器实例
		"""
		offset = (page - 1) * page_size
		return self.offset(offset).limit(page_size)

	def build (self) -> Select:
		"""
		构建最终查询

		Returns:
			SQLAlchemy查询对象
		"""
		query = self._query

		# 应用过滤条件
		if self._conditions:
			query = query.where(and_(*self._conditions))

		# 应用软删除过滤
		if not self._include_deleted and hasattr(self.model, 'is_deleted'):
			query = query.where(self.model.is_deleted == False)

		# 应用排序条件
		if self._sort_conditions:
			query = query.order_by(*self._sort_conditions)

		return query

	@classmethod
	def from_query_params (cls, model, params: QueryParams) -> Select:
		"""
		从查询参数构建查询

		Args:
			model: SQLAlchemy模型类
			params: 查询参数对象

		Returns:
			SQLAlchemy查询对象
		"""
		builder = cls(model)

		# 添加过滤条件
		if params.filters:
			builder.filter_many(params.filters, params.logical_operator)

		# 添加排序条件
		if params.sorts:
			builder.sort_many(params.sorts)

		# 设置是否包含已删除记录
		builder.include_deleted(params.include_deleted)

		return builder.build()