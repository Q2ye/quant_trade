"""
时间分桶管理器 - 管理时序数据的时间分桶策略

主要功能：
1. 创建和管理时间分桶
2. 按时间分桶查询数据
3. 自动维护分桶结构
4. 分桶统计和分析

继承自：BaseRepository（因为不是直接的时序数据，而是配置管理）
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.system_models import TimeBucketConfig
from shared.database.repositories.base.repository_base import BaseRepository, RepositoryError


class TimeBucketManager(BaseRepository[TimeBucketConfig]):
	"""
	时间分桶管理器类

	负责管理时序数据的时间分桶策略，支持按不同时间粒度分桶
	"""

	def __init__ (self, session: AsyncSession):
		"""初始化时间分桶管理器"""
		super().__init__(session, TimeBucketConfig)

	async def create_bucket_config (
			self,
			table_name: str,
			bucket_interval: str,
			aggregate_functions: List[str] = None,
			retention_days: int = 365,
			is_active: bool = True
	) -> TimeBucketConfig:
		"""
		创建时间分桶配置

		Args:
			table_name: 超表名
			bucket_interval: 分桶间隔（1m, 1h, 1d, 1w, 1M）
			aggregate_functions: 聚合函数列表
			retention_days: 数据保留天数
			is_active: 是否激活

		Returns:
			时间分桶配置对象
		"""
		try:
			# 验证间隔格式
			valid_intervals = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"]
			if bucket_interval not in valid_intervals:
				raise RepositoryError(
					f"无效的分桶间隔: {bucket_interval}，有效值: {valid_intervals}",
					"INVALID_BUCKET_INTERVAL"
				)

			# 检查配置是否已存在
			existing = await self.get_by(
				table_name=table_name,
				bucket_interval=bucket_interval
			)
			if existing:
				raise RepositoryError(
					f"表 '{table_name}' 的分桶配置 '{bucket_interval}' 已存在",
					"BUCKET_CONFIG_EXISTS"
				)

			# 创建分桶配置
			bucket_config = {
				"table_name": table_name,
				"bucket_interval": bucket_interval,
				"aggregate_functions": aggregate_functions or ["avg", "min", "max", "count"],
				"retention_days": retention_days,
				"is_active": is_active,
				"last_bucket_time": None,
				"created_at": datetime.now(),
				"updated_at": datetime.now()
			}

			return await self.create(bucket_config)

		except SQLAlchemyError as e:
			raise RepositoryError(f"创建分桶配置失败: {str(e)}", "BUCKET_CONFIG_CREATE_ERROR")

	async def get_by_table (self, table_name: str) -> List[TimeBucketConfig]:
		"""
		获取指定表的所有分桶配置

		Args:
			table_name: 表名

		Returns:
			分桶配置列表
		"""
		try:
			return await self.get_many(table_name=table_name, is_active=True)
		except Exception as e:
			raise RepositoryError(f"获取分桶配置失败: {str(e)}")

	async def update_bucket_config (
			self,
			config_id: str,
			updates: Dict[str, Any]
	) -> TimeBucketConfig:
		"""
		更新分桶配置

		Args:
			config_id: 配置ID
			updates: 更新字段

		Returns:
			更新后的配置对象
		"""
		try:
			return await self.update(config_id, updates)
		except Exception as e:
			raise RepositoryError(f"更新分桶配置失败: {str(e)}")

	async def generate_time_buckets (
			self,
			table_name: str,
			bucket_interval: str,
			start_time: datetime,
			end_time: datetime
	) -> List[Dict[str, Any]]:
		"""
		生成时间分桶

		Args:
			table_name: 表名
			bucket_interval: 分桶间隔
			start_time: 开始时间
			end_time: 结束时间

		Returns:
			分桶列表
		"""
		try:
			# 获取分桶配置
			bucket_config = await self.get_by(
				table_name=table_name,
				bucket_interval=bucket_interval,
				is_active=True
			)

			if not bucket_config:
				raise RepositoryError(
					f"未找到表 '{table_name}' 的分桶配置 '{bucket_interval}'",
					"BUCKET_CONFIG_NOT_FOUND"
				)

			# 根据间隔生成时间桶
			buckets = []
			current_time = start_time

			while current_time < end_time:
				bucket_end = self._add_interval(current_time, bucket_interval)

				buckets.append({
					"table_name": table_name,
					"bucket_interval": bucket_interval,
					"bucket_start": current_time,
					"bucket_end": bucket_end,
					"aggregate_functions": bucket_config.aggregate_functions,
					"status": "pending"
				})

				current_time = bucket_end

			return buckets

		except Exception as e:
			raise RepositoryError(f"生成时间分桶失败: {str(e)}")

	@staticmethod
	def _add_interval (dt: datetime, interval: str) -> datetime:
		"""
		根据间隔字符串增加时间（私有方法）

		Args:
			dt: 原始时间
			interval: 时间间隔

		Returns:
			增加后的时间
		"""
		interval_map = {
			"1m": timedelta(minutes=1),
			"5m": timedelta(minutes=5),
			"15m": timedelta(minutes=15),
			"30m": timedelta(minutes=30),
			"1h": timedelta(hours=1),
			"4h": timedelta(hours=4),
			"1d": timedelta(days=1),
			"1w": timedelta(weeks=1)
		}

		if interval in interval_map:
			return dt + interval_map[interval]
		elif interval == "1M":
			# 处理月份增加
			if dt.month == 12:
				return dt.replace(year=dt.year + 1, month=1)
			else:
				return dt.replace(month=dt.month + 1)
		else:
			raise ValueError(f"不支持的间隔: {interval}")

	async def create_bucket_materialized_view (
			self,
			table_name: str,
			bucket_interval: str,
			view_name: str = None
	) -> str:
		"""
		创建分桶物化视图

		Args:
			table_name: 原始表名
			bucket_interval: 分桶间隔
			view_name: 视图名（可选）

		Returns:
			创建的视图名
		"""
		try:
			bucket_config = await self.get_by(
				table_name=table_name,
				bucket_interval=bucket_interval,
				is_active=True
			)

			if not bucket_config:
				raise RepositoryError(f"分桶配置不存在", "BUCKET_CONFIG_NOT_FOUND")

			# 生成视图名
			if not view_name:
				view_name = f"{table_name}_{bucket_interval}_buckets"

			# 构建聚合函数SQL
			agg_functions = []
			for func_name in bucket_config.aggregate_functions:
				if func_name == "avg":
					agg_functions.append("AVG(close) as avg_close")
				elif func_name == "min":
					agg_functions.append("MIN(close) as min_close")
				elif func_name == "max":
					agg_functions.append("MAX(close) as max_close")
				elif func_name == "count":
					agg_functions.append("COUNT(*) as record_count")
				elif func_name == "sum":
					agg_functions.append("SUM(volume) as total_volume")
				elif func_name == "first":
					agg_functions.append("FIRST_VALUE(close) as open_price")
				elif func_name == "last":
					agg_functions.append("LAST_VALUE(close) as close_price")

			agg_sql = ", ".join(agg_functions)

			# 创建物化视图（PostgreSQL语法）
			create_view_sql = text(f"""
                CREATE MATERIALIZED VIEW IF NOT EXISTS {view_name} AS
                SELECT 
                    symbol,
                    time_bucket('{bucket_interval}', timestamp) as bucket_time,
                    {agg_sql}
                FROM {table_name}
                WHERE timestamp IS NOT NULL
                GROUP BY symbol, time_bucket('{bucket_interval}', timestamp)
                ORDER BY bucket_time
            """)

			await self.session.execute(create_view_sql)

			# 创建索引
			index_sql = text(f"""
                CREATE INDEX IF NOT EXISTS idx_{view_name}_bucket_time 
                ON {view_name} (bucket_time, symbol)
            """)

			await self.session.execute(index_sql)

			# 更新配置
			bucket_config.materialized_view = view_name
			bucket_config.updated_at = datetime.now()
			await self.session.flush()

			return view_name

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"创建物化视图失败: {str(e)}")

	async def refresh_bucket_view (self, view_name: str, concurrently: bool = False) -> bool:
		"""
		刷新分桶物化视图

		Args:
			view_name: 视图名
			concurrently: 是否并发刷新

		Returns:
			是否成功
		"""
		try:
			if concurrently:
				refresh_sql = text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}")
			else:
				refresh_sql = text(f"REFRESH MATERIALIZED VIEW {view_name}")

			await self.session.execute(refresh_sql)
			return True

		except Exception as e:
			raise RepositoryError(f"刷新物化视图失败: {str(e)}")

	async def drop_bucket_view (self, view_name: str) -> bool:
		"""
		删除分桶物化视图

		Args:
			view_name: 视图名

		Returns:
			是否成功
		"""
		try:
			drop_sql = text(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}")
			await self.session.execute(drop_sql)
			return True

		except Exception as e:
			raise RepositoryError(f"删除物化视图失败: {str(e)}")

	async def get_bucket_statistics (
			self,
			table_name: str,
			bucket_interval: str,
			start_time: datetime,
			end_time: datetime
	) -> Dict[str, Any]:
		"""
		获取分桶统计信息

		Args:
			table_name: 表名
			bucket_interval: 分桶间隔
			start_time: 开始时间
			end_time: 结束时间

		Returns:
			分桶统计信息
		"""
		try:
			# 检查是否有物化视图
			bucket_config = await self.get_by(
				table_name=table_name,
				bucket_interval=bucket_interval,
				is_active=True
			)

			if not bucket_config:
				raise RepositoryError(f"分桶配置不存在", "BUCKET_CONFIG_NOT_FOUND")

			view_name = bucket_config.materialized_view

			if not view_name:
				# 如果没有物化视图，直接查询原始表
				return await self._calculate_bucket_stats_raw(
					table_name, bucket_interval, start_time, end_time
				)
			else:
				# 查询物化视图
				return await self._calculate_bucket_stats_view(
					view_name, start_time, end_time
				)

		except Exception as e:
			raise RepositoryError(f"获取分桶统计失败: {str(e)}")

	async def _calculate_bucket_stats_raw (
			self,
			table_name: str,
			bucket_interval: str,
			start_time: datetime,
			end_time: datetime
	) -> Dict[str, Any]:
		"""从原始表计算分桶统计（私有方法）"""
		# 实现原始表统计计算
		pass

	async def _calculate_bucket_stats_view (
			self,
			view_name: str,
			start_time: datetime,
			end_time: datetime
	) -> Dict[str, Any]:
		"""从物化视图计算分桶统计（私有方法）"""
		# 实现物化视图统计计算
		pass

	async def schedule_bucket_generation (self) -> Dict[str, Any]:
		"""
		调度分桶生成任务

		Returns:
			调度结果
		"""
		try:
			# 获取所有活跃的分桶配置
			active_configs = await self.get_many(is_active=True)

			results = {
				"total_configs": len(active_configs),
				"processed": 0,
				"errors": [],
				"details": []
			}

			for config in active_configs:
				try:
					# 检查是否需要生成新的分桶
					needs_generation = await self._needs_new_bucket(config)

					if needs_generation:
						# 生成新的分桶
						bucket_info = await self._generate_next_bucket(config)
						results["details"].append({
							"table": config.table_name,
							"interval": config.bucket_interval,
							"generated": True,
							"bucket_time": bucket_info.get("bucket_time")
						})
					else:
						results["details"].append({
							"table": config.table_name,
							"interval": config.bucket_interval,
							"generated": False,
							"reason": "No new data"
						})

					results["processed"] += 1

				except Exception as e:
					results["errors"].append({
						"table": config.table_name,
						"interval": config.bucket_interval,
						"error": str(e)
					})

			return results

		except Exception as e:
			raise RepositoryError(f"调度分桶生成失败: {str(e)}")

	async def _needs_new_bucket (self, config: TimeBucketConfig) -> bool:
		"""检查是否需要生成新的分桶（私有方法）"""
		# 实现检查逻辑
		pass

	async def _generate_next_bucket (self, config: TimeBucketConfig) -> Dict[str, Any]:
		"""生成下一个分桶（私有方法）"""
		# 实现生成逻辑
		pass