# -*- coding: utf-8 -*-
"""
风险监控引擎

继承 EngineBase，周期性检查风险指标（回撤、仓位、VaR等），
与 MonitorThresholdRepository 中的阈值比较，发现突破时发布告警事件。

订阅事件：无（自主定时检查）
发布事件：monitor.risk.threshold.breached, monitor.risk.alert.triggered
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from quant_server.core.engines.base.engine_base import EngineBase
from quant_server.core.engines.types.entities import EngineConfigEntity
from quant_server.core.engines.types.enums import EngineType

from quant_server.modules.monitor.services.risk_service import RiskMonitorService
from quant_server.modules.monitor.events.risk_events import RiskMonitorEvent
from quant_server.modules.monitor.constants import ModuleConfig

logger = logging.getLogger(__name__)


class RiskMonitorEngine(EngineBase):
    """风险监控引擎 — 定时检查风险指标"""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        event_engine=None,
        threshold_repo=None,
    ):
        cfg = config or {}
        config_obj = EngineConfigEntity(
            name=cfg.get("name", "risk_monitor"),
            engine_type="risk_monitor",
            dependencies=cfg.get("dependencies", []),
            max_retries=cfg.get("max_retries", 3),
            retry_delay=cfg.get("retry_delay", 1.0),
            config=cfg,
        )
        super().__init__(config=config_obj, event_engine=event_engine)

        self._check_interval = cfg.get(
            "risk_check_interval", ModuleConfig.RISK_CHECK_INTERVAL
        )
        self._threshold_repo = threshold_repo
        self._check_task: Optional[asyncio.Task] = None
        self._last_risk_metrics: Dict[str, Any] = {}

    @property
    def engine_type(self) -> EngineType:
        return EngineType.RISK_MONITOR

    async def _on_initialize(self) -> None:
        logger.info("风险监控引擎初始化")

    async def _on_start(self) -> None:
        logger.info(f"风险监控引擎启动，检查间隔: {self._check_interval}s")
        self._check_task = asyncio.create_task(
            self._check_loop(),
            name="risk_monitor_check",
        )

    async def _on_stop(self) -> None:
        logger.info("风险监控引擎停止")
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
            self._check_task = None

    async def _check_loop(self) -> None:
        while self.record.status.value == "running":
            try:
                await self.check_and_publish()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"风险检查异常: {e}")
                await asyncio.sleep(min(self._check_interval, 10.0))

    async def check_and_publish(self, risk_metrics: Optional[Dict[str, float]] = None
                                ) -> Dict[str, Any]:
        """执行一次风险检查并发布事件"""
        metrics = risk_metrics or self._last_risk_metrics or {}
        if not metrics:
            return {"status": "no_data"}

        evaluation = await RiskMonitorService.evaluate_risk(
            metrics, self._threshold_repo
        )
        self._last_risk_metrics = metrics

        event = RiskMonitorEvent.metrics_updated(metrics)
        await self._publish_event(event.event_type, event.data)

        for breach in evaluation["breaches"]:
            breach_event = RiskMonitorEvent.threshold_breached(
                RiskMonitorEvent.__dataclass_fields__.get(
                    "risk_type", type("", (), {})
                )() if False else type("RM", (), {
                    "risk_type": breach.get("metric", ""),
                    "metric_name": breach.get("metric", ""),
                    "current_value": breach.get("value", 0),
                    "warning_threshold": breach.get("warning_threshold", 0),
                    "critical_threshold": breach.get("critical_threshold", 0),
                    "breached_level": breach.get("level", "warning"),
                })()
            )
            # Simpler approach — construct data directly
            await self._publish_event("monitor.risk.threshold.breached", {
                "risk_type": breach.get("metric", ""),
                "metric_name": breach.get("metric", ""),
                "current_value": breach.get("value", 0),
                "warning_threshold": breach.get("warning_threshold", 0),
                "critical_threshold": breach.get("critical_threshold", 0),
                "breached_level": breach.get("level", "warning"),
            })

            if breach.get("level") == "critical":
                alert_event = RiskMonitorEvent.alert_triggered(
                    risk_type=breach.get("metric", ""),
                    message=f"风险阈值突破: {breach.get('metric')} = {breach.get('value')} "
                            f"(严重阈值: {breach.get('critical_threshold')})",
                    level="critical",
                )
                await self._publish_event(alert_event.event_type, alert_event.data)

        return evaluation

    async def update_risk_metrics(self, metrics: Dict[str, float]) -> None:
        """外部更新风险指标数据（由 handlers 或其他引擎调用）"""
        self._last_risk_metrics.update(metrics)

    async def get_risk_metrics(self) -> Dict[str, Any]:
        """获取最近的风险指标"""
        return dict(self._last_risk_metrics)
