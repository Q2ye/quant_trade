# -*- coding: utf-8 -*-
"""
日志服务

无状态服务，提供日志分析、异常追踪和审计支持。
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class LogService:
	"""日志服务 — 无状态"""

	@staticmethod
	async def get_recent_errors (
			session: Optional[AsyncSession] = None,
			hours: int = 24,
			limit: int = 50,
	) -> List[Dict[str, Any]]:
		"""获取最近的系统错误日志"""
		# 从数据库监控告警表获取最近的错误
		if session:
			try:
				from shared.database.repositories.analysis.monitor.monitor_alert_repo import \
					MonitorAlertRepository
				repo = MonitorAlertRepository(session)
				alerts = await repo.get_recent_alerts(
					hours=hours,
					alert_type="system_error",
					limit=limit,
				)
				return [
					{
						"id": a.id,
						"title": a.title,
						"message": a.message,
						"level": a.alert_level,
						"source_module": a.source_module,
						"created_at": a.created_at.isoformat() if a.created_at else None,
						"status": a.status,
					}
					for a in alerts
				]
			except Exception as e:
				logger.warning(f"获取系统错误日志失败: {e}")

		return []

	@staticmethod
	async def analyze_error_patterns (
			session: AsyncSession,
			days: int = 7,
	) -> Dict[str, Any]:
		"""分析错误模式"""
		try:
			from shared.database.repositories.analysis.monitor.alert_delivery_log_repo import \
				AlertDeliveryLogRepository

			repo = AlertDeliveryLogRepository(session)
			failure_analysis = await repo.get_failure_analysis(days=days)

			return {
				"period_days": days,
				"failure_patterns": failure_analysis,
				"total_failures": sum(f["failure_count"] for f in failure_analysis),
				"analyzed_at": datetime.now(timezone.utc).isoformat(),
			}
		except Exception as e:
			logger.error(f"分析错误模式失败: {e}")
			return {"error": str(e)}

	@staticmethod
	async def get_channel_delivery_stats (
			session: AsyncSession,
			hours: int = 24,
	) -> Dict[str, Any]:
		"""获取各渠道的发送统计"""
		try:
			from shared.database.repositories.analysis.monitor.alert_delivery_log_repo import \
				AlertDeliveryLogRepository

			repo = AlertDeliveryLogRepository(session)
			return await repo.get_channel_statistics(hours=hours)
		except Exception as e:
			logger.error(f"获取渠道统计失败: {e}")
			return {"error": str(e)}
