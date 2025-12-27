# -*- coding: utf-8 -*-
"""
策略参数数据仓库
提供策略参数数据的统一访问接口
位置：shared/database/repositories/parameter_repo.py
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc

from .base import BaseRepository
from quant_server.shared.database.models.business_models import Strategy


class ParameterRepository:
	"""策略参数数据Repository - 纯数据访问

	注意：在现有模型中，策略参数存储在Strategy表的parameters字段（JSON类型）
	如果需要独立的参数表，需要先创建Parameter模型
	"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.strategy_repo = BaseRepository(session, Strategy)

	# ==================== 策略参数操作 ====================

	async def get_strategy_parameters (self, strategy_id: str) -> Optional[Dict[str, Any]]:
		"""获取策略参数"""
		strategy = await self.strategy_repo.get(strategy_id)
		if strategy and strategy.parameters:
			return strategy.parameters
		return None

	async def update_strategy_parameters (
			self,
			strategy_id: str,
			parameters: Dict[str, Any]
	) -> Optional[Strategy]:
		"""更新策略参数"""
		return await self.strategy_repo.update(strategy_id, {'parameters': parameters})

	async def get_parameter_value (
			self,
			strategy_id: str,
			param_name: str,
			default: Any = None
	) -> Any:
		"""获取特定参数值"""
		params = await self.get_strategy_parameters(strategy_id)
		if params and param_name in params:
			return params[param_name]
		return default

	async def set_parameter_value (
			self,
			strategy_id: str,
			param_name: str,
			param_value: Any
	) -> bool:
		"""设置特定参数值"""
		params = await self.get_strategy_parameters(strategy_id) or {}
		params[param_name] = param_value

		result = await self.update_strategy_parameters(strategy_id, params)
		return result is not None

	async def delete_parameter (
			self,
			strategy_id: str,
			param_name: str
	) -> bool:
		"""删除特定参数"""
		params = await self.get_strategy_parameters(strategy_id)
		if params and param_name in params:
			del params[param_name]
			result = await self.update_strategy_parameters(strategy_id, params)
			return result is not None
		return False

	async def get_strategies_by_parameter (
			self,
			param_name: str,
			param_value: Any = None
	) -> List[Strategy]:
		"""根据参数查找策略"""
		# 由于参数是JSON字段，需要使用JSON查询
		# 这里使用简单的LIKE查询，实际生产环境可能需要使用数据库特定的JSON函数

		query = select(Strategy).where(
			Strategy.parameters.like(f'%"{param_name}"%')
		)

		if param_value is not None:
			# 更精确的匹配需要数据库特定的JSON函数
			# 这里只是简单示例
			pass

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_all_parameter_names (self) -> List[str]:
		"""获取所有参数名（去重）"""
		# 注意：这种方法在大量数据时可能效率不高
		# 实际生产环境可能需要使用更高效的方法

		query = select(Strategy.parameters).where(
			Strategy.parameters.isnot(None)
		)

		result = await self.session.execute(query)
		rows = result.scalars().all()

		param_names = set()
		for params in rows:
			if params:
				param_names.update(params.keys())

		return list(param_names)

	async def get_parameter_statistics (
			self,
			param_name: str
	) -> Dict[str, Any]:
		"""获取参数统计信息"""
		# 获取使用该参数的策略数量
		count_query = select(func.count()).where(
			Strategy.parameters.like(f'%"{param_name}"%')
		)

		count_result = await self.session.execute(count_query)
		strategy_count = count_result.scalar() or 0

		# 获取参数值的分布
		# 由于参数是JSON字段，获取分布信息比较复杂
		# 这里只返回简单的统计

		return {
			'param_name': param_name,
			'strategy_count': strategy_count,
			'has_distribution': False  # 表示未计算值分布
		}

	async def batch_update_parameters (
			self,
			updates: List[Dict[str, Any]]
	) -> Dict[str, int]:
		"""批量更新策略参数

		Args:
			updates: 更新列表，每个元素包含 strategy_id 和 parameters

		Returns:
			Dict with success_count and failed_count
		"""
		success_count = 0
		failed_count = 0

		for update in updates:
			strategy_id = update.get('strategy_id')
			parameters = update.get('parameters')

			if not strategy_id or not parameters:
				failed_count += 1
				continue

			try:
				result = await self.update_strategy_parameters(strategy_id, parameters)
				if result:
					success_count += 1
				else:
					failed_count += 1
			except Exception:
				failed_count += 1

		return {
			'success_count': success_count,
			'failed_count': failed_count,
			'total': len(updates)
		}

	async def export_parameters (
			self,
			strategy_ids: Optional[List[str]] = None
	) -> List[Dict[str, Any]]:
		"""导出策略参数"""
		query = select(Strategy.id, Strategy.name, Strategy.parameters)

		if strategy_ids:
			query = query.where(Strategy.id.in_(strategy_ids))

		result = await self.session.execute(query)
		rows = result.all()

		return [
			{
				'strategy_id': row[0],
				'strategy_name': row[1],
				'parameters': row[2] or {}
			}
			for row in rows
		]

	async def import_parameters (
			self,
			import_data: List[Dict[str, Any]]
	) -> Dict[str, int]:
		"""导入策略参数"""
		success_count = 0
		failed_count = 0

		for item in import_data:
			strategy_id = item.get('strategy_id')
			parameters = item.get('parameters')

			if not strategy_id or not parameters:
				failed_count += 1
				continue

			try:
				# 检查策略是否存在
				strategy = await self.strategy_repo.get(strategy_id)
				if not strategy:
					failed_count += 1
					continue

				# 更新参数
				result = await self.update_strategy_parameters(strategy_id, parameters)
				if result:
					success_count += 1
				else:
					failed_count += 1
			except Exception:
				failed_count += 1

		return {
			'success_count': success_count,
			'failed_count': failed_count,
			'total': len(import_data)
		}