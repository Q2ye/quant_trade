# -*- coding: utf-8 -*-
"""
审计日志Repository
位置：quant_server/shared/database/repositories/system/audit_repo.py
职责：管理系统审计日志的数据访问
注意：审计日志用于系统安全监控、操作追踪和合规审计
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.system_models import AuditLog
from shared.database.repositories.base import BaseRepository


class AuditRepository(BaseRepository):
	"""审计日志仓库 - 负责系统审计日志的数据访问"""

	def __init__(self, session: AsyncSession):
		super().__init__(session, AuditLog)

	async def create_audit_log(
			self,
			action_type: str,
			resource_type: str,
			resource_id: Optional[str] = None,
			user_id: Optional[str] = None,
			username: Optional[str] = None,
			old_values: Optional[Dict[str, Any]] = None,
			new_values: Optional[Dict[str, Any]] = None,
			changed_fields: Optional[List[str]] = None,
			ip_address: Optional[str] = None,
			user_agent: Optional[str] = None,
			status: str = "success",
			error_message: Optional[str] = None
	) -> AuditLog:
		"""
		创建审计日志记录

		Args:
			action_type: 操作类型（CREATE, UPDATE, DELETE, LOGIN, LOGOUT等）
			resource_type: 资源类型
			resource_id: 资源ID（可选）
			user_id: 用户ID（可选）
			username: 用户名（可选）
			old_values: 旧值（可选）
			new_values: 新值（可选）
			changed_fields: 变更字段列表（可选）
			ip_address: IP地址（可选）
			user_agent: 用户代理（可选）
			status: 操作状态（success, failed）
			error_message: 错误信息（可选）

		Returns:
			AuditLog: 创建的审计日志记录
		"""
		try:
			# 创建审计日志记录
			audit_log = AuditLog(
				action_type=action_type,
				resource_type=resource_type,
				resource_id=resource_id,
				resource_name=f"{resource_type}_{resource_id}" if resource_id else None,
				user_id=user_id,
				username=username,
				old_values=old_values,
				new_values=new_values,
				changed_fields=changed_fields,
				ip_address=ip_address,
				user_agent=user_agent,
				status=status,
				error_message=error_message
			)

			self.session.add(audit_log)
			await self.session.commit()
			await self.session.refresh(audit_log)
			
			return audit_log
		except Exception as e:
			await self.session.rollback()
			raise Exception(f"创建审计日志失败: {str(e)}")

	async def get_audit_logs(
			self,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			action_type: Optional[str] = None,
			resource_type: Optional[str] = None,
			resource_id: Optional[str] = None,
			user_id: Optional[str] = None,
			status: Optional[str] = None,
			limit: int = 1000,
			offset: int = 0
	) -> List[AuditLog]:
		"""
		获取审计日志列表

		Args:
			start_time: 开始时间（可选）
			end_time: 结束时间（可选）
			action_type: 操作类型过滤（可选）
			resource_type: 资源类型过滤（可选）
			resource_id: 资源ID过滤（可选）
			user_id: 用户ID过滤（可选）
			status: 状态过滤（可选）
			limit: 返回数量限制
			offset: 偏移量

		Returns:
			审计日志列表
		"""
		try:
			# 构建查询条件
			query = select(AuditLog)

			# 添加过滤条件
			if start_time:
				query = query.where(AuditLog.created_at >= start_time)
			if end_time:
				query = query.where(AuditLog.created_at <= end_time)
			if action_type:
				query = query.where(AuditLog.action_type == action_type)
			if resource_type:
				query = query.where(AuditLog.resource_type == resource_type)
			if resource_id:
				query = query.where(AuditLog.resource_id == resource_id)
			if user_id:
				query = query.where(AuditLog.user_id == user_id)
			if status:
				query = query.where(AuditLog.status == status)

			# 获取分页数据
			query = query.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit)
			result = await self.session.execute(query)
			logs = result.scalars().all()

			return logs
		except Exception as e:
			raise Exception(f"获取审计日志失败: {str(e)}")

	async def get_audit_statistics(
			self,
			start_time: datetime,
			end_time: datetime
	) -> Dict[str, Any]:
		"""
		获取审计日志统计信息

		Args:
			start_time: 开始时间
			end_time: 结束时间

		Returns:
			统计信息字典
		"""
		try:
			# 按操作类型统计
			action_stats_query = select(
				AuditLog.action_type,
				func.count().label('count'),
				func.count(func.distinct(AuditLog.user_id)).label('user_count')
			).where(
				and_(
					AuditLog.created_at >= start_time,
					AuditLog.created_at <= end_time
				)
			).group_by(AuditLog.action_type)

			action_result = await self.session.execute(action_stats_query)
			action_stats = [
				{"action_type": row.action_type, "count": row.count, "user_count": row.user_count}
				for row in action_result
			]

			# 按资源类型统计
			resource_stats_query = select(
				AuditLog.resource_type,
				func.count().label('count'),
				func.count(func.distinct(AuditLog.action_type)).label('action_count')
			).where(
				and_(
					AuditLog.created_at >= start_time,
					AuditLog.created_at <= end_time
				)
			).group_by(AuditLog.resource_type)

			resource_result = await self.session.execute(resource_stats_query)
			resource_stats = [
				{"resource_type": row.resource_type, "count": row.count, "action_count": row.action_count}
				for row in resource_result
			]

			# 按用户统计
			user_stats_query = select(
				AuditLog.user_id,
				AuditLog.username,
				func.count().label('operation_count'),
				func.count(func.distinct(AuditLog.action_type)).label('action_count')
			).where(
				and_(
					AuditLog.created_at >= start_time,
					AuditLog.created_at <= end_time,
					AuditLog.user_id.isnot(None)
				)
			).group_by(AuditLog.user_id, AuditLog.username)

			user_result = await self.session.execute(user_stats_query)
			user_stats = [
				{
					"user_id": row.user_id,
					"username": row.username,
					"operation_count": row.operation_count,
					"action_count": row.action_count
				}
				for row in user_result
			]

			# 错误率统计
			error_stats_query = select(
				func.count().label('total_count'),
				func.count().filter(AuditLog.status == 'failed').label('error_count')
			).where(
				and_(
					AuditLog.created_at >= start_time,
					AuditLog.created_at <= end_time
				)
			)

			error_result = await self.session.execute(error_stats_query)
			error_row = error_result.first()
			total_count = error_row.total_count if error_row else 0
			error_count = error_row.error_count if error_row else 0
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
				"action_distribution": action_stats,
				"resource_distribution": resource_stats,
				"user_operations": user_stats
			}
		except Exception as e:
			raise Exception(f"获取审计日志统计失败: {str(e)}")

	async def get_user_audit_summary(
			self,
			user_id: str,
			start_time: datetime,
			end_time: datetime
	) -> Dict[str, Any]:
		"""
		获取用户审计摘要

		Args:
			user_id: 用户ID
			start_time: 开始时间
			end_time: 结束时间

		Returns:
			用户审计摘要
		"""
		try:
			# 用户操作统计
			user_stats_query = select(
				AuditLog.action_type,
				AuditLog.resource_type,
				func.count().label('operation_count')
			).where(
				and_(
					AuditLog.user_id == user_id,
					AuditLog.created_at >= start_time,
					AuditLog.created_at <= end_time
				)
			).group_by(AuditLog.action_type, AuditLog.resource_type)

			user_result = await self.session.execute(user_stats_query)
			user_stats = [
				{
					"action_type": row.action_type,
					"resource_type": row.resource_type,
					"operation_count": row.operation_count
				}
				for row in user_result
			]

			# 用户错误统计
			error_stats_query = select(
				func.count().label('total_count'),
				func.count().filter(AuditLog.status == 'failed').label('error_count')
			).where(
				and_(
					AuditLog.user_id == user_id,
					AuditLog.created_at >= start_time,
					AuditLog.created_at <= end_time
				)
			)

			error_result = await self.session.execute(error_stats_query)
			error_row = error_result.first()
			total_count = error_row.total_count if error_row else 0
			error_count = error_row.error_count if error_row else 0

			return {
				"user_id": user_id,
				"time_range": {
					"start_time": start_time,
					"end_time": end_time
				},
				"summary": {
					"total_operations": total_count,
					"error_operations": error_count,
					"error_rate": error_count / total_count if total_count > 0 else 0
				},
				"operation_breakdown": user_stats
			}
		except Exception as e:
			raise Exception(f"获取用户审计摘要失败: {str(e)}")

	async def get_resource_audit_trail(
			self,
			resource_type: str,
			resource_id: str,
			limit: int = 100
	) -> List[AuditLog]:
		"""
		获取资源审计轨迹

		Args:
			resource_type: 资源类型
			resource_id: 资源ID
			limit: 返回数量限制

		Returns:
			资源审计轨迹列表
		"""
		try:
			query = select(AuditLog).where(
				and_(
					AuditLog.resource_type == resource_type,
					AuditLog.resource_id == resource_id
				)
			).order_by(desc(AuditLog.created_at)).limit(limit)

			result = await self.session.execute(query)
			logs = result.scalars().all()

			return logs
		except Exception as e:
			raise Exception(f"获取资源审计轨迹失败: {str(e)}")

	async def cleanup_old_logs(
			self,
			retention_days: int = 365
	) -> Dict[str, int]:
		"""
		清理过期审计日志

		Args:
			retention_days: 保留天数，默认为365天

		Returns:
			清理结果统计
		"""
		try:
			cutoff_date = datetime.now() - timedelta(days=retention_days)
			
			# 删除过期日志
			delete_query = select(AuditLog).where(AuditLog.created_at < cutoff_date)
			result = await self.session.execute(delete_query)
			logs_to_delete = result.scalars().all()
			
			# 批量删除
			for log in logs_to_delete:
				await self.session.delete(log)
			
			await self.session.commit()
			
			return {
				"deleted_count": len(logs_to_delete),
				"cutoff_date": cutoff_date
			}
		except Exception as e:
			await self.session.rollback()
			raise Exception(f"清理过期审计日志失败: {str(e)}")

	async def batch_create_logs(
			self,
			log_data_list: List[Dict[str, Any]]
	) -> List[AuditLog]:
		"""
		批量创建审计日志

		Args:
			log_data_list: 日志数据列表

		Returns:
			创建的审计日志列表
		"""
		try:
			logs = []
			for log_data in log_data_list:
				log = AuditLog(
					action_type=log_data.get("action_type", "UNKNOWN"),
					resource_type=log_data.get("resource_type", "unknown"),
					resource_id=log_data.get("resource_id"),
					resource_name=log_data.get("resource_name"),
					user_id=log_data.get("user_id"),
					username=log_data.get("username"),
					old_values=log_data.get("old_values"),
					new_values=log_data.get("new_values"),
					changed_fields=log_data.get("changed_fields"),
					ip_address=log_data.get("ip_address"),
					user_agent=log_data.get("user_agent"),
					status=log_data.get("status", "success"),
					error_message=log_data.get("error_message")
				)
				logs.append(log)

			self.session.add_all(logs)
			await self.session.commit()
			
			# 刷新对象以获取ID
			for log in logs:
				await self.session.refresh(log)
			
			return logs
		except Exception as e:
			await self.session.rollback()
			raise Exception(f"批量创建审计日志失败: {str(e)}")