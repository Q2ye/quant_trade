"""
数据保留策略管理器 - 管理时序数据的自动清理策略

主要功能：
1. 创建和管理数据保留策略
2. 自动清理过期数据
3. 策略执行日志记录
4. 清理统计和报告

继承自：BaseRepository（因为是策略配置管理）
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.system_models import RetentionPolicy, RetentionPolicyLog
from quant_server.shared.database.repositories.base.repository_base import BaseRepository, RepositoryError


class RetentionPolicyManager(BaseRepository[RetentionPolicy]):
	"""
	数据保留策略管理器类

	负责管理时序数据的自动清理策略，防止数据无限增长
	"""

	def __init__ (self, session: AsyncSession):
		"""初始化保留策略管理器"""
		super().__init__(session, RetentionPolicy)

	async def create_retention_policy (
			self,
			table_name: str,
			retention_period: str,
			cleanup_strategy: str = "drop",
			schedule_interval: str = "1 day",
			is_active: bool = True,
			conditions: Dict[str, Any] = None
	) -> RetentionPolicy:
		"""
		创建数据保留策略

		Args:
			table_name: 表名
			retention_period: 保留周期（如 '30 days', '1 year', '1000 rows'）
			cleanup_strategy: 清理策略（drop, archive, compress）
			schedule_interval: 调度间隔
			is_active: 是否激活
			conditions: 额外条件

		Returns:
			保留策略对象
		"""
		try:
			# 验证保留周期格式
			if not self._validate_retention_period(retention_period):
				raise RepositoryError(
					f"无效的保留周期格式: {retention_period}",
					"INVALID_RETENTION_PERIOD"
				)

			# 验证清理策略
			valid_strategies = ["drop", "archive", "compress", "move_to_cold_storage"]
			if cleanup_strategy not in valid_strategies:
				raise RepositoryError(
					f"无效的清理策略: {cleanup_strategy}，有效值: {valid_strategies}",
					"INVALID_CLEANUP_STRATEGY"
				)

			# 检查是否已存在相同策略
			existing = await self.get_by(
				table_name=table_name,
				retention_period=retention_period,
				is_active=True
			)
			if existing:
				raise RepositoryError(
					f"表 '{table_name}' 的保留策略已存在",
					"RETENTION_POLICY_EXISTS"
				)

			# 创建策略
			policy_data = {
				"table_name": table_name,
				"retention_period": retention_period,
				"cleanup_strategy": cleanup_strategy,
				"schedule_interval": schedule_interval,
				"is_active": is_active,
				"conditions": conditions or {},
				"last_executed": None,
				"next_execution": self._calculate_next_execution(schedule_interval),
				"created_at": datetime.now(),
				"updated_at": datetime.now()
			}

			return await self.create(policy_data)

		except SQLAlchemyError as e:
			raise RepositoryError(f"创建保留策略失败: {str(e)}", "RETENTION_POLICY_CREATE_ERROR")

	@staticmethod
	def _validate_retention_period (period: str) -> bool:
		"""
		验证保留周期格式（私有方法）

		Args:
			period: 保留周期字符串

		Returns:
			是否有效
		"""
		# 支持格式: "30 days", "1 year", "1000 rows", "10GB"
		import re

		pattern = r'^(\d+)\s*(days?|months?|years?|rows?|KB|MB|GB|TB)$'
		return bool(re.match(pattern, period, re.IGNORECASE))

	@staticmethod
	def _calculate_next_execution (schedule_interval: str) -> datetime:
		"""
		计算下次执行时间（私有方法）

		Args:
			schedule_interval: 调度间隔

		Returns:
			下次执行时间
		"""
		interval_map = {
			"1 hour": timedelta(hours=1),
			"4 hours": timedelta(hours=4),
			"1 day": timedelta(days=1),
			"1 week": timedelta(weeks=1),
			"1 month": timedelta(days=30),  # 近似值
			"1 year": timedelta(days=365)  # 近似值
		}

		default_interval = timedelta(days=1)
		delta = interval_map.get(schedule_interval.lower(), default_interval)

		return datetime.now() + delta

	async def get_active_policies (self) -> List[RetentionPolicy]:
		"""
		获取所有活跃的保留策略

		Returns:
			活跃策略列表
		"""
		try:
			return await self.get_many(is_active=True)
		except Exception as e:
			raise RepositoryError(f"获取活跃策略失败: {str(e)}")

	async def execute_policy (self, policy_id: str, dry_run: bool = False) -> Dict[str, Any]:
		"""
		执行保留策略

		Args:
			policy_id: 策略ID
			dry_run: 试运行（不实际删除）

		Returns:
			执行结果
		"""
		try:
			policy = await self.get(policy_id)
			if not policy:
				raise RepositoryError(f"保留策略不存在", "RETENTION_POLICY_NOT_FOUND")

			if not policy.is_active:
				raise RepositoryError(f"保留策略未激活", "RETENTION_POLICY_INACTIVE")

			# 执行清理
			result = await self._execute_cleanup(policy, dry_run)

			# 记录执行日志
			log_data = {
				"policy_id": policy_id,
				"execution_time": datetime.now(),
				"dry_run": dry_run,
				"rows_affected": result.get("rows_affected", 0),
				"space_reclaimed": result.get("space_reclaimed", "0 bytes"),
				"execution_status": "success",
				"error_message": None,
				"execution_details": result
			}

			await self._create_execution_log(log_data)

			# 更新策略执行时间
			policy.last_executed = datetime.now()
			policy.next_execution = self._calculate_next_execution(policy.schedule_interval)
			policy.updated_at = datetime.now()

			await self.session.flush()

			return {
				"policy_id": policy_id,
				"table_name": policy.table_name,
				"dry_run": dry_run,
				"execution_time": datetime.now(),
				"result": result
			}

		except Exception as e:
			# 记录错误日志
			if 'policy' in locals():
				await self._create_execution_log({
					"policy_id": policy_id,
					"execution_time": datetime.now(),
					"dry_run": dry_run,
					"rows_affected": 0,
					"space_reclaimed": "0 bytes",
					"execution_status": "failed",
					"error_message": str(e),
					"execution_details": {}
				})

			raise RepositoryError(f"执行保留策略失败: {str(e)}")

	async def _execute_cleanup (self, policy: RetentionPolicy, dry_run: bool) -> Dict[str, Any]:
		"""
		执行实际的数据清理（私有方法）

		Args:
			policy: 保留策略
			dry_run: 试运行

		Returns:
			清理结果
		"""
		try:
			table_name = policy.table_name
			retention_period = policy.retention_period
			strategy = policy.cleanup_strategy

			# 解析保留周期
			cutoff_time = self._parse_retention_cutoff(retention_period)

			if dry_run:
				# 试运行：只统计不删除
				return await self._analyze_cleanup(table_name, cutoff_time, strategy)
			else:
				# 实际执行
				if strategy == "drop":
					return await self._drop_old_data(table_name, cutoff_time)
				elif strategy == "archive":
					return await self._archive_old_data(table_name, cutoff_time)
				elif strategy == "compress":
					return await self._compress_old_data(table_name, cutoff_time)
				else:
					raise ValueError(f"不支持的清理策略: {strategy}")

		except Exception as e:
			raise Exception(f"执行清理失败: {str(e)}")

	@staticmethod
	def _parse_retention_cutoff (retention_period: str) -> datetime:
		"""
		解析保留周期，计算截止时间（私有方法）

		Args:
			retention_period: 保留周期字符串

		Returns:
			截止时间
		"""
		import re

		match = re.match(r'^(\d+)\s*(days?|months?|years?|rows?|KB|MB|GB|TB)$', retention_period, re.IGNORECASE)
		if not match:
			raise ValueError(f"无法解析保留周期: {retention_period}")

		value = int(match.group(1))
		unit = match.group(2).lower()

		now = datetime.now()

		if unit in ['day', 'days']:
			return now - timedelta(days=value)
		elif unit in ['month', 'months']:
			return now - timedelta(days=value * 30)  # 近似值
		elif unit in ['year', 'years']:
			return now - timedelta(days=value * 365)  # 近似值
		else:
			# 对于基于行数或大小的策略，需要查询数据库确定
			raise ValueError(f"基于 {unit} 的保留策略需要特殊处理")

	async def _analyze_cleanup (
			self,
			table_name: str,
			cutoff_time: datetime,
			strategy: str
	) -> Dict[str, Any]:
		"""
		分析清理操作（私有方法，试运行）

		Args:
			table_name: 表名
			cutoff_time: 截止时间
			strategy: 清理策略

		Returns:
			分析结果
		"""
		try:
			# 查询待清理的数据统计
			count_query = text(f"""
                SELECT COUNT(*) as total_rows
                FROM {table_name}
                WHERE timestamp < :cutoff_time
            """)

			result = await self.session.execute(count_query, {"cutoff_time": cutoff_time})
			row = result.first()

			total_rows = row.total_rows if row else 0

			# 估计空间占用
			size_query = text(f"""
                SELECT pg_size_pretty(pg_total_relation_size(:table_name)) as total_size
            """)

			size_result = await self.session.execute(size_query, {"table_name": table_name})
			size_row = size_result.first()
			total_size = size_row.total_size if size_row else "0 bytes"

			return {
				"table_name": table_name,
				"cutoff_time": cutoff_time,
				"estimated_rows_affected": total_rows,
				"estimated_space_reclaimed": total_size,
				"cleanup_strategy": strategy,
				"execution_type": "dry_run"
			}

		except Exception as e:
			raise Exception(f"分析清理操作失败: {str(e)}")

	async def _drop_old_data (
			self,
			table_name: str,
			cutoff_time: datetime
	) -> Dict[str, Any]:
		"""
		删除旧数据（私有方法）

		Args:
			table_name: 表名
			cutoff_time: 截止时间

		Returns:
			删除结果
		"""
		try:
			# 记录删除前的统计
			before_stats = await self._get_table_statistics(table_name)

			# 执行删除
			delete_query = text(f"""
                DELETE FROM {table_name}
                WHERE timestamp < :cutoff_time
                RETURNING COUNT(*) as deleted_count
            """)

			result = await self.session.execute(delete_query, {"cutoff_time": cutoff_time})
			row = result.first()
			deleted_count = row.deleted_count if row else 0

			# 记录删除后的统计
			after_stats = await self._get_table_statistics(table_name)

			# 清理空间（PostgreSQL）
			vacuum_query = text(f"VACUUM ANALYZE {table_name}")
			await self.session.execute(vacuum_query)

			return {
				"action": "drop",
				"cutoff_time": cutoff_time,
				"rows_affected": deleted_count,
				"space_reclaimed": f"{before_stats.get('total_size', '0 bytes')} -> {after_stats.get('total_size', '0 bytes')}",
				"before_stats": before_stats,
				"after_stats": after_stats,
				"execution_time": datetime.now()
			}

		except Exception as e:
			await self.session.rollback()
			raise Exception(f"删除旧数据失败: {str(e)}")

	async def _archive_old_data (
			self,
			table_name: str,
			cutoff_time: datetime
	) -> Dict[str, Any]:
		"""
		归档旧数据到历史表（私有方法）

		Args:
			table_name: 表名
			cutoff_time: 截止时间

		Returns:
			归档结果
		"""
		try:
			archive_table = f"{table_name}_history"

			# 创建归档表（如果不存在）
			create_archive_query = text(f"""
                CREATE TABLE IF NOT EXISTS {archive_table} 
                AS TABLE {table_name} WITH NO DATA
            """)

			await self.session.execute(create_archive_query)

			# 归档数据
			archive_query = text(f"""
                WITH moved_rows AS (
                    DELETE FROM {table_name}
                    WHERE timestamp < :cutoff_time
                    RETURNING *
                )
                INSERT INTO {archive_table}
                SELECT * FROM moved_rows
            """)

			result = await self.session.execute(archive_query, {"cutoff_time": cutoff_time})

			# 获取移动的行数
			moved_count = result.rowcount if result.rowcount else 0

			return {
				"action": "archive",
				"cutoff_time": cutoff_time,
				"rows_moved": moved_count,
				"archive_table": archive_table,
				"execution_time": datetime.now()
			}

		except Exception as e:
			await self.session.rollback()
			raise Exception(f"归档旧数据失败: {str(e)}")

	async def _compress_old_data (
			self,
			table_name: str,
			cutoff_time: datetime
	) -> Dict[str, Any]:
		"""
		压缩旧数据（私有方法）

		Args:
			table_name: 表名
			cutoff_time: 截止时间

		Returns:
			压缩结果
		"""
		try:
			# PostgreSQL的压缩示例（使用TimescaleDB）
			compress_query = text(f"""
                SELECT compress_chunk(chunk)
                FROM show_chunks(:table_name, older_than => :cutoff_time) AS chunk
            """)

			result = await self.session.execute(compress_query, {
				"table_name": table_name,
				"cutoff_time": cutoff_time
			})

			compressed_chunks = result.fetchall()

			return {
				"action": "compress",
				"cutoff_time": cutoff_time,
				"chunks_compressed": len(compressed_chunks),
				"compressed_chunks": [chunk[0] for chunk in compressed_chunks],
				"execution_time": datetime.now()
			}

		except Exception as e:
			raise Exception(f"压缩旧数据失败: {str(e)}")

	async def _get_table_statistics (self, table_name: str) -> Dict[str, Any]:
		"""
		获取表统计信息（私有方法）

		Args:
			table_name: 表名

		Returns:
			统计信息
		"""
		try:
			stats_query = text(f"""
                SELECT 
                    COUNT(*) as total_rows,
                    MIN(timestamp) as min_time,
                    MAX(timestamp) as max_time,
                    pg_size_pretty(pg_total_relation_size(:table_name)) as total_size,
                    pg_size_pretty(pg_relation_size(:table_name)) as table_size
                FROM {table_name}
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
					"table_size": row.table_size
				}
			return {}

		except (SQLAlchemyError, ValueError):
			return {}

	async def _create_execution_log (self, log_data: Dict[str, Any]) -> Optional[RetentionPolicyLog]:
		"""
		创建执行日志（私有方法）

		Args:
			log_data: 日志数据

		Returns:
			日志记录对象或None
		"""
		try:
			from quant_server.shared.database.repositories.system.ops import RetentionPolicyLogRepository

			log_repo = RetentionPolicyLogRepository(self.session)
			return await log_repo.create(log_data)

		except Exception as e:
			# 如果日志记录失败，不影响主流程
			print(f"创建保留策略日志失败: {e}")
			return None

	async def schedule_all_policies (self, dry_run: bool = False) -> Dict[str, Any]:
		"""
		调度执行所有到期的保留策略

		Args:
			dry_run: 试运行

		Returns:
			调度执行结果
		"""
		try:
			# 获取所有需要执行的策略
			now = datetime.now()
			due_policies = await self.get_many(
				is_active=True,
				next_execution__lt=now
			)

			results = {
				"total_policies": len(due_policies),
				"executed": 0,
				"skipped": 0,
				"errors": [],
				"details": []
			}

			for policy in due_policies:
				try:
					# 执行策略
					execution_result = await self.execute_policy(policy.id, dry_run)

					results["details"].append({
						"policy_id": policy.id,
						"table_name": policy.table_name,
						"status": "executed",
						"dry_run": dry_run,
						"result": execution_result
					})

					results["executed"] += 1

				except Exception as e:
					results["errors"].append({
						"policy_id": policy.id,
						"table_name": policy.table_name,
						"error": str(e)
					})
					results["skipped"] += 1

			return results

		except Exception as e:
			raise RepositoryError(f"调度保留策略失败: {str(e)}")

	async def get_policy_statistics (self, policy_id: str) -> Dict[str, Any]:
		"""
		获取策略执行统计

		Args:
			policy_id: 策略ID

		Returns:
			策略统计
		"""
		try:
			policy = await self.get(policy_id)
			if not policy:
				raise RepositoryError(f"保留策略不存在", "RETENTION_POLICY_NOT_FOUND")

			# 获取执行日志
			from quant_server.shared.database.repositories.system.ops import RetentionPolicyLogRepository

			log_repo = RetentionPolicyLogRepository(self.session)
			execution_logs = await log_repo.get_many(policy_id=policy_id, limit=100)

			# 计算统计
			total_executions = len(execution_logs)
			successful_executions = len([log for log in execution_logs if log.execution_status == "success"])
			failed_executions = total_executions - successful_executions

			total_rows_cleaned = sum(log.rows_affected or 0 for log in execution_logs)

			return {
				"policy_id": policy_id,
				"table_name": policy.table_name,
				"retention_period": policy.retention_period,
				"total_executions": total_executions,
				"successful_executions": successful_executions,
				"failed_executions": failed_executions,
				"total_rows_cleaned": total_rows_cleaned,
				"last_execution": policy.last_executed,
				"next_execution": policy.next_execution,
				"execution_logs_summary": [
					{
						"execution_time": log.execution_time,
						"status": log.execution_status,
						"rows_affected": log.rows_affected,
						"dry_run": log.dry_run
					}
					for log in execution_logs[:10]  # 最近10次
				]
			}

		except Exception as e:
			raise RepositoryError(f"获取策略统计失败: {str(e)}")

	async def validate_policy (self, policy_id: str) -> Dict[str, Any]:
		"""
		验证保留策略的有效性

		Args:
			policy_id: 策略ID

		Returns:
			验证结果
		"""
		try:
			policy = await self.get(policy_id)
			if not policy:
				raise RepositoryError(f"保留策略不存在", "RETENTION_POLICY_NOT_FOUND")

			validation_results = {
				"policy_id": policy_id,
				"table_name": policy.table_name,
				"checks": [],
				"is_valid": True,
				"issues": []
			}

			# 检查表是否存在
			table_exists = await self._check_table_exists(policy.table_name)
			validation_results["checks"].append({
				"check": "table_exists",
				"passed": table_exists,
				"message": f"表 '{policy.table_name}' {'存在' if table_exists else '不存在'}"
			})

			if not table_exists:
				validation_results["is_valid"] = False
				validation_results["issues"].append(f"表 '{policy.table_name}' 不存在")

			# 检查时间列是否存在
			if table_exists:
				has_time_column = await self._check_time_column(policy.table_name)
				validation_results["checks"].append({
					"check": "time_column_exists",
					"passed": has_time_column,
					"message": f"时间列 {'存在' if has_time_column else '不存在'}"
				})

				if not has_time_column:
					validation_results["is_valid"] = False
					validation_results["issues"].append(f"表 '{policy.table_name}' 没有时间列")

			# 验证保留周期格式
			period_valid = self._validate_retention_period(policy.retention_period)
			validation_results["checks"].append({
				"check": "retention_period_valid",
				"passed": period_valid,
				"message": f"保留周期 '{policy.retention_period}' {'有效' if period_valid else '无效'}"
			})

			if not period_valid:
				validation_results["is_valid"] = False
				validation_results["issues"].append(f"保留周期 '{policy.retention_period}' 格式无效")

			# 检查调度间隔
			schedule_valid = policy.schedule_interval in [
				"1 hour", "4 hours", "1 day", "1 week", "1 month", "1 year"
			]
			validation_results["checks"].append({
				"check": "schedule_interval_valid",
				"passed": schedule_valid,
				"message": f"调度间隔 '{policy.schedule_interval}' {'有效' if schedule_valid else '无效'}"
			})

			if not schedule_valid:
				validation_results["is_valid"] = False
				validation_results["issues"].append(f"调度间隔 '{policy.schedule_interval}' 无效")

			return validation_results

		except Exception as e:
			raise RepositoryError(f"验证保留策略失败: {str(e)}")

	async def _check_table_exists (self, table_name: str) -> bool:
		"""检查表是否存在（私有方法）"""
		try:
			check_query = text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = :table_name
                )
            """)

			result = await self.session.execute(check_query, {"table_name": table_name})
			return result.scalar()
		except (SQLAlchemyError, ValueError):
			return False

	async def _check_time_column (self, table_name: str) -> bool:
		"""检查时间列是否存在（私有方法）"""
		try:
			check_query = text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = :table_name 
                    AND column_name IN ('timestamp', 'created_at', 'trade_date', 'time')
                )
            """)

			result = await self.session.execute(check_query, {"table_name": table_name})
			return result.scalar()
		except (SQLAlchemyError, ValueError):
			return False