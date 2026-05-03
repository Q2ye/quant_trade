# -*- coding: utf-8 -*-
"""
因子研究Repository
负责factor_research表的数据访问

位置：shared/database/repositories/analysis/factor_research_repo.py

设计原则：
1. 遵循RepositoryBase基类规范
2. 提供因子研究特定查询方法
3. 支持复杂状态管理和进度更新
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
from sqlalchemy import desc, and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.repositories.base.repository_base import BaseRepository
from shared.database.repositories.types import (
	RepositoryResult, PaginationParams, PaginationResult
)
from shared.database.models.business_models import FactorResearch


class FactorResearchRepository(BaseRepository[FactorResearch]):
	"""
	因子研究Repository
	提供因子研究任务的数据访问接口
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化因子研究Repository

		Args:
			session: 数据库会话
		"""
		super().__init__(session, FactorResearch)

	async def create_research_task (
			self,
			research_id: str,
			research_name: str,
			factor_name: str,
			user_id: str,
			factor_definition: Optional[Dict] = None,
			factor_category: Optional[str] = None,
			universe: Optional[List[str]] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			parameters: Optional[Dict] = None,
			analysis_type: str = 'ic_analysis',
			created_by: Optional[int] = None
	) -> RepositoryResult[FactorResearch]:
		"""
		创建因子研究任务

		Args:
			research_id: 研究任务ID
			research_name: 研究任务名称
			factor_name: 因子名称
			user_id: 用户ID
			factor_definition: 因子定义
			factor_category: 因子类别
			universe: 股票池
			start_date: 开始日期
			end_date: 结束日期
			parameters: 研究参数
			analysis_type: 分析类型
			created_by: 创建人ID

		Returns:
			RepositoryResult: 创建结果
		"""
		try:
			# 准备数据
			research_data = {
				'research_id': research_id,
				'research_name': research_name,
				'factor_name': factor_name,
				'factor_definition': factor_definition or {},
				'factor_category': factor_category,
				'universe': universe or [],
				'start_date': start_date,
				'end_date': end_date,
				'parameters': parameters or {},
				'analysis_type': analysis_type,
				'user_id': user_id,
				'created_by': created_by or user_id,
				'updated_by': created_by or user_id,
				'status': 'pending',
				'progress': 0.0,
				'calculated_count': 0,
				'total_stocks': len(universe) if universe else 0
			}

			# 创建记录
			result = await self.create(research_data)

			return RepositoryResult(
				success=True,
				data=result,
			)

		except Exception as e:
			return RepositoryResult(
				success=False,
				error=str(e)
			)

	async def get_by_research_id (
			self,
			research_id: str
	) -> RepositoryResult[Optional[FactorResearch]]:
		"""
		根据研究ID获取研究任务

		Args:
			research_id: 研究任务ID

		Returns:
			RepositoryResult: 查询结果
		"""
		try:
			# 使用基类的查询方法
			result = await self.session.execute(
				select(self.model).where(self.model.research_id == research_id)
			)
			task = result.scalar_one_or_none()

			if task:
				return RepositoryResult(
					success=True,
					data=task,
				)
			else:
				return RepositoryResult(
					success=False,
					error=f"研究任务不存在: {research_id}",
				)

		except Exception as e:
			return RepositoryResult(
				success=False,
				error=str(e),
			)

	async def update_research_status (
			self,
			research_id: str,
			status: str,
			error_message: Optional[str] = None,
			error_stack: Optional[str] = None
	) -> RepositoryResult[bool]:
		"""
		更新研究任务状态

		Args:
			research_id: 研究任务ID
			status: 新状态
			error_message: 错误信息（如果有）
			error_stack: 错误堆栈（如果有）

		Returns:
			RepositoryResult: 更新结果
		"""
		try:
			# 先获取任务
			result = await self.get_by_research_id(research_id)
			if not result.success or not result.data:
				return RepositoryResult(
					success=False,
					error=f"研究任务不存在: {research_id}",
				)

			task = result.data
			task_id = task.id

			# 准备更新数据
			update_data = {
				'status': status,
				'updated_at': datetime.now()
			}

			# 根据状态设置时间戳
			if status == 'running':
				update_data['started_at'] = datetime.now()
			elif status in ['completed', 'failed', 'cancelled']:
				update_data['completed_at'] = datetime.now()

			# 设置错误信息
			if error_message:
				update_data['error_message'] = error_message
			if error_stack:
				update_data['error_stack'] = error_stack

			# 执行更新
			await self.update(task_id, update_data)

			return RepositoryResult(
				success=True,
				data=True,
			)

		except Exception as e:
			return RepositoryResult(
				success=False,
				error=str(e),
			)

	async def update_research_progress (
			self,
			research_id: str,
			progress: float,
			calculated_count: Optional[int] = None,
			total_stocks: Optional[int] = None
	) -> RepositoryResult[bool]:
		"""
		更新研究任务进度

		Args:
			research_id: 研究任务ID
			progress: 进度（0-1）
			calculated_count: 已计算数量
			total_stocks: 总数量

		Returns:
			RepositoryResult: 更新结果
		"""
		try:
			# 先获取任务
			result = await self.get_by_research_id(research_id)
			if not result.success or not result.data:
				return RepositoryResult(
					success=False,
					error=f"研究任务不存在: {research_id}",
				)

			task = result.data
			task_id = task.id

			# 准备更新数据
			update_data = {
				'progress': max(0.0, min(1.0, progress)),  # 限制在0-1之间
				'updated_at': datetime.now()
			}

			# 更新数量信息
			if calculated_count is not None:
				update_data['calculated_count'] = calculated_count
			if total_stocks is not None:
				update_data['total_stocks'] = total_stocks

			# 执行更新
			await self.update(task_id, update_data)

			return RepositoryResult(
				success=True,
				data=True,
			)

		except Exception as e:
			return RepositoryResult(
				success=False,
				error=str(e),
			)

	async def save_research_result (
			self,
			research_id: str,
			result: Dict[str, Any],
			summary: Optional[Dict[str, Any]] = None,
			report: Optional[Dict[str, Any]] = None
	) -> RepositoryResult[bool]:
		"""
		保存研究结果

		Args:
			research_id: 研究任务ID
			result: 研究结果
			summary: 研究总结
			report: 详细报告

		Returns:
			RepositoryResult: 保存结果
		"""
		try:
			# 先获取任务
			research_result = await self.get_by_research_id(research_id)
			if not research_result.success or not research_result.data:
				return RepositoryResult(
					success=False,
					error=f"研究任务不存在: {research_id}",
				)

			task = research_result.data
			task_id = task.id

			# 准备更新数据
			update_data = {
				'result': result,
				'updated_at': datetime.now()
			}

			# 添加可选字段
			if summary:
				update_data['summary'] = summary
			if report:
				update_data['report'] = report

			# 提取性能指标
			if result.get('analysis_results', {}).get('ic_analysis'):
				ic_analysis = result['analysis_results']['ic_analysis']
				if 'ic_mean' in ic_analysis:
					update_data['ic_mean'] = ic_analysis['ic_mean']
				if 'ic_ir' in ic_analysis:
					update_data['ic_ir'] = ic_analysis['ic_ir']

			if result.get('analysis_results', {}).get('quantile_analysis'):
				quantile_analysis = result['analysis_results']['quantile_analysis']
				if 'top_minus_bottom' in quantile_analysis:
					update_data['top_minus_bottom'] = quantile_analysis['top_minus_bottom']

			# 执行更新
			await self.update(task_id, update_data)

			return RepositoryResult(
				success=True,
				data=True,
			)

		except Exception as e:
			return RepositoryResult(
				success=False,
				error=str(e),
			)


	async def get_user_research_tasks (
			self,
			user_id: str,
			status: Optional[str] = None,
			factor_name: Optional[str] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			pagination: Optional[PaginationParams] = None
	) -> RepositoryResult[PaginationResult[FactorResearch]]:
		"""
		获取用户的研究任务列表

		Args:
			user_id: 用户ID
			status: 状态筛选
			factor_name: 因子名称筛选
			start_date: 开始日期筛选
			end_date: 结束日期筛选
			pagination: 分页参数

		Returns:
			RepositoryResult: 查询结果
		"""
		try:
			# 构建基础查询
			query = select(self.model).where(self.model.user_id == user_id)

			if status:
				query = query.where(self.model.status == status)

			if factor_name:
				query = query.where(self.model.factor_name.ilike(f'%{factor_name}%'))

			if start_date:
				start_datetime = datetime.combine(start_date, datetime.min.time())
				query = query.where(self.model.created_at >= start_datetime)

			if end_date:
				end_datetime = datetime.combine(end_date, datetime.max.time())
				query = query.where(self.model.created_at <= end_datetime)

			query = query.order_by(desc(self.model.created_at))

			# 初始化总数为查询结果数量（用于不分页情况）
			# total_count = 0

			if pagination:
				# 计算总数
				count_query = select(func.count()).select_from(query.subquery())
				count_result = await self.session.execute(count_query)
				total_count = count_result.scalar() or 0

				# 应用分页 - 使用get_offset()和get_limit()方法
				offset = pagination.get_offset()
				limit = pagination.get_limit()
				query = query.offset(offset).limit(limit)
			else:
				# 不分页，获取所有结果
				result = await self.session.execute(query)
				tasks = result.scalars().all()
				total_count = len(tasks)

				# 创建分页结果（不分页时page=1, page_size=总数）
				pagination_result = PaginationResult(
					items=tasks,
					total=total_count,
					page=1,
					page_size=total_count,
					total_pages=1
				)

				return RepositoryResult(
					success=True,
					data=pagination_result,
				)

			# 执行分页查询
			result = await self.session.execute(query)
			tasks = result.scalars().all()

			# 计算总页数
			if pagination and pagination.page_size > 0:
				total_pages = (total_count + pagination.page_size - 1) // pagination.page_size
			else:
				total_pages = 1

			# 构建分页结果
			pagination_result = PaginationResult(
				items=tasks,
				total=total_count,
				page=pagination.page if pagination else 1,
				page_size=pagination.page_size if pagination else total_count,
				total_pages=total_pages
			)

			return RepositoryResult(
				success=True,
				data=pagination_result,
			)

		except Exception as e:
			return RepositoryResult(
				success=False,
				error=str(e),
			)

	async def get_recent_research_tasks (
			self,
			days: int = 7,
			limit: int = 100
	) -> RepositoryResult[List[FactorResearch]]:
		"""
		获取最近的研究任务

		Args:
			days: 最近天数
			limit: 限制数量

		Returns:
			RepositoryResult: 查询结果
		"""
		try:
			# 计算开始时间
			start_date = datetime.now() - timedelta(days=days)

			# 构建查询
			query = select(self.model).where(
				and_(
					self.model.created_at >= start_date,
					self.model.status.in_(['completed', 'running'])
				)
			).order_by(
				desc(self.model.created_at)
			).limit(limit)

			result = await self.session.execute(query)
			tasks = result.scalars().all()

			return RepositoryResult(
				success=True,
				data=tasks,
			)

		except Exception as e:
			return RepositoryResult(
				success=False,
				error=str(e),
			)

	async def get_top_factors (
			self,
			metric: str = 'ic_mean',
			category: Optional[str] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			limit: int = 10
	) -> RepositoryResult[List[Dict[str, Any]]]:
		"""
		获取表现最好的因子

		Args:
			metric: 排序指标（ic_mean, ic_ir, top_minus_bottom）
			category: 因子类别筛选
			start_date: 开始日期筛选
			end_date: 结束日期筛选
			limit: 限制数量

		Returns:
			RepositoryResult: 查询结果
		"""
		try:
			# 构建查询
			query = select(self.model).where(
				and_(
					self.model.status == 'completed',
					getattr(self.model, metric) is not None
				)
			)

			if category:
				query = query.where(self.model.factor_category == category)

			if start_date:
				start_datetime = datetime.combine(start_date, datetime.min.time())
				query = query.where(self.model.completed_at >= start_datetime)

			if end_date:
				end_datetime = datetime.combine(end_date, datetime.max.time())
				query = query.where(self.model.completed_at <= end_datetime)

			# 根据指标排序
			if metric in ['ic_mean', 'ic_ir', 'top_minus_bottom']:
				query = query.order_by(desc(getattr(self.model, metric)))

			query = query.limit(limit)

			# 执行查询
			result = await self.session.execute(query)
			tasks = result.scalars().all()

			# 转换为字典列表
			result_data = []
			for task in tasks:
				task_data = {
					'factor_name': task.factor_name,
					'factor_category': task.factor_category,
					'ic_mean': float(task.ic_mean) if task.ic_mean is not None else None,
					'ic_ir': float(task.ic_ir) if task.ic_ir is not None else None,
					'top_minus_bottom': (
						float(task.top_minus_bottom)
						if task.top_minus_bottom is not None
						else None
					),
					'research_id': task.research_id,
					'completed_at': task.completed_at.isoformat() if task.completed_at else None
				}
				result_data.append(task_data)

			return RepositoryResult(
				success=True,
				data=result_data,
			)

		except Exception as e:
			return RepositoryResult(
				success=False,
				error=str(e),
			)

	async def cancel_pending_tasks (
			self,
			user_id: Optional[int] = None,
			older_than_hours: int = 24
	) -> RepositoryResult[int]:
		"""
		取消超时的待处理任务

		Args:
			user_id: 用户ID（可选）
			older_than_hours: 超过多少小时的任务

		Returns:
			RepositoryResult: 取消数量
		"""
		try:
			# 计算超时时间
			timeout_time = datetime.now() - timedelta(hours=older_than_hours)

			# 构建查询条件
			conditions = [
				self.model.status == 'pending',
				self.model.created_at <= timeout_time
			]

			if user_id:
				conditions.append(self.model.user_id == user_id)

			# 查询超时任务
			query = select(self.model).where(and_(*conditions))
			result = await self.session.execute(query)
			tasks = result.scalars().all()

			# 批量更新状态
			updated_count = 0
			for task in tasks:
				update_data = {
					'status': 'cancelled',
					'error_message': '任务超时自动取消',
					'completed_at': datetime.now(),
					'updated_at': datetime.now()
				}
				await self.update(task.id, update_data)
				updated_count += 1

			return RepositoryResult(
				success=True,
				data=updated_count,
			)

		except Exception as e:
			return RepositoryResult(
				success=False,
				error=str(e),
			)