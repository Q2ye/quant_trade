# -*- coding: utf-8 -*-
"""
策略数据仓库
提供策略数据的统一访问接口
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, or_, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BusinessException
from shared.database.models.business_models import Strategy
from shared.database.repositories.strategy.management.strategy_parameter_repo import StrategyParameterRepository
from shared.database.repositories.base import BaseRepository


class StrategyRepository(BaseRepository[Strategy]):
	"""策略数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		"""初始化Repository"""
		super().__init__(session, Strategy)

	# ==================== 基础CRUD操作 ====================
	# 直接使用继承自 BaseRepository 的方法（get, create, update, delete, get_by, get_many, count, batch_create, batch_upsert 等）

	async def get_by_id (self, strategy_id: str) -> Optional[Strategy]:
		"""根据策略ID获取策略（主键为字符串类型）"""
		return await self.get_by(id=strategy_id)

	# ==================== 业务查询方法 ====================

	async def get_by_user (self, user_id: str) -> List[Strategy]:
		"""根据用户ID获取策略"""
		return await self.get_many(
			user_id=user_id
		)

	async def get_by_name (self, name: str, user_id: Optional[str] = None) -> Optional[Strategy]:
		"""根据策略名称获取策略"""
		filters = {'name': name}

		if user_id:
			filters['user_id'] = user_id

		result = await self.get_many(limit=1, **filters)
		return result[0] if result else None

	async def get_by_status (self, status: str) -> List[Strategy]:
		"""根据状态获取策略"""
		return await self.get_many(
			status=status
		)

	async def get_by_type (self, strategy_type: str) -> List[Strategy]:
		"""根据类型获取策略"""
		return await self.get_many(
			strategy_type=strategy_type
		)

	async def get_active_strategies (self) -> List[Strategy]:
		"""获取活跃策略（状态为running）"""
		return await self.get_by_status('running')

	async def get_user_active_strategies (self, user_id: str) -> List[Strategy]:
		"""获取用户的活跃策略"""
		return await self.get_many(
			user_id=user_id,
			status='running'
		)

	async def search_strategies (
			self,
			keyword: Optional[str] = None,
			user_id: Optional[str] = None,
			strategy_type: Optional[str] = None,
			status: Optional[str] = None,
			limit: int = 100
	) -> List[Strategy]:
		"""搜索策略"""
		query = select(Strategy)

		if keyword:
			query = query.where(
				or_(
					Strategy.name.like(f"%{keyword}%"),
					Strategy.description.like(f"%{keyword}%"),
					Strategy.id.like(f"%{keyword}%")
				)
			)

		if user_id:
			query = query.where(Strategy.user_id == user_id)

		if strategy_type:
			query = query.where(Strategy.strategy_type == strategy_type)

		if status:
			query = query.where(Strategy.status == status)

		query = query.order_by(Strategy.created_at.desc()).limit(limit)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_strategy_statistics (
			self,
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""获取策略统计信息"""
		# 基础查询
		query = select(
			func.count(Strategy.id).label('total_count'),
			func.sum(case((Strategy.status == 'running', 1), else_=0)).label('running_count'),
			func.sum(case((Strategy.status == 'stopped', 1), else_=0)).label('stopped_count'),
			func.sum(case((Strategy.status == 'error', 1), else_=0)).label('error_count'),
			func.count(func.distinct(Strategy.strategy_type)).label('type_count')
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
			Strategy.strategy_type,
			func.count(Strategy.id).label('count'),
			func.sum(case((Strategy.status == 'running', 1), else_=0)).label('running')
		)

		if user_id:
			type_query = type_query.where(Strategy.user_id == user_id)

		type_query = type_query.group_by(
			Strategy.strategy_type
		).order_by(
			func.count(Strategy.id).desc()
		)

		type_result = await self.session.execute(type_query)
		type_stats = [
			{
				'type': row.strategy_type,
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
			user_id: Optional[str] = None,
			days: int = 30
	) -> List[Dict[str, Any]]:
		"""获取策略创建趋势"""
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=days - 1)

		query = select(
			func.date(Strategy.created_at).label('date'),
			func.count(Strategy.id).label('count'),
			Strategy.strategy_type
		).where(
			Strategy.created_at >= start_date
		).group_by(
			func.date(Strategy.created_at),
			Strategy.strategy_type
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

			date_dict[date_str]['by_type'][row.strategy_type] = row.count
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
		"""
		更新策略参数

		Args:
			strategy_id: 策略ID
			parameters: 参数字典

		Returns:
			是否成功更新
		"""
		try:
				strategy = await self.get(strategy_id)
				if not strategy:
					return False

				try:
					# 使用策略参数仓库更新参数
					parameter_repo = StrategyParameterRepository(self.session)

					# 批量更新参数
					for param_name, param_value in parameters.items():
						# 检查 upsert_parameter 方法是否存在
						if hasattr(parameter_repo, 'upsert_parameter'):
							await parameter_repo.upsert_parameter(
								strategy_id=strategy_id,
								param_name=param_name,
								param_value=param_value
							)
						else:
							# 如果方法不存在，使用 create 或 update 方法
							# 首先尝试查找现有参数
							existing_param = await parameter_repo.get_by(
								strategy_id=strategy_id,
								param_name=param_name
							)
							
							if existing_param:
								# 更新现有参数
								await parameter_repo.update(
									existing_param.id,
									{'param_value': str(param_value)}
								)
							else:
								# 创建新参数
								await parameter_repo.create({
									'strategy_id': strategy_id,
									'param_name': param_name,
									'param_value': str(param_value)
								})

					return True
				except ImportError:
					# 如果策略参数模型未定义，使用策略的parameters字段
					if hasattr(strategy, 'parameters'):
						# 合并现有参数
						if hasattr(strategy.parameters, 'update'):
							strategy.parameters.update(parameters)
						else:
							strategy.parameters = parameters

						await self.session.commit()
						return True
					else:
						# 如果连parameters字段都没有，记录日志并返回False
						return False

		except BusinessException:
			await self.session.rollback()
			# 记录错误日志
			return False

	async def get_strategy_parameters (
			self,
			strategy_id: str
	) -> Optional[Dict[str, Any]]:
		"""获取策略参数"""
		strategy = await self.get(strategy_id)
		if not strategy:
			return None

		return {}

	async def get_strategies_by_parameter (
			self,
			param_name: str,
			param_value: Any = None,
			operator: str = "="
	) -> List[Strategy]:
		"""
		根据参数查找策略

		Args:
			param_name: 参数名称
			param_value: 参数值（可选，不提供时返回具有该参数的所有策略）
			operator: 比较操作符（=, >, <, >=, <=, like, in等）

		Returns:
			符合条件的策略列表
		"""
		try:
			# 检查策略参数表是否存在
			from shared.database.models.business_models import StrategyParameter
			from shared.database.models.business_models import Strategy

			# 构建关联查询
			query = select(Strategy).join(
				StrategyParameter,
				StrategyParameter.strategy_id == Strategy.id
			).where(StrategyParameter.param_name == param_name)

			# 如果提供了参数值，应用过滤条件
			if param_value is not None:
				if operator == "=":
					query = query.where(StrategyParameter.param_value == str(param_value))
				elif operator == ">":
					query = query.where(StrategyParameter.param_value > str(param_value))
				elif operator == "<":
					query = query.where(StrategyParameter.param_value < str(param_value))
				elif operator == ">=":
					query = query.where(StrategyParameter.param_value >= str(param_value))
				elif operator == "<=":
					query = query.where(StrategyParameter.param_value <= str(param_value))
				elif operator == "like":
					query = query.where(StrategyParameter.param_value.like(f"%{param_value}%"))
				elif operator == "in":
					if isinstance(param_value, (list, tuple)):
						query = query.where(StrategyParameter.param_value.in_([str(v) for v in param_value]))
					else:
						query = query.where(StrategyParameter.param_value == str(param_value))

			# 执行查询
			result = await self.session.execute(query)
			strategies = result.scalars().all()

			return strategies

		except ImportError:
			# 如果策略参数模型未定义，使用策略的parameters字段进行过滤
			all_strategies = await self.get_all()
			matching_strategies = []

			for strategy in all_strategies:
				if hasattr(strategy, 'parameters') and strategy.parameters:
					if param_name in strategy.parameters:
						if param_value is None:
							# 只要参数存在就匹配
							matching_strategies.append(strategy)
						else:
							# 比较参数值
							strategy_param_value = strategy.parameters[param_name]

							if operator == "=" and strategy_param_value == param_value:
								matching_strategies.append(strategy)
							elif operator == ">" and strategy_param_value > param_value:
								matching_strategies.append(strategy)
							elif operator == "<" and strategy_param_value < param_value:
								matching_strategies.append(strategy)
							elif operator == ">=" and strategy_param_value >= param_value:
								matching_strategies.append(strategy)
							elif operator == "<=" and strategy_param_value <= param_value:
								matching_strategies.append(strategy)
							elif operator == "like" and str(param_value) in str(strategy_param_value):
								matching_strategies.append(strategy)
							elif operator == "in" and strategy_param_value in param_value:
								matching_strategies.append(strategy)

			return matching_strategies

		except BusinessException :
			# 记录错误日志
			return []

	async def get_top_strategies_by_user (
			self,
			top_n: int = 10
	) -> List[Dict[str, Any]]:
		"""获取策略数量最多的用户"""
		query = select(
			Strategy.user_id,
			func.count(Strategy.id).label('strategy_count'),
			func.sum(case((Strategy.status == 'running', 1), else_=0)).label('running_count')
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
		return await super().batch_create(data_list)

	async def batch_upsert (
			self,
			match_fields: List[str],
			data_list: List[Dict[str, Any]],
			update_fields: List[str] = None
	) -> List[Strategy]:
		"""批量插入或更新策略记录"""
		return await super().batch_upsert(match_fields, data_list, update_fields)

	async def deactivate_user_strategies (self, user_id: str) -> int:
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
				'type': s.strategy_type,
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