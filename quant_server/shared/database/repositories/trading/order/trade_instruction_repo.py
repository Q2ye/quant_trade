# -*- coding: utf-8 -*-
"""
交易指令仓库 - 提供交易指令数据的统一访问接口

基于BaseRepository实现，提供交易指令相关的CRUD操作和业务查询方法
位置：quant_server/shared/database/repositories/trading/order/trade_instruction_repository.py

设计原则：
1. 纯数据访问：只做CRUD，不做业务逻辑
2. 继承BaseRepository：复用基础CRUD操作
3. 指令状态管理：支持指令状态流转查询
4. 批量操作：支持批量指令处理
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, update, and_, func, desc, asc, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from core.exceptions.business_exceptions import OrderException
from shared.database.models.business_models import TradeInstruction, SysUser, Strategy
from shared.database.repositories.base import BaseRepository, RepositoryError
from shared.database.repositories.types import (
	PaginationParams,
	PaginationResult,
	FilterCondition,
	FilterOperator,
	SortCondition
)


class TradeInstructionRepository(BaseRepository[TradeInstruction]):
	"""交易指令仓库 - 交易指令数据访问层"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化交易指令仓库

		Args:
			session: 数据库会话
		"""
		super().__init__(session, TradeInstruction)

	# ==================== 业务查询方法 ====================

	async def get_by_instruction_id (self, instruction_id: str, with_details: bool = False) -> Optional[
		TradeInstruction]:
		"""
		根据指令ID获取交易指令

		Args:
			instruction_id: 指令ID
			with_details: 是否加载详细信息

		Returns:
			交易指令对象或None
		"""
		try:
			query = select(TradeInstruction).where(TradeInstruction.instruction_id == instruction_id)

			if with_details:
				query = query.options(
					joinedload(TradeInstruction.user),
					joinedload(TradeInstruction.strategy)
				)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"获取交易指令失败: {str(e)}")

	async def get_by_user_id (
			self,
			user_id: str,
			instruction_type: Optional[str] = None,
			status: Optional[str] = None,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			skip: int = 0,
			limit: int = 100,
			order_by: str = "created_at_desc"
	) -> List[TradeInstruction]:
		"""
		根据用户ID获取交易指令

		Args:
			user_id: 用户ID
			instruction_type: 指令类型过滤
			status: 指令状态过滤
			start_date: 开始时间
			end_date: 结束时间
			skip: 跳过记录数
			limit: 限制记录数
			order_by: 排序方式

		Returns:
			交易指令列表
		"""
		try:
			filters = [TradeInstruction.user_id == user_id]

			if instruction_type:
				filters.append(TradeInstruction.instruction_type == instruction_type)
			if status:
				filters.append(TradeInstruction.status == status)
			if start_date:
				filters.append(TradeInstruction.created_at >= start_date)
			if end_date:
				filters.append(TradeInstruction.created_at <= end_date)

			# 构建排序
			order_clause = self._build_order_by(order_by)

			query = (
				select(TradeInstruction)
				.where(and_(*filters))
				.order_by(*order_clause)
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取用户交易指令失败: {str(e)}")

	async def get_by_strategy_id (
			self,
			strategy_id: str,
			instruction_type: Optional[str] = None,
			status: Optional[str] = None,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			skip: int = 0,
			limit: int = 100
	) -> List[TradeInstruction]:
		"""
		根据策略ID获取交易指令

		Args:
			strategy_id: 策略ID
			instruction_type: 指令类型过滤
			status: 指令状态过滤
			start_date: 开始时间
			end_date: 结束时间
			skip: 跳过记录数
			limit: 限制记录数

		Returns:
			交易指令列表
		"""
		try:
			filters = [TradeInstruction.strategy_id == strategy_id]

			if instruction_type:
				filters.append(TradeInstruction.instruction_type == instruction_type)
			if status:
				filters.append(TradeInstruction.status == status)
			if start_date:
				filters.append(TradeInstruction.created_at >= start_date)
			if end_date:
				filters.append(TradeInstruction.created_at <= end_date)

			query = (
				select(TradeInstruction)
				.where(and_(*filters))
				.order_by(desc(TradeInstruction.created_at))
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取策略交易指令失败: {str(e)}")

	async def get_by_status (
			self,
			status: str,
			instruction_type: Optional[str] = None,
			user_id: Optional[int] = None,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			skip: int = 0,
			limit: int = 100
	) -> List[TradeInstruction]:
		"""
		根据状态获取交易指令

		Args:
			status: 指令状态
			instruction_type: 指令类型过滤
			user_id: 用户ID过滤
			start_date: 开始时间
			end_date: 结束时间
			skip: 跳过记录数
			limit: 限制记录数

		Returns:
			交易指令列表
		"""
		try:
			filters = [TradeInstruction.status == status]

			if instruction_type:
				filters.append(TradeInstruction.instruction_type == instruction_type)
			if user_id:
				filters.append(TradeInstruction.user_id == user_id)
			if start_date:
				filters.append(TradeInstruction.created_at >= start_date)
			if end_date:
				filters.append(TradeInstruction.created_at <= end_date)

			query = (
				select(TradeInstruction)
				.where(and_(*filters))
				.order_by(asc(TradeInstruction.created_at))
				.offset(skip)
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取状态交易指令失败: {str(e)}")

	async def get_pending_instructions (
			self,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None,
			instruction_type: Optional[str] = None,
			limit: int = 100
	) -> List[TradeInstruction]:
		"""
		获取待处理指令

		Args:
			user_id: 用户ID过滤
			strategy_id: 策略ID过滤
			instruction_type: 指令类型过滤
			limit: 限制记录数

		Returns:
			待处理指令列表
		"""
		try:
			filters = [TradeInstruction.status == 'pending']

			if user_id:
				filters.append(TradeInstruction.user_id == user_id)
			if strategy_id:
				filters.append(TradeInstruction.strategy_id == strategy_id)
			if instruction_type:
				filters.append(TradeInstruction.instruction_type == instruction_type)

			query = (
				select(TradeInstruction)
				.where(and_(*filters))
				.order_by(asc(TradeInstruction.created_at))
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取待处理指令失败: {str(e)}")

	async def get_executing_instructions (
			self,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None,
			instruction_type: Optional[str] = None,
			limit: int = 100
	) -> List[TradeInstruction]:
		"""
		获取执行中指令

		Args:
			user_id: 用户ID过滤
			strategy_id: 策略ID过滤
			instruction_type: 指令类型过滤
			limit: 限制记录数

		Returns:
			执行中指令列表
		"""
		try:
			filters = [TradeInstruction.status == 'executing']

			if user_id:
				filters.append(TradeInstruction.user_id == user_id)
			if strategy_id:
				filters.append(TradeInstruction.strategy_id == strategy_id)
			if instruction_type:
				filters.append(TradeInstruction.instruction_type == instruction_type)

			query = (
				select(TradeInstruction)
				.where(and_(*filters))
				.order_by(asc(TradeInstruction.created_at))
				.limit(limit)
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取执行中指令失败: {str(e)}")

	async def get_today_instructions (
			self,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None,
			instruction_type: Optional[str] = None
	) -> List[TradeInstruction]:
		"""
		获取今日指令

		Args:
			user_id: 用户ID过滤
			strategy_id: 策略ID过滤
			instruction_type: 指令类型过滤

		Returns:
			今日指令列表
		"""
		try:
			today = datetime.now().date()
			start_of_day = datetime.combine(today, datetime.min.time())
			end_of_day = datetime.combine(today, datetime.max.time())

			filters = [
				TradeInstruction.created_at >= start_of_day,
				TradeInstruction.created_at <= end_of_day
			]

			if user_id:
				filters.append(TradeInstruction.user_id == user_id)
			if strategy_id:
				filters.append(TradeInstruction.strategy_id == strategy_id)
			if instruction_type:
				filters.append(TradeInstruction.instruction_type == instruction_type)

			query = (
				select(TradeInstruction)
				.where(and_(*filters))
				.order_by(desc(TradeInstruction.created_at))
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取今日指令失败: {str(e)}")

	async def get_recent_instructions (
			self,
			days: int = 7,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None,
			instruction_type: Optional[str] = None
	) -> List[TradeInstruction]:
		"""
		获取最近N天的指令

		Args:
			days: 天数
			user_id: 用户ID过滤
			strategy_id: 策略ID过滤
			instruction_type: 指令类型过滤

		Returns:
			最近指令列表
		"""
		try:
			end_time = datetime.now()
			start_time = end_time - timedelta(days=days)

			filters = [
				TradeInstruction.created_at >= start_time,
				TradeInstruction.created_at <= end_time
			]

			if user_id:
				filters.append(TradeInstruction.user_id == user_id)
			if strategy_id:
				filters.append(TradeInstruction.strategy_id == strategy_id)
			if instruction_type:
				filters.append(TradeInstruction.instruction_type == instruction_type)

			query = (
				select(TradeInstruction)
				.where(and_(*filters))
				.order_by(desc(TradeInstruction.created_at))
			)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取最近指令失败: {str(e)}")

	# ==================== 指令统计方法 ====================

	async def get_instruction_statistics (
			self,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None,
			instruction_type: Optional[str] = None,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None
	) -> Dict[str, Any]:
		"""
		获取指令统计信息

		Args:
			user_id: 用户ID过滤
			strategy_id: 策略ID过滤
			instruction_type: 指令类型过滤
			start_date: 开始时间
			end_date: 结束时间

		Returns:
			指令统计信息字典
		"""
		try:
			filters = []

			if user_id:
				filters.append(TradeInstruction.user_id == user_id)
			if strategy_id:
				filters.append(TradeInstruction.strategy_id == strategy_id)
			if instruction_type:
				filters.append(TradeInstruction.instruction_type == instruction_type)
			if start_date:
				filters.append(TradeInstruction.created_at >= start_date)
			if end_date:
				filters.append(TradeInstruction.created_at <= end_date)

			where_clause = and_(*filters) if filters else True

			# 执行统计查询
			result = await self.session.execute(
				select(
					func.count(TradeInstruction.id).label('total_instructions'),
					func.sum(case((TradeInstruction.status == 'completed', 1), else_=0)).label('completed_count'),
					func.sum(case((TradeInstruction.status == 'failed', 1), else_=0)).label('failed_count'),
					func.sum(case((TradeInstruction.status == 'cancelled', 1), else_=0)).label('cancelled_count'),
					func.avg(
						case(
							(TradeInstruction.executed_at.isnot(None),
							 func.extract('epoch', TradeInstruction.executed_at - TradeInstruction.created_at)),
							else_=None
						)
					).label('avg_execution_time_seconds')
				).where(where_clause)
			)

			row = result.first()

			return {
				'total_instructions': row.total_instructions or 0,
				'completed_count': row.completed_count or 0,
				'failed_count': row.failed_count or 0,
				'cancelled_count': row.cancelled_count or 0,
				'success_rate': (row.completed_count or 0) / (row.total_instructions or 1) * 100,
				'avg_execution_time_seconds': float(
					row.avg_execution_time_seconds) if row.avg_execution_time_seconds else 0
			}

		except Exception as e:
			raise RepositoryError(f"获取指令统计失败: {str(e)}")

	async def get_instruction_status_summary (
			self,
			user_id: Optional[int] = None,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None
	) -> Dict[str, int]:
		"""
		获取指令状态汇总

		Args:
			user_id: 用户ID过滤
			start_date: 开始时间
			end_date: 结束时间

		Returns:
			指令状态统计字典
		"""
		try:
			filters = []

			if user_id:
				filters.append(TradeInstruction.user_id == user_id)
			if start_date:
				filters.append(TradeInstruction.created_at >= start_date)
			if end_date:
				filters.append(TradeInstruction.created_at <= end_date)

			where_clause = and_(*filters) if filters else True

			# 按状态分组统计
			result = await self.session.execute(
				select(
					TradeInstruction.status,
					func.count(TradeInstruction.id).label('count')
				)
				.where(where_clause)
				.group_by(TradeInstruction.status)
			)

			status_summary = {}
			for row in result.all():
				status_summary[row.status] = row.count

			return status_summary

		except Exception as e:
			raise RepositoryError(f"获取指令状态汇总失败: {str(e)}")

	async def get_instruction_summary_by_date (
			self,
			start_date: date,
			end_date: date,
			user_id: Optional[int] = None,
			instruction_type: Optional[str] = None
	) -> List[Dict[str, Any]]:
		"""
		按日期汇总指令统计

		Args:
			start_date: 开始日期
			end_date: 结束日期
			user_id: 用户ID过滤
			instruction_type: 指令类型过滤

		Returns:
			按日期汇总的指令统计列表
		"""
		try:
			filters = [
				TradeInstruction.created_at >= start_date,
				TradeInstruction.created_at <= end_date + timedelta(days=1)
			]

			if user_id:
				filters.append(TradeInstruction.user_id == user_id)
			if instruction_type:
				filters.append(TradeInstruction.instruction_type == instruction_type)

			query = (
				select(
					func.date(TradeInstruction.created_at).label('instruction_date'),
					func.count(TradeInstruction.id).label('instruction_count'),
					func.sum(case((TradeInstruction.status == 'completed', 1), else_=0)).label('completed_count'),
					func.sum(case((TradeInstruction.status == 'failed', 1), else_=0)).label('failed_count'),
					func.sum(case((TradeInstruction.status == 'cancelled', 1), else_=0)).label('cancelled_count')
				)
				.where(and_(*filters))
				.group_by(func.date(TradeInstruction.created_at))
				.order_by(desc(func.date(TradeInstruction.created_at)))
			)

			result = await self.session.execute(query)
			rows = result.all()

			summary = []
			for row in rows:
				summary.append({
					'instruction_date': row.instruction_date,
					'instruction_count': row.instruction_count or 0,
					'completed_count': row.completed_count or 0,
					'failed_count': row.failed_count or 0,
					'cancelled_count': row.cancelled_count or 0,
					'success_rate': (row.completed_count or 0) / (row.instruction_count or 1) * 100
				})

			return summary

		except Exception as e:
			raise RepositoryError(f"获取按日期指令汇总失败: {str(e)}")

	async def get_instruction_summary_by_type (
			self,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			user_id: Optional[int] = None,
			top_n: int = 10
	) -> List[Dict[str, Any]]:
		"""
		按类型汇总指令统计

		Args:
			start_date: 开始时间
			end_date: 结束时间
			user_id: 用户ID过滤
			top_n: 返回前N个

		Returns:
			按类型汇总的指令统计列表
		"""
		try:
			filters = []

			if user_id:
				filters.append(TradeInstruction.user_id == user_id)
			if start_date:
				filters.append(TradeInstruction.created_at >= start_date)
			if end_date:
				filters.append(TradeInstruction.created_at <= end_date)

			where_clause = and_(*filters) if filters else True

			query = (
				select(
					TradeInstruction.instruction_type,
					func.count(TradeInstruction.id).label('instruction_count'),
					func.sum(case((TradeInstruction.status == 'completed', 1), else_=0)).label('completed_count'),
					func.avg(
						case(
							(TradeInstruction.executed_at.isnot(None),
							 func.extract('epoch', TradeInstruction.executed_at - TradeInstruction.created_at)),
							else_=None
						)
					).label('avg_execution_time_seconds')
				)
				.where(where_clause)
				.group_by(TradeInstruction.instruction_type)
				.order_by(desc(func.count(TradeInstruction.id)))
				.limit(top_n)
			)

			result = await self.session.execute(query)
			rows = result.all()

			summary = []
			for row in rows:
				summary.append({
					'instruction_type': row.instruction_type,
					'instruction_count': row.instruction_count or 0,
					'completed_count': row.completed_count or 0,
					'success_rate': (row.completed_count or 0) / (row.instruction_count or 1) * 100,
					'avg_execution_time_seconds': float(
						row.avg_execution_time_seconds) if row.avg_execution_time_seconds else 0
				})

			return summary

		except Exception as e:
			raise RepositoryError(f"获取按类型指令汇总失败: {str(e)}")

	# ==================== 高级查询方法 ====================

	async def get_instruction_with_details (
			self,
			instruction_id: str
	) -> Optional[Dict[str, Any]]:
		"""
		获取指令详情（包含关联信息）

		Args:
			instruction_id: 指令ID

		Returns:
			指令详情字典或None
		"""
		try:
			# 获取指令及关联的用户、策略信息
			query = (
				select(TradeInstruction, SysUser, Strategy)
				.join(SysUser, TradeInstruction.user_id == SysUser.id)
				.outerjoin(Strategy, TradeInstruction.strategy_id == Strategy.id)
				.where(TradeInstruction.instruction_id == instruction_id)
			)

			result = await self.session.execute(query)
			row = result.first()

			if not row:
				return None

			instruction, user, strategy = row

			# 解析执行结果
			execution_result = {}
			if instruction.execution_result:
				try:
					execution_result = instruction.execution_result
				except OrderException:
					execution_result = {}

			return {
				'instruction': instruction,
				'user': user,
				'strategy': strategy,
				'execution_result': execution_result
			}

		except Exception as e:
			raise RepositoryError(f"获取指令详情失败: {str(e)}")

	async def search_instructions (
			self,
			query_params: Dict[str, Any],
			pagination: PaginationParams
	) -> PaginationResult[TradeInstruction]:
		"""
		搜索指令

		Args:
			query_params: 查询参数
			pagination: 分页参数

		Returns:
			分页结果
		"""
		try:
			filters = []

			# 构建过滤条件
			if 'user_id' in query_params:
				filters.append(TradeInstruction.user_id == query_params['user_id'])
			if 'strategy_id' in query_params:
				filters.append(TradeInstruction.strategy_id == query_params['strategy_id'])
			if 'instruction_type' in query_params:
				filters.append(TradeInstruction.instruction_type == query_params['instruction_type'])
			if 'status' in query_params:
				filters.append(TradeInstruction.status == query_params['status'])

			# 时间范围
			if 'start_time' in query_params:
				filters.append(TradeInstruction.created_at >= query_params['start_time'])
			if 'end_time' in query_params:
				filters.append(TradeInstruction.created_at <= query_params['end_time'])

			if 'executed_start_time' in query_params:
				filters.append(TradeInstruction.executed_at >= query_params['executed_start_time'])
			if 'executed_end_time' in query_params:
				filters.append(TradeInstruction.executed_at <= query_params['executed_end_time'])

			# 构建过滤条件对象
			filter_conditions = []
			for field, value in query_params.items():
				if hasattr(TradeInstruction, field):
					filter_conditions.append(
						FilterCondition(field=field, operator=FilterOperator.EQ, value=value)
					)

			# 执行分页查询
			return await self.paginate(
				pagination=pagination,
				filters=filter_conditions,
				sorts=[SortCondition(field="created_at", descending=True)]
			)

		except Exception as e:
			raise RepositoryError(f"搜索指令失败: {str(e)}")

	# ==================== 批量操作方法 ====================

	async def batch_update_status (
			self,
			instruction_ids: List[str],
			status: str,
			update_time: Optional[datetime] = None,
			execution_result: Optional[Dict] = None,
			error_message: Optional[str] = None
	) -> int:
		"""
		批量更新指令状态

		Args:
			instruction_ids: 指令ID列表
			status: 新状态
			update_time: 更新时间
			execution_result: 执行结果
			error_message: 错误信息

		Returns:
			更新的记录数
		"""
		try:
			if not instruction_ids:
				return 0

			update_data: Dict[str, Any] = {'status': status}
			if update_time:
				update_data['updated_at'] = update_time
			else:
				update_data['updated_at'] = datetime.now()

			# 如果是执行完成状态，设置执行时间
			if status == 'completed' or status == 'failed':
				update_data['executed_at'] = update_data['updated_at']

			if execution_result is not None:
				update_data['execution_result'] = execution_result

			if error_message is not None:
				update_data['error_message'] = error_message

			query = (
				update(self.model)
				.where(self.model.instruction_id.in_(instruction_ids))
				.values(**update_data)
			)

			result = await self.session.execute(query)
			return result.rowcount or 0

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"批量更新指令状态失败: {str(e)}")

	async def batch_create_instructions (
			self,
			instructions_data: List[Dict[str, Any]]
	) -> List[TradeInstruction]:
		"""
		批量创建指令

		Args:
			instructions_data: 指令数据列表

		Returns:
			创建的指令列表
		"""
		try:
			if not instructions_data:
				return []

			# 准备批量插入数据
			now = datetime.now()
			for instruction_data in instructions_data:
				if 'created_at' not in instruction_data:
					instruction_data['created_at'] = now
				if 'updated_at' not in instruction_data:
					instruction_data['updated_at'] = now

			return await self.batch_create(instructions_data)

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"批量创建指令失败: {str(e)}")

	async def batch_cancel_pending_instructions (
			self,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None,
			instruction_type: Optional[str] = None
	) -> int:
		"""
		批量取消待处理指令

		Args:
			user_id: 用户ID过滤
			strategy_id: 策略ID过滤
			instruction_type: 指令类型过滤

		Returns:
			取消的指令数
		"""
		try:
			filters = [TradeInstruction.status == 'pending']

			if user_id:
				filters.append(TradeInstruction.user_id == user_id)
			if strategy_id:
				filters.append(TradeInstruction.strategy_id == strategy_id)
			if instruction_type:
				filters.append(TradeInstruction.instruction_type == instruction_type)

			update_data = {
				'status': 'cancelled',
				'updated_at': datetime.now(),
				'cancelled_at': datetime.now()
			}

			query = (
				update(self.model)
				.where(and_(*filters))
				.values(**update_data)
			)

			result = await self.session.execute(query)
			return result.rowcount or 0

		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"批量取消待处理指令失败: {str(e)}")

	# ==================== 辅助方法 ====================

	@staticmethod
	def _build_order_by (order_by: str) -> List:
		"""
		构建排序子句

		Args:
			order_by: 排序字符串，格式：field_[asc/desc]

		Returns:
			排序子句列表
		"""
		order_mappings = {
			'created_at_asc': [asc(TradeInstruction.created_at)],
			'created_at_desc': [desc(TradeInstruction.created_at)],
			'updated_at_asc': [asc(TradeInstruction.updated_at)],
			'updated_at_desc': [desc(TradeInstruction.updated_at)],
			'status_asc': [asc(TradeInstruction.status)],
			'status_desc': [desc(TradeInstruction.status)],
			'instruction_type_asc': [asc(TradeInstruction.instruction_type)],
			'instruction_type_desc': [desc(TradeInstruction.instruction_type)],
		}

		return order_mappings.get(order_by, [desc(TradeInstruction.created_at)])

	async def get_instruction_summary (self) -> Dict[str, Any]:
		"""
		获取指令数据摘要

		Returns:
			指令数据摘要字典
		"""
		try:
			# 总指令数
			total_instructions = await self.count()

			# 今日指令数
			today = datetime.now().date()
			today_query = select(func.count()).select_from(TradeInstruction).where(
				and_(
					TradeInstruction.created_at >= today,
					TradeInstruction.created_at < today + timedelta(days=1)
				)
			)
			today_result = await self.session.execute(today_query)
			today_instructions = today_result.scalar() or 0

			# 待处理指令数
			pending_query = select(func.count()).select_from(TradeInstruction).where(
				TradeInstruction.status == 'pending'
			)
			pending_result = await self.session.execute(pending_query)
			pending_instructions = pending_result.scalar() or 0

			# 执行中指令数
			executing_query = select(func.count()).select_from(TradeInstruction).where(
				TradeInstruction.status == 'executing'
			)
			executing_result = await self.session.execute(executing_query)
			executing_instructions = executing_result.scalar() or 0

			# 涉及用户数
			user_count = await self.session.execute(
				select(func.count(func.distinct(TradeInstruction.user_id)))
			)
			user_count_value = user_count.scalar() or 0

			# 涉及策略数
			strategy_count = await self.session.execute(
				select(func.count(func.distinct(TradeInstruction.strategy_id)))
				.where(TradeInstruction.strategy_id.isnot(None))
			)
			strategy_count_value = strategy_count.scalar() or 0

			# 按类型统计
			type_stats = await self.session.execute(
				select(
					TradeInstruction.instruction_type,
					func.count(TradeInstruction.id).label('count')
				)
				.group_by(TradeInstruction.instruction_type)
			)

			type_dict = {}
			for row in type_stats.all():
				type_dict[row.instruction_type] = row.count

			# 按状态统计
			status_stats = await self.session.execute(
				select(
					TradeInstruction.status,
					func.count(TradeInstruction.id).label('count')
				)
				.group_by(TradeInstruction.status)
			)

			status_dict = {}
			for row in status_stats.all():
				status_dict[row.status] = row.count

			# 日期范围
			date_range = await self.session.execute(
				select(
					func.min(TradeInstruction.created_at),
					func.max(TradeInstruction.created_at)
				)
			)
			min_time, max_time = date_range.first()

			# 平均执行时间
			avg_execution_time = await self.session.execute(
				select(
					func.avg(
						func.extract('epoch', TradeInstruction.executed_at - TradeInstruction.created_at)
					).label('avg_seconds')
				)
				.where(
					and_(
						TradeInstruction.status.in_(['completed', 'failed']),
						TradeInstruction.executed_at.isnot(None),
						TradeInstruction.created_at.isnot(None)
					)
				)
			)
			avg_seconds = avg_execution_time.scalar()

			return {
				'total_instructions': total_instructions,
				'today_instructions': today_instructions,
				'pending_instructions': pending_instructions,
				'executing_instructions': executing_instructions,
				'user_count': user_count_value,
				'strategy_count': strategy_count_value,
				'type_stats': type_dict,
				'status_stats': status_dict,
				'date_range': {
					'min_time': min_time,
					'max_time': max_time
				},
				'avg_execution_time_seconds': float(avg_seconds) if avg_seconds else 0
			}

		except Exception as e:
			raise RepositoryError(f"获取指令摘要失败: {str(e)}")