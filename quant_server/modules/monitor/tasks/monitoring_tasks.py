# -*- coding: utf-8 -*-
"""
监控定时任务

供系统任务调度器调用的独立函数，触发各监控引擎的检查周期。
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def scheduled_system_check (main_engine=None) -> Dict[str, Any]:
	"""定时系统指标采集 — 由任务调度器周期性调用"""
	try:
		if main_engine is None:
			return {"status": "skipped", "reason": "no main_engine"}

		engine = await main_engine.get_engine("system_monitor")
		if engine is None:
			return {"status": "skipped", "reason": "engine not found"}

		result = await engine.collect_and_publish()
		logger.info(f"定时系统检查完成: {result.get('status', 'unknown')}")
		return result
	except Exception as e:
		logger.error(f"定时系统检查失败: {e}")
		return {"status": "error", "error": str(e)}


async def scheduled_risk_check (
		main_engine=None,
		risk_metrics: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
	"""定时风险指标检查 — 由任务调度器周期性调用"""
	try:
		if main_engine is None:
			return {"status": "skipped", "reason": "no main_engine"}

		engine = await main_engine.get_engine("risk_monitor")
		if engine is None:
			return {"status": "skipped", "reason": "engine not found"}

		result = await engine.check_and_publish(risk_metrics)
		logger.info(f"定时风险检查完成: {len(result.get('breaches', []))} 个突破")
		return result
	except Exception as e:
		logger.error(f"定时风险检查失败: {e}")
		return {"status": "error", "error": str(e)}


async def scheduled_business_aggregation (main_engine=None) -> Dict[str, Any]:
	"""定时业务指标聚合 — 由任务调度器周期性调用"""
	try:
		if main_engine is None:
			return {"status": "skipped", "reason": "no main_engine"}

		engine = await main_engine.get_engine("business_monitor")
		if engine is None:
			return {"status": "skipped", "reason": "engine not found"}

		result = await engine.aggregate_and_publish()
		logger.info("定时业务指标聚合完成")
		return result
	except Exception as e:
		logger.error(f"定时业务指标聚合失败: {e}")
		return {"status": "error", "error": str(e)}


async def scheduled_health_check (main_engine=None, event_engine=None) -> Dict[str, Any]:
	"""定时综合健康检查 — 由任务调度器周期性调用"""
	try:
		from quant_server.modules.monitor.services.system_service import SystemMonitorService

		result = await SystemMonitorService.get_health_status(
			main_engine=main_engine,
			event_engine=event_engine,
		)
		logger.info(f"定时健康检查完成: {result.get('status', 'unknown')}")
		return result
	except Exception as e:
		logger.error(f"定时健康检查失败: {e}")
		return {"status": "error", "error": str(e)}
