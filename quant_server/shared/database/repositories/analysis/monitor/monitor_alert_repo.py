# quant_server/shared/database/repositories/analysis/monitor/monitor_alert_repository.py
"""
监控报警记录Repository
负责MonitorAlert表的数据访问操作

继承自BaseRepository，提供监控报警记录的标准CRUD操作
以及报警状态管理、时间范围查询等业务方法
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, delete, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from shared.database.models.business_models import MonitorAlert
from shared.database.repositories.base.repository_base import BaseRepository, RepositoryError


class MonitorAlertRepository(BaseRepository[MonitorAlert]):
	"""
	监控报警记录Repository
	继承自BaseRepository，提供监控报警相关的数据访问方法
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化监控报警Repository

		Args:
			session: 数据库会话
		"""
		super().__init__(session, MonitorAlert)

	async def create_alert (
			self,
			alert_type: str,
			alert_level: str,
			source_module: str,
			title: str,
			message: str,
			source_id: Optional[str] = None,
			metadata: Optional[Dict[str, Any]] = None,
			notification_channels: Optional[List[str]] = None
	) -> MonitorAlert:
		"""
		创建监控报警记录

		Args:
			alert_type: 报警类型（system_error, risk_trigger, data_quality, performance）
			alert_level: 报警级别（critical, warning, info）
			source_module: 报警来源模块
			title: 报警标题
			message: 报警详细信息
			source_id: 报警来源ID（可选）
			metadata: 报警元数据（可选）
			notification_channels: 通知渠道（可选）

		Returns:
			MonitorAlert: 创建的报警记录对象
		"""
		try:
			alert_data = {
				'alert_type': alert_type,
				'alert_level': alert_level,
				'source_module': source_module,
				'title': title,
				'message': message,
				'status': 'active',
				'source_id': source_id,
				'metadata': metadata or {},
				'notification_channels': notification_channels or ["email", "wechat"],
				'notification_sent': False
			}

			return await self.create(alert_data)
		except Exception as e:
			raise RepositoryError(f"创建监控报警失败: {str(e)}")

	async def get_active_alerts (
			self,
			alert_type: Optional[str] = None,
			alert_level: Optional[str] = None,
			source_module: Optional[str] = None,
			limit: int = 100
	) -> List[MonitorAlert]:
		"""
		获取活跃状态的报警记录

		Args:
			alert_type: 报警类型过滤（可选）
			alert_level: 报警级别过滤（可选）
			source_module: 来源模块过滤（可选）
			limit: 限制记录数

		Returns:
			List[MonitorAlert]: 活跃报警记录列表
		"""
		try:
			filters = {'status': 'active'}

			if alert_type:
				filters['alert_type'] = alert_type
			if alert_level:
				filters['alert_level'] = alert_level
			if source_module:
				filters['source_module'] = source_module

			return await self.get_many(limit=limit, **filters)
		except Exception as e:
			raise RepositoryError(f"获取活跃报警失败: {str(e)}")

	async def get_recent_alerts (
			self,
			hours: int = 24,
			alert_type: Optional[str] = None,
			alert_level: Optional[str] = None,
			limit: int = 100
	) -> List[MonitorAlert]:
		"""
		获取最近指定小时内的报警记录

		Args:
			hours: 时间范围（小时）
			alert_type: 报警类型过滤（可选）
			alert_level: 报警级别过滤（可选）
			limit: 限制记录数

		Returns:
			List[MonitorAlert]: 最近报警记录列表
		"""
		try:
			time_threshold = datetime.now() - timedelta(hours=hours)

			query = select(self.model).where(
				self.model.created_at >= time_threshold
			)

			if alert_type:
				query = query.where(self.model.alert_type == alert_type)
			if alert_level:
				query = query.where(self.model.alert_level == alert_level)

			query = query.order_by(desc(self.model.created_at)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取最近报警失败: {str(e)}")

	async def update_alert_status (
			self,
			alert_id: str,
			status: str,
			user_id: Optional[str] = None,
			remarks: Optional[str] = None
	) -> bool:
		"""
		更新报警状态

		Args:
			alert_id: 报警ID
			status: 新状态（active, acknowledged, resolved, suppressed）
			user_id: 操作用户ID（可选）
			remarks: 备注（可选）

		Returns:
			bool: 更新是否成功
		"""
		try:
			update_data = {'status': status}

			if status == 'acknowledged' and user_id:
				update_data['acknowledged_by'] = str(user_id)
				update_data['acknowledged_at'] = datetime.now().isoformat()
			elif status == 'resolved' and user_id:
				update_data['resolved_by'] = str(user_id)
				update_data['resolved_at'] = datetime.now().isoformat()

			if remarks:
				update_data['remarks'] = remarks

			return await self.update(alert_id, update_data) is not None
		except Exception as e:
			raise RepositoryError(f"更新报警状态失败: {str(e)}")

	async def acknowledge_alert (
			self,
			alert_id: str,
			user_id: str,
			remarks: Optional[str] = None
	) -> bool:
		"""
		确认报警

		Args:
			alert_id: 报警ID
			user_id: 确认用户ID
			remarks: 备注（可选）

		Returns:
			bool: 确认是否成功
		"""
		return await self.update_alert_status(alert_id, 'acknowledged', user_id, remarks)

	async def resolve_alert (
			self,
			alert_id: str,
			user_id: str,
			remarks: Optional[str] = None
	) -> bool:
		"""
		解决报警

		Args:
			alert_id: 报警ID
			user_id: 解决用户ID
			remarks: 备注（可选）

		Returns:
			bool: 解决是否成功
		"""
		return await self.update_alert_status(alert_id, 'resolved', user_id, remarks)

	async def mark_notification_sent (
			self,
			alert_id: str,
			channels: Optional[List[str]] = None
	) -> bool:
		"""
		标记报警通知已发送

		Args:
			alert_id: 报警ID
			channels: 已发送的渠道列表（可选）

		Returns:
			bool: 标记是否成功
		"""
		try:
			update_data : Dict[str, Any] = {'notification_sent': True}

			if channels:
				# 更新已发送的渠道
				query = select(self.model).where(self.model.id == alert_id)
				result = await self.session.execute(query)
				alert = result.scalar_one_or_none()

				if alert:
					existing_channels = alert.notification_channels or []
					# 只保留未发送的渠道
					remaining_channels = [ch for ch in existing_channels if ch not in channels]

					if remaining_channels:
						update_data['notification_channels'] = remaining_channels
					else:
						# 所有渠道都已发送
						update_data['notification_channels'] = []

			return await self.update(alert_id, update_data) is not None
		except Exception as e:
			raise RepositoryError(f"标记通知发送失败: {str(e)}")

	async def get_alerts_by_source (
			self,
			source_module: str,
			source_id: str,
			limit: int = 50
	) -> List[MonitorAlert]:
		"""
		根据来源获取报警记录

		Args:
			source_module: 来源模块
			source_id: 来源ID
			limit: 限制记录数

		Returns:
			List[MonitorAlert]: 报警记录列表
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.source_module == source_module,
					self.model.source_id == source_id
				)
			).order_by(desc(self.model.created_at)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取来源报警失败: {str(e)}")

	async def get_critical_alerts_count (
			self,
			hours: Optional[int] = None
	) -> Dict[str, int]:
		"""
		获取各级别报警统计

		Args:
			hours: 时间范围（小时，可选）

		Returns:
			Dict[str, int]: 各级别报警数量统计
		"""
		try:
			query = select(
				self.model.alert_level,
				func.count(self.model.id).label('count')
			)

			if hours:
				time_threshold = datetime.now() - timedelta(hours=hours)
				query = query.where(self.model.created_at >= time_threshold)

			query = query.group_by(self.model.alert_level)

			result = await self.session.execute(query)

			stats = {'critical': 0, 'warning': 0, 'info': 0}
			for row in result.all():
				level = row.alert_level
				count = row.count
				if level in stats:
					stats[level] = count

			return stats
		except Exception as e:
			raise RepositoryError(f"获取报警统计失败: {str(e)}")

	async def get_unresolved_alerts_summary (self) -> Dict[str, Any]:
		"""
		获取未解决报警摘要

		Returns:
			Dict[str, Any]: 未解决报警摘要信息
		"""
		try:
			# 获取各模块的未解决报警数
			query = select(
				self.model.source_module,
				self.model.alert_level,
				func.count(self.model.id).label('count')
			).where(
				self.model.status.in_(['active', 'acknowledged'])
			).group_by(
				self.model.source_module,
				self.model.alert_level
			).order_by(
				self.model.source_module,
				desc(self.model.alert_level)
			)

			result = await self.session.execute(query)

			summary : Dict[str, Any] = {
				'total': 0,
				'by_module': {},
				'by_level': {'critical': 0, 'warning': 0, 'info': 0}
			}

			for row in result.all():
				module = row.source_module
				level = row.alert_level
				count = row.count

				if module not in summary['by_module']:
					summary['by_module'][module] = {'critical': 0, 'warning': 0, 'info': 0}

				summary['by_module'][module][level] = count
				summary['by_level'][level] += count
				summary['total'] += count

			return summary
		except Exception as e:
			raise RepositoryError(f"获取未解决报警摘要失败: {str(e)}")

	async def get_alerts_with_delivery_logs (
			self,
			alert_ids: Optional[List[str]] = None,
			limit: int = 100
	) -> List[MonitorAlert]:
		"""
		获取报警记录及其发送日志

		Args:
			alert_ids: 报警ID列表（可选）
			limit: 限制记录数

		Returns:
			List[MonitorAlert]: 包含发送日志的报警记录列表
		"""
		try:
			query = select(self.model).options(
				joinedload(self.model.delivery_logs)
			)

			if alert_ids:
				query = query.where(self.model.id.in_(alert_ids))

			query = query.order_by(desc(self.model.created_at)).limit(limit)

			result = await self.session.execute(query)
			return result.unique().scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取报警及发送日志失败: {str(e)}")

	async def cleanup_old_alerts (
			self,
			days: int = 30,
			keep_resolved: bool = True
	) -> int:
		"""
		清理旧的报警记录

		Args:
			days: 保留天数
			keep_resolved: 是否保留已解决的报警

		Returns:
			int: 删除的记录数
		"""
		try:
			time_threshold = datetime.now() - timedelta(days=days)

			conditions = [self.model.created_at < time_threshold]

			if keep_resolved:
				# 只删除已解决的报警
				conditions.append(self.model.status == 'resolved')

			query = delete(self.model).where(and_(*conditions))

			result = await self.session.execute(query) # type: ignore
			await self.session.commit()

			return result.rowcount if result.rowcount is not None else 0
		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"清理旧报警失败: {str(e)}")