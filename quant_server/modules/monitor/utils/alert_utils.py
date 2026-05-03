# -*- coding: utf-8 -*-
"""
告警工具

无状态工具类，提供告警消息格式化、渠道验证、重试策略计算等功能。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from modules.monitor.constants import (
	ALERT_TEMPLATES,
	AlertType,
	NotificationChannel,
	ModuleConfig,
)


class AlertUtils:
	"""告警工具类 — 纯静态方法，无状态"""

	@staticmethod
	def format_alert_message (alert_type: AlertType, context: Dict[str, Any]) -> Dict[str, str]:
		"""根据模板格式化告警标题和消息"""
		templates = ALERT_TEMPLATES.get(alert_type)
		if not templates:
			return {
				"title": f"[{context.get('level', 'warning')}] {alert_type.value}",
				"message": context.get("message", ""),
			}

		title = templates["title"]
		message = templates["message"]

		for key, value in context.items():
			placeholder = f"{{{key}}}"
			title = title.replace(placeholder, str(value))
			message = message.replace(placeholder, str(value))

		return {"title": title, "message": message}

	@staticmethod
	def validate_channels (channels: List[str]) -> List[str]:
		"""验证通知渠道是否有效，返回有效渠道列表"""
		valid = {ch.value for ch in NotificationChannel}
		return [ch for ch in channels if ch in valid]

	@staticmethod
	def get_retry_delay (attempt: int) -> float:
		"""计算指数退避重试延迟（秒）"""
		base = ModuleConfig.ALERT_RETRY_DELAY
		return min(base * (2 ** attempt), 60.0)

	@staticmethod
	def should_retry (attempt: int, status: str) -> bool:
		"""判断是否应该重试"""
		if attempt >= ModuleConfig.ALERT_RETRY_MAX:
			return False
		return status == "failed"

	@staticmethod
	def generate_alert_summary (alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
		"""生成告警摘要统计"""
		summary = {
			"total": len(alerts),
			"by_level": {"critical": 0, "warning": 0, "info": 0},
			"by_type": {},
			"by_status": {"active": 0, "acknowledged": 0, "resolved": 0},
			"latest_alert": None,
		}

		latest_time: Optional[datetime] = None

		for alert in alerts:
			level = alert.get("alert_level", "info")
			if level in summary["by_level"]:
				summary["by_level"][level] += 1

			alert_type = alert.get("alert_type", "unknown")
			summary["by_type"][alert_type] = summary["by_type"].get(alert_type, 0) + 1

			status = alert.get("status", "active")
			if status in summary["by_status"]:
				summary["by_status"][status] += 1

			created = alert.get("created_at")
			if created and (latest_time is None or created > latest_time):
				latest_time = created
				summary["latest_alert"] = alert

		return summary
