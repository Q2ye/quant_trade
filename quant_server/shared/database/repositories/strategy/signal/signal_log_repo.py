# -*- coding: utf-8 -*-
"""
信号日志数据仓库 - 信号处理日志数据访问
记录信号生成、处理、执行等过程中的日志信息

设计原则：
1. 纯数据访问：只做CRUD，不包含业务逻辑
2. 统一接口：继承BaseRepository，提供标准数据访问方法
3. 审计追踪：记录完整的信号处理链路
4. 异步支持：完全异步化设计

注意：需要先创建SignalLog模型，这里假设模型已存在
位置：shared/database/repositories/strategy/signal/signal_log_repository.py
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.repositories.base import BaseRepository, RepositoryError

# 假设的SignalLog模型，实际需要根据数据库模型调整
# from shared.database.models.business_models import SignalLog

# 由于模型不存在，这里使用一个占位符
# 实际使用时需要导入正确的模型
try:
	from shared.database.models.business_models import SignalLog

	MODEL_EXISTS = True
except ImportError:
	# 创建模拟的SignalLog类用于开发
	class SignalLog:
		"""信号日志模型（占位符）"""
		__tablename__ = 'signal_logs'

		id: int
		signal_id: str  # 关联的信号ID
		log_type: str  # 日志类型：generate/process/execute/error
		log_level: str  # 日志级别：info/warning/error/debug
		message: str  # 日志消息
		details: Dict[str, Any]  # 详细数据（JSON格式）
		created_at: datetime


	MODEL_EXISTS = False


class SignalLogRepository(BaseRepository[SignalLog]):
	"""
	信号日志数据仓库
	继承BaseRepository，提供SignalLog模型的专用数据访问方法
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化信号日志仓库

		Args:
			session: 数据库会话，提供数据访问上下文
		"""
		super().__init__(session, SignalLog)

	# ==================== 专用查询方法 ====================

	async def get_by_signal_id (
			self,
			signal_id: str,
			log_type: Optional[str] = None,
			log_level: Optional[str] = None,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			skip: int = 0,
			limit: int = 100,
			order_by_desc: bool = True
	) -> List[SignalLog]:
		"""
		根据信号ID获取日志记录

		Args:
			signal_id: 信号ID
			log_type: 日志类型（可选）
			log_level: 日志级别（可选）
			start_time: 开始时间（可选）
			end_time: 结束时间（可选）
			skip: 跳过的记录数
			limit: 返回的最大记录数
			order_by_desc: 是否按时间降序排列

		Returns:
			日志记录列表

		Raises:
			RepositoryError: 查询失败时抛出
		"""
		try:
			# 构建查询条件
			filters = {"signal_id": signal_id}
			if log_type:
				filters["log_type"] = log_type
			if log_level:
				filters["log_level"] = log_level

			# 构建时间范围条件
			time_filters = []
			if start_time:
				time_filters.append(self.model.created_at >= start_time)
			if end_time:
				time_filters.append(self.model.created_at <= end_time)

			# 执行查询
			query = self.build_query()

			# 应用基本过滤条件
			for attr, value in filters.items():
				if hasattr(self.model, attr):
					query = query.where(getattr(self.model, attr) == value)

			# 应用时间过滤条件
			if time_filters:
				query = query.where(and_(*time_filters))

			# 应用排序
			if order_by_desc:
				query = query.order_by(desc(str(self.model.created_at)))
			else:
				query = query.order_by(asc(str(self.model.created_at)))

			# 应用分页
			query = query.offset(skip).limit(limit)

			return await self.execute_query(query)

		except Exception as e:
			raise RepositoryError(f"按信号ID查询日志失败: {str(e)}")

	async def get_by_log_type (
			self,
			log_type: str,
			signal_id: Optional[str] = None,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			limit: int = 100
	) -> List[SignalLog]:
		"""
		根据日志类型获取日志记录

		Args:
			log_type: 日志类型
			signal_id: 信号ID（可选）
			start_time: 开始时间（可选）
			end_time: 结束时间（可选）
			limit: 最大返回记录数

		Returns:
			日志记录列表
		"""
		try:
			filters = {"log_type": log_type}
			if signal_id:
				filters["signal_id"] = signal_id

			# 构建时间范围条件
			time_filters = []
			if start_time:
				time_filters.append(self.model.created_at >= start_time)
			if end_time:
				time_filters.append(self.model.created_at <= end_time)

			# 执行查询
			query = self.build_query()

			# 应用基本过滤条件
			for attr, value in filters.items():
				if hasattr(self.model, attr):
					query = query.where(getattr(self.model, attr) == value)

			# 应用时间过滤条件
			if time_filters:
				query = query.where(and_(*time_filters))

			# 应用排序和分页
			query = query.order_by(desc(str(self.model.created_at))).limit(limit)

			return await self.execute_query(query)

		except Exception as e:
			raise RepositoryError(f"按日志类型查询失败: {str(e)}")

	async def get_error_logs (
			self,
			signal_id: Optional[str] = None,
			days: int = 7,
			limit: int = 100
	) -> List[SignalLog]:
		"""
		获取错误日志记录

		Args:
			signal_id: 信号ID（可选）
			days: 查询天数
			limit: 最大返回记录数

		Returns:
			错误日志记录列表
		"""
		try:
			cutoff_time = datetime.now() - timedelta(days=days)

			filters = {
				"log_level": "error",
				"created_at": (">=", cutoff_time)
			}
			if signal_id:
				filters["signal_id"] = signal_id

			return await self.get_many(
				skip=0,
				limit=limit,
				order_by="created_at DESC",
				**filters
			)

		except Exception as e:
			raise RepositoryError(f"获取错误日志失败: {str(e)}")

	async def get_recent_logs (
			self,
			hours: int = 24,
			log_level: Optional[str] = None,
			log_type: Optional[str] = None,
			limit: int = 200
	) -> List[SignalLog]:
		"""
		获取最近N小时的日志记录

		Args:
			hours: 小时数
			log_level: 日志级别（可选）
			log_type: 日志类型（可选）
			limit: 最大返回记录数

		Returns:
			日志记录列表
		"""
		try:
			cutoff_time = datetime.now() - timedelta(hours=hours)

			filters: Dict[str, Any] = {"created_at": (">=", cutoff_time)}
			if log_level:
				filters["log_level"] = log_level
			if log_type:
				filters["log_type"] = log_type

			return await self.get_many(
				skip=0,
				limit=limit,
				order_by="created_at DESC",
				**filters
			)

		except Exception as e:
			raise RepositoryError(f"获取最近日志失败: {str(e)}")

	async def get_log_statistics (
			self,
			signal_id: Optional[str] = None,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None
	) -> Dict[str, Any]:
		"""
		获取日志统计信息

		Args:
			signal_id: 信号ID（可选）
			start_time: 开始时间（可选）
			end_time: 结束时间（可选）

		Returns:
			统计信息字典
		"""
		try:
			# 构建查询条件
			conditions = []
			if signal_id:
				conditions.append(self.model.signal_id == signal_id)
			if start_time:
				conditions.append(self.model.created_at >= start_time)
			if end_time:
				conditions.append(self.model.created_at <= end_time)

			where_clause = and_(*conditions) if conditions else True

			# 统计总日志数
			total_query = select(func.count()).select_from(self.model).where(where_clause)
			total_result = await self.session.execute(total_query)
			total_count = total_result.scalar() or 0

			# 按日志级别统计
			level_query = (
				select(self.model.log_level, func.count().label("count"))
				.where(where_clause)
				.group_by(self.model.log_level)
				.order_by(func.count().desc())
			)
			level_result = await self.session.execute(level_query)
			level_stats = {row[0]: row[1] for row in level_result.all()}

			# 按日志类型统计
			type_query = (
				select(self.model.log_type, func.count().label("count"))
				.where(where_clause)
				.group_by(self.model.log_type)
				.order_by(func.count().desc())
			)
			type_result = await self.session.execute(type_query)
			type_stats = {row[0]: row[1] for row in type_result.all()}

			# 错误率统计
			error_count = level_stats.get("error", 0)
			error_rate = error_count / total_count if total_count > 0 else 0

			return {
				"total_count": total_count,
				"by_level": level_stats,
				"by_type": type_stats,
				"error_count": error_count,
				"error_rate": error_rate,
				"time_range": {
					"start_time": start_time,
					"end_time": end_time
				}
			}

		except Exception as e:
			raise RepositoryError(f"获取日志统计失败: {str(e)}")

	async def get_log_trend (
			self,
			signal_id: Optional[str] = None,
			days: int = 30
	) -> List[Dict[str, Any]]:
		"""
		获取日志生成趋势

		Args:
			signal_id: 信号ID（可选）
			days: 天数

		Returns:
			趋势数据列表
		"""
		try:
			end_date = datetime.now().date()
			start_date = end_date - timedelta(days=days - 1)

			# 构建基础查询
			query = (
				select(
					func.date(self.model.created_at).label("date"),
					self.model.log_level,
					func.count().label("count")
				)
				.where(
					and_(
						self.model.created_at >= start_date,
						self.model.created_at < end_date + timedelta(days=1)
					)
				)
				.group_by(func.date(self.model.created_at), self.model.log_level)
				.order_by(func.date(self.model.created_at).asc())
			)

			# 添加信号过滤条件
			if signal_id:
				query = query.where(self.model.signal_id == signal_id)

			# 执行查询
			result = await self.session.execute(query)
			rows = result.all()

			# 按日期组织数据
			date_dict = {}
			for row in rows:
				date_str = row.date.strftime('%Y-%m-%d')
				if date_str not in date_dict:
					date_dict[date_str] = {
						'date': row.date,
						'total': 0,
						'by_level': {}
					}

				date_dict[date_str]['by_level'][row.log_level] = row.count
				date_dict[date_str]['total'] += row.count

			# 转换为有序列表
			trend_list = []
			current_date = start_date
			while current_date <= end_date:
				date_str = current_date.strftime('%Y-%m-%d')
				if date_str in date_dict:
					trend_list.append(date_dict[date_str])
				else:
					trend_list.append({
						'date': current_date,
						'total': 0,
						'by_level': {}
					})
				current_date += timedelta(days=1)

			return trend_list

		except Exception as e:
			raise RepositoryError(f"获取日志趋势失败: {str(e)}")

	async def create_signal_log (
			self,
			signal_id: str,
			log_type: str,
			log_level: str,
			message: str,
			details: Optional[Dict[str, Any]] = None
	) -> SignalLog:
		"""
		创建信号日志记录（便捷方法）

		Args:
			signal_id: 信号ID
			log_type: 日志类型
			log_level: 日志级别
			message: 日志消息
			details: 详细数据（可选）

		Returns:
			创建的日志记录
		"""
		try:
			log_data = {
				"signal_id": signal_id,
				"log_type": log_type,
				"log_level": log_level,
				"message": message,
				"details": details or {},
				"created_at": datetime.now()
			}

			return await self.create(log_data)

		except Exception as e:
			raise RepositoryError(f"创建信号日志失败: {str(e)}")

	async def batch_create_logs (
			self,
			log_data_list: List[Dict[str, Any]]
	) -> List[SignalLog]:
		"""
		批量创建日志记录

		Args:
			log_data_list: 日志数据列表

		Returns:
			创建的日志记录列表
		"""
		try:
			# 添加时间戳
			now = datetime.now()
			for data in log_data_list:
				data['created_at'] = data.get('created_at', now)

			return await self.batch_create(log_data_list)

		except Exception as e:
			raise RepositoryError(f"批量创建日志失败: {str(e)}")

	async def delete_old_logs (
			self,
			days: int = 90
	) -> int:
		"""
		删除旧日志记录

		Args:
			days: 保留天数

		Returns:
			删除的记录数
		"""
		try:
			cutoff_time = datetime.now() - timedelta(days=days)

			# 执行删除
			deleted_count = await self.delete_by(
				created_at=("<", cutoff_time)
			)

			return deleted_count

		except Exception as e:
			raise RepositoryError(f"删除旧日志失败: {str(e)}")

	async def get_log_summary (self) -> Dict[str, Any]:
		"""
		获取日志数据摘要

		Returns:
			摘要信息
		"""
		try:
			# 总日志数
			total_count = await self.count()

			# 今日日志数
			today = datetime.now().date()
			tomorrow = today + timedelta(days=1)
			today_count = await self.count(
				created_at=[(">=", today), ("<", tomorrow)]
			)

			# 错误日志数
			error_count = await self.count(log_level="error")

			# 按类型统计
			type_stats_query = (
				select(self.model.log_type, func.count().label('count'))
				.group_by(self.model.log_type)
				.order_by(func.count().desc())
				.limit(10)
			)
			type_stats_result = await self.session.execute(type_stats_query)
			type_stats = {row[0]: row[1] for row in type_stats_result.all()}

			# 最近活跃的信号（最近3天有日志的信号）
			recent_days = 3
			cutoff_time = datetime.now() - timedelta(days=recent_days)

			recent_signals_query = (
				select(
					self.model.signal_id,
					func.max(self.model.created_at).label('last_log_time'),
					func.count().label('log_count')
				)
				.where(self.model.created_at >= cutoff_time)
				.group_by(self.model.signal_id)
				.order_by(func.max(self.model.created_at).desc())
				.limit(10)
			)
			recent_signals_result = await self.session.execute(recent_signals_query)

			recent_signals = [
				{
					'signal_id': row.signal_id,
					'last_log_time': row.last_log_time,
					'log_count': row.log_count
				}
				for row in recent_signals_result.all()
			]

			return {
				'total_count': total_count,
				'today_count': today_count,
				'error_count': error_count,
				'error_rate': error_count / total_count if total_count > 0 else 0,
				'type_stats': type_stats,
				'recent_signals': recent_signals,
				'summary_time': datetime.now()
			}

		except Exception as e:
			raise RepositoryError(f"获取日志摘要失败: {str(e)}")