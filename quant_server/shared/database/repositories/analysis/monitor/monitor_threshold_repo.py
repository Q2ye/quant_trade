# -*- coding: utf-8 -*-
"""
监控阈值配置表Repository
位置：shared/database/repositories/analysis/monitor/monitor_threshold_repo.py
功能：提供监控阈值的CRUD操作、阈值验证、阈值查询等功能
包括阈值查询、有效性验证、批量更新等
"""
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import select, and_, func, desc, asc, case
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.business_models import MonitorThreshold
from quant_server.shared.database.repositories.base import BaseRepository, RepositoryError


class MonitorThresholdRepository(BaseRepository[MonitorThreshold]):
	"""监控阈值配置Repository"""

	def __init__ (self, session: AsyncSession):
		"""初始化Repository"""
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
			description: Optional[str] = None,
			is_active: bool = True
	) -> MonitorThreshold:
		"""
		创建监控阈值

		Args:
			metric_type: 指标类型
			metric_name: 指标名称
			warning_threshold: 警告阈值
			critical_threshold: 严重阈值
			min_value: 最小值
			max_value: 最大值
			unit: 单位
			description: 描述
			is_active: 是否激活

		Returns:
			监控阈值配置
		"""
		try:
			# 验证阈值有效性
			if not self._validate_thresholds(
					warning_threshold=warning_threshold,
					critical_threshold=critical_threshold,
					min_value=min_value,
					max_value=max_value
			):
				raise RepositoryError("阈值配置无效")

			data = {
				"metric_type": metric_type,
				"metric_name": metric_name,
				"warning_threshold": warning_threshold,
				"critical_threshold": critical_threshold,
				"min_value": min_value,
				"max_value": max_value,
				"unit": unit,
				"description": description,
				"is_active": is_active
			}

			return await self.create(data)
		except Exception as e:
			raise RepositoryError(f"创建监控阈值失败: {str(e)}")

	async def update_threshold (
			self,
			threshold_id: str,
			warning_threshold: Optional[float] = None,
			critical_threshold: Optional[float] = None,
			min_value: Optional[float] = None,
			max_value: Optional[float] = None,
			unit: Optional[str] = None,
			description: Optional[str] = None,
			is_active: Optional[bool] = None
	) -> bool:
		"""
		更新监控阈值

		Args:
			threshold_id: 阈值ID
			warning_threshold: 警告阈值
			critical_threshold: 严重阈值
			min_value: 最小值
			max_value: 最大值
			unit: 单位
			description: 描述
			is_active: 是否激活

		Returns:
			是否更新成功
		"""
		try:
			# 验证阈值有效性
			if not self._validate_thresholds(
				warning_threshold=warning_threshold,
				critical_threshold=critical_threshold,
				min_value=min_value,
				max_value=max_value
			):
				raise RepositoryError("阈值配置无效")

			# 直接使用update方法，不需要先获取对象
			update_data = {}
			if warning_threshold is not None:
				update_data["warning_threshold"] = warning_threshold
			if critical_threshold is not None:
				update_data["critical_threshold"] = critical_threshold
			if min_value is not None:
				update_data["min_value"] = min_value
			if max_value is not None:
				update_data["max_value"] = max_value
			if unit is not None:
				update_data["unit"] = unit
			if description is not None:
				update_data["description"] = description
			if is_active is not None:
				update_data["is_active"] = is_active

			if update_data:
				await self.update(threshold_id, update_data)
				return True
			return True
		except Exception as e:
			raise RepositoryError(f"更新监控阈值失败: {str(e)}")

	async def get_by_metric (
			self,
			metric_type: str,
			metric_name: str
	) -> Optional[MonitorThreshold]:
		"""
		根据指标类型和名称获取阈值

		Args:
			metric_type: 指标类型
			metric_name: 指标名称

		Returns:
			监控阈值配置
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.metric_type == metric_type,
					self.model.metric_name == metric_name
				)
			).order_by(
				desc(self.model.is_active),
				desc(self.model.created_at)
			)

			result = await self.session.execute(query)
			return result.scalars().first()
		except Exception as e:
			raise RepositoryError(f"获取指标阈值失败: {str(e)}")

	async def get_active_thresholds (
			self,
			metric_type: Optional[str] = None,
			limit: int = 100
	) -> List[MonitorThreshold]:
		"""
		获取激活的阈值

		Args:
			metric_type: 指标类型
			limit: 限制记录数

		Returns:
			激活的监控阈值列表
		"""
		try:
			query = select(self.model).where(
				self.model.is_active == True
			)

			if metric_type:
				query = query.where(self.model.metric_type == metric_type)

			query = query.order_by(
				asc(self.model.metric_type),
				asc(self.model.metric_name)
			).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取激活阈值失败: {str(e)}")

	async def get_thresholds_by_type (
			self,
			metric_type: str,
			include_inactive: bool = False
	) -> List[MonitorThreshold]:
		"""
		根据指标类型获取阈值

		Args:
			metric_type: 指标类型
			include_inactive: 是否包含未激活的阈值

		Returns:
			监控阈值列表
		"""
		try:
			query = select(self.model).where(
				self.model.metric_type == metric_type
			)

			if not include_inactive:
				query = query.where(self.model.is_active == True)

			query = query.order_by(
				asc(self.model.metric_name)
			)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取指标类型阈值失败: {str(e)}")

	async def validate_value (
			self,
			metric_type: str,
			metric_name: str,
			value: float
	) -> Tuple[str, str]:
		"""
		验证值是否在阈值范围内

		Args:
			metric_type: 指标类型
			metric_name: 指标名称
			value: 要验证的值

		Returns:
			(status, message) 元组，其中 status 为 "normal", "warning", "critical" 或 "error"
		"""
		try:
			threshold = await self.get_by_metric(metric_type, metric_name)
			if not threshold:
				return "error", f"未找到 {metric_type}.{metric_name} 的阈值配置"

			# 检查最小值和最大值
			if threshold.min_value is not None and value < threshold.min_value:
				return "critical", f"值 {value} 低于最小值 {threshold.min_value}"
			if threshold.max_value is not None and value > threshold.max_value:
				return "critical", f"值 {value} 高于最大值 {threshold.max_value}"

			# 检查警告和严重阈值
			if threshold.critical_threshold is not None:
				if threshold.critical_threshold < threshold.warning_threshold:
					# 阈值越低越严重（如错误率）
					if value <= threshold.critical_threshold:
						return "critical", f"值 {value} 达到严重阈值 {threshold.critical_threshold}"
					elif value <= threshold.warning_threshold:
						return "warning", f"值 {value} 达到警告阈值 {threshold.warning_threshold}"
				else:
					# 阈值越高越严重（如延迟）
					if value >= threshold.critical_threshold:
						return "critical", f"值 {value} 达到严重阈值 {threshold.critical_threshold}"
					elif value >= threshold.warning_threshold:
						return "warning", f"值 {value} 达到警告阈值 {threshold.warning_threshold}"

			return "normal", "值在正常范围内"
		except Exception as e:
			raise RepositoryError(f"验证值失败: {str(e)}")

	async def get_threshold_summary (
			self,
			metric_type: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取阈值摘要

		Args:
			metric_type: 指标类型

		Returns:
			阈值摘要
		"""
		try:
			query = select(
				func.count().label("total_thresholds"),
				func.count(case((self.model.is_active == True, 1), else_=None)).label("active_thresholds"),
				func.count(case((self.model.is_active == False, 1), else_=None)).label("inactive_thresholds"),
				self.model.metric_type
			)

			if metric_type:
				query = query.where(self.model.metric_type == metric_type)

			query = query.group_by(
				self.model.metric_type
			)

			result = await self.session.execute(query)
			rows = result.fetchall()

			summary = {
				"total_thresholds": 0,
				"active_thresholds": 0,
				"inactive_thresholds": 0,
				"by_metric_type": {}
			}

			for row in rows:
				total = row.total_thresholds or 0
				active = row.active_thresholds or 0
				inactive = row.inactive_thresholds or 0

				summary["total_thresholds"] += total
				summary["active_thresholds"] += active
				summary["inactive_thresholds"] += inactive

				metric_type_val = row.metric_type or "unknown"
				summary["by_metric_type"][metric_type_val] = {
					"total": total,
					"active": active,
					"inactive": inactive,
					"active_percentage": round((active / total * 100), 2) if total > 0 else 0
				}

			return summary
		except Exception as e:
			raise RepositoryError(f"获取阈值摘要失败: {str(e)}")

	async def batch_update_active_status (
			self,
			threshold_ids: List[str],
			is_active: bool
	) -> int:
		"""
		批量更新阈值激活状态

		Args:
			threshold_ids: 阈值ID列表
			is_active: 激活状态

		Returns:
			更新的记录数
		"""
		try:
			if not threshold_ids:
				return 0

			from sqlalchemy import update
			update_stmt = update(self.model).where(
				self.model.id.in_(threshold_ids)
			).values(is_active=is_active)

			result = await self.session.execute(update_stmt)
			await self.session.commit()
			return result.rowcount
		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"批量更新阈值激活状态失败: {str(e)}")

	async def delete_inactive_thresholds (self, days: int = 30) -> int:
		"""
		删除未激活的阈值

		Args:
			days: 未激活天数

		Returns:
			删除的记录数
		"""
		try:
			from datetime import datetime, timedelta

			cutoff_date = datetime.now() - timedelta(days=days)
			query = select(self.model).where(
				and_(
					self.model.is_active == False,
					self.model.updated_at < cutoff_date
				)
			)

			result = await self.session.execute(query)
			thresholds_to_delete = result.scalars().all()

			for threshold in thresholds_to_delete:
				await self.session.delete(threshold)

			await self.session.flush()
			return len(thresholds_to_delete)
		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"删除未激活阈值失败: {str(e)}")

	@staticmethod
	def _validate_thresholds (
			warning_threshold: Optional[float] = None,
			critical_threshold: Optional[float] = None,
			min_value: Optional[float] = None,
			max_value: Optional[float] = None
	) -> bool:
		"""
		验证阈值配置的有效性

		Args:
			warning_threshold: 警告阈值
			critical_threshold: 严重阈值
			min_value: 最小值
			max_value: 最大值

		Returns:
			是否有效
		"""
		try:
			# 检查最小值和最大值
			if min_value is not None and max_value is not None:
				if min_value > max_value:
					return False

			# 检查警告和严重阈值
			if warning_threshold is not None and critical_threshold is not None:
				# 两种情况都有效：
				# 1. 严重阈值 < 警告阈值（如错误率）
				# 2. 严重阈值 > 警告阈值（如延迟）
				pass

			# 检查阈值是否在最小值和最大值范围内
			if min_value is not None:
				if warning_threshold is not None and warning_threshold < min_value:
					return False
				if critical_threshold is not None and critical_threshold < min_value:
					return False

			if max_value is not None:
				if warning_threshold is not None and warning_threshold > max_value:
					return False
				if critical_threshold is not None and critical_threshold > max_value:
					return False

			return True
		except Exception:  # type: ignore
			return False