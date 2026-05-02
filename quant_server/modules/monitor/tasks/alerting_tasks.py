# -*- coding: utf-8 -*-
"""
告警定时任务

供系统任务调度器调用的独立函数，处理告警清理、重试和摘要生成。
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def scheduled_alert_cleanup (
		session=None,
		retention_days: int = 90,
) -> Dict[str, Any]:
	"""定时清理过期告警记录"""
	try:
		if session is None:
			return {"status": "skipped", "reason": "no db session"}

		from quant_server.shared.database.repositories.analysis.monitor.monitor_alert_repo import (
			MonitorAlertRepository,
		)

		repo = MonitorAlertRepository(session)
		cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

		resolved_count = 0
		active_alerts = await repo.get_active_alerts(limit=10000)
		for alert in active_alerts:
			if alert.status == "resolved" and alert.resolved_at:
				resolved_at = alert.resolved_at
				if hasattr(resolved_at, 'replace') and resolved_at.replace(tzinfo=None) < cutoff.replace(tzinfo=None):
					await repo.resolve_alert(alert.id, "system", "过期自动清理")
					resolved_count += 1

		logger.info(f"告警清理完成: 清理 {resolved_count} 条过期告警")
		return {"status": "success", "cleaned": resolved_count}
	except Exception as e:
		logger.error(f"告警清理失败: {e}")
		return {"status": "error", "error": str(e)}


async def scheduled_alert_retry (
		session=None,
		alert_manager=None,
		max_retry_hours: int = 24,
) -> Dict[str, Any]:
	"""定时重试失败的告警通知"""
	try:
		if session is None:
			return {"status": "skipped", "reason": "no db session"}

		from quant_server.shared.database.repositories.analysis.monitor.alert_delivery_log_repo import (
			AlertDeliveryLogRepository,
		)

		repo = AlertDeliveryLogRepository(session)
		retried = 0
		failure_analysis = await repo.get_failure_analysis(days=max(1, max_retry_hours // 24))

		for item in failure_analysis:
			channel = item.get("channel", "")
			count = item.get("failure_count", 0)
			if count > 0 and alert_manager:
				try:
					await alert_manager.retry_failed(channel)
					retried += count
				except Exception as e:
					logger.warning(f"重试渠道 {channel} 失败: {e}")

		logger.info(f"告警重试完成: 重试 {retried} 条")
		return {"status": "success", "retried": retried}
	except Exception as e:
		logger.error(f"告警重试失败: {e}")
		return {"status": "error", "error": str(e)}


async def scheduled_alert_summary (session=None) -> Dict[str, Any]:
	"""定时生成告警摘要"""
	try:
		if session is None:
			return {"status": "skipped", "reason": "no db session"}

		from quant_server.shared.database.repositories.analysis.monitor.monitor_alert_repo import (
			MonitorAlertRepository,
		)
		from quant_server.modules.monitor.constants import AlertLevel

		repo = MonitorAlertRepository(session)

		summary = await repo.get_unresolved_alerts_summary()
		critical_stats = await repo.get_critical_alerts_count()
		critical_count = critical_stats.get('critical', 0)

		result = {
			"timestamp": datetime.now(timezone.utc).isoformat(),
			"unresolved": summary,
			"critical_count": critical_count,
		}

		if critical_count > 0:
			logger.warning(f"告警摘要: {critical_count} 条严重告警未解决")
		else:
			logger.info("告警摘要: 无严重告警")

		return result
	except Exception as e:
		logger.error(f"告警摘要生成失败: {e}")
		return {"status": "error", "error": str(e)}
