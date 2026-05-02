# -*- coding: utf-8 -*-
"""
业务监控引擎

继承 EngineBase，周期性聚合业务指标（交易量、PnL、策略绩效）。
可通过 session 连接数据库查询，也可接收外部推送的指标数据。

订阅事件：无（主动聚合 + 可接收外部推送）
发布事件：monitor.business.metrics.updated
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from quant_server.core.engines.base.engine_base import EngineBase
from quant_server.core.engines.types.entities import EngineConfigEntity
from quant_server.core.engines.types.enums import EngineType
from quant_server.modules.monitor.constants import ModuleConfig
from quant_server.modules.monitor.services.business_service import BusinessMonitorService

logger = logging.getLogger(__name__)


class BusinessMonitorEngine(EngineBase):
	"""业务监控引擎 — 定时聚合业务指标"""

	def __init__ (
			self,
			config: Optional[Dict[str, Any]] = None,
			event_engine=None,
			db_session_factory=None,
	):
		cfg = config or {}
		config_obj = EngineConfigEntity(
			name=cfg.get("name", "business_monitor"),
			engine_type="business_monitor",
			dependencies=cfg.get("dependencies", []),
			max_retries=cfg.get("max_retries", 3),
			retry_delay=cfg.get("retry_delay", 1.0),
			config=cfg,
		)
		super().__init__(config=config_obj, event_engine=event_engine)

		self._aggregate_interval = cfg.get(
			"business_metrics_interval", ModuleConfig.BUSINESS_METRICS_INTERVAL
		)
		self._db_session_factory = db_session_factory
		self._last_metrics: Dict[str, Any] = {}
		self._aggregate_task: Optional[asyncio.Task] = None

	@property
	def engine_type (self) -> EngineType:
		return EngineType.CUSTOM

	async def _on_initialize (self) -> None:
		logger.info("业务监控引擎初始化")

	async def _on_start (self) -> None:
		logger.info(f"业务监控引擎启动，聚合间隔: {self._aggregate_interval}s")
		self._aggregate_task = asyncio.create_task(
			self._aggregation_loop(),
			name="business_monitor_aggregate",
		)

	async def _on_stop (self) -> None:
		logger.info("业务监控引擎停止")
		if self._aggregate_task:
			self._aggregate_task.cancel()
			try:
				await self._aggregate_task
			except asyncio.CancelledError:
				pass
			self._aggregate_task = None

	async def _aggregation_loop (self) -> None:
		while self.record.status.value == "running":
			try:
				await self.aggregate_and_publish()
				await asyncio.sleep(self._aggregate_interval)
			except asyncio.CancelledError:
				break
			except Exception as e:
				logger.error(f"业务指标聚合异常: {e}")
				await asyncio.sleep(min(self._aggregate_interval, 30))

	async def aggregate_and_publish (self) -> Dict[str, Any]:
		"""执行一次聚合并发布事件"""
		session = None
		if self._db_session_factory:
			try:
				session = await self._db_session_factory()
			except Exception as e:
				logger.warning(f"获取数据库会话失败: {e}")

		try:
			metrics = await BusinessMonitorService.aggregate_metrics(session=session)
		finally:
			pass  # session 生命周期由 factory 管理

		self._last_metrics = metrics

		await self._publish_event("monitor.business.metrics.updated", {
			"metrics": metrics,
		})

		return metrics

	async def get_latest_metrics (self) -> Dict[str, Any]:
		"""获取最新业务指标"""
		return dict(self._last_metrics)
