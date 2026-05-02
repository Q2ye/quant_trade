# -*- coding: utf-8 -*-
"""
告警服务

无状态服务，处理告警的创建、路由、去重和生命周期管理。
被 AlertEngine 和 handlers 调用。
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.modules.monitor.constants import AlertType
from quant_server.modules.monitor.utils.alert_utils import AlertUtils

logger = logging.getLogger(__name__)


class AlertService:
	"""告警服务 — 无状态"""

	@staticmethod
	async def create_alert (
			session: AsyncSession,
			alert_type: str,
			alert_level: str,
			title: str,
			message: str,
			source_module: str = "monitor",
			source_id: Optional[str] = None,
			metadata: Optional[Dict[str, Any]] = None,
			notification_channels: Optional[List[str]] = None,
	) -> Dict[str, Any]:
		"""
		创建告警记录

		Returns:
			{"alert_id": str, "alert": MonitorAlert}
		"""
		from quant_server.shared.database.repositories.analysis.monitor.monitor_alert_repo import MonitorAlertRepository

		repo = MonitorAlertRepository(session)

		try:
			alert = await repo.create_alert(
				alert_type=alert_type,
				alert_level=alert_level,
				source_module=source_module,
				title=title,
				message=message,
				source_id=source_id,
				metadata=metadata or {},
				notification_channels=notification_channels or ["email", "wechat"],
			)

			logger.info(f"告警已创建: {alert.id} [{alert_level}] {title}")
			return {"alert_id": alert.id, "alert": alert}
		except Exception as e:
			logger.error(f"创建告警失败: {e}")
			raise

	@staticmethod
	async def acknowledge_alert (
			session: AsyncSession,
			alert_id: str,
			user_id: str,
			remarks: Optional[str] = None,
	) -> bool:
		"""确认告警"""
		from quant_server.shared.database.repositories.analysis.monitor.monitor_alert_repo import MonitorAlertRepository

		repo = MonitorAlertRepository(session)
		return await repo.acknowledge_alert(alert_id, user_id, remarks)

	@staticmethod
	async def resolve_alert (
			session: AsyncSession,
			alert_id: str,
			user_id: str,
			remarks: Optional[str] = None,
	) -> bool:
		"""解决告警"""
		from quant_server.shared.database.repositories.analysis.monitor.monitor_alert_repo import MonitorAlertRepository

		repo = MonitorAlertRepository(session)
		return await repo.resolve_alert(alert_id, user_id, remarks)

	@staticmethod
	async def check_duplicate (
			session: AsyncSession,
			alert_type: str,
			source_module: str,
			title: str,
			within_hours: int = 1,
	) -> bool:
		"""检查是否存在重复告警（相同类型+标题+来源，N小时内）"""
		from quant_server.shared.database.repositories.analysis.monitor.monitor_alert_repo import MonitorAlertRepository

		repo = MonitorAlertRepository(session)
		recent = await repo.get_recent_alerts(
			hours=within_hours,
			alert_type=alert_type,
			limit=50,
		)

		for alert in recent:
			if (getattr(alert, 'title', '') == title and
					getattr(alert, 'source_module', '') == source_module):
				return True
		return False

	@staticmethod
	async def get_active_alerts (
			session: AsyncSession,
			alert_type: Optional[str] = None,
			alert_level: Optional[str] = None,
			limit: int = 100,
	) -> List[Dict[str, Any]]:
		"""获取活跃告警列表"""
		from quant_server.shared.database.repositories.analysis.monitor.monitor_alert_repo import MonitorAlertRepository

		repo = MonitorAlertRepository(session)
		alerts = await repo.get_active_alerts(
			alert_type=alert_type,
			alert_level=alert_level,
			limit=limit,
		)

		return [
			{
				"id": a.id,
				"alert_type": a.alert_type,
				"alert_level": a.alert_level,
				"source_module": a.source_module,
				"title": a.title,
				"message": a.message,
				"status": a.status,
				"created_at": a.created_at.isoformat() if a.created_at else None,
			}
			for a in alerts
		]

	@staticmethod
	async def get_alert_history (
			session: AsyncSession,
			alert_level: Optional[str] = None,
			hours: int = 168,
			limit: int = 100,
	) -> List[Dict[str, Any]]:
		"""获取告警历史"""
		from quant_server.shared.database.repositories.analysis.monitor.monitor_alert_repo import MonitorAlertRepository

		repo = MonitorAlertRepository(session)
		alerts = await repo.get_recent_alerts(
			hours=hours,
			alert_level=alert_level,
			limit=limit,
		)

		return [
			{
				"id": a.id,
				"alert_type": a.alert_type,
				"alert_level": a.alert_level,
				"source_module": a.source_module,
				"title": a.title,
				"message": a.message,
				"status": a.status,
				"created_at": a.created_at.isoformat() if a.created_at else None,
				"acknowledged_at": a.acknowledged_at.isoformat() if getattr(a, 'acknowledged_at', None) else None,
				"resolved_at": a.resolved_at.isoformat() if getattr(a, 'resolved_at', None) else None,
			}
			for a in alerts
		]

	@staticmethod
	async def get_alert_summary (session: AsyncSession) -> Dict[str, Any]:
		"""获取告警摘要统计"""
		from quant_server.shared.database.repositories.analysis.monitor.monitor_alert_repo import MonitorAlertRepository

		repo = MonitorAlertRepository(session)
		return await repo.get_unresolved_alerts_summary()

	@staticmethod
	async def render_template (
			session: AsyncSession,
			alert_type: str,
			alert_level: str,
			context: Dict[str, Any],
	) -> Optional[Dict[str, str]]:
		"""使用模板渲染告警消息"""
		from quant_server.shared.database.repositories.analysis.monitor.alert_template_repo import \
			AlertTemplateRepository

		repo = AlertTemplateRepository(session)
		try:
			return await repo.render_by_type_level(alert_type, alert_level, context)
		except Exception:
			# 模板渲染失败时使用内置模板
			return AlertUtils.format_alert_message(
				AlertType(alert_type) if alert_type in [e.value for e in AlertType] else AlertType.SYSTEM_ERROR,
				context,
			)
