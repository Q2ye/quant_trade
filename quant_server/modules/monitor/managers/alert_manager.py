# -*- coding: utf-8 -*-
"""
告警管理器

管理告警的完整生命周期：创建 → 路由 → 发送 → 追踪。
协调 AlertEngine 和 alerters 之间的工作流。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from modules.monitor.utils.alert_utils import AlertUtils

logger = logging.getLogger(__name__)


class AlertManager:
	"""告警管理器"""

	def __init__ (self, config: Optional[Dict[str, Any]] = None):
		cfg = config or {}
		self._alerters: Dict[str, Any] = {}
		self._retry_max = cfg.get("retry_max", 3)
		self._retry_delay = cfg.get("retry_delay", 5.0)

	def register_alerter (self, channel: str, alerter: Any) -> None:
		"""注册告警渠道"""
		self._alerters[channel] = alerter
		logger.info(f"告警渠道已注册: {channel}")

	def get_alerter (self, channel: str) -> Optional[Any]:
		"""获取告警渠道"""
		return self._alerters.get(channel)

	async def dispatch (
			self,
			session: AsyncSession,
			alert_id: str,
			title: str,
			message: str,
			channels: Optional[List[str]] = None,
	) -> Dict[str, Any]:
		"""
		分发告警到指定渠道

		Returns:
			{"alert_id": str, "results": {channel: bool}}
		"""
		channels = channels or ["email"]
		valid_channels = AlertUtils.validate_channels(channels)
		results: Dict[str, Any] = {}

		from shared.database.repositories.analysis.monitor.alert_delivery_log_repo import \
			AlertDeliveryLogRepository
		delivery_repo = AlertDeliveryLogRepository(session)

		for channel in valid_channels:
			alerter = self._alerters.get(channel)
			if not alerter or not getattr(alerter, 'enabled', False):
				results[channel] = "skipped"
				continue

			# 创建发送日志
			log_entry = await delivery_repo.create_delivery_log(
				alert_id=alert_id,
				channel=channel,
				recipient=channel,
				status="pending",
			)

			success = False
			last_error = None

			for attempt in range(self._retry_max):
				try:
					success = await alerter.send(title, message)
					if success:
						break
				except Exception as e:
					last_error = str(e)
					logger.warning(
						f"告警发送失败 ({channel}, 尝试 {attempt + 1}/{self._retry_max}): {e}"
					)
					if attempt < self._retry_max - 1:
						await asyncio.sleep(AlertUtils.get_retry_delay(attempt))

			if success:
				await delivery_repo.update_delivery_status(log_entry.id, "sent")
				results[channel] = "sent"
			else:
				await delivery_repo.update_delivery_status(
					log_entry.id, "failed",
					error_message=last_error or "发送失败",
					increment_retry=True,
				)
				results[channel] = "failed"
				logger.error(f"告警发送最终失败: {channel} -> alert:{alert_id}")

		return {"alert_id": alert_id, "results": results}

	async def create_and_dispatch (
			self,
			session: AsyncSession,
			alert_type: str,
			alert_level: str,
			title: str,
			message: str,
			source_module: str = "monitor",
			channels: Optional[List[str]] = None,
			metadata: Optional[Dict[str, Any]] = None,
			dedup: bool = True,
	) -> Dict[str, Any]:
		"""
		创建告警并分发 — 一 站式方法

		1. 可选去重检查
		2. 存入 MonitorAlert
		3. 分发到各类通知渠道
		4. 返回完整结果
		"""
		from modules.monitor.services.alert_service import AlertService

		# 去重
		if dedup:
			is_dup = await AlertService.check_duplicate(
				session, alert_type, source_module, title
			)
			if is_dup:
				logger.info(f"检测到重复告警，跳过: {title}")
				return {"status": "duplicate", "alert_id": None}

		# 创建告警记录
		result = await AlertService.create_alert(
			session=session,
			alert_type=alert_type,
			alert_level=alert_level,
			title=title,
			message=message,
			source_module=source_module,
			metadata=metadata,
			notification_channels=channels,
		)

		alert_id = result["alert_id"]

		# 分发通知
		try:
			dispatch_result = await self.dispatch(
				session=session,
				alert_id=alert_id,
				title=title,
				message=message,
				channels=channels,
			)
		except Exception as e:
			logger.error(f"告警分发失败: alert:{alert_id}, error:{e}")
			dispatch_result = {"error": str(e)}

		# 标记通知已发送
		from shared.database.repositories.analysis.monitor.monitor_alert_repo import MonitorAlertRepository
		alert_repo = MonitorAlertRepository(session)
		sent_channels = [
			ch for ch, status in dispatch_result.get("results", {}).items()
			if status == "sent"
		]
		if sent_channels:
			await alert_repo.mark_notification_sent(alert_id, sent_channels)

		return {
			"alert_id": alert_id,
			"status": "dispatched",
			"dispatch": dispatch_result,
		}

	def get_registered_channels (self) -> List[str]:
		"""获取已注册的渠道列表"""
		return list(self._alerters.keys())
