# -*- coding: utf-8 -*-
"""
策略数据仓库
提供策略数据的统一访问接口
位置：shared/database/repositories/strategy_repo.py
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, distinct, case

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.business_models import Strategy


class StrategyRepository(BaseRepository[Strategy]):
	"""策略数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		"""初始化Repository"""
		super().__init__(session, Strategy)

	# ==================== 基础CRUD操作 ====================
	# 直接使用继承自 BaseRepository 的方法（get, create, update, delete, get_by, get_many, count, batch_create, batch_upsert 等）

	async def get_by_id(self, strategy_id: str) -> Optional[Strategy]:
		"""根据策略ID获取策略（主键为字符串类型）"""
		return await self.get_by(id=strategy_id)

	# ==================== 业务查询方法 ====================

	async def get_by_user (self, user_id: int) -> List[Strategy]:
		"""根据用户ID获取策略"""
		return await self.get_many(
			Strategy.user_id == user_id,
			order_by=Strategy.created_at.desc()
		)

	async def get_by_name (self, name: str, user_id: Optional[int] = None) -> Optional[Strategy]:
		"""根据策略名称获取策略"""
		filters = [Strategy.name == name]

		if user_id:
			filters.append(Strategy.user_id == user_id)

		return await self.get_one(*filters)

	async def get_by_status (self, status: str) -> List[Strategy]:
		"""根据状态获取策略"""
		return await self.get_many(
			Strategy.status == status,
			order_by=Strategy.created_at.desc()
		)

	async def get_by_type (self, strategy_type: str) -> List[Strategy]:
		"""根据类型获取策略"""
		return await self.get_many(
			Strategy.type == strategy_type,
			order_by=Strategy.created_at.desc()
		)

	async def get_active_strategies (self) -> List[Strategy]:
		"""获取活跃策略（状态为running）"""
		return await self.get_by_status('running')

	async def get_user_active_strategies (self, user_id: int) -> List[Strategy]:
		"""获取用户的活跃策略"""
		return await self.get_many(
			and_(
				Strategy.user_id == user_id,
				Strategy.status == 'running'
			),
			order_by=Strategy.created_at.desc()
		)

	async def search_strategies (
			self,
			keyword: Optional[str] = None,
			user_id: Optional[int] = None,
			strategy_type: Optional[str] = None,
			status: Optional[str] = None,
			limit: int = 100
	) -> List[Strategy]:
		"""搜索策略"""
		filters = []

		if keyword:
			filters.append(
				or_(
					Strategy.name.like(f"%{keyword}%"),
					Strategy.description.like(f"%{keyword}%"),
					Strategy.id.like(f"%{keyword}%")
				)
			)

		if user_id:
			filters.append(Strategy.user_id == user_id)

		if strategy_type:
			filters.append(Strategy.type == strategy_type)

		if status:
			filters.append(Strategy.status == status)

		return await self.get_many(
			*filters,
			limit=limit,
			order_by=Strategy.created_at.desc()
		)

	async def get_strategy_statistics (
			self,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""获取策略统计信息"""
		# 基础查询
		query = select(
			func.count(Strategy.id).label('total_count'),
			func.sum(case([(Strategy.status == 'running', 1)], else_=0)).label('running_count'),
			func.sum(case([(Strategy.status == 'stopped', 1)], else_=0)).label('stopped_count'),
			func.sum(case([(Strategy.status == 'error', 1)], else_=0)).label('error_count'),
			func.count(func.distinct(Strategy.type)).label('type_count')
		)

		if user_id:
			query = query.where(Strategy.user_id == user_id)

		result = await self.session.execute(query)
		row = result.first()

		if not row:
			return {}

		stats = {
			'total_count': row.total_count or 0,
			'running_count': row.running_count or 0,
			'stopped_count': row.stopped_count or 0,
			'error_count': row.error_count or 0,
			'type_count': row.type_count or 0
		}

		# 按类型统计
		type_query = select(
			Strategy.type,
			func.count(Strategy.id).label('count'),
			func.sum(case([(Strategy.status == 'running', 1)], else_=0)).label('running')
		)

		if user_id:
			type_query = type_query.where(Strategy.user_id == user_id)

		type_query = type_query.group_by(
			Strategy.type
		).order_by(
			func.count(Strategy.id).desc()
		)

		type_result = await self.session.execute(type_query)
		type_stats = [
			{
				'type': row.type,
				'count': row.count,
				'running': row.running or 0
			}
			for row in type_result.all()
		]

		stats['type_stats'] = type_stats

		# 按状态统计
		status_query = select(
			Strategy.status,
			func.count(Strategy.id).label('count')
		)

		if user_id:
			status_query = status_query.where(Strategy.user_id == user_id)

		status_query = status_query.group_by(
			Strategy.status
		).order_by(
			func.count(Strategy.id).desc()
		)

		status_result = await self.session.execute(status_query)
		status_stats = {row.status: row.count for row in status_result.all()}

		stats['status_stats'] = status_stats

		# 最近创建的策略
		recent_query = select(
			func.count(Strategy.id).label('count')
		).where(
			Strategy.created_at >= datetime.now() - timedelta(days=7)
		)

		if user_id:
			recent_query = recent_query.where(Strategy.user_id == user_id)

		recent_result = await self.session.execute(recent_query)
		recent_count = recent_result.scalar() or 0

		stats['recent_7_days_count'] = recent_count

		return stats

	async def get_strategy_trend (
			self,
			user_id: Optional[int] = None,
			days: int = 30
	) -> List[Dict[str, Any]]:
		"""获取策略创建趋势"""
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=days - 1)

		query = select(
			func.date(Strategy.created_at).label('date'),
			func.count(Strategy.id).label('count'),
			Strategy.type
		).where(
			Strategy.created_at >= start_date
		).group_by(
			func.date(Strategy.created_at),
			Strategy.type
		).order_by(
			func.date(Strategy.created_at).asc()
		)

		if user_id:
			query = query.where(Strategy.user_id == user_id)

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
					'by_type': {}
				}

			date_dict[date_str]['by_type'][row.type] = row.count
			date_dict[date_str]['total'] += row.count

		# 转换为列表
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
					'by_type': {}
				})
			current_date += timedelta(days=1)

		return trend_list

	async def update_strategy_status (
			self,
			strategy_id: str,
			status: str
	) -> bool:
		"""更新策略状态"""
		strategy = await self.get(strategy_id)
		if not strategy:
			return False

		result = await self.update(strategy_id, {'status': status})
		return result is not None

	async def start_strategy (self, strategy_id: str) -> bool:
		"""启动策略"""
		return await self.update_strategy_status(strategy_id, 'running')

	async def stop_strategy (self, strategy_id: str) -> bool:
		"""停止策略"""
		return await self.update_strategy_status(strategy_id, 'stopped')

	async def update_strategy_parameters (
			self,
			strategy_id: str,
			parameters: Dict[str, Any]
	) -> bool:
		"""更新策略参数"""
		strategy = await self.get(strategy_id)
		if not strategy:
			return False

		# 合并现有参数
		existing_params = strategy.parameters or {}
		updated_params = {**existing_params, **parameters}

		result = await self.update(strategy_id, {'parameters': updated_params})
		return result is not None

	async def get_strategy_parameters (
			self,
			strategy_id: str
	) -> Optional[Dict[str, Any]]:
		"""获取策略参数"""
		strategy = await self.get(strategy_id)
		if not strategy:
			return None

		return strategy.parameters

	async def get_strategies_by_parameter (
			self,
			param_name: str,
			param_value: Any = None
	) -> List[Strategy]:
		"""根据参数查找策略"""
		# 由于参数是JSON字段，这里使用简单的LIKE查询
		# 实际生产环境可能需要使用数据库特定的JSON函数

		query = select(Strategy).where(
			Strategy.parameters.like(f'%"{param_name}"%')
		)

		if param_value is not None:
			# 更精确的匹配需要数据库特定的JSON函数
			# 这里只是简单示例
			pass

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_top_strategies_by_user (
			self,
			top_n: int = 10
	) -> List[Dict[str, Any]]:
		"""获取策略数量最多的用户"""
		query = select(
			Strategy.user_id,
			func.count(Strategy.id).label('strategy_count'),
			func.sum(case([(Strategy.status == 'running', 1)], else_=0)).label('running_count')
		).group_by(
			Strategy.user_id
		).order_by(
			func.count(Strategy.id).desc()
		).limit(top_n)

		result = await self.session.execute(query)
		rows = result.all()

		return [
			{
				'user_id': row[0],
				'strategy_count': row[1],
				'running_count': row[2] or 0
			}
			for row in rows
		]

	async def get_strategy_performance_summary (
			self,
			strategy_id: str
	) -> Dict[str, Any]:
		"""获取策略绩效摘要（需要关联绩效数据）"""
		# 这里需要关联StrategyDailyPerformance表
		# 实际实现需要根据数据库设计调整

		strategy = await self.get(strategy_id)
		if not strategy:
			return {'error': '策略不存在'}

		# 这里只是示例，实际需要查询绩效数据
		return {
			'strategy_id': strategy_id,
			'strategy_name': strategy.name,
			'total_return': 0,  # 实际需要计算
			'sharpe_ratio': 0,  # 实际需要计算
			'max_drawdown': 0,  # 实际需要计算
			'win_rate': 0,  # 实际需要计算
			'has_performance_data': False
		}

	async def batch_create (
			self,
			data_list: List[Dict[str, Any]]
	) -> List[Strategy]:
		"""批量创建策略记录"""
		return await self.batch_create(data_list)

	async def batch_upsert (
			self,
			data_list: List[Dict[str, Any]],
			match_fields: List[str] = ['id']
	) -> List[Strategy]:
		"""批量插入或更新策略记录"""
		return await self.batch_upsert(data_list, match_fields)

	async def deactivate_user_strategies (self, user_id: int) -> int:
		"""停用用户的所有策略"""
		strategies = await self.get_by_user(user_id)

		deactivated = 0
		for strategy in strategies:
			if strategy.status == 'running':
				success = await self.stop_strategy(strategy.id)
				if success:
					deactivated += 1

		return deactivated

	async def delete_old_strategies (
			self,
			days: int = 365,
			status: str = 'stopped'
	) -> int:
		"""删除旧策略记录"""
		cutoff_time = datetime.now() - timedelta(days=days)

		# 获取要删除的记录
		query = select(Strategy.id).where(
			and_(
				Strategy.status == status,
				Strategy.updated_at < cutoff_time
			)
		)

		result = await self.session.execute(query)
		old_strategy_ids = [row[0] for row in result.all()]

		# 批量删除
		deleted_count = 0
		for strategy_id in old_strategy_ids:
			success = await self.delete(strategy_id, soft=False)
			if success:
				deleted_count += 1

		return deleted_count

	async def get_strategy_summary (self) -> Dict[str, Any]:
		"""获取策略数据摘要"""
		# 基础统计
		stats = await self.get_strategy_statistics()

		# 用户统计
		user_stats = await self.get_top_strategies_by_user(10)

		# 最近活跃的策略
		recent_active = await self.session.execute(
			select(Strategy).where(
				Strategy.status == 'running'
			).order_by(
				Strategy.updated_at.desc()
			).limit(10)
		)

		recent_strategies = [
			{
				'id': s.id,
				'name': s.name,
				'user_id': s.user_id,
				'type': s.type,
				'updated_at': s.updated_at
			}
			for s in recent_active.scalars().all()
		]

		# 参数统计
		# 这里可以统计常用参数等，但实现较复杂

		return {
			'statistics': stats,
			'top_users': user_stats,
			'recent_active_strategies': recent_strategies,
			'timestamp': datetime.now().isoformat()
		}