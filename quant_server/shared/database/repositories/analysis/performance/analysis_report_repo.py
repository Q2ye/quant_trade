# quant_server/shared/database/repositories/analysis/performance/analysis_report_repository.py
"""
分析报告Repository
负责AnalysisReport表的数据访问操作

继承自BaseRepository，提供分析报告的管理功能
包括报告生成、查询、归档等业务方法
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func, desc, asc
from sqlalchemy.orm import joinedload

from quant_server.shared.database.models.business_models import AnalysisReport
from quant_server.shared.database.repositories.base.repository_base import BaseRepository, RepositoryError


class AnalysisReportRepository(BaseRepository[AnalysisReport]):
	"""
	分析报告Repository
	继承自BaseRepository，提供分析报告的数据访问方法
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化分析报告Repository

		Args:
			session: 数据库会话
		"""
		super().__init__(session, AnalysisReport)

	async def create_report (
			self,
			report_type: str,
			report_name: str,
			report_config: Dict[str, Any],
			generated_by: Optional[int] = None,
			report_data: Optional[Dict[str, Any]] = None,
			format: str = "json",
			is_public: bool = False,
			tags: Optional[List[str]] = None
	) -> AnalysisReport:
		"""
		创建分析报告

		Args:
			report_type: 报告类型（daily, weekly, monthly, performance, risk, custom）
			report_name: 报告名称
			report_config: 报告生成配置
			generated_by: 生成人ID（可选）
			report_data: 报告数据（可选）
			format: 报告格式（json, html, pdf, excel）
			is_public: 是否公开
			tags: 标签列表（可选）

		Returns:
			AnalysisReport: 创建的报告对象
		"""
		try:
			report_data = {
				'report_type': report_type,
				'report_name': report_name,
				'report_config': report_config,
				'format': format,
				'status': 'pending',
				'generated_by': generated_by,
				'report_data': report_data or {},
				'is_public': is_public,
				'tags': tags or []
			}

			return await self.create(report_data)
		except Exception as e:
			raise RepositoryError(f"创建分析报告失败: {str(e)}")

	async def update_report_status (
			self,
			report_id: int,
			status: str,
			file_path: Optional[str] = None,
			file_size: Optional[int] = None,
			error_message: Optional[str] = None
	) -> bool:
		"""
		更新报告状态

		Args:
			report_id: 报告ID
			status: 新状态（pending, generating, completed, failed）
			file_path: 文件存储路径（可选）
			file_size: 文件大小（可选）
			error_message: 错误信息（可选）

		Returns:
			bool: 更新是否成功
		"""
		try:
			update_data = {'status': status}

			if status == 'completed':
				update_data['generated_at'] = datetime.now()

			if file_path is not None:
				update_data['file_path'] = file_path

			if file_size is not None:
				update_data['file_size'] = file_size

			if error_message is not None:
				update_data['error_message'] = error_message

			return await self.update(report_id, update_data) is not None
		except Exception as e:
			raise RepositoryError(f"更新报告状态失败: {str(e)}")

	async def mark_as_generating (self, report_id: int) -> bool:
		"""
		标记报告为生成中

		Args:
			report_id: 报告ID

		Returns:
			bool: 标记是否成功
		"""
		return await self.update_report_status(report_id, 'generating')

	async def mark_as_completed (
			self,
			report_id: int,
			file_path: str,
			file_size: int
	) -> bool:
		"""
		标记报告为已完成

		Args:
			report_id: 报告ID
			file_path: 文件存储路径
			file_size: 文件大小

		Returns:
			bool: 标记是否成功
		"""
		return await self.update_report_status(
			report_id, 'completed', file_path, file_size
		)

	async def mark_as_failed (
			self,
			report_id: int,
			error_message: str
	) -> bool:
		"""
		标记报告为失败

		Args:
			report_id: 报告ID
			error_message: 错误信息

		Returns:
			bool: 标记是否成功
		"""
		return await self.update_report_status(
			report_id, 'failed', error_message=error_message
		)

	async def get_reports_by_type (
			self,
			report_type: str,
			only_public: bool = False,
			limit: int = 100,
			offset: int = 0
	) -> Tuple[List[AnalysisReport], int]:
		"""
		根据类型获取报告

		Args:
			report_type: 报告类型
			only_public: 是否只获取公开报告
			limit: 限制记录数
			offset: 偏移量

		Returns:
			Tuple[List[AnalysisReport], int]: 报告列表和总数
		"""
		try:
			# 构建查询条件
			conditions = [self.model.report_type == report_type]

			if only_public:
				conditions.append(self.model.is_public == True)

			# 获取总数
			count_query = select(func.count()).select_from(self.model).where(
				and_(*conditions)
			)
			total_result = await self.session.execute(count_query)
			total = total_result.scalar() or 0

			# 获取数据
			query = select(self.model).where(
				and_(*conditions)
			).order_by(
				desc(self.model.created_at)
			).offset(offset).limit(limit)

			result = await self.session.execute(query)
			reports = result.scalars().all()

			return reports, total
		except Exception as e:
			raise RepositoryError(f"获取类型报告失败: {str(e)}")

	async def get_recent_reports (
			self,
			days: int = 7,
			report_type: Optional[str] = None,
			status: Optional[str] = None,
			limit: int = 50
	) -> List[AnalysisReport]:
		"""
		获取最近指定天数内的报告

		Args:
			days: 天数
			report_type: 报告类型过滤（可选）
			status: 状态过滤（可选）
			limit: 限制记录数

		Returns:
			List[AnalysisReport]: 最近报告列表
		"""
		try:
			time_threshold = datetime.now() - timedelta(days=days)

			conditions = [self.model.created_at >= time_threshold]

			if report_type:
				conditions.append(self.model.report_type == report_type)

			if status:
				conditions.append(self.model.status == status)

			query = select(self.model).where(
				and_(*conditions)
			).order_by(
				desc(self.model.created_at)
			).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取最近报告失败: {str(e)}")

	async def search_reports (
			self,
			keyword: str,
			report_type: Optional[str] = None,
			status: Optional[str] = None,
			is_public: Optional[bool] = None,
			limit: int = 50
	) -> List[AnalysisReport]:
		"""
		搜索报告

		Args:
			keyword: 搜索关键词
			report_type: 报告类型过滤（可选）
			status: 状态过滤（可选）
			is_public: 是否公开过滤（可选）
			limit: 限制记录数

		Returns:
			List[AnalysisReport]: 搜索结果的报告列表
		"""
		try:
			conditions = []

			if keyword:
				conditions.append(
					or_(
						self.model.report_name.ilike(f'%{keyword}%'),
						self.model.tags.contains([keyword]) if hasattr(self.model.tags, 'contains') else False
					)
				)

			if report_type:
				conditions.append(self.model.report_type == report_type)

			if status:
				conditions.append(self.model.status == status)

			if is_public is not None:
				conditions.append(self.model.is_public == is_public)

			query = select(self.model)

			if conditions:
				query = query.where(and_(*conditions))

			query = query.order_by(desc(self.model.created_at)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"搜索报告失败: {str(e)}")

	async def get_user_reports (
			self,
			user_id: int,
			report_type: Optional[str] = None,
			limit: int = 100,
			offset: int = 0
	) -> Tuple[List[AnalysisReport], int]:
		"""
		获取用户相关的报告（生成的报告或公开报告）

		Args:
			user_id: 用户ID
			report_type: 报告类型过滤（可选）
			limit: 限制记录数
			offset: 偏移量

		Returns:
			Tuple[List[AnalysisReport], int]: 报告列表和总数
		"""
		try:
			# 用户生成的报告或公开报告
			conditions = [
				or_(
					self.model.generated_by == user_id,
					self.model.is_public == True
				)
			]

			if report_type:
				conditions.append(self.model.report_type == report_type)

			# 获取总数
			count_query = select(func.count()).select_from(self.model).where(
				and_(*conditions)
			)
			total_result = await self.session.execute(count_query)
			total = total_result.scalar() or 0

			# 获取数据
			query = select(self.model).where(
				and_(*conditions)
			).order_by(
				desc(self.model.created_at)
			).offset(offset).limit(limit)

			result = await self.session.execute(query)
			reports = result.scalars().all()

			return reports, total
		except Exception as e:
			raise RepositoryError(f"获取用户报告失败: {str(e)}")

	async def get_report_statistics (
			self,
			days: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		获取报告统计信息

		Args:
			days: 时间范围（天数，可选）

		Returns:
			Dict[str, Any]: 报告统计信息
		"""
		try:
			# 构建基础查询
			query = select(
				self.model.report_type,
				self.model.status,
				func.count(self.model.id).label('count'),
				func.sum(func.cast(self.model.is_public, func.Integer)).label('public_count')
			)

			if days:
				time_threshold = datetime.now() - timedelta(days=days)
				query = query.where(self.model.created_at >= time_threshold)

			query = query.group_by(
				self.model.report_type,
				self.model.status
			)

			result = await self.session.execute(query)

			stats = {
				'total': 0,
				'by_type': {},
				'by_status': {
					'pending': 0,
					'generating': 0,
					'completed': 0,
					'failed': 0
				}
			}

			for report_type, status, count, public_count in result.all():
				if report_type not in stats['by_type']:
					stats['by_type'][report_type] = {
						'total': 0,
						'public': 0,
						'private': 0,
						'by_status': {
							'pending': 0,
							'generating': 0,
							'completed': 0,
							'failed': 0
						}
					}

				stats['by_type'][report_type]['total'] += count
				stats['by_type'][report_type]['public'] += public_count
				stats['by_type'][report_type]['private'] += (count - public_count)
				stats['by_type'][report_type]['by_status'][status] = count

				stats['by_status'][status] += count
				stats['total'] += count

			return stats
		except Exception as e:
			raise RepositoryError(f"获取报告统计失败: {str(e)}")

	async def get_report_trend (
			self,
			days: int = 30,
			report_type: Optional[str] = None
	) -> List[Dict[str, Any]]:
		"""
		获取报告生成趋势

		Args:
			days: 天数
			report_type: 报告类型过滤（可选）

		Returns:
			List[Dict[str, Any]]: 趋势数据
		"""
		try:
			# 使用日期分组统计
			# 具体实现依赖于数据库的日期函数

			# 这里简化实现，按天统计
			time_threshold = datetime.now() - timedelta(days=days)

			# 根据数据库类型选择适当的日期截断函数
			# 这里假设使用PostgreSQL的date_trunc

			query = select(
				func.date_trunc('day', self.model.created_at).label('date'),
				func.count(self.model.id).label('count'),
				func.sum(func.cast(self.model.status == 'completed', func.Integer)).label('completed_count')
			).where(
				self.model.created_at >= time_threshold
			)

			if report_type:
				query = query.where(self.model.report_type == report_type)

			query = query.group_by(
				func.date_trunc('day', self.model.created_at)
			).order_by(
				func.date_trunc('day', self.model.created_at)
			)

			result = await self.session.execute(query)

			trend_data = []
			for date, count, completed_count in result.all():
				trend_data.append({
					'date': date,
					'total_count': count,
					'completed_count': completed_count or 0,
					'success_rate': (completed_count / count * 100) if count > 0 else 0
				})

			return trend_data
		except Exception as e:
			# 如果数据库不支持date_trunc，使用简化方法
			# 获取所有数据并在Python中处理
			reports = await self.get_recent_reports(days=days, report_type=report_type, limit=1000)

			# 按日期分组
			daily_stats = {}
			for report in reports:
				date_key = report.created_at.date()
				if date_key not in daily_stats:
					daily_stats[date_key] = {
						'total': 0,
						'completed': 0
					}

				daily_stats[date_key]['total'] += 1
				if report.status == 'completed':
					daily_stats[date_key]['completed'] += 1

			# 转换为列表
			trend_data = []
			for date_key, stats in sorted(daily_stats.items()):
				trend_data.append({
					'date': date_key,
					'total_count': stats['total'],
					'completed_count': stats['completed'],
					'success_rate': (stats['completed'] / stats['total'] * 100) if stats['total'] > 0 else 0
				})

			return trend_data

	async def add_report_tag (
			self,
			report_id: int,
			tag: str
	) -> bool:
		"""
		为报告添加标签

		Args:
			report_id: 报告ID
			tag: 标签

		Returns:
			bool: 添加是否成功
		"""
		try:
			report = await self.get(report_id)

			if not report:
				return False

			current_tags = report.tags or []

			if tag not in current_tags:
				current_tags.append(tag)

				return await self.update(report_id, {'tags': current_tags}) is not None

			return True
		except Exception as e:
			raise RepositoryError(f"添加报告标签失败: {str(e)}")

	async def remove_report_tag (
			self,
			report_id: int,
			tag: str
	) -> bool:
		"""
		移除报告的标签

		Args:
			report_id: 报告ID
			tag: 标签

		Returns:
			bool: 移除是否成功
		"""
		try:
			report = await self.get(report_id)

			if not report:
				return False

			current_tags = report.tags or []

			if tag in current_tags:
				current_tags.remove(tag)

				return await self.update(report_id, {'tags': current_tags}) is not None

			return True
		except Exception as e:
			raise RepositoryError(f"移除报告标签失败: {str(e)}")

	async def get_reports_by_tags (
			self,
			tags: List[str],
			match_all: bool = False,
			limit: int = 50
	) -> List[AnalysisReport]:
		"""
		根据标签获取报告

		Args:
			tags: 标签列表
			match_all: 是否匹配所有标签
			limit: 限制记录数

		Returns:
			List[AnalysisReport]: 匹配的报告列表
		"""
		try:
			if not tags:
				return []

			query = select(self.model)

			if match_all:
				# 需要包含所有标签
				for tag in tags:
					query = query.where(
						self.model.tags.contains([tag]) if hasattr(self.model.tags, 'contains') else False
					)
			else:
				# 匹配任意标签
				conditions = []
				for tag in tags:
					conditions.append(
						self.model.tags.contains([tag]) if hasattr(self.model.tags, 'contains') else False
					)

				if conditions:
					query = query.where(or_(*conditions))

			query = query.order_by(desc(self.model.created_at)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取标签报告失败: {str(e)}")

	async def cleanup_old_reports (
			self,
			days: int = 90,
			keep_completed: bool = True
	) -> int:
		"""
		清理旧的报告

		Args:
			days: 保留天数
			keep_completed: 是否保留已完成的报告

		Returns:
			int: 删除的记录数
		"""
		try:
			time_threshold = datetime.now() - timedelta(days=days)

			conditions = [self.model.created_at < time_threshold]

			if keep_completed:
				# 只删除非完成状态的报告
				conditions.append(self.model.status != 'completed')

			query = delete(self.model).where(and_(*conditions))

			result = await self.session.execute(query)
			await self.session.commit()

			return result.rowcount or 0
		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"清理旧报告失败: {str(e)}")