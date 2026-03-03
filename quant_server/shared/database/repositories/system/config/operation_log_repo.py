# -*- coding: utf-8 -*-
"""
日志数据仓库
位置：quant_server/shared/database/repositories/operation_log_repo.py
职责：管理系统日志、操作日志、错误日志等数据访问
注意：日志数据用于系统监控、故障排查和审计
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, text, between
from sqlalchemy.orm import selectinload, joinedload

from quant_server.shared.database.repositories.base import BaseRepository


# 假设的日志数据模型类
# todo 缺少的模型待补充
class SystemLog:
	"""系统日志模型"""
	__tablename__ = 'system_logs'
	pass


class OperationLog:
	"""操作日志模型"""
	__tablename__ = 'operation_logs'
	pass


class ErrorLog:
	"""错误日志模型"""
	__tablename__ = 'error_logs'
	pass


class AuditLog:
	"""审计日志模型"""
	__tablename__ = 'audit_logs'
	pass


class LogRepository:
	"""日志数据仓库 - 负责日志数据的管理和访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.system_log_repo = BaseRepository[SystemLog](session, SystemLog)
		self.operation_log_repo = BaseRepository[OperationLog](session, OperationLog)
		self.error_log_repo = BaseRepository[ErrorLog](session, ErrorLog)
		self.audit_log_repo = BaseRepository[AuditLog](session, AuditLog)

	# ==================== 系统日志操作 ====================

	async def create_system_log (
			self,
			level: str,
			module: str,
			message: str,
			details: Dict[str, Any] = None,
			user_id: int = None
	) -> Dict[str, Any]:
		"""
		创建系统日志

		Args:
			level: 日志级别（DEBUG, INFO, WARN, ERROR, FATAL）
			module: 模块名称
			message: 日志消息
			details: 详细信息（可选）
			user_id: 用户ID（可选）

		Returns:
			创建结果
		"""
		import json

		query = text("""
                     INSERT INTO system_logs
                         (log_level, module, message, details, user_id, ip_address, created_at)
                     VALUES (:level, :module, :message, :details, :user_id, :ip_address, NOW())
                     RETURNING id
		             """)

		# 获取客户端IP（如果有）
		# 实际项目中可以从请求上下文中获取
		ip_address = "127.0.0.1"

		result = await self.session.execute(
			query,
			{
				"level": level,
				"module": module,
				"message": message,
				"details": json.dumps(details) if details else None,
				"user_id": user_id,
				"ip_address": ip_address
			}
		)

		row = result.fetchone()
		if row:
			return {"id": row[0], "status": "created"}

		return {"status": "failed"}

	async def get_system_logs (
			self,
			start_time: datetime = None,
			end_time: datetime = None,
			level: str = None,
			module: str = None,
			user_id: int = None,
			limit: int = 1000,
			skip: int = 0
	) -> List[Dict[str, Any]]:
		"""
		获取系统日志

		Args:
			start_time: 开始时间（可选）
			end_time: 结束时间（可选）
			level: 日志级别过滤（可选）
			module: 模块过滤（可选）
			user_id: 用户ID过滤（可选）
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			系统日志列表
		"""
		conditions = []
		params = {"limit": limit, "skip": skip}

		if start_time:
			conditions.append("created_at >= :start_time")
			params["start_time"] = start_time

		if end_time:
			conditions.append("created_at <= :end_time")
			params["end_time"] = end_time

		if level:
			conditions.append("log_level = :level")
			params["level"] = level

		if module:
			conditions.append("module = :module")
			params["module"] = module

		if user_id:
			conditions.append("user_id = :user_id")
			params["user_id"] = user_id

		where_clause = " AND ".join(conditions) if conditions else "1=1"

		query_text = f"""
            SELECT 
                id, log_level, module, message, 
                details, user_id, ip_address, created_at
            FROM system_logs 
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :skip
        """

		result = await self.session.execute(text(query_text), params)
		rows = result.fetchall()

		logs = []
		for row in rows:
			log_entry = {
				"id": row.id,
				"level": row.log_level,
				"module": row.module,
				"message": row.message,
				"user_id": row.user_id,
				"ip_address": row.ip_address,
				"created_at": row.created_at
			}

			if row.details:
				try:
					log_entry["details"] = json.loads(row.details)
				except:
					log_entry["details"] = row.details

			logs.append(log_entry)

		return logs

	async def get_system_log_stats (
			self,
			start_time: datetime,
			end_time: datetime
	) -> Dict[str, Any]:
		"""
		获取系统日志统计

		Args:
			start_time: 开始时间
			end_time: 结束时间

		Returns:
			系统日志统计
		"""
		# 按级别统计
		level_stats_query = text("""
                                 SELECT log_level,
                                        COUNT(*)               as count,
                                        COUNT(DISTINCT module) as module_count
                                 FROM system_logs
                                 WHERE created_at >= :start_time
                                   AND created_at <= :end_time
                                 GROUP BY log_level
                                 ORDER BY count DESC
		                         """)

		level_result = await self.session.execute(
			level_stats_query,
			{"start_time": start_time, "end_time": end_time}
		)
		level_rows = level_result.fetchall()

		# 按模块统计
		module_stats_query = text("""
                                  SELECT module,
                                         COUNT(*)                  as count,
                                         COUNT(DISTINCT log_level) as level_count
                                  FROM system_logs
                                  WHERE created_at >= :start_time
                                    AND created_at <= :end_time
                                  GROUP BY module
                                  ORDER BY count DESC
                                  LIMIT 10
		                          """)

		module_result = await self.session.execute(
			module_stats_query,
			{"start_time": start_time, "end_time": end_time}
		)
		module_rows = module_result.fetchall()

		# 时间分布统计
		time_dist_query = text("""
                               SELECT DATE_TRUNC('hour', created_at) as hour_bucket,
                                      COUNT(*)                       as count
                               FROM system_logs
                               WHERE created_at >= :start_time
                                 AND created_at <= :end_time
                               GROUP BY hour_bucket
                               ORDER BY hour_bucket
		                       """)

		time_result = await self.session.execute(
			time_dist_query,
			{"start_time": start_time, "end_time": end_time}
		)
		time_rows = time_result.fetchall()

		# 错误率统计
		error_rate_query = text("""
                                SELECT COUNT(CASE WHEN log_level IN ('ERROR', 'FATAL') THEN 1 END) as error_count,
                                       COUNT(*)                                                    as total_count
                                FROM system_logs
                                WHERE created_at >= :start_time
                                  AND created_at <= :end_time
		                        """)

		error_result = await self.session.execute(
			error_rate_query,
			{"start_time": start_time, "end_time": end_time}
		)
		error_row = error_result.fetchone()

		error_count = error_row.error_count if error_row else 0
		total_count = error_row.total_count if error_row else 0
		error_rate = error_count / total_count if total_count > 0 else 0

		return {
			"time_range": {
				"start_time": start_time,
				"end_time": end_time
			},
			"summary": {
				"total_logs": total_count,
				"error_logs": error_count,
				"error_rate": error_rate
			},
			"level_distribution": [
				{
					"level": row.log_level,
					"count": row.count,
					"module_count": row.module_count
				}
				for row in level_rows
			],
			"top_modules": [
				{
					"module": row.module,
					"count": row.count,
					"level_count": row.level_count
				}
				for row in module_rows
			],
			"time_distribution": [
				{
					"hour": row.hour_bucket,
					"count": row.count
				}
				for row in time_rows
			]
		}

	# ==================== 操作日志操作 ====================

	async def create_operation_log (
			self,
			user_id: int,
			operation: str,
			resource_type: str,
			resource_id: str = None,
			details: Dict[str, Any] = None,
			status: str = "success",
			ip_address: str = None
	) -> Dict[str, Any]:
		"""
		创建操作日志

		Args:
			user_id: 用户ID
			operation: 操作类型（CREATE, READ, UPDATE, DELETE, EXECUTE等）
			resource_type: 资源类型
			resource_id: 资源ID（可选）
			details: 详细信息（可选）
			status: 操作状态（success, failed）
			ip_address: IP地址（可选）

		Returns:
			创建结果
		"""
		import json

		query = text("""
                     INSERT INTO operation_logs
                     (user_id, operation, resource_type, resource_id, details, status, ip_address, created_at)
                     VALUES (:user_id, :operation, :resource_type, :resource_id, :details, :status, :ip_address, NOW())
                     RETURNING id
		             """)

		result = await self.session.execute(
			query,
			{
				"user_id": user_id,
				"operation": operation,
				"resource_type": resource_type,
				"resource_id": resource_id,
				"details": json.dumps(details) if details else None,
				"status": status,
				"ip_address": ip_address or "127.0.0.1"
			}
		)

		row = result.fetchone()
		if row:
			return {"id": row[0], "status": "created"}

		return {"status": "failed"}

	async def get_operation_logs (
			self,
			user_id: int = None,
			operation: str = None,
			resource_type: str = None,
			resource_id: str = None,
			status: str = None,
			start_time: datetime = None,
			end_time: datetime = None,
			limit: int = 500,
			skip: int = 0
	) -> List[Dict[str, Any]]:
		"""
		获取操作日志

		Args:
			user_id: 用户ID过滤（可选）
			operation: 操作类型过滤（可选）
			resource_type: 资源类型过滤（可选）
			resource_id: 资源ID过滤（可选）
			status: 状态过滤（可选）
			start_time: 开始时间（可选）
			end_time: 结束时间（可选）
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			操作日志列表
		"""
		conditions = []
		params = {"limit": limit, "skip": skip}

		if user_id:
			conditions.append("user_id = :user_id")
			params["user_id"] = user_id

		if operation:
			conditions.append("operation = :operation")
			params["operation"] = operation

		if resource_type:
			conditions.append("resource_type = :resource_type")
			params["resource_type"] = resource_type

		if resource_id:
			conditions.append("resource_id = :resource_id")
			params["resource_id"] = resource_id

		if status:
			conditions.append("status = :status")
			params["status"] = status

		if start_time:
			conditions.append("created_at >= :start_time")
			params["start_time"] = start_time

		if end_time:
			conditions.append("created_at <= :end_time")
			params["end_time"] = end_time

		where_clause = " AND ".join(conditions) if conditions else "1=1"

		query_text = f"""
            SELECT 
                id, user_id, operation, resource_type, resource_id,
                details, status, ip_address, created_at
            FROM operation_logs 
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :skip
        """

		result = await self.session.execute(text(query_text), params)
		rows = result.fetchall()

		logs = []
		for row in rows:
			log_entry = {
				"id": row.id,
				"user_id": row.user_id,
				"operation": row.operation,
				"resource_type": row.resource_type,
				"resource_id": row.resource_id,
				"status": row.status,
				"ip_address": row.ip_address,
				"created_at": row.created_at
			}

			if row.details:
				try:
					log_entry["details"] = json.loads(row.details)
				except:
					log_entry["details"] = row.details

			logs.append(log_entry)

		return logs

	async def get_user_operation_summary (
			self,
			user_id: int,
			start_time: datetime,
			end_time: datetime
	) -> Dict[str, Any]:
		"""
		获取用户操作摘要

		Args:
			user_id: 用户ID
			start_time: 开始时间
			end_time: 结束时间

		Returns:
			用户操作摘要
		"""
		# 操作类型统计
		operation_stats_query = text("""
                                     SELECT operation,
                                            COUNT(*)                      as count,
                                            COUNT(DISTINCT resource_type) as resource_types
                                     FROM operation_logs
                                     WHERE user_id = :user_id
                                       AND created_at >= :start_time
                                       AND created_at <= :end_time
                                     GROUP BY operation
                                     ORDER BY count DESC
		                             """)

		op_result = await self.session.execute(
			operation_stats_query,
			{"user_id": user_id, "start_time": start_time, "end_time": end_time}
		)
		op_rows = op_result.fetchall()

		# 资源类型统计
		resource_stats_query = text("""
                                    SELECT resource_type,
                                           COUNT(*)                  as count,
                                           COUNT(DISTINCT operation) as operations
                                    FROM operation_logs
                                    WHERE user_id = :user_id
                                      AND created_at >= :start_time
                                      AND created_at <= :end_time
                                    GROUP BY resource_type
                                    ORDER BY count DESC
		                            """)

		resource_result = await self.session.execute(
			resource_stats_query,
			{"user_id": user_id, "start_time": start_time, "end_time": end_time}
		)
		resource_rows = resource_result.fetchall()

		# 成功率统计
		success_rate_query = text("""
                                  SELECT COUNT(CASE WHEN status = 'success' THEN 1 END) as success_count,
                                         COUNT(*)                                       as total_count
                                  FROM operation_logs
                                  WHERE user_id = :user_id
                                    AND created_at >= :start_time
                                    AND created_at <= :end_time
		                          """)

		success_result = await self.session.execute(
			success_rate_query,
			{"user_id": user_id, "start_time": start_time, "end_time": end_time}
		)
		success_row = success_result.fetchone()

		success_count = success_row.success_count if success_row else 0
		total_count = success_row.total_count if success_row else 0
		success_rate = success_count / total_count if total_count > 0 else 0

		return {
			"user_id": user_id,
			"time_range": {
				"start_time": start_time,
				"end_time": end_time
			},
			"summary": {
				"total_operations": total_count,
				"successful_operations": success_count,
				"success_rate": success_rate
			},
			"operation_statistics": [
				{
					"operation": row.operation,
					"count": row.count,
					"resource_types": row.resource_types
				}
				for row in op_rows
			],
			"resource_statistics": [
				{
					"resource_type": row.resource_type,
					"count": row.count,
					"operations": row.operations
				}
				for row in resource_rows
			]
		}

	# ==================== 错误日志操作 ====================

	async def create_error_log (
			self,
			error_type: str,
			error_message: str,
			stack_trace: str = None,
			module: str = None,
			user_id: int = None,
			request_data: Dict[str, Any] = None,
			resolved: bool = False
	) -> Dict[str, Any]:
		"""
		创建错误日志

		Args:
			error_type: 错误类型
			error_message: 错误消息
			stack_trace: 堆栈跟踪（可选）
			module: 模块名称（可选）
			user_id: 用户ID（可选）
			request_data: 请求数据（可选）
			resolved: 是否已解决

		Returns:
			创建结果
		"""
		import json

		query = text("""
                     INSERT INTO error_logs
                     (error_type, error_message, stack_trace, module, user_id, request_data, resolved, created_at)
                     VALUES (:error_type, :error_message, :stack_trace, :module, :user_id, :request_data, :resolved,
                             NOW())
                     RETURNING id
		             """)

		result = await self.session.execute(
			query,
			{
				"error_type": error_type,
				"error_message": error_message,
				"stack_trace": stack_trace,
				"module": module,
				"user_id": user_id,
				"request_data": json.dumps(request_data) if request_data else None,
				"resolved": resolved
			}
		)

		row = result.fetchone()
		if row:
			return {"id": row[0], "status": "created"}

		return {"status": "failed"}

	async def get_error_logs (
			self,
			resolved: bool = None,
			error_type: str = None,
			module: str = None,
			user_id: int = None,
			start_time: datetime = None,
			end_time: datetime = None,
			limit: int = 500,
			skip: int = 0
	) -> List[Dict[str, Any]]:
		"""
		获取错误日志

		Args:
			resolved: 是否已解决过滤（可选）
			error_type: 错误类型过滤（可选）
			module: 模块过滤（可选）
			user_id: 用户ID过滤（可选）
			start_time: 开始时间（可选）
			end_time: 结束时间（可选）
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			错误日志列表
		"""
		conditions = []
		params = {"limit": limit, "skip": skip}

		if resolved is not None:
			conditions.append("resolved = :resolved")
			params["resolved"] = resolved

		if error_type:
			conditions.append("error_type = :error_type")
			params["error_type"] = error_type

		if module:
			conditions.append("module = :module")
			params["module"] = module

		if user_id:
			conditions.append("user_id = :user_id")
			params["user_id"] = user_id

		if start_time:
			conditions.append("created_at >= :start_time")
			params["start_time"] = start_time

		if end_time:
			conditions.append("created_at <= :end_time")
			params["end_time"] = end_time

		where_clause = " AND ".join(conditions) if conditions else "1=1"

		query_text = f"""
            SELECT 
                id, error_type, error_message, stack_trace,
                module, user_id, request_data, resolved, created_at
            FROM error_logs 
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :skip
        """

		result = await self.session.execute(text(query_text), params)
		rows = result.fetchall()

		errors = []
		for row in rows:
			error_entry = {
				"id": row.id,
				"error_type": row.error_type,
				"error_message": row.error_message,
				"stack_trace": row.stack_trace,
				"module": row.module,
				"user_id": row.user_id,
				"resolved": row.resolved,
				"created_at": row.created_at
			}

			if row.request_data:
				try:
					error_entry["request_data"] = json.loads(row.request_data)
				except:
					error_entry["request_data"] = row.request_data

			errors.append(error_entry)

		return errors

	async def mark_error_resolved (self, error_id: int, resolution_notes: str = None) -> bool:
		"""
		标记错误为已解决

		Args:
			error_id: 错误ID
			resolution_notes: 解决说明（可选）

		Returns:
			是否成功
		"""
		query = text("""
                     UPDATE error_logs
                     SET resolved         = true,
                         resolution_notes = :notes,
                         resolved_at      = NOW()
                     WHERE id = :error_id
		             """)

		result = await self.session.execute(
			query,
			{"error_id": error_id, "notes": resolution_notes}
		)

		return result.rowcount > 0

	async def get_error_statistics (
			self,
			start_time: datetime,
			end_time: datetime
	) -> Dict[str, Any]:
		"""
		获取错误统计

		Args:
			start_time: 开始时间
			end_time: 结束时间

		Returns:
			错误统计信息
		"""
		# 错误类型统计
		type_stats_query = text("""
                                SELECT error_type,
                                       COUNT(*)                             as count,
                                       COUNT(DISTINCT module)               as module_count,
                                       COUNT(CASE WHEN resolved THEN 1 END) as resolved_count
                                FROM error_logs
                                WHERE created_at >= :start_time
                                  AND created_at <= :end_time
                                GROUP BY error_type
                                ORDER BY count DESC
		                        """)

		type_result = await self.session.execute(
			type_stats_query,
			{"start_time": start_time, "end_time": end_time}
		)
		type_rows = type_result.fetchall()

		# 模块错误统计
		module_stats_query = text("""
                                  SELECT module,
                                         COUNT(*)                   as count,
                                         COUNT(DISTINCT error_type) as type_count
                                  FROM error_logs
                                  WHERE created_at >= :start_time
                                    AND created_at <= :end_time
                                  GROUP BY module
                                  ORDER BY count DESC
                                  LIMIT 10
		                          """)

		module_result = await self.session.execute(
			module_stats_query,
			{"start_time": start_time, "end_time": end_time}
		)
		module_rows = module_result.fetchall()

		# 解决率统计
		resolution_stats_query = text("""
                                      SELECT COUNT(CASE WHEN resolved THEN 1 END) as resolved_count,
                                             COUNT(*)                             as total_count
                                      FROM error_logs
                                      WHERE created_at >= :start_time
                                        AND created_at <= :end_time
		                              """)

		resolution_result = await self.session.execute(
			resolution_stats_query,
			{"start_time": start_time, "end_time": end_time}
		)
		resolution_row = resolution_result.fetchone()

		resolved_count = resolution_row.resolved_count if resolution_row else 0
		total_count = resolution_row.total_count if resolution_row else 0
		resolution_rate = resolved_count / total_count if total_count > 0 else 0

		# 最近未解决的错误
		unresolved_query = text("""
                                SELECT id,
                                       error_type,
                                       error_message,
                                       module,
                                       created_at
                                FROM error_logs
                                WHERE created_at >= :start_time
                                  AND created_at <= :end_time
                                  AND resolved = false
                                ORDER BY created_at DESC
                                LIMIT 10
		                        """)

		unresolved_result = await self.session.execute(
			unresolved_query,
			{"start_time": start_time, "end_time": end_time}
		)
		unresolved_rows = unresolved_result.fetchall()

		return {
			"time_range": {
				"start_time": start_time,
				"end_time": end_time
			},
			"summary": {
				"total_errors": total_count,
				"resolved_errors": resolved_count,
				"resolution_rate": resolution_rate,
				"unresolved_errors": total_count - resolved_count
			},
			"error_type_distribution": [
				{
					"error_type": row.error_type,
					"count": row.count,
					"module_count": row.module_count,
					"resolved_count": row.resolved_count,
					"resolution_rate": row.resolved_count / row.count if row.count > 0 else 0
				}
				for row in type_rows
			],
			"top_modules_with_errors": [
				{
					"module": row.module,
					"error_count": row.count,
					"error_type_count": row.type_count
				}
				for row in module_rows
			],
			"recent_unresolved_errors": [
				{
					"id": row.id,
					"error_type": row.error_type,
					"error_message": row.error_message[:100] + "..." if len(
						row.error_message) > 100 else row.error_message,
					"module": row.module,
					"created_at": row.created_at
				}
				for row in unresolved_rows
			]
		}

	# ==================== 审计日志操作 ====================

	async def create_audit_log (
			self,
			action: str,
			resource_type: str,
			resource_id: str,
			old_value: Dict[str, Any] = None,
			new_value: Dict[str, Any] = None,
			user_id: int = None,
			ip_address: str = None
	) -> Dict[str, Any]:
		"""
		创建审计日志

		Args:
			action: 审计动作
			resource_type: 资源类型
			resource_id: 资源ID
			old_value: 旧值（可选）
			new_value: 新值（可选）
			user_id: 用户ID（可选）
			ip_address: IP地址（可选）

		Returns:
			创建结果
		"""
		import json

		query = text("""
                     INSERT INTO audit_logs
                     (action, resource_type, resource_id, old_value, new_value, user_id, ip_address, created_at)
                     VALUES (:action, :resource_type, :resource_id, :old_value, :new_value, :user_id, :ip_address,
                             NOW())
                     RETURNING id
		             """)

		result = await self.session.execute(
			query,
			{
				"action": action,
				"resource_type": resource_type,
				"resource_id": resource_id,
				"old_value": json.dumps(old_value) if old_value else None,
				"new_value": json.dumps(new_value) if new_value else None,
				"user_id": user_id,
				"ip_address": ip_address or "127.0.0.1"
			}
		)

		row = result.fetchone()
		if row:
			return {"id": row[0], "status": "created"}

		return {"status": "failed"}

	async def get_audit_logs (
			self,
			resource_type: str = None,
			resource_id: str = None,
			action: str = None,
			user_id: int = None,
			start_time: datetime = None,
			end_time: datetime = None,
			limit: int = 500,
			skip: int = 0
	) -> List[Dict[str, Any]]:
		"""
		获取审计日志

		Args:
			resource_type: 资源类型过滤（可选）
			resource_id: 资源ID过滤（可选）
			action: 动作过滤（可选）
			user_id: 用户ID过滤（可选）
			start_time: 开始时间（可选）
			end_time: 结束时间（可选）
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			审计日志列表
		"""
		conditions = []
		params = {"limit": limit, "skip": skip}

		if resource_type:
			conditions.append("resource_type = :resource_type")
			params["resource_type"] = resource_type

		if resource_id:
			conditions.append("resource_id = :resource_id")
			params["resource_id"] = resource_id

		if action:
			conditions.append("action = :action")
			params["action"] = action

		if user_id:
			conditions.append("user_id = :user_id")
			params["user_id"] = user_id

		if start_time:
			conditions.append("created_at >= :start_time")
			params["start_time"] = start_time

		if end_time:
			conditions.append("created_at <= :end_time")
			params["end_time"] = end_time

		where_clause = " AND ".join(conditions) if conditions else "1=1"

		query_text = f"""
            SELECT 
                id, action, resource_type, resource_id,
                old_value, new_value, user_id, ip_address, created_at
            FROM audit_logs 
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :skip
        """

		result = await self.session.execute(text(query_text), params)
		rows = result.fetchall()

		audit_logs = []
		for row in rows:
			audit_entry = {
				"id": row.id,
				"action": row.action,
				"resource_type": row.resource_type,
				"resource_id": row.resource_id,
				"user_id": row.user_id,
				"ip_address": row.ip_address,
				"created_at": row.created_at
			}

			if row.old_value:
				try:
					audit_entry["old_value"] = json.loads(row.old_value)
				except:
					audit_entry["old_value"] = row.old_value

			if row.new_value:
				try:
					audit_entry["new_value"] = json.loads(row.new_value)
				except:
					audit_entry["new_value"] = row.new_value

			audit_logs.append(audit_entry)

		return audit_logs

	async def get_resource_audit_trail (
			self,
			resource_type: str,
			resource_id: str
	) -> List[Dict[str, Any]]:
		"""
		获取资源的审计轨迹

		Args:
			resource_type: 资源类型
			resource_id: 资源ID

		Returns:
			审计轨迹列表
		"""
		query = text("""
                     SELECT id,
                            action,
                            old_value,
                            new_value,
                            user_id,
                            ip_address,
                            created_at
                     FROM audit_logs
                     WHERE resource_type = :resource_type
                       AND resource_id = :resource_id
                     ORDER BY created_at
		             """)

		result = await self.session.execute(
			query,
			{"resource_type": resource_type, "resource_id": resource_id}
		)
		rows = result.fetchall()

		audit_trail = []
		for row in rows:
			trail_entry = {
				"id": row.id,
				"action": row.action,
				"user_id": row.user_id,
				"ip_address": row.ip_address,
				"timestamp": row.created_at
			}

			if row.old_value:
				try:
					trail_entry["old_value"] = json.loads(row.old_value)
				except:
					trail_entry["old_value"] = row.old_value

			if row.new_value:
				try:
					trail_entry["new_value"] = json.loads(row.new_value)
				except:
					trail_entry["new_value"] = row.new_value

			audit_trail.append(trail_entry)

		return audit_trail

	# ==================== 批量操作 ====================

	async def batch_create_system_logs (
			self,
			log_data_list: List[Dict[str, Any]]
	) -> List[Dict[str, Any]]:
		"""
		批量创建系统日志

		Args:
			log_data_list: 日志数据列表

		Returns:
			创建结果列表
		"""
		results = []

		for log_data in log_data_list:
			result = await self.create_system_log(
				level=log_data.get("level", "INFO"),
				module=log_data.get("module", "unknown"),
				message=log_data.get("message", ""),
				details=log_data.get("details"),
				user_id=log_data.get("user_id")
			)
			results.append(result)

		return results

	async def batch_create_operation_logs (
			self,
			operation_data_list: List[Dict[str, Any]]
	) -> List[Dict[str, Any]]:
		"""
		批量创建操作日志

		Args:
			operation_data_list: 操作日志数据列表

		Returns:
			创建结果列表
		"""
		results = []

		for op_data in operation_data_list:
			result = await self.create_operation_log(
				user_id=op_data.get("user_id"),
				operation=op_data.get("operation", "UNKNOWN"),
				resource_type=op_data.get("resource_type", "unknown"),
				resource_id=op_data.get("resource_id"),
				details=op_data.get("details"),
				status=op_data.get("status", "success"),
				ip_address=op_data.get("ip_address")
			)
			results.append(result)

		return results

	async def cleanup_old_logs (self, days_to_keep: int = 90) -> Dict[str, int]:
		"""
		清理旧日志

		Args:
			days_to_keep: 保留天数

		Returns:
			各类型日志清理数量
		"""
		cutoff_date = datetime.now() - timedelta(days=days_to_keep)

		# 清理系统日志
		system_delete_query = text("""
                                   DELETE
                                   FROM system_logs
                                   WHERE created_at < :cutoff_date
		                           """)
		system_result = await self.session.execute(
			system_delete_query,
			{"cutoff_date": cutoff_date}
		)
		system_count = system_result.rowcount

		# 清理操作日志
		operation_delete_query = text("""
                                      DELETE
                                      FROM operation_logs
                                      WHERE created_at < :cutoff_date
		                              """)
		operation_result = await self.session.execute(
			operation_delete_query,
			{"cutoff_date": cutoff_date}
		)
		operation_count = operation_result.rowcount

		# 清理错误日志（只清理已解决的）
		error_delete_query = text("""
                                  DELETE
                                  FROM error_logs
                                  WHERE resolved = true
                                    AND created_at < :cutoff_date
		                          """)
		error_result = await self.session.execute(
			error_delete_query,
			{"cutoff_date": cutoff_date}
		)
		error_count = error_result.rowcount

		# 清理审计日志
		audit_delete_query = text("""
                                  DELETE
                                  FROM audit_logs
                                  WHERE created_at < :cutoff_date
		                          """)
		audit_result = await self.session.execute(
			audit_delete_query,
			{"cutoff_date": cutoff_date}
		)
		audit_count = audit_result.rowcount

		return {
			"system_logs_deleted": system_count,
			"operation_logs_deleted": operation_count,
			"error_logs_deleted": error_count,
			"audit_logs_deleted": audit_count,
			"total_deleted": system_count + operation_count + error_count + audit_count
		}