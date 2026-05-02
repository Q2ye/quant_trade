# -*- coding: utf-8 -*-
"""
系统监控服务

无状态服务，处理系统指标评估、阈值比较和健康状态判断。
被 SystemMonitorEngine 调用。
"""

import logging
from typing import Any, Dict

from quant_server.modules.monitor.collectors.system_collector import SystemCollector
from quant_server.modules.monitor.events.types import SystemMetricsData
from quant_server.modules.monitor.utils.metric_utils import MetricUtils

logger = logging.getLogger(__name__)


class SystemMonitorService:
	"""系统监控服务 — 无状态"""

	@staticmethod
	async def evaluate_metrics (
			metrics: SystemMetricsData,
			threshold_repo=None,  # Optional[MonitorThresholdRepository]
	) -> Dict[str, Any]:
		"""
		评估系统指标，返回分级结果

		Returns:
			{
				"metrics": {...},
				"alerts": [{"metric": str, "level": str, "value": float, "threshold": float}],
				"overall_status": "normal" | "warning" | "critical"
			}
		"""
		alerts = []
		overall_status = "normal"

		checks = [
			("system.cpu_usage", metrics.cpu_usage),
			("system.memory_usage", metrics.memory_usage),
			("system.disk_usage", metrics.disk_usage),
		]

		for key, value in checks:
			level, warn_thr, crit_thr = MetricUtils.compare_with_threshold(value, key)
			if level != "normal":
				alerts.append({
					"metric": key,
					"level": level,
					"value": value,
					"warning_threshold": warn_thr,
					"critical_threshold": crit_thr,
				})
				if level == "critical" or (level == "warning" and overall_status == "normal"):
					overall_status = level

			# 如果有 threshold_repo，验证值
			if threshold_repo:
				try:
					status, msg = await threshold_repo.validate_value(
						"system", key.replace("system.", ""), value
					)
					if status in ("warning", "critical"):
						logger.warning(f"阈值验证触发: {key} = {value} -> {status}: {msg}")
				except Exception:
					pass

		return {
			"metrics": {
				"cpu_usage": metrics.cpu_usage,
				"memory_usage": metrics.memory_usage,
				"disk_usage": metrics.disk_usage,
				"network_in": metrics.network_in,
				"network_out": metrics.network_out,
				"process_count": metrics.process_count,
				"thread_count": metrics.thread_count,
			},
			"alerts": alerts,
			"overall_status": overall_status,
		}

	@staticmethod
	async def get_health_status (
			main_engine=None,
			event_engine=None,
	) -> Dict[str, Any]:
		"""
		获取系统综合健康状态

		Args:
			main_engine: 主引擎实例（可选，用于获取所有引擎状态）
			event_engine: 事件引擎实例（可选，用于获取事件引擎状态）

		Returns:
			健康状态汇总
		"""
		components: Dict[str, Any] = {}
		all_healthy = True

		# 检查事件引擎
		if event_engine:
			try:
				stats = event_engine.get_statistics()
				evt_status = "healthy" if stats.get("failed_events", 0) < 10 else "degraded"
				components["event_engine"] = {
					"status": evt_status,
					"queue_size": stats.get("current_queue_size", 0),
					"total_events": stats.get("total_events", 0),
					"failed_events": stats.get("failed_events", 0),
					"avg_latency_ms": stats.get("avg_processing_time_ms", 0),
				}
				if evt_status != "healthy":
					all_healthy = False
			except Exception as e:
				components["event_engine"] = {"status": "error", "error": str(e)}
				all_healthy = False

		# 检查主引擎及其子引擎
		if main_engine:
			try:
				system_status = await main_engine.get_system_status()
				engines_info = system_status.get("engines", {})
				components["main_engine"] = {
					"status": "healthy",
					"engine_count": engines_info.get("total", 0),
					"system_mode": system_status.get("events", {}).get("mode", "unknown"),
					"uptime": system_status.get("events", {}).get("status", {}).get("uptime", 0),
				}
				components["engines_detail"] = engines_info
			except Exception as e:
				components["main_engine"] = {"status": "error", "error": str(e)}
				all_healthy = False

		# 采集系统资源
		try:
			metrics = await SystemCollector.collect()
			evaluation = await SystemMonitorService.evaluate_metrics(metrics)
			components["system_resources"] = {
				"status": evaluation["overall_status"],
				"metrics": evaluation["metrics"],
			}
			if evaluation["overall_status"] == "critical":
				all_healthy = False
		except Exception as e:
			components["system_resources"] = {"status": "error", "error": str(e)}
			all_healthy = False

		return {
			"status": "healthy" if all_healthy else "degraded",
			"components": components,
			"timestamp": SystemMetricsData().timestamp.isoformat(),
		}
