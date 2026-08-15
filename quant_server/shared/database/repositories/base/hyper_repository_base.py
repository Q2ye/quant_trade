# quant_server/shared/database/repositories/base/hyper_repository_base.py
"""
超表Repository基类 - 时序数据专用

专为时序数据（如行情数据、监控数据等）设计的Repository基类
提供时间分片、数据保留策略、批量写入等优化功能
"""

from datetime import datetime
from typing import List, Dict, Any, Optional, Type

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from .repository_base import BaseRepository, T, RepositoryError
from ..types import TimeRange


class HyperRepositoryBase(BaseRepository[T]):
	"""超表Repository基类 - 针对时序数据优化"""

	def __init__ (self, session: AsyncSession, model: Type[T]):
		"""
		初始化超表Repository

		Args:
			session: 数据库会话
			model: 数据表模型（超表）
		"""
		super().__init__(session, model)
		self.time_column = "timestamp"  # 默认时间列名

	async def get_by_time_range (
			self,
			start_time: datetime,
			end_time: datetime,
			symbol: Optional[str] = None,
			limit: int = 1000
	) -> List[T]:
		"""
		根据时间范围查询数据（时序数据专用）

		Args:
			start_time: 开始时间
			end_time: 结束时间
			symbol: 标的代码（可选）
			limit: 限制记录数

		Returns:
			时间范围内的数据列表
		"""
		try:
			query = select(self.model).where(
				and_(
					getattr(self.model, self.time_column) >= start_time,
					getattr(self.model, self.time_column) <= end_time
				)
			)

			if symbol and hasattr(self.model, 'symbol'):
				query = query.where(self.model.symbol == symbol)

			query = query.order_by(getattr(self.model, self.time_column)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"按时间范围查询失败: {str(e)}")

	async def get_latest_record (
			self,
			symbol: Optional[str] = None,
			limit: int = 1
	) -> Optional[T]:
		"""
		获取最新记录

		Args:
			symbol: 标的代码（可选）
			limit: 限制记录数

		Returns:
			最新记录或None
		"""
		try:
			query = select(self.model)

			if symbol and hasattr(self.model, 'symbol'):
				query = query.where(self.model.symbol == symbol)

			query = query.order_by(desc(getattr(self.model, self.time_column))).limit(limit)

			result = await self.session.execute(query)
			if limit == 1:
				return result.scalar_one_or_none()
			else:
				return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取最新记录失败: {str(e)}")

	async def batch_insert (
			self,
			records: List[Dict[str, Any]],
			conflict_strategy: str = "upsert",
			chunk_size: int = 1000,
	) -> int:
		"""
		分批批量插入，避免 PostgreSQL 32767 参数上限。

		Args:
			records: 记录列表
			conflict_strategy: upsert / ignore
			    - ignore: ON CONFLICT DO NOTHING（冲突时跳过）
			    - upsert: ON CONFLICT DO UPDATE（冲突时更新非约束列）
			chunk_size: 每批记录数（默认 1000，12 列时 ~12000 参数，远低于 32767）

		Returns:
			插入/更新的记录数
		"""
		if not records:
			return 0

		from sqlalchemy.dialects.postgresql import insert as pg_insert

		now = datetime.now()
		total = 0

		for i in range(0, len(records), chunk_size):
			chunk = records[i:i + chunk_size]
			# 转换日期
			for record in chunk:
				record = self._convert_record_datetime(record)
				if hasattr(self.model, 'created_at'):
					record.setdefault('created_at', now)
				if hasattr(self.model, 'updated_at'):
					record.setdefault('updated_at', now)

			stmt = pg_insert(self.model).values(chunk)

			if conflict_strategy == "ignore":
				stmt = stmt.on_conflict_do_nothing()
				result = await self.session.execute(stmt)
				total += result.rowcount
			elif conflict_strategy == "upsert":
				info = self._resolve_conflict_info()
				if info is None:
					stmt = stmt.on_conflict_do_nothing()
				else:
					conflict_cols, constraint_name = info
					# 仅更新数据中实际存在的列，避免将未传入的列设为 NULL
					data_keys = set(chunk[0].keys()) if chunk else set()
					skip_set = set(conflict_cols) | {'created_at', 'id'}
					update_cols = {
						c.name: stmt.excluded[c.name]
						for c in self.model.__table__.columns
						if c.name not in skip_set and c.name in data_keys
					}
					if constraint_name:
						stmt = stmt.on_conflict_do_update(
							constraint=constraint_name,
							set_=update_cols,
						)
					else:
						stmt = stmt.on_conflict_do_update(
							index_elements=conflict_cols,
							set_=update_cols,
						)
				result = await self.session.execute(stmt)
				total += result.rowcount

		return total

	def _resolve_conflict_info (self):
		"""
		从 Model 反射冲突列与约束名，用于 ON CONFLICT 子句。

		Returns:
			(columns: List[str], constraint_name: Optional[str]) 或 None
			None 表示无法确定，调用方应退化为 DO NOTHING

		解析优先级：
		1. __table_args__ 中的 UniqueConstraint（优先，含约束名）
		2. __table__.constraints 中的 UniqueConstraint / PrimaryKeyConstraint
		3. 返回 None
		"""
		from sqlalchemy import UniqueConstraint, PrimaryKeyConstraint

		# 阶段 1：__table_args__ 中的 UniqueConstraint（优先，有名有姓）
		ta = getattr(self.model, '__table_args__', None)
		if isinstance(ta, tuple):
			for arg in ta:
				if isinstance(arg, UniqueConstraint):
					return (
						[c if isinstance(c, str) else c.name for c in arg.columns],
						getattr(arg, 'name', None),
					)

		# 阶段 2：__table__.constraints
		for constraint in self.model.__table__.constraints:
			if isinstance(constraint, UniqueConstraint):
				return (
					[col.name for col in constraint.columns],
					getattr(constraint, 'name', None),
				)
			if isinstance(constraint, PrimaryKeyConstraint):
				return (
					[col.name for col in constraint.columns],
					getattr(constraint, 'name', None),
				)

		# 无法确定冲突列
		return None

	async def delete_by_time_range (
			self,
			start_time: datetime,
			end_time: datetime,
			symbol: Optional[str] = None
	) -> int:
		"""
		删除时间范围内的数据

		Args:
			start_time: 开始时间
			end_time: 结束时间
			symbol: 标的代码（可选）

		Returns:
			删除的记录数
		"""
		try:
			# 构建删除查询
			from sqlalchemy import delete as sql_delete
			query = sql_delete(self.model)

			# 构建条件列表
			conditions = [
				getattr(self.model, self.time_column) >= start_time,
				getattr(self.model, self.time_column) <= end_time
			]

			# 添加标的代码条件
			if symbol and hasattr(self.model, 'symbol'):
				conditions.append(self.model.symbol == symbol)

			# 应用所有条件（修复：where() 返回新语句对象，必须接收返回值，
			# 否则执行的是无条件 DELETE 全表——灾难级 bug）
			if conditions:
				query = query.where(and_(*conditions))

			result = await self.session.execute(query)
			return result.rowcount or 0

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"按时间范围删除失败: {str(e)}")


	async def get_statistics (
			self,
			start_time: datetime,
			end_time: datetime,
			symbol: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取统计信息

		Args:
			start_time: 开始时间
			end_time: 结束时间
			symbol: 标的代码（可选）

		Returns:
			统计信息字典
		"""
		try:
			query = select(
				func.count().label("count"),
				func.min(getattr(self.model, self.time_column)).label("first_time"),
				func.max(getattr(self.model, self.time_column)).label("last_time")
			).where(
				and_(
					getattr(self.model, self.time_column) >= start_time,
					getattr(self.model, self.time_column) <= end_time
				)
			)

			if symbol and hasattr(self.model, 'symbol'):
				query = query.where(self.model.symbol == symbol)

			result = await self.session.execute(query)
			stats = result.first()

			return {
				"count": stats.count if stats else 0,
				"first_time": stats.first_time,
				"last_time": stats.last_time,
				"time_range": TimeRange(start=stats.first_time, end=stats.last_time) if stats else None
			}

		except Exception as e:
			raise RepositoryError(f"获取统计信息失败: {str(e)}")
