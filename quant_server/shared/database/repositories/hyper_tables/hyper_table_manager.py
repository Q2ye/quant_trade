"""
超表管理器 - 管理时序表的元数据和配置

主要功能：
1. 创建和管理超表
2. 配置超表属性（时间列、标签列等）
3. 查询超表状态和统计信息
4. 管理超表的分区策略

继承自：HyperRepositoryBase（因为是时序数据管理）
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, and_, or_
from sqlalchemy.exc import SQLAlchemyError

from quant_server.shared.database.repositories.base.hyper_repository_base import HyperRepositoryBase
from quant_server.shared.database.repositories.base.repository_base import RepositoryError
from quant_server.shared.database.models.system_models import HyperTableMetadata, TimeBucketConfig
from quant_server.shared.database.repositories.hyper_tables import ChunkManager, TimeBucketManager


class HyperTableManager(HyperRepositoryBase[HyperTableMetadata]):
	"""
	超表管理器类

	负责管理系统中所有超表（时序表）的元数据和配置信息
	"""

	def __init__ (self, session: AsyncSession):
		"""初始化超表管理器"""
		super().__init__(session, HyperTableMetadata)
		self.time_column = "created_at"

	async def create_hyper_table (
			self,
			table_name: str,
			time_column: str,
			tags: List[str] = None,
			chunk_time_interval: str = "1 day",
			compression_enabled: bool = True,
			compression_settings: Dict[str, Any] = None
	) -> HyperTableMetadata:
		"""
		创建新的超表

		Args:
			table_name: 表名
			time_column: 时间列名
			tags: 标签列列表（用于索引和查询优化）
			chunk_time_interval: 数据块时间间隔
			compression_enabled: 是否启用压缩
			compression_settings: 压缩设置

		Returns:
			创建的HyperTableMetadata对象

		Raises:
			RepositoryError: 创建失败时抛出
		"""
		try:
			# 检查表是否已存在
			existing = await self.get_by(table_name=table_name)
			if existing:
				raise RepositoryError(f"超表 '{table_name}' 已存在", "HYPER_TABLE_EXISTS")

			# 构建超表配置
			hyper_table_config = {
				"table_name": table_name,
				"time_column": time_column,
				"tags": tags or [],
				"chunk_time_interval": chunk_time_interval,
				"compression_enabled": compression_enabled,
				"compression_settings": compression_settings or {},
				"status": "active",
				"created_at": datetime.now(),
				"updated_at": datetime.now()
			}

			# 创建超表元数据记录
			return await self.create(hyper_table_config)

		except SQLAlchemyError as e:
			raise RepositoryError(f"创建超表失败: {str(e)}", "HYPER_TABLE_CREATE_ERROR")

	async def get_all_tables (self) -> List[HyperTableMetadata]:
		"""
		获取所有超表信息

		Returns:
			超表元数据列表
		"""
		try:
			return await self.get_all(status="active")
		except Exception as e:
			raise RepositoryError(f"获取超表列表失败: {str(e)}")

	async def get_table_info (self, table_name: str) -> Dict[str, Any]:
		"""
		获取超表详细信息

		Args:
			table_name: 表名

		Returns:
			超表信息字典
		"""
		try:
			hyper_table = await self.get_by(table_name=table_name, status="active")
			if not hyper_table:
				raise RepositoryError(f"超表 '{table_name}' 不存在", "HYPER_TABLE_NOT_FOUND")

			# 获取关联的时间分桶配置
			time_bucket_manager = TimeBucketManager(self.session)
			time_buckets = await time_bucket_manager.get_by_table(table_name)

			# 获取统计信息
			stats = await self._get_table_statistics(table_name)

			return {
				"table_name": hyper_table.table_name,
				"time_column": hyper_table.time_column,
				"tags": hyper_table.tags,
				"chunk_time_interval": hyper_table.chunk_time_interval,
				"compression_enabled": hyper_table.compression_enabled,
				"compression_settings": hyper_table.compression_settings,
				"status": hyper_table.status,
				"time_buckets": time_buckets,
				"statistics": stats,
				"created_at": hyper_table.created_at,
				"updated_at": hyper_table.updated_at
			}

		except Exception as e:
			raise RepositoryError(f"获取超表信息失败: {str(e)}")

	async def update_table_config (
			self,
			table_name: str,
			config_updates: Dict[str, Any]
	) -> HyperTableMetadata:
		"""
		更新超表配置

		Args:
			table_name: 表名
			config_updates: 配置更新字典

		Returns:
			更新后的超表元数据
		"""
		try:
			hyper_table = await self.get_by(table_name=table_name)
			if not hyper_table:
				raise RepositoryError(f"超表 '{table_name}' 不存在", "HYPER_TABLE_NOT_FOUND")

			# 更新配置
			for key, value in config_updates.items():
				if hasattr(hyper_table, key):
					setattr(hyper_table, key, value)

			hyper_table.updated_at = datetime.now()
			await self.session.flush()

			return hyper_table

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"更新超表配置失败: {str(e)}")

	async def disable_table (self, table_name: str, reason: str = "") -> bool:
		"""
		禁用超表

		Args:
			table_name: 表名
			reason: 禁用原因

		Returns:
			是否成功
		"""
		try:
			hyper_table = await self.get_by(table_name=table_name)
			if not hyper_table:
				raise RepositoryError(f"超表 '{table_name}' 不存在", "HYPER_TABLE_NOT_FOUND")

			hyper_table.status = "disabled"
			hyper_table.disabled_reason = reason
			hyper_table.updated_at = datetime.now()
			hyper_table.disabled_at = datetime.now()

			await self.session.flush()
			return True

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"禁用超表失败: {str(e)}")

	async def enable_table (self, table_name: str) -> bool:
		"""
		启用已禁用的超表

		Args:
			table_name: 表名

		Returns:
			是否成功
		"""
		try:
			hyper_table = await self.get_by(table_name=table_name)
			if not hyper_table:
				raise RepositoryError(f"超表 '{table_name}' 不存在", "HYPER_TABLE_NOT_FOUND")

			hyper_table.status = "active"
			hyper_table.disabled_reason = None
			hyper_table.updated_at = datetime.now()
			hyper_table.enabled_at = datetime.now()

			await self.session.flush()
			return True

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"启用超表失败: {str(e)}")

	async def _get_table_statistics (self, table_name: str) -> Dict[str, Any]:
		"""
		获取超表统计信息（私有方法）

		Args:
			table_name: 表名

		Returns:
			统计信息字典
		"""
		try:
			# 使用原始SQL查询统计信息（依赖具体数据库）
			# 这里是一个PostgreSQL示例
			stats_query = text(f"""
                SELECT 
                    COUNT(*) as total_rows,
                    MIN({self.time_column}) as min_time,
                    MAX({self.time_column}) as max_time,
                    pg_size_pretty(pg_total_relation_size(:table_name)) as total_size,
                    COUNT(DISTINCT symbol) as unique_symbols
                FROM {table_name}
                WHERE {self.time_column} IS NOT NULL
            """)

			result = await self.session.execute(stats_query, {"table_name": table_name})
			row = result.first()

			if row:
				return {
					"total_rows": row.total_rows,
					"time_range": {
						"min": row.min_time,
						"max": row.max_time
					},
					"total_size": row.total_size,
					"unique_symbols": row.unique_symbols
				}
			return {}

		except Exception:
			# 如果查询失败，返回空统计
			return {}

	async def optimize_table (self, table_name: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
		"""
		优化超表性能

		Args:
			table_name: 表名
			options: 优化选项

		Returns:
			优化结果
		"""
		try:
			options = options or {}

			# 1. 重建索引
			if options.get("rebuild_index", False):
				await self._rebuild_indexes(table_name)

			# 2. 重新压缩数据
			if options.get("recompress", False):
				await self._recompress_data(table_name)

			# 3. 合并小数据块
			if options.get("merge_chunks", False):
				chunk_manager = ChunkManager(self.session)
				await chunk_manager.merge_small_chunks(table_name)

			return {
				"table_name": table_name,
				"optimized": True,
				"operations": list(options.keys()),
				"timestamp": datetime.now()
			}

		except Exception as e:
			raise RepositoryError(f"优化超表失败: {str(e)}")

	async def _rebuild_indexes (self, table_name: str):
		"""重建索引（私有方法）"""
		# 实现索引重建逻辑
		pass

	async def _recompress_data (self, table_name: str):
		"""重新压缩数据（私有方法）"""
		# 实现数据重新压缩逻辑
		pass

	async def get_table_size (self, table_name: str) -> Dict[str, Any]:
		"""
		获取超表大小信息

		Args:
			table_name: 表名

		Returns:
			大小信息字典
		"""
		try:
			# PostgreSQL示例
			size_query = text(f"""
                SELECT 
                    pg_size_pretty(pg_total_relation_size(:table_name)) as total_size,
                    pg_size_pretty(pg_relation_size(:table_name)) as table_size,
                    pg_size_pretty(pg_indexes_size(:table_name)) as index_size,
                    pg_size_pretty(pg_total_relation_size(:table_name) - pg_relation_size(:table_name)) as toast_size
            """)

			result = await self.session.execute(size_query, {"table_name": table_name})
			row = result.first()

			if row:
				return {
					"total_size": row.total_size,
					"table_size": row.table_size,
					"index_size": row.index_size,
					"toast_size": row.toast_size
				}
			return {}

		except Exception as e:
			raise RepositoryError(f"获取表大小失败: {str(e)}")

	async def cleanup_orphaned_chunks (self, table_name: str) -> int:
		"""
		清理孤立的超表数据块

		Args:
			table_name: 表名

		Returns:
			清理的数据块数量
		"""
		try:
			chunk_manager = ChunkManager(self.session)
			return await chunk_manager.cleanup_orphaned(table_name)

		except Exception as e:
			raise RepositoryError(f"清理孤立数据块失败: {str(e)}")