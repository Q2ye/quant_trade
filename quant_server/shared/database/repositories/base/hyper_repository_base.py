# quant_server/shared/database/repositories/base/hyper_repository_base.py
"""
超表Repository基类 - 时序数据专用

专为时序数据（如行情数据、监控数据等）设计的Repository基类
提供时间分片、数据保留策略、批量写入等优化功能
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text, desc, delete
from sqlalchemy.sql import Select

from .repository_base import BaseRepository, T, RepositoryError
from .pagination import PaginationParams, PaginationResult
from ..types import TimeRange


class HyperRepositoryBase(BaseRepository[T]):
	"""超表Repository基类 - 针对时序数据优化"""

	def __init__ (self, session: AsyncSession, model: T):
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
			conflict_strategy: str = "upsert"
	) -> int:
		"""
		批量插入时序数据（优化性能）

		Args:
			records: 记录列表
			conflict_strategy: 冲突处理策略（upsert/ignore/replace）

		Returns:
			插入的记录数
		"""
		try:
			if not records:
				return 0

			# 准备批量插入数据
			now = datetime.now()
			for record in records:
				if hasattr(self.model, 'created_at'):
					record['created_at'] = record.get('created_at', now)
				if hasattr(self.model, 'updated_at'):
					record['updated_at'] = record.get('updated_at', now)

			# 批量插入
			if conflict_strategy == "upsert":
				# 使用upsert（需要具体数据库支持）
				return await self._batch_upsert(records)
			elif conflict_strategy == "ignore":
				# 忽略冲突
				return await self._batch_insert_ignore(records)
			else:
				# 普通插入
				instances = [self.model(**record) for record in records]
				self.session.add_all(instances)
				await self.session.flush()
				return len(instances)

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"批量插入失败: {str(e)}")

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
			query = delete(self.model).where(
				and_(
					getattr(self.model, self.time_column) >= start_time,
					getattr(self.model, self.time_column) <= end_time
				)
			)

			if symbol and hasattr(self.model, 'symbol'):
				query = query.where(self.model.symbol == symbol)

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
			# 这里实现具体的聚合逻辑
			# 根据interval生成时间桶，执行聚合查询
			pass

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