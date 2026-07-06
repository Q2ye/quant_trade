# -*- coding: utf-8 -*-
"""
API使用日志表Repository
位置：shared/database/repositories/system/api_usage_log_repo.py
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.system_models import ApiUsageLog
from shared.database.repositories.base.repository_base import RepositoryError
from shared.database.repositories.base import BaseRepository


class ApiUsageLogRepository(BaseRepository[ApiUsageLog]):
	"""API使用日志Repository"""

	def __init__ (self, session: AsyncSession):
		"""初始化Repository"""
		super().__init__(session, ApiUsageLog)

	async def log_api_usage (
			self,
			user_id: Optional[str],
			api_endpoint: str,
			http_method: str,
			request_headers: Optional[Dict[str, Any]],
			request_body: Optional[str],
			query_params: Optional[Dict[str, Any]],
			response_status: int,
			response_time: int,
			ip_address: Optional[str] = None,
			user_agent: Optional[str] = None
	) -> ApiUsageLog:
		"""
		记录API使用日志

		Args:
			user_id: 用户ID
			api_endpoint: API端点
			http_method: HTTP方法
			request_headers: 请求头
			request_body: 请求体
			query_params: 查询参数
			response_status: 响应状态码
			response_time: 响应时间（毫秒）
			ip_address: IP地址
			user_agent: 用户代理

		Returns:
			API使用日志记录
		"""
		try:
			data = {
				"user_id": user_id,
				"api_endpoint": api_endpoint,
				"http_method": http_method,
				"request_headers": request_headers,
				"request_body": request_body,
				"query_params": query_params,
				"response_status": response_status,
				"response_time": response_time,
				"ip_address": ip_address,
				"user_agent": user_agent
			}

			return await self.create(data)
		except Exception as e:
			raise RepositoryError(f"记录API使用日志失败: {str(e)}")

	async def get_user_api_usage (
			self,
			user_id: str,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			limit: int = 100
	) -> List[ApiUsageLog]:
		"""
		获取用户的API使用记录

		Args:
			user_id: 用户ID
			start_date: 开始日期
			end_date: 结束日期
			limit: 限制记录数

		Returns:
			API使用日志列表
		"""
		try:
			query = select(self.model).where(
				self.model.user_id == user_id
			)

			if start_date:
				query = query.where(self.model.created_at >= start_date)
			if end_date:
				query = query.where(self.model.created_at <= end_date)

			query = query.order_by(desc(self.model.created_at)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取用户API使用记录失败: {str(e)}")

	async def get_api_endpoint_usage (
			self,
			api_endpoint: str,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None
	) -> List[ApiUsageLog]:
		"""
		获取指定API端点的使用记录

		Args:
			api_endpoint: API端点
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			API使用日志列表
		"""
		try:
			query = select(self.model).where(
				self.model.api_endpoint == api_endpoint
			)

			if start_date:
				query = query.where(self.model.created_at >= start_date)
			if end_date:
				query = query.where(self.model.created_at <= end_date)

			query = query.order_by(desc(self.model.created_at))

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取API端点使用记录失败: {str(e)}")

	async def get_usage_statistics (
			self,
			start_date: datetime,
			end_date: datetime,
			group_by: str = "hour"  # hour, day, week, month
	) -> List[Dict[str, Any]]:
		"""
		获取API使用统计

		Args:
			start_date: 开始日期
			end_date: 结束日期
			group_by: 分组方式

		Returns:
			统计结果列表
		"""
		try:
			# 构建时间格式化表达式
			if group_by == "hour":
				time_format = func.date_format(self.model.created_at, "%Y-%m-%d %H:00:00")
			elif group_by == "day":
				time_format = func.date_format(self.model.created_at, "%Y-%m-%d")
			elif group_by == "week":
				time_format = func.date_format(self.model.created_at, "%Y-%u")
			elif group_by == "month":
				time_format = func.date_format(self.model.created_at, "%Y-%m")
			else:
				time_format = func.date_format(self.model.created_at, "%Y-%m-%d")

			query = select(
				time_format.label("time_period"),
				func.count().label("request_count"),
				func.avg(self.model.response_time).label("avg_response_time"),
					func.max(self.model.response_time).label("max_response_time"),
					func.min(self.model.response_time).label("min_response_time")
			).where(
				and_(
					self.model.created_at >= start_date,
					self.model.created_at <= end_date
				)
			).group_by(
				"time_period"
			).order_by(
				"time_period"
			)

			result = await self.session.execute(query)
			rows = result.fetchall()

			return [
				{
					"time_period": row.time_period,
					"request_count": row.request_count,
					"avg_response_time": float(row.avg_response_time or 0),
					"max_response_time": row.max_response_time or 0,
					"min_response_time": row.min_response_time or 0
				}
				for row in rows
			]
		except Exception as e:
			raise RepositoryError(f"获取API使用统计失败: {str(e)}")

	async def get_user_usage_statistics (
			self,
			user_id: str,
			start_date: datetime,
			end_date: datetime
	) -> Dict[str, Any]:
		"""
		获取用户API使用统计

		Args:
			user_id: 用户ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			用户统计信息
		"""
		try:
			# 总请求数
			total_query = select(func.count()).where(
				and_(
					self.model.user_id == user_id,
					self.model.created_at >= start_date,
					self.model.created_at <= end_date
				)
			)
			total_result = await self.session.execute(total_query)
			total_requests = total_result.scalar() or 0

			# 成功请求数
			success_query = select(func.count()).where(
				and_(
					self.model.user_id == user_id,
					self.model.response_status >= 200,
					self.model.response_status < 300,
					self.model.created_at >= start_date,
					self.model.created_at <= end_date
				)
			)
			success_result = await self.session.execute(success_query)
			success_requests = success_result.scalar() or 0

			# 平均响应时间
			avg_time_query = select(func.avg(self.model.response_time)).where(
			and_(
				self.model.user_id == user_id,
				self.model.created_at >= start_date,
				self.model.created_at <= end_date
			)
		)
			avg_time_result = await self.session.execute(avg_time_query)
			avg_response_time = avg_time_result.scalar() or 0

			# 最常用API端点
			top_endpoint_query = select(
				self.model.api_endpoint,
				func.count().label("count")
			).where(
				and_(
					self.model.user_id == user_id,
					self.model.created_at >= start_date,
					self.model.created_at <= end_date
				)
			).group_by(
				self.model.api_endpoint
			).order_by(
				desc("count")
			).limit(5)

			top_endpoint_result = await self.session.execute(top_endpoint_query)
			top_endpoints = [
				{"api_endpoint": row.api_endpoint, "count": row.count}
				for row in top_endpoint_result.fetchall()
			]

			return {
				"total_requests": total_requests,
				"success_requests": success_requests,
				"success_rate": (success_requests / total_requests * 100) if total_requests > 0 else 0,
				"avg_response_time": float(avg_response_time),
				"top_endpoints": top_endpoints
			}
		except Exception as e:
			raise RepositoryError(f"获取用户API使用统计失败: {str(e)}")

	async def get_slow_requests (
			self,
			threshold_ms: int = 1000,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			limit: int = 100
	) -> List[ApiUsageLog]:
		"""
		获取慢请求记录

		Args:
			threshold_ms: 响应时间阈值（毫秒）
			start_date: 开始日期
			end_date: 结束日期
			limit: 限制记录数

		Returns:
			慢请求日志列表
		"""
		try:
			query = select(self.model).where(
			self.model.response_time >= threshold_ms
		)

			if start_date:
				query = query.where(self.model.created_at >= start_date)
			if end_date:
				query = query.where(self.model.created_at <= end_date)

			query = query.order_by(desc(self.model.response_time)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取慢请求记录失败: {str(e)}")

	async def get_error_requests (
			self,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			limit: int = 100
	) -> List[ApiUsageLog]:
		"""
		获取错误请求记录

		Args:
			start_date: 开始日期
			end_date: 结束日期
			limit: 限制记录数

		Returns:
			错误请求日志列表
		"""
		try:
			query = select(self.model).where(
				self.model.response_status >= 400
			)

			if start_date:
				query = query.where(self.model.created_at >= start_date)
			if end_date:
				query = query.where(self.model.created_at <= end_date)

			query = query.order_by(desc(self.model.created_at)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取错误请求记录失败: {str(e)}")

	async def cleanup_old_logs (self, days_to_keep: int = 30) -> int:
		"""
		清理旧日志

		Args:
			days_to_keep: 保留天数

		Returns:
			删除的记录数
		"""
		try:
			cutoff_date = datetime.now() - timedelta(days=days_to_keep)

			query = select(self.model).where(
				self.model.created_at < cutoff_date
			)
			result = await self.session.execute(query)
			old_logs = result.scalars().all()

			if old_logs:
				for log in old_logs:
					await self.session.delete(log)
				await self.session.flush()

			return len(old_logs)
		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"清理旧日志失败: {str(e)}")