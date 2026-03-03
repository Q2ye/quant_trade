# quant_server/shared/database/repositories/analysis/monitor/monitor_threshold_repository.py
"""
监控阈值配置Repository
负责MonitorThreshold表的数据访问操作

继承自BaseRepository，提供监控阈值配置的管理功能
包括阈值查询、有效性验证、批量更新等
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func

from quant_server.shared.database.models.business_models import MonitorThreshold
from quant_server.shared.database.repositories.base.repository_base import BaseRepository, RepositoryError


class MonitorThresholdRepository(BaseRepository[MonitorThreshold]):
	"""
	监控阈值配置Repository
	继承自BaseRepository，提供监控阈值配置的数据访问方法
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化监控阈值Repository

		Args:
			session: 数据库会话
		"""
		super().__init__(session, MonitorThreshold)

	async def create_threshold (
			self,
			metric_type: str,
			metric_name: str,
			warning_threshold: Optional[float] = None,
			critical_threshold: Optional[float] = None,
			min_value: Optional[float] = None,
			max_value: Optional[float] = None,
			unit: Optional[str] = None,
			description: Optional[str] = None
	) -> MonitorThreshold:
		"""
		创建监控阈值配置

		Args:
			metric_type: 指标类型
			metric_name: 指标名称
			warning_threshold: 警告阈值（可选）
			critical_threshold: 严重阈值（可选）
			min_value: 最小值（可选）
			max_value: 最大值（可选）
			unit: 单位（可选）
			description: 描述（可选）

		Returns:
			MonitorThreshold: 创建的阈值配置对象
		"""
		try:
			threshold_data = {
				'metric_type': metric_type,
				'metric_name': metric_name,
				'warning_threshold': warning_threshold,
				'critical_threshold': critical_threshold,
				'min_value': min_value,
				'max_value': max_value,
				'unit': unit,
				'description': description,
				'is_active': True
			}

			return await self.create(threshold_data)
		except Exception as e:
			raise RepositoryError(f"创建监控阈值失败: {str(e)}")

	async def get_active_thresholds (
			self,
			metric_type: Optional[str] = None,
			metric_name: Optional[str] = None
	) -> List[MonitorThreshold]:
		"""
		获取活跃的阈值配置

		Args:
			metric_type: 指标类型过滤（可选）
			metric_name: 指标名称过滤（可选）

		Returns:
			List[MonitorThreshold]: 活跃阈值配置列表
		"""
		try:
			filters = {'is_active': True}

			if metric_type:
				filters['metric_type'] = metric_type
			if metric_name:
				filters['metric_name'] = metric_name

			return await self.get_all(**filters)
		except Exception as e:
			raise RepositoryError(f"获取活跃阈值失败: {str(e)}")

	async def get_threshold_by_metric (
			self,
			metric_type: str,
			metric_name: str
	) -> Optional[MonitorThreshold]:
		"""
		根据指标类型和名称获取阈值配置

		Args:
			metric_type: 指标类型
			metric_name: 指标名称

		Returns:
			Optional[MonitorThreshold]: 阈值配置对象或None
		"""
		try:
			return await self.get_by(
				metric_type=metric_type,
				metric_name=metric_name,
				is_active=True
			)
		except Exception as e:
			raise RepositoryError(f"获取指标阈值失败: {str(e)}")

	async def evaluate_metric_value (
			self,
			metric_type: str,
			metric_name: str,
			value: float
	) -> Dict[str, Any]:
		"""
		评估指标值是否超过阈值

		Args:
			metric_type: 指标类型
			metric_name: 指标名称
			value: 指标值

		Returns:
			Dict[str, Any]: 评估结果
		"""
		try:
			threshold = await self.get_threshold_by_metric(metric_type, metric_name)

			if not threshold:
				return {
					'status': 'unknown',
					'message': f'No threshold found for {metric_type}.{metric_name}',
					'value': value
				}

			# 检查是否超出范围
			if threshold.min_value is not None and value < threshold.min_value:
				return {
					'status': 'critical',
					'level': 'critical',
					'message': f'Value {value} below minimum {threshold.min_value}',
					'value': value,
					'threshold': threshold.min_value,
					'threshold_type': 'min'
				}

			if threshold.max_value is not None and value > threshold.max_value:
				return {
					'status': 'critical',
					'level': 'critical',
					'message': f'Value {value} above maximum {threshold.max_value}',
					'value': value,
					'threshold': threshold.max_value,
					'threshold_type': 'max'
				}

			# 检查是否超过严重阈值
			if threshold.critical_threshold is not None:
				if threshold.critical_threshold >= 0 and value >= threshold.critical_threshold:
					return {
						'status': 'critical',
						'level': 'critical',
						'message': f'Value {value} reached critical threshold {threshold.critical_threshold}',
						'value': value,
						'threshold': threshold.critical_threshold,
						'threshold_type': 'critical'
					}
				elif threshold.critical_threshold < 0 and value <= threshold.critical_threshold:
					return {
						'status': 'critical',
						'level': 'critical',
						'message': f'Value {value} reached critical threshold {threshold.critical_threshold}',
						'value': value,
						'threshold': threshold.critical_threshold,
						'threshold_type': 'critical'
					}

			# 检查是否超过警告阈值
			if threshold.warning_threshold is not None:
				if threshold.warning_threshold >= 0 and value >= threshold.warning_threshold:
					return {
						'status': 'warning',
						'level': 'warning',
						'message': f'Value {value} reached warning threshold {threshold.warning_threshold}',
						'value': value,
						'threshold': threshold.warning_threshold,
						'threshold_type': 'warning'
					}
				elif threshold.warning_threshold < 0 and value <= threshold.warning_threshold:
					return {
						'status': 'warning',
						'level': 'warning',
						'message': f'Value {value} reached warning threshold {threshold.warning_threshold}',
						'value': value,
						'threshold': threshold.warning_threshold,
						'threshold_type': 'warning'
					}

			# 正常状态
			return {
				'status': 'normal',
				'level': 'normal',
				'message': f'Value {value} within acceptable range',
				'value': value
			}
		except Exception as e:
			raise RepositoryError(f"评估指标值失败: {str(e)}")

	async def batch_evaluate_metrics (
			self,
			metrics: List[Dict[str, Any]]
	) -> List[Dict[str, Any]]:
		"""
		批量评估多个指标值

		Args:
			metrics: 指标列表，每个元素包含metric_type, metric_name, value

		Returns:
			List[Dict[str, Any]]: 批量评估结果
		"""
		try:
			results = []

			for metric in metrics:
				result = await self.evaluate_metric_value(
					metric['metric_type'],
					metric['metric_name'],
					metric['value']
				)
				results.append(result)

			return results
		except Exception as e:
			raise RepositoryError(f"批量评估指标失败: {str(e)}")

	async def update_threshold (
			self,
			threshold_id: int,
			warning_threshold: Optional[float] = None,
			critical_threshold: Optional[float] = None,
			min_value: Optional[float] = None,
			max_value: Optional[float] = None,
			unit: Optional[str] = None,
			description: Optional[str] = None,
			is_active: Optional[bool] = None
	) -> Optional[MonitorThreshold]:
		"""
		更新阈值配置

		Args:
			threshold_id: 阈值配置ID
			warning_threshold: 警告阈值（可选）
			critical_threshold: 严重阈值（可选）
			min_value: 最小值（可选）
			max_value: 最大值（可选）
			unit: 单位（可选）
			description: 描述（可选）
			is_active: 是否激活（可选）

		Returns:
			Optional[MonitorThreshold]: 更新后的阈值配置对象
		"""
		try:
			update_data = {}

			if warning_threshold is not None:
				update_data['warning_threshold'] = warning_threshold
			if critical_threshold is not None:
				update_data['critical_threshold'] = critical_threshold
			if min_value is not None:
				update_data['min_value'] = min_value
			if max_value is not None:
				update_data['max_value'] = max_value
			if unit is not None:
				update_data['unit'] = unit
			if description is not None:
				update_data['description'] = description
			if is_active is not None:
				update_data['is_active'] = is_active

			return await self.update(threshold_id, update_data)
		except Exception as e:
			raise RepositoryError(f"更新阈值配置失败: {str(e)}")

	async def deactivate_threshold (self, threshold_id: int) -> bool:
		"""
		停用阈值配置

		Args:
			threshold_id: 阈值配置ID

		Returns:
			bool: 停用是否成功
		"""
		try:
			return await self.update(threshold_id, {'is_active': False}) is not None
		except Exception as e:
			raise RepositoryError(f"停用阈值配置失败: {str(e)}")

	async def get_thresholds_by_type (
			self,
			metric_type: str,
			only_active: bool = True
	) -> List[MonitorThreshold]:
		"""
		根据指标类型获取阈值配置

		Args:
			metric_type: 指标类型
			only_active: 是否只获取活跃配置

		Returns:
			List[MonitorThreshold]: 阈值配置列表
		"""
		try:
			filters = {'metric_type': metric_type}

			if only_active:
				filters['is_active'] = True

			return await self.get_all(**filters)
		except Exception as e:
			raise RepositoryError(f"获取类型阈值失败: {str(e)}")

	async def search_thresholds (
			self,
			keyword: str,
			metric_type: Optional[str] = None,
			limit: int = 50
	) -> List[MonitorThreshold]:
		"""
		搜索阈值配置

		Args:
			keyword: 搜索关键词
			metric_type: 指标类型过滤（可选）
			limit: 限制记录数

		Returns:
			List[MonitorThreshold]: 搜索结果的阈值配置列表
		"""
		try:
			query = select(self.model).where(
				or_(
					self.model.metric_name.ilike(f'%{keyword}%'),
					self.model.description.ilike(f'%{keyword}%') if self.model.description else False
				)
			)

			if metric_type:
				query = query.where(self.model.metric_type == metric_type)

			query = query.where(self.model.is_active == True).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"搜索阈值配置失败: {str(e)}")

	async def get_threshold_summary (self) -> Dict[str, Any]:
		"""
		获取阈值配置摘要

		Returns:
			Dict[str, Any]: 阈值配置摘要信息
		"""
		try:
			# 统计各类型阈值数量
			query = select(
				self.model.metric_type,
				func.count(self.model.id).label('count'),
				func.sum(func.cast(self.model.is_active, func.Integer)).label('active_count')
			).group_by(self.model.metric_type)

			result = await self.session.execute(query)

			summary = {
				'total': 0,
				'active': 0,
				'by_type': {}
			}

			for metric_type, count, active_count in result.all():
				summary['by_type'][metric_type] = {
					'total': count,
					'active': active_count,
					'inactive': count - active_count
				}
				summary['total'] += count
				summary['active'] += active_count

			summary['inactive'] = summary['total'] - summary['active']

			return summary
		except Exception as e:
			raise RepositoryError(f"获取阈值摘要失败: {str(e)}")