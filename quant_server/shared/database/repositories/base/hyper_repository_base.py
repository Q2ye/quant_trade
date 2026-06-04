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
			conflict_strategy: upsert / ignore / replace
			chunk_size: 每批记录数（默认 1000，12 列时 ~12000 参数，远低于 32767）

		Returns:
			插入的记录数
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
			# upsert: on_conflict_do_nothing (same as ignore for full sync)

			result = await self.session.execute(stmt)
			total += result.rowcount

		return total

	async def _batch_upsert (self, records: List[Dict[str, Any]]) -> int:
		"""批量upsert实现（需要根据具体数据库调整）"""
		# 这里实现具体的upsert逻辑
		# 例如使用PostgreSQL的ON CONFLICT或MySQL的INSERT ... ON DUPLICATE KEY UPDATE
		pass

	async def _batch_insert_ignore (self, records: List[Dict[str, Any]]) -> int:
		"""批量插入忽略冲突"""
		# 这里实现具体的数据冲突忽略逻辑
		pass

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

			# 应用所有条件
			if conditions:
				query.where(and_(*conditions))

			result = await self.session.execute(query)
			return result.rowcount or 0

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"按时间范围删除失败: {str(e)}")

	async def aggregate_by_interval (
			self,
			start_time: datetime,
			end_time: datetime,
			interval: str = "1d",
			aggregation: Dict[str, str] = None,
			group_by: List[str] = None
	) -> List[Dict[str, Any]]:
		"""
		按时间间隔聚合数据

		Args:
			start_time: 开始时间
			end_time: 结束时间
			interval: 时间间隔（1m, 1h, 1d等）
			aggregation: 聚合函数映射（字段名: 函数名）
			group_by: 分组字段

		Returns:
			聚合结果列表
		"""
		try:
			from sqlalchemy import func

			# 构建基础查询
			query = select()

			# 生成时间桶表达式
			time_column = getattr(self.model, self.time_column)

			# 根据interval生成时间桶
			if interval == "1m":
				time_bucket = func.date_trunc('minute', time_column)
			elif interval == "1h":
				time_bucket = func.date_trunc('hour', time_column)
			elif interval == "1d":
				time_bucket = func.date_trunc('day', time_column)
			elif interval == "1w":
				time_bucket = func.date_trunc('week', time_column)
			elif interval == "1M":
				time_bucket = func.date_trunc('month', time_column)
			else:
				time_bucket = func.date_trunc('day', time_column)  # 默认按天

			# 添加时间桶到查询
			query = query.add_columns(time_bucket.label('time_bucket'))

			# 处理聚合函数
			if aggregation:
				for field, agg_func in aggregation.items():
					if hasattr(self.model, field):
						column = getattr(self.model, field)
						if agg_func == "sum":
							query = query.add_columns(func.sum(column).label(f"sum_{field}"))
						elif agg_func == "avg":
							query = query.add_columns(func.avg(column).label(f"avg_{field}"))
						elif agg_func == "max":
							query = query.add_columns(func.max(column).label(f"max_{field}"))
						elif agg_func == "min":
							query = query.add_columns(func.min(column).label(f"min_{field}"))
						elif agg_func == "count":
							query = query.add_columns(func.count(column).label(f"count_{field}"))
			else:
				# 默认聚合：计数
				query = query.add_columns(func.count().label('count'))

			# 添加分组
			group_by_columns = ['time_bucket']
			if group_by:
				for field in group_by:
					if hasattr(self.model, field):
						column = getattr(self.model, field)
						query = query.add_columns(column.label(field))
						group_by_columns.append(field)

			# 设置FROM子句和WHERE条件
			query = query.select_from(self.model)
			query = query.where(
				and_(
					time_column >= start_time,
					time_column <= end_time
				)
			)

			# 执行分组
			query = query.group_by(*group_by_columns)
			query = query.order_by('time_bucket')

			# 执行查询
			result = await self.session.execute(query)
			rows = result.all()

			# 转换结果为字典列表
			aggregated_data = []
			for row in rows:
				row_dict = {}
				for i, column in enumerate(result.keys()):
					row_dict[column] = row[i]
				aggregated_data.append(row_dict)

			return aggregated_data

		except Exception as e:
			raise RepositoryError(f"按时间间隔聚合失败: {str(e)}")

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
