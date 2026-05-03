# -*- coding: utf-8 -*-
"""
告警引擎

继承 EngineBase，管理告警的创建、分发和生命周期。
订阅系统/风险/业务引擎的告警事件，统一路由到通知渠道。

订阅事件：monitor.risk.alert.triggered, monitor.system.health.changed
发布事件：monitor.alert.created, monitor.alert.notification.sent/failed
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from core.engines.base.engine_base import EngineBase
from core.engines.types.entities import EngineConfigEntity
from core.engines.types.enums import EngineType
from modules.monitor.constants import ModuleConfig, AlertLevel, AlertType
from modules.monitor.events.alert_events import AlertMonitorEvent
from modules.monitor.managers.alert_manager import AlertManager

logger = logging.getLogger(__name__)


class AlertEngine(EngineBase):
	"""告警引擎 — 统一告警生命周期管理"""

	def __init__ (
			self,
			config: Optional[Dict[str, Any]] = None,
			event_engine=None,
			db_session_factory=None,
	):
		cfg = config or {}
		config_obj = EngineConfigEntity(
			name=cfg.get("name", "alert_engine"),
			engine_type="alert_engine",
			dependencies=cfg.get("dependencies", []),
			max_retries=cfg.get("max_retries", 3),
			retry_delay=cfg.get("retry_delay", 1.0),
			config=cfg,
		)
		super().__init__(config=config_obj, event_engine=event_engine)

		self._alert_manager = AlertManager(cfg)
		self._db_session_factory = db_session_factory
		self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=ModuleConfig.ENGINE_QUEUE_SIZE)
		self._process_task: Optional[asyncio.Task] = None

	@property
	def engine_type (self) -> EngineType:
		return EngineType.CUSTOM

	@property
	def alert_manager (self) -> AlertManager:
		return self._alert_manager

	async def _on_initialize (self) -> None:
		logger.info("告警引擎初始化")

	async def _on_start (self) -> None:
		logger.info("告警引擎启动")
		self._process_task = asyncio.create_task(
			self._process_loop(),
			name="alert_engine_process",
		)

		# 注册事件处理器 — 监听风险告警
		if self.event_engine:
			self.event_engine.register(
				"monitor.risk.alert.triggered",
				self._handle_risk_alert,
			)
			self.event_engine.register(
				"monitor.system.health.changed",
				self._handle_system_alert,
			)

	async def _on_stop (self) -> None:
		logger.info("告警引擎停止")
		if self._process_task:
			self._process_task.cancel()
			try:
				await self._process_task
			except asyncio.CancelledError:
				pass
			self._process_task = None

	async def _process_loop (self) -> None:
		"""处理告警事件队列"""
		while self.record.status.value == "running":
			try:
				alert_data = await asyncio.wait_for(
					self._event_queue.get(), timeout=5.0
				)
				await self._process_alert(alert_data)
				self._event_queue.task_done()
			except asyncio.TimeoutError:
				continue
			except asyncio.CancelledError:
				break
			except Exception as e:
				logger.error(f"告警处理异常: {e}")

	async def _process_alert (self, alert_data: Dict[str, Any]) -> None:
		"""处理单个告警"""
		session = None
		if self._db_session_factory:
			try:
				session = await self._db_session_factory()
			except Exception as e:
				logger.error(f"获取会话失败: {e}")
				return

		if not session:
			logger.warning("无数据库会话，告警无法持久化")
			return

		try:
			result = await self._alert_manager.create_and_dispatch(
				session=session,
				alert_type=alert_data.get("alert_type", "system_error"),
				alert_level=alert_data.get("alert_level", AlertLevel.WARNING.value),
				title=alert_data.get("title", "未知告警"),
				message=alert_data.get("message", ""),
				source_module=alert_data.get("source_module", "monitor"),
				channels=alert_data.get("channels"),
				metadata=alert_data.get("metadata"),
			)

			alert_id = result.get("alert_id")
			if alert_id:
				created_event = AlertMonitorEvent.alert_created(
					alert_id=alert_id,
					alert_type=AlertType(alert_data.get("alert_type", "system_error")),
					alert_level=AlertLevel(alert_data.get("alert_level", AlertLevel.WARNING.value)),
					title=alert_data.get("title", ""),
					message=alert_data.get("message", ""),
				)
				await self._publish_event(
					created_event.event_type, created_event.data
				)

				for ch, status in result.get("dispatch", {}).get("results", {}).items():
					if status == "sent":
						sent_event = AlertMonitorEvent.notification_sent(alert_id, [ch])
						await self._publish_event(sent_event.event_type, sent_event.data)
					elif status == "failed":
						failed_event = AlertMonitorEvent.notification_failed(
							alert_id, ch, "发送失败"
						)
						await self._publish_event(failed_event.event_type, failed_event.data)

		except Exception as e:
			logger.error(f"告警处理失败: {e}")
		finally:
			pass  # session 生命周期由 factory 管理

	async def trigger_alert (
			self,
			alert_type: str,
			alert_level: str,
			title: str,
			message: str,
			source_module: str = "monitor",
			channels: Optional[list] = None,
			metadata: Optional[Dict[str, Any]] = None,
	) -> Optional[str]:
		"""
		外部触发告警（由 handlers 调用）

		Returns:
			alert_id 或 None（若去重导致跳过）
		"""
		session = None
		if self._db_session_factory:
			try:
				session = await self._db_session_factory()
			except (OSError, asyncio.TimeoutError):
				return None

		if not session:
			return None

		try:
			result = await self._alert_manager.create_and_dispatch(
				session=session,
				alert_type=alert_type,
				alert_level=alert_level,
				title=title,
				message=message,
				source_module=source_module,
				channels=channels,
				metadata=metadata,
			)
			return result.get("alert_id")
		except Exception as e:
			logger.error(f"手动触发告警失败: {e}")
			return None

	async def _handle_risk_alert (self, event) -> None:
		"""处理风险告警事件"""
		data = event.data if hasattr(event, 'data') else event.get('data', {})
		await self._event_queue.put({
			"alert_type": "risk_trigger",
			"alert_level": data.get("level", AlertLevel.WARNING.value),
			"title": f"[{data.get('level', 'warning')}] 风险预警 - {data.get('risk_type', 'unknown')}",
			"message": data.get("message", ""),
			"source_module": "monitor.risk_monitor",
			"metadata": data,
		})

	async def _handle_system_alert (self, event) -> None:
		"""处理系统健康变化事件"""
		data = event.data if hasattr(event, 'data') else event.get('data', {})
		alert_level = data.get("new_status", AlertLevel.WARNING.value)
		if alert_level not in ("warning", "critical"):
			return

		await self._event_queue.put({
			"alert_type": "system_error",
			"alert_level": alert_level,
			"title": f"[{alert_level}] 系统健康变化 - {data.get('component', 'unknown')}",
			"message": data.get("message", ""),
			"source_module": "monitor.system_monitor",
			"metadata": data,
		})
