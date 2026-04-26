# -*- coding: utf-8 -*-
"""
操作日志Repository
位置：quant_server/shared/database/repositories/system/operation_log_repo.py
职责：管理系统操作日志的数据访问
注意：操作日志用于系统监控、故障排查和审计
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.system_models import SystemLog
from quant_server.shared.database.repositories.base import BaseRepository


class OperationLogRepository(BaseRepository):
	"""操作日志仓库 - 负责系统操作日志的数据访问"""

	def __init__(self, session: AsyncSession):
		super().__init__(session, SystemLog)

	async def create_log(
			self,
			log_level: str,
			module: str,
			action: str,
			details: Optional[Dict[str, Any]] = None,
			user_id: Optional[str] = None,
			ip_address: Optional[str] = None,
			user_agent: Optional[str] = None,
			execution_time: Optional[int] = None
	) -> SystemLog:
		"""
		创建操作日志

		Args:
			log_level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
			module: 模块名称
			action: 操作动作
			details: 详细信息（可选）
			user_id: 用户ID（可选）
			ip_address: IP地址（可选）
			user_agent: 用户代理（可选）
			execution_time: 执行时间（毫秒）（可选）

		Returns:
			SystemLog: 创建的操作日志记录
		"""
		try:
			# 创建操作日志记录
			operation_log = SystemLog(
				log_level=log_level,
				module=module,
				action=action,
				details=str(details) if details else None,
				user_id=user_id,
				ip_address=ip_address,
				user_agent=user_agent,
				execution_time=execution_time
			)

			self.session.add(operation_log)
			await self.session.commit()
			await self.session.refresh(operation_log)
			
			return operation_log
		except Exception as e:
			await self.session.rollback()
			raise Exception(f"创建操作日志失败: {str(e)}")

	async def get_logs(
			self,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			log_level: Optional[str] = None,
			module: Optional[str] = None,
			user_id: Optional[str] = None,
			action: Optional[str] = None,
			limit: int = 1000,
			offset: int = 0
	) -> List[SystemLog]:
		"""
		获取操作日志列表

		Args:
			start_time: 开始时间（可选）
			end_time: 结束时间（可选）
			log_level: 日志级别过滤（可选）
			module: 模块过滤（可选）
			user_id: 用户ID过滤（可选）
			action: 操作动作过滤（可选）
			limit: 返回数量限制
			offset: 偏移量

		Returns:
			操作日志列表
		"""
		try:
			# 构建查询条件
			query = select(SystemLog)

			# 添加过滤条件
			if start_time:
				query = query.where(SystemLog.created_at >= start_time)
			if end_time:
				query = query.where(SystemLog.created_at <= end_time)
			if log_level:
				query = query.where(SystemLog.log_level == log_level)
			if module:
				query = query.where(SystemLog.module == module)
			if user_id:
				query = query.where(SystemLog.user_id == user_id)
			if action:
				query = query.where(SystemLog.action == action)

			# 获取分页数据
			query = query.order_by(desc(SystemLog.created_at)).offset(offset).limit(limit)
			result = await self.session.execute(query)
			logs = result.scalars().all()

			return logs
		except Exception as e:
			raise Exception(f"获取操作日志失败: {str(e)}")

	async def get_log_statistics(
			self,
			start_time: datetime,
			end_time: datetime
	) -> Dict[str, Any]:
		"""
		获取操作日志统计信息

		Args:
			start_time: 开始时间
			end_time: 结束时间

		Returns:
			统计信息字典
		"""
		try:
			# 按日志级别统计
			level_stats_query = select(
				SystemLog.log_level,
				func.count().label('count'),
				func.count(func.distinct(SystemLog.module)).label('module_count')
			).where(
				and_(
					SystemLog.created_at >= start_time,
					SystemLog.created_at <= end_time
				)
			).group_by(SystemLog.log_level)

			level_result = await self.session.execute(level_stats_query)
			level_stats = [
				{"level": row.log_level, "count": row.count, "module_count": row.module_count}
				for row in level_result
			]

			# 按模块统计
			module_stats_query = select(
				SystemLog.module,
				func.count().label('count'),
				func.count(func.distinct(SystemLog.log_level)).label('level_count')
			).where(
				and_(
					SystemLog.created_at >= start_time,
					SystemLog.created_at <= end_time
				)
			).group_by(SystemLog.module)

			module_result = await self.session.execute(module_stats_query)
			module_stats = [
				{"module": row.module, "count": row.count, "level_count": row.level_count}
				for row in module_result
			]

			# 错误率统计
			error_stats_query = select(
				func.count().label('total_count'),
				func.count().filter(SystemLog.log_level.in_(['ERROR', 'CRITICAL'])).label('error_count')
			).where(
				and_(
					SystemLog.created_at >= start_time,
					SystemLog.created_at <= end_time
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
				"level_distribution": level_stats,
				"module_distribution": module_stats
			}
		except Exception as e:
			raise Exception(f"获取操作日志统计失败: {str(e)}")

	async def get_user_operation_summary(
			self,
			user_id: str,
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
		try:
			# 用户操作统计
			user_stats_query = select(
				SystemLog.module,
				func.count().label('operation_count'),
				func.count(func.distinct(SystemLog.action)).label('action_count')
			).where(
				and_(
					SystemLog.user_id == user_id,
					SystemLog.created_at >= start_time,
					SystemLog.created_at <= end_time
				)
			).group_by(SystemLog.module)

			user_result = await self.session.execute(user_stats_query)
			user_stats = [
				{"module": row.module, "operation_count": row.operation_count, "action_count": row.action_count}
				for row in user_result
			]

			# 用户错误统计
			error_stats_query = select(
				func.count().label('total_count'),
				func.count().filter(SystemLog.log_level.in_(['ERROR', 'CRITICAL'])).label('error_count')
			).where(
				and_(
					SystemLog.user_id == user_id,
					SystemLog.created_at >= start_time,
					SystemLog.created_at <= end_time
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
				"module_operations": user_stats
			}
		except Exception as e:
			raise Exception(f"获取用户操作摘要失败: {str(e)}")

	async def cleanup_old_logs(
			self,
			retention_days: int = 90
	) -> Dict[str, int]:
		"""
		清理过期日志

		Args:
			retention_days: 保留天数，默认为90天

		Returns:
			清理结果统计
		"""
		try:
			cutoff_date = datetime.now() - timedelta(days=retention_days)
			
			# 删除过期日志
			delete_query = select(SystemLog).where(SystemLog.created_at < cutoff_date)
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
			raise Exception(f"清理过期日志失败: {str(e)}")

	async def batch_create_logs(
			self,
			log_data_list: List[Dict[str, Any]]
	) -> List[SystemLog]:
		"""
		批量创建操作日志

		Args:
			log_data_list: 日志数据列表

		Returns:
			创建的操作日志列表
		"""
		try:
			logs = []
			for log_data in log_data_list:
				log = SystemLog(
					log_level=log_data.get("log_level", "INFO"),
					module=log_data.get("module", "unknown"),
					action=log_data.get("action", ""),
					details=str(log_data.get("details")) if log_data.get("details") else None,
					user_id=log_data.get("user_id"),
					ip_address=log_data.get("ip_address"),
					user_agent=log_data.get("user_agent"),
					execution_time=log_data.get("execution_time")
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
			raise Exception(f"批量创建操作日志失败: {str(e)}")