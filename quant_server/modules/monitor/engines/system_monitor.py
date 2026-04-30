# -*- coding: utf-8 -*-
"""
系统监控引擎

继承 EngineBase，周期性采集系统资源指标（CPU/内存/磁盘/网络），
评估健康状况，通过 EventEngine 发布事件。

订阅事件：无（自主定时采集）
发布事件：monitor.system.metrics.collected, monitor.system.health.changed
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from quant_server.core.engines.base.engine_base import EngineBase
from quant_server.core.engines.types.entities import EngineConfigEntity
from quant_server.core.engines.types.enums import EngineType

from quant_server.modules.monitor.collectors.system_collector import SystemCollector
from quant_server.modules.monitor.collectors.metric_collector import MetricCollector
from quant_server.modules.monitor.services.system_service import SystemMonitorService
from quant_server.modules.monitor.events.system_events import SystemMonitorEvent
from quant_server.modules.monitor.events.health_events import HealthMonitorEvent
from quant_server.modules.monitor.constants import ModuleConfig

logger = logging.getLogger(__name__)


class SystemMonitorEngine(EngineBase):
    """系统监控引擎 — 定时采集 OS 资源指标"""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        event_engine=None,
    ):
        cfg = config or {}
        config_obj = EngineConfigEntity(
            name=cfg.get("name", "system_monitor"),
            engine_type="system_monitor",
            dependencies=cfg.get("dependencies", []),
            max_retries=cfg.get("max_retries", 3),
            retry_delay=cfg.get("retry_delay", 1.0),
            config=cfg,
        )
        super().__init__(config=config_obj, event_engine=event_engine)

        self._collect_interval = cfg.get(
            "system_collect_interval", ModuleConfig.SYSTEM_COLLECT_INTERVAL
        )
        self._metric_collector = MetricCollector()
        self._collect_task: Optional[asyncio.Task] = None

    @property
    def engine_type(self) -> EngineType:
        return EngineType.SYSTEM_MONITOR

    async def _on_initialize(self) -> None:
        logger.info("系统监控引擎初始化")

    async def _on_start(self) -> None:
        logger.info(f"系统监控引擎启动，采集间隔: {self._collect_interval}s")

        self._collect_task = asyncio.create_task(
            self._collection_loop(),
            name="system_monitor_collect",
        )

    async def _on_stop(self) -> None:
        logger.info("系统监控引擎停止")
        if self._collect_task:
            self._collect_task.cancel()
            try:
                await self._collect_task
            except asyncio.CancelledError:
                pass
            self._collect_task = None

    async def _collection_loop(self) -> None:
        """周期性采集系统指标"""
        while self.record.status.value == "running":
            try:
                await self.collect_and_publish()
                await asyncio.sleep(self._collect_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"系统指标采集异常: {e}")
                await asyncio.sleep(min(self._collect_interval, 5.0))

    async def collect_and_publish(self) -> Dict[str, Any]:
        """执行一次采集并发布事件"""
        metrics = await SystemCollector.collect()
        self._metric_collector.record_batch({
            "cpu_usage": metrics.cpu_usage,
            "memory_usage": metrics.memory_usage,
            "disk_usage": metrics.disk_usage,
            "network_in": metrics.network_in,
            "network_out": metrics.network_out,
            "thread_count": metrics.thread_count,
            "process_count": metrics.process_count,
        })

        evaluation = await SystemMonitorService.evaluate_metrics(metrics)

        event = SystemMonitorEvent.metrics_collected(metrics)
        await self._publish_event(event.event_type, event.data)

        if evaluation["alerts"]:
            for alert in evaluation["alerts"]:
                health_event = SystemMonitorEvent.health_changed(
                    component="system",
                    old_status="normal",
                    new_status=alert["level"],
                    message=f"{alert['metric']}: {alert['value']} (阈值: {alert['warning_threshold']})",
                )
                await self._publish_event(health_event.event_type, health_event.data)

        return {"metrics": evaluation["metrics"], "status": evaluation["overall_status"]}

    async def get_latest_metrics(self) -> Dict[str, Any]:
        """获取最新采集的指标"""
        return self._metric_collector.get_all_latest()

    async def health_check(self) -> Dict[str, Any]:
        """覆盖 EngineBase.health_check"""
        base = await super().health_check()
        base["metrics"] = self._metric_collector.get_all_latest()
        return base
