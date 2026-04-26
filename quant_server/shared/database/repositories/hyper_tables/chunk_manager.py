"""
数据分片管理器 - 管理时序数据的分片存储

主要功能：
1. 创建和管理数据分片
2. 分片大小和性能监控
3. 分片合并和分裂
4. 分片存储优化

继承自：BaseRepository（因为是分片元数据管理）
"""

from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy import select, and_, or_, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.system_models import ChunkMetadata
from quant_server.shared.database.repositories.base.repository_base import BaseRepository, RepositoryError


class ChunkManager(BaseRepository[ChunkMetadata]):
	"""
	数据分片管理器类

	负责管理时序数据的分片存储，优化查询性能
	"""

	def __init__ (self, session: AsyncSession):
		"""初始化分片管理器"""
		super().__init__(session, ChunkMetadata)

	async def create_chunk (
			self,
			table_name: str,
			chunk_name: str,
			start_time: datetime,
			end_time: datetime,
			storage_type: str = "hot",
			max_size_mb: int = 1024,
			compression_enabled: bool = False
	) -> ChunkMetadata:
		"""
		创建新的数据分片

		Args:
			table_name: 表名
			chunk_name: 分片名
			start_time: 分片开始时间
			end_time: 分片结束时间
			storage_type: 存储类型（hot, warm, cold）
			max_size_mb: 最大大小（MB）
			compression_enabled: 是否启用压缩

		Returns:
			分片元数据对象
		"""
		try:
			# 检查时间范围有效性
			if start_time >= end_time:
				raise RepositoryError(
					"分片开始时间必须早于结束时间",
					"INVALID_TIME_RANGE"
				)

			# 检查分片是否重叠
			overlapping = await self._find_overlapping_chunks(
				table_name, start_time, end_time
			)

			if overlapping:
				raise RepositoryError(
					f"分片时间范围与现有分片重叠: {overlapping}",
					"CHUNK_OVERLAP"
				)

			# 创建分片元数据
			chunk_data = {
				"table_name": table_name,
				"chunk_name": chunk_name,
				"start_time": start_time,
				"end_time": end_time,
				"storage_type": storage_type,
				"max_size_mb": max_size_mb,
				"compression_enabled": compression_enabled,
				"current_size_mb": 0,
				"row_count": 0,
				"status": "active",
				"created_at": datetime.now(),
				"updated_at": datetime.now()
			}

			return await self.create(chunk_data)

		except SQLAlchemyError as e:
			raise RepositoryError(f"创建分片失败: {str(e)}", "CHUNK_CREATE_ERROR")

	async def _find_overlapping_chunks (
			self,
			table_name: str,
			start_time: datetime,
			end_time: datetime
	) -> List[ChunkMetadata]:
		"""
		查找重叠的分片（私有方法）

		Args:
			table_name: 表名
			start_time: 开始时间
			end_time: 结束时间

		Returns:
			重叠的分片列表
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.table_name == table_name,
					self.model.status == "active",
					or_(
						and_(
							self.model.start_time <= start_time,
							self.model.end_time > start_time
						),
						and_(
							self.model.start_time < end_time,
							self.model.end_time >= end_time
						),
						and_(
							self.model.start_time >= start_time,
							self.model.end_time <= end_time
						)
					)
				)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise Exception(f"查找重叠分片失败: {str(e)}")

	async def get_table_chunks (
			self,
			table_name: str,
			status: str = "active",
			storage_type: str = None
	) -> List[ChunkMetadata]:
		"""
		获取表的所有分片

		Args:
			table_name: 表名
			status: 状态过滤
			storage_type: 存储类型过滤

		Returns:
			分片列表
		"""
		try:
			filters = {"table_name": table_name}

			if status:
				filters["status"] = status

			if storage_type:
				filters["storage_type"] = storage_type

			return await self.get_many(**filters)

		except Exception as e:
			raise RepositoryError(f"获取分片列表失败: {str(e)}")

	async def update_chunk_statistics (self, chunk_id: str) -> ChunkMetadata:
		"""
		更新分片统计信息

		Args:
			chunk_id: 分片ID

		Returns:
			更新后的分片元数据
		"""
		try:
			chunk = await self.get(chunk_id)
			if not chunk:
				raise RepositoryError(f"分片不存在", "CHUNK_NOT_FOUND")

			# 查询分片实际统计信息
			stats = await self._get_chunk_real_stats(chunk.chunk_name)

			# 更新统计信息
			chunk.current_size_mb = stats.get("size_mb", 0)
			chunk.row_count = stats.get("row_count", 0)
			chunk.compression_ratio = stats.get("compression_ratio", 1.0)
			chunk.updated_at = datetime.now()

			await self.session.flush()
			return chunk

		except Exception as e:
			raise RepositoryError(f"更新分片统计失败: {str(e)}")

	async def _get_chunk_real_stats (
				self,
				chunk_name: str
			) -> Dict[str, Any]:
		"""
		获取分片实际统计信息（私有方法）

		Args:
			chunk_name: 分片名

		Returns:
			统计信息字典
		"""
		try:
			# PostgreSQL/TimescaleDB 特定查询
			stats_query = text(f"""
                SELECT 
                    pg_size_pretty(pg_total_relation_size(:chunk_name)) as size_pretty,
                    pg_total_relation_size(:chunk_name) / (1024 * 1024) as size_mb,
                    COUNT(*) as row_count,
                    pg_total_relation_size(:chunk_name) / NULLIF(COUNT(*), 0) as avg_row_size
                FROM {chunk_name}
            """)

			result = await self.session.execute(stats_query, {"chunk_name": chunk_name})
			row = result.first()

			if row:
				compression_ratio = 1.0
				if row.size_mb > 0:
					# 估算压缩比（如果有压缩）
					uncompressed_size = row.row_count * row.avg_row_size if row.avg_row_size else 0
					if uncompressed_size > 0:
						compression_ratio = uncompressed_size / (row.size_mb * 1024 * 1024)

				return {
					"size_mb": row.size_mb or 0,
					"row_count": row.row_count or 0,
					"avg_row_size": row.avg_row_size or 0,
					"compression_ratio": compression_ratio,
					"size_pretty": row.size_pretty or "0 bytes"
				}

			return {"size_mb": 0, "row_count": 0, "compression_ratio": 1.0}

		except Exception as e:
			# 如果查询失败，返回默认值
			print(f"获取分片统计失败: {e}")
			return {"size_mb": 0, "row_count": 0, "compression_ratio": 1.0}

	async def find_chunk_for_time (
			self,
			table_name: str,
			timestamp: datetime
	) -> Optional[ChunkMetadata]:
		"""
		查找包含指定时间点的分片

		Args:
			table_name: 表名
			timestamp: 时间点

		Returns:
			包含该时间点的分片，如果没有则返回None
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.table_name == table_name,
					self.model.status == "active",
					self.model.start_time <= timestamp,
					self.model.end_time > timestamp
				)
			).order_by(self.model.start_time)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"查找分片失败: {str(e)}")

	async def merge_small_chunks (
			self,
			table_name: str,
			min_size_mb: int = 100,
			max_chunks: int = 10
	) -> List[Dict[str, Any]]:
		"""
		合并小分片

		Args:
			table_name: 表名
			min_size_mb: 最小分片大小（小于此值的分片会被合并）
			max_chunks: 最大合并分片数

		Returns:
			合并结果列表
		"""
		try:
			# 查找小分片
			small_chunks = await self.get_many(
				table_name=table_name,
				status="active",
				current_size_mb__lt=min_size_mb,
				limit=max_chunks
			)

			if not small_chunks:
				return [{"status": "no_small_chunks", "message": "没有需要合并的小分片"}]

			# 按时间排序
			small_chunks.sort(key=lambda x: x.start_time)

			results = []

			# 合并相邻的小分片
			for i in range(0, len(small_chunks), 2):
				if i + 1 >= len(small_chunks):
					# 单个分片无法合并
					results.append({
						"chunk_id": small_chunks[i].id,
						"chunk_name": small_chunks[i].chunk_name,
						"status": "skipped",
						"reason": "没有相邻分片可合并"
					})
					continue

				chunk1 = small_chunks[i]
				chunk2 = small_chunks[i + 1]

				# 检查是否时间连续
				if chunk1.end_time != chunk2.start_time:
					results.append({
						"chunk1_id": chunk1.id,
						"chunk2_id": chunk2.id,
						"status": "skipped",
						"reason": "分片时间不连续"
					})
					continue

				# 执行合并
				try:
					merged_chunk = await self._merge_two_chunks(chunk1, chunk2)

					results.append({
						"chunk1_id": chunk1.id,
						"chunk1_name": chunk1.chunk_name,
						"chunk2_id": chunk2.id,
						"chunk2_name": chunk2.chunk_name,
						"merged_chunk_id": merged_chunk.id,
						"merged_chunk_name": merged_chunk.chunk_name,
						"status": "merged",
						"new_size_mb": merged_chunk.current_size_mb,
						"new_row_count": merged_chunk.row_count
					})

				except Exception as e:
					results.append({
						"chunk1_id": chunk1.id,
						"chunk2_id": chunk2.id,
						"status": "failed",
						"error": str(e)
					})

			return results

		except Exception as e:
			raise RepositoryError(f"合并小分片失败: {str(e)}")

	async def _merge_two_chunks (
			self,
			chunk1: ChunkMetadata,
			chunk2: ChunkMetadata
	) -> ChunkMetadata:
		"""
		合并两个分片（私有方法）

		Args:
			chunk1: 第一个分片
			chunk2: 第二个分片

		Returns:
			合并后的新分片
		"""
		try:
			# 创建新分片名
			new_chunk_name = f"{chunk1.table_name}_merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

			# 创建合并后的分片
			merged_chunk = await self.create_chunk(
				table_name=chunk1.table_name,
				chunk_name=new_chunk_name,
				start_time=chunk1.start_time,
				end_time=chunk2.end_time,
				storage_type=chunk1.storage_type,
				max_size_mb=max(chunk1.max_size_mb, chunk2.max_size_mb),
				compression_enabled=chunk1.compression_enabled or chunk2.compression_enabled
			)

			# 复制数据到新分片（数据库特定操作）
			await self._copy_chunk_data(chunk1.chunk_name, new_chunk_name)
			await self._copy_chunk_data(chunk2.chunk_name, new_chunk_name)

			# 禁用旧分片
			chunk1.status = "merged"
			chunk1.merged_into = merged_chunk.id
			chunk1.updated_at = datetime.now()

			chunk2.status = "merged"
			chunk2.merged_into = merged_chunk.id
			chunk2.updated_at = datetime.now()

			# 更新新分片统计
			await self.update_chunk_statistics(merged_chunk.id)

			await self.session.flush()
			return merged_chunk

		except Exception as e:
			await self.session.rollback()
			raise Exception(f"合并分片失败: {str(e)}")

	async def _copy_chunk_data (self, source_chunk: str, target_chunk: str):
		"""复制分片数据（私有方法）"""
		try:
			copy_query = text(f"""
                INSERT INTO {target_chunk}
                SELECT * FROM {source_chunk}
                ON CONFLICT DO NOTHING
            """)

			await self.session.execute(copy_query)

		except Exception as e:
			raise Exception(f"复制分片数据失败: {str(e)}")

	async def split_large_chunk (
			self,
			chunk_id: str,
			split_time: datetime = None,
			target_size_mb: int = 512
	) -> Tuple[ChunkMetadata, ChunkMetadata]:
		"""
		分裂大分片

		Args:
			chunk_id: 分片ID
			split_time: 分裂时间点（可选，不指定则按大小分裂）
			target_size_mb: 目标分片大小（MB）

		Returns:
			(分裂后的第一个分片, 分裂后的第二个分片)
		"""
		try:
			chunk = await self.get(chunk_id)
			if not chunk:
				raise RepositoryError(f"分片不存在", "CHUNK_NOT_FOUND")

			if chunk.current_size_mb < target_size_mb * 2:
				raise RepositoryError(
					f"分片大小 {chunk.current_size_mb}MB 不足目标大小的两倍 {target_size_mb * 2}MB",
					"CHUNK_TOO_SMALL"
				)

			# 确定分裂时间点
			if not split_time:
				split_time = await self._find_split_time(
					chunk.chunk_name, target_size_mb
				)

			# 验证分裂时间有效性
			if not (chunk.start_time < split_time < chunk.end_time):
				raise RepositoryError(
					f"分裂时间必须在分片时间范围内 ({chunk.start_time} 到 {chunk.end_time})",
					"INVALID_SPLIT_TIME"
				)

			# 创建新分片名
			chunk1_name = f"{chunk.table_name}_split1_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
			chunk2_name = f"{chunk.table_name}_split2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

			# 创建分裂后的分片
			chunk1 = await self.create_chunk(
				table_name=chunk.table_name,
				chunk_name=chunk1_name,
				start_time=chunk.start_time,
				end_time=split_time,
				storage_type=chunk.storage_type,
				max_size_mb=target_size_mb,
				compression_enabled=chunk.compression_enabled
			)

			chunk2 = await self.create_chunk(
				table_name=chunk.table_name,
				chunk_name=chunk2_name,
				start_time=split_time,
				end_time=chunk.end_time,
				storage_type=chunk.storage_type,
				max_size_mb=target_size_mb,
				compression_enabled=chunk.compression_enabled
			)

			# 复制数据到新分片
			await self._split_chunk_data(
				chunk.chunk_name,
				chunk1_name,
				chunk2_name,
				split_time
			)

			# 禁用原分片
			chunk.status = "split"
			chunk.split_into = f"{chunk1.id},{chunk2.id}"
			chunk.updated_at = datetime.now()

			# 更新新分片统计
			await self.update_chunk_statistics(chunk1.id)
			await self.update_chunk_statistics(chunk2.id)

			await self.session.flush()
			return chunk1, chunk2

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"分裂分片失败: {str(e)}")

	async def _find_split_time (
				self,
				chunk_name: str,
				target_size_mb: int
			) -> datetime:
		"""
		查找合适的分裂时间点（私有方法）

		Args:
			chunk_name: 分片名
			target_size_mb: 目标大小

		Returns:
			分裂时间点
		"""
		try:
			# 查询按时间累积的大小
			split_query = text(f"""
                WITH cumulative_stats AS (
                    SELECT 
                        timestamp,
                        SUM(pg_column_size(t.*)) OVER (ORDER BY timestamp) / (1024 * 1024) as cumulative_mb,
                        COUNT(*) OVER (ORDER BY timestamp) as cumulative_rows
                    FROM {chunk_name} t
                    WHERE timestamp IS NOT NULL
                )
                SELECT timestamp
                FROM cumulative_stats
                WHERE cumulative_mb >= :target_mb
                ORDER BY timestamp
                LIMIT 1
            """)

			result = await self.session.execute(split_query, {"target_mb": target_size_mb})
			row = result.first()

			if row:
				return row.timestamp
			else:
				# 如果没有找到，返回中间时间
				time_query = text(f"""
                    SELECT 
                        MIN(timestamp) as min_time,
                        MAX(timestamp) as max_time
                    FROM {chunk_name}
                """)

				time_result = await self.session.execute(time_query)
				time_row = time_result.first()

				if time_row and time_row.min_time and time_row.max_time:
					return time_row.min_time + (time_row.max_time - time_row.min_time) / 2
				else:
					raise Exception("无法确定分裂时间点")

		except Exception as e:
			raise Exception(f"查找分裂时间点失败: {str(e)}")

	async def _split_chunk_data (
			self,
			source_chunk: str,
			target_chunk1: str,
			target_chunk2: str,
			split_time: datetime
	):
		"""分裂分片数据（私有方法）"""
		try:
			# 复制第一部分数据
			copy1_query = text(f"""
                INSERT INTO {target_chunk1}
                SELECT * FROM {source_chunk}
                WHERE timestamp < :split_time
                ON CONFLICT DO NOTHING
            """)

			await self.session.execute(copy1_query, {"split_time": split_time})

			# 复制第二部分数据
			copy2_query = text(f"""
                INSERT INTO {target_chunk2}
                SELECT * FROM {source_chunk}
                WHERE timestamp >= :split_time
                ON CONFLICT DO NOTHING
            """)

			await self.session.execute(copy2_query, {"split_time": split_time})

		except Exception as e:
			raise Exception(f"分裂分片数据失败: {str(e)}")

	async def move_chunk_to_storage (
			self,
			chunk_id: str,
			target_storage: str,
			archive_path: str = None
	) -> Dict[str, Any]:
		"""
		移动分片到不同存储层

		Args:
			chunk_id: 分片ID
			target_storage: 目标存储类型（hot, warm, cold）
			archive_path: 归档路径（冷存储时需要）

		Returns:
			移动结果
		"""
		try:
			valid_storages = ["hot", "warm", "cold"]
			if target_storage not in valid_storages:
				raise RepositoryError(
					f"无效的存储类型: {target_storage}，有效值: {valid_storages}",
					"INVALID_STORAGE_TYPE"
				)

			chunk = await self.get(chunk_id)
			if not chunk:
				raise RepositoryError(f"分片不存在", "CHUNK_NOT_FOUND")

			# 记录移动前状态
			original_storage = chunk.storage_type

			if target_storage == "cold" and not archive_path:
				raise RepositoryError("冷存储需要指定归档路径", "ARCHIVE_PATH_REQUIRED")

			# 执行移动操作
			if target_storage == "cold":
				# 归档到冷存储
				await self._archive_to_cold_storage(chunk.chunk_name, archive_path)
				chunk.storage_location = archive_path
			elif target_storage == "warm":
				# 移动到温存储（压缩）
				await self._compress_chunk(chunk.chunk_name)
			else:
				# 移动到热存储（解压）
				await self._decompress_chunk(chunk.chunk_name)

			# 更新分片元数据
			chunk.storage_type = target_storage
			chunk.last_storage_move = datetime.now()
			chunk.updated_at = datetime.now()

			await self.session.flush()

			return {
				"chunk_id": chunk_id,
				"chunk_name": chunk.chunk_name,
				"original_storage": original_storage,
				"new_storage": target_storage,
				"archive_path": archive_path,
				"move_time": datetime.now()
			}

		except Exception as e:
			raise RepositoryError(f"移动分片存储失败: {str(e)}")

	async def _archive_to_cold_storage (self, chunk_name: str, archive_path: str):
		"""归档到冷存储（私有方法）"""
		# 实现归档逻辑（可能涉及文件系统操作）
		pass

	async def _compress_chunk (self, chunk_name: str):
		"""压缩分片（私有方法）"""
		try:
			compress_query = text(f"""
                ALTER TABLE {chunk_name} SET (
                    timescaledb.compress,
                    timescaledb.compress_segmentby = 'symbol'
                )
            """)

			await self.session.execute(compress_query)
		except Exception as e:
			raise Exception(f"压缩分片失败: {str(e)}")

	async def _decompress_chunk (self, chunk_name: str):
		"""解压分片（私有方法）"""
		try:
			decompress_query = text(f"""
                ALTER TABLE {chunk_name} SET (
                    timescaledb.compress = false
                )
            """)

			await self.session.execute(decompress_query)
		except Exception as e:
			raise Exception(f"解压分片失败: {str(e)}")

	async def cleanup_orphaned (self, table_name: str) -> int:
		"""
		清理孤立的分片（数据库中存在但元数据中不存在的分片）

		Args:
			table_name: 表名

		Returns:
			清理的分片数量
		"""
		try:
			# 获取数据库中实际存在的分片
			db_chunks = await self._get_physical_chunks(table_name)

			# 获取元数据中的分片
			meta_chunks = await self.get_table_chunks(table_name)
			meta_chunk_names = {chunk.chunk_name for chunk in meta_chunks}

			# 找出孤立分片
			orphaned_chunks = [chunk for chunk in db_chunks if chunk not in meta_chunk_names]

			cleaned_count = 0

			for chunk_name in orphaned_chunks:
				try:
					# 删除孤立分片
					drop_query = text(f"DROP TABLE IF EXISTS {chunk_name}")
					await self.session.execute(drop_query)
					cleaned_count += 1

				except Exception as e:
					print(f"删除孤立分片 {chunk_name} 失败: {e}")

			return cleaned_count

		except Exception as e:
			raise RepositoryError(f"清理孤立分片失败: {str(e)}")

	async def _get_physical_chunks (self, table_name: str) -> List[str]:
		"""
		获取数据库中物理存在的分片（私有方法）

		Args:
			table_name: 表名

		Returns:
			分片名列表
		"""
		try:
			# PostgreSQL/TimescaleDB 查询
			chunks_query = text(f"""
                SELECT child.relname as chunk_name
                FROM pg_inherits
                JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
                JOIN pg_class child ON pg_inherits.inhrelid = child.oid
                WHERE parent.relname = :table_name
            """)

			result = await self.session.execute(chunks_query, {"table_name": table_name})
			rows = result.fetchall()

			return [row.chunk_name for row in rows]

		except Exception as e:
			raise Exception(f"获取物理分片失败: {str(e)}")

	async def get_chunk_performance_metrics (
			self,
			chunk_id: str,
			days: int = 7
	) -> Dict[str, Any]:
		"""
		获取分片性能指标

		Args:
			chunk_id: 分片ID
			days: 统计天数

		Returns:
			性能指标
		"""
		chunk = await self.get(chunk_id)
		try:
			if not chunk:
				raise RepositoryError(f"分片不存在", "CHUNK_NOT_FOUND")

			# 查询分片查询统计（需要系统表支持）
			perf_query = text(f"""
                WITH chunk_stats AS (
                    SELECT 
                        COUNT(*) as total_queries,
                        AVG(execution_time_ms) as avg_execution_time,
                        MAX(execution_time_ms) as max_execution_time,
                        MIN(execution_time_ms) as min_execution_time,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY execution_time_ms) as p95_execution_time
                    FROM system.query_logs
                    WHERE table_name = :chunk_name
                    AND query_time >= NOW() - INTERVAL ':days days'
                )
                SELECT * FROM chunk_stats
            """)

			result = await self.session.execute(perf_query, {
				"chunk_name": chunk.chunk_name,
				"days": days
			})

			row = result.first()

			if row:
				return {
					"chunk_id": chunk_id,
					"chunk_name": chunk.chunk_name,
					"statistics_period_days": days,
					"total_queries": row.total_queries or 0,
					"avg_execution_time_ms": row.avg_execution_time or 0,
					"max_execution_time_ms": row.max_execution_time or 0,
					"min_execution_time_ms": row.min_execution_time or 0,
					"p95_execution_time_ms": row.p95_execution_time or 0,
					"collected_at": datetime.now()
				}

			return {
				"chunk_id": chunk_id,
				"chunk_name": chunk.chunk_name,
				"message": "无性能数据",
				"collected_at": datetime.now()
			}

		except Exception as e:
			# 如果查询失败，返回基本统计
			return {
				"chunk_id": chunk_id,
				"chunk_name": getattr(chunk, 'chunk_name', 'unknown') if 'chunk' in locals() else 'unknown',
				"error": str(e),
				"collected_at": datetime.now()
			}

	async def optimize_chunk_layout (self, table_name: str) -> Dict[str, Any]:
		"""
		优化分片布局

		Args:
			table_name: 表名

		Returns:
			优化结果
		"""
		try:
			# 获取所有分片
			chunks = await self.get_table_chunks(table_name, status="active")

			if not chunks:
				return {"status": "no_chunks", "message": "没有活跃分片"}

			optimization_results = {
				"table_name": table_name,
				"total_chunks": len(chunks),
				"operations_performed": [],
				"issues_found": [],
				"summary": {}
			}

			# 1. 合并小分片
			merge_results = await self.merge_small_chunks(table_name)
			optimization_results["operations_performed"].extend([
				{"operation": "merge", "details": result}
				for result in merge_results
			])

			# 2. 分裂大分片
			large_chunks = [c for c in chunks if c.current_size_mb > 1024]
			for chunk in large_chunks:
				try:
					chunk1, chunk2 = await self.split_large_chunk(chunk.id)
					optimization_results["operations_performed"].append({
						"operation": "split",
						"chunk_id": chunk.id,
						"new_chunks": [chunk1.id, chunk2.id]
					})
				except Exception as e:
					optimization_results["issues_found"].append({
						"chunk_id": chunk.id,
						"issue": "split_failed",
						"error": str(e)
					})

			# 3. 重新平衡存储层
			hot_chunks = [c for c in chunks if c.storage_type == "hot"]
			if len(hot_chunks) > 10:  # 热分片太多
				# 将旧 分片移到温存储
				old_hot_chunks = sorted(hot_chunks, key=lambda x: x.start_time)[:5]

				for chunk in old_hot_chunks:
					try:
						await self.move_chunk_to_storage(chunk.id, "warm")
						optimization_results["operations_performed"].append({
							"operation": "move_to_warm",
							"chunk_id": chunk.id
						})
					except Exception as e:
						optimization_results["issues_found"].append({
							"chunk_id": chunk.id,
							"issue": "move_failed",
							"error": str(e)
						})

			# 4. 更新所有分片统计
			for chunk in chunks:
				try:
					await self.update_chunk_statistics(chunk.id)
				except Exception as e:
					optimization_results["issues_found"].append({
						"chunk_id": chunk.id,
						"issue": "stats_update_failed",
						"error": str(e)
					})

			# 生成摘要
			optimized_chunks = await self.get_table_chunks(table_name, status="active")

			optimization_results["summary"] = {
				"before_chunks": len(chunks),
				"after_chunks": len(optimized_chunks),
				"total_operations": len(optimization_results["operations_performed"]),
				"total_issues": len(optimization_results["issues_found"]),
				"optimization_time": datetime.now()
			}

			return optimization_results

		except Exception as e:
			raise RepositoryError(f"优化分片布局失败: {str(e)}")