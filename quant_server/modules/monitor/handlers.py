# -*- coding: utf-8 -*-
"""
监控模块 API 处理函数

负责处理 HTTP 请求，调用服务层/仓库/引擎完成业务逻辑。
通过依赖注入获取 session / event_engine / main_engine。
"""

import logging
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from modules.monitor.collectors.system_collector import SystemCollector
from modules.monitor.services.alert_service import AlertService
from modules.monitor.services.strategy_health_service import StrategyHealthService
from modules.monitor.services.system_service import SystemMonitorService

logger = logging.getLogger(__name__)


async def get_strategy_health (
		session: AsyncSession,
		user_id: str,
		strategy_id: str = "",
) -> Dict[str, Any]:
	"""策略健康度检查（基建设计 §三）：输出 running 策略的 healthy/warning/stop 分级。

	- 不传 strategy_id → 返回全部运行中策略
	- 传 strategy_id → 返回单个策略
	"""
	try:
		if strategy_id:
			data = await StrategyHealthService.check_strategy_health(session, strategy_id)
		else:
			data = await StrategyHealthService.check_all(session)
		return {"success": True, "data": data}
	except Exception as e:
		logger.error(f"策略健康检查失败: {e}", exc_info=True)
		return {"success": False, "data": [], "error": str(e)}


async def get_live_summary(session: AsyncSession, user_id: str) -> Dict[str, Any]:
    """实盘监控「三个数」汇总：当日盈亏 / 总回撤 / 可用资金 + 阈值预警。

    数据源：
    - 当日盈亏：account_daily_performance 最新结算日（跨账户聚合）
    - 总回撤：composite_account_snapshots 净值峰值回撤（正深度口径）
    - 可用资金：accounts.available_balance / total_balance

    阈值（与 risk 模块一致）：单日亏损 3%/5%、总回撤 10%/20%、可用资金占比 <10%/<5%。
    """
    from sqlalchemy import text

    def _level(value: float, warn: float, crit: float, higher_is_worse: bool) -> str:
        if higher_is_worse:
            if value >= crit:
                return "critical"
            if value >= warn:
                return "warning"
            return "normal"
        if value <= crit:
            return "critical"
        if value <= warn:
            return "warning"
        return "normal"

    try:
        # 1. 当日盈亏（最新结算日，跨账户聚合）
        daily_pnl_row = (await session.execute(text(
            "SELECT COALESCE(SUM(daily_pnl), 0) "
            "FROM account_daily_performance "
            "WHERE trade_date = (SELECT MAX(trade_date) FROM account_daily_performance)"
        ))).first()
        daily_pnl = float(daily_pnl_row[0] or 0)

        # 2. 总回撤（组合净值峰值回撤，正深度口径）
        navs = [
            float(r[0]) for r in (await session.execute(text(
                "SELECT total_nav FROM composite_account_snapshots ORDER BY trade_date ASC"
            ))).fetchall()
            if r[0] is not None
        ]
        drawdown = 0.0
        peak = 0.0
        for n in navs:
            if n > peak:
                peak = n
            if peak > 0:
                dd = (peak - n) / peak
                if dd > drawdown:
                    drawdown = dd

        # 3. 可用资金
        acct = (await session.execute(text(
            "SELECT COALESCE(SUM(available_balance), 0), COALESCE(SUM(total_balance), 0) FROM accounts"
        ))).first()
        available_cash = float(acct[0] or 0)
        total_balance = float(acct[1] or 0)
        available_cash_ratio = available_cash / total_balance if total_balance > 0 else 0.0
        # 组合级当日收益率（SUM(daily_pnl) / SUM(total_balance)，避免 AVG 被零账户稀释）
        daily_return = daily_pnl / total_balance if total_balance > 0 else 0.0
        daily_loss_pct = -daily_return * 100 if daily_return < 0 else 0.0

        # 4. 阈值评估
        alerts = [
            {"metric": "daily_loss", "label": "当日亏损", "value": round(daily_loss_pct, 2),
             "level": _level(daily_loss_pct, 3.0, 5.0, True),
             "warning_threshold": 3.0, "critical_threshold": 5.0, "unit": "%"},
            {"metric": "drawdown", "label": "总回撤", "value": round(drawdown * 100, 2),
             "level": _level(drawdown * 100, 10.0, 20.0, True),
             "warning_threshold": 10.0, "critical_threshold": 20.0, "unit": "%"},
            {"metric": "available_cash", "label": "可用资金占比", "value": round(available_cash_ratio * 100, 2),
             "level": _level(available_cash_ratio * 100, 10.0, 5.0, False),
             "warning_threshold": 10.0, "critical_threshold": 5.0, "unit": "%"},
        ]
        overall = "normal"
        if any(a["level"] == "critical" for a in alerts):
            overall = "critical"
        elif any(a["level"] == "warning" for a in alerts):
            overall = "warning"

        return {"success": True, "data": {
            "daily_pnl": round(daily_pnl, 2),
            "daily_return": round(daily_return, 6),
            "drawdown": round(drawdown, 6),
            "available_cash": round(available_cash, 2),
            "total_balance": round(total_balance, 2),
            "available_cash_ratio": round(available_cash_ratio, 6),
            "overall_level": overall,
            "alerts": alerts,
        }}
    except Exception as e:
        logger.error(f"实盘监控汇总失败: {e}", exc_info=True)
        return {"success": False, "data": None, "error": str(e)}


async def get_system_metrics (
		session: AsyncSession,
		request,
		user_id: str,
) -> Dict[str, Any]:
	"""获取系统监控指标 — 实时采集 OS 资源"""
	try:
		metrics = await SystemCollector.collect()
		evaluation = await SystemMonitorService.evaluate_metrics(metrics)

		return {
			"success": True,
			"data": {
				"cpu_usage": metrics.cpu_usage,
				"memory_usage": metrics.memory_usage,
				"disk_usage": metrics.disk_usage,
				"network_in": metrics.network_in,
				"network_out": metrics.network_out,
				"thread_count": metrics.thread_count,
				"process_count": metrics.process_count,
				"status": evaluation.get("overall_status", "normal"),
				"alerts": evaluation.get("alerts", []),
			},
		}
	except Exception as e:
		logger.error(f"获取系统指标失败: {e}")
		return {"success": False, "data": {}, "error": str(e)}


async def get_risk_alerts (
		session: AsyncSession,
		request,
		user_id: str,
) -> Dict[str, Any]:
	"""获取风险告警列表"""
	try:
		alert_level = getattr(request, 'alert_level', None)
		alerts = await AlertService.get_active_alerts(
			session=session,
			alert_type="risk_trigger",
			alert_level=alert_level,
		)

		return {
			"success": True,
			"data": alerts,
			"pagination": {"page": 1, "page_size": 20, "total": len(alerts)},
		}
	except Exception as e:
		logger.error(f"获取风险告警失败: {e}")
		return {"success": False, "data": [], "pagination": {}, "error": str(e)}


async def get_business_metrics (
		session: AsyncSession,
		request,
		user_id: str,
) -> Dict[str, Any]:
	"""获取业务指标"""
	try:
		from modules.monitor.services.business_service import BusinessMonitorService

		metrics = await BusinessMonitorService.aggregate_metrics(session=session)
		return {"success": True, "data": metrics}
	except Exception as e:
		logger.error(f"获取业务指标失败: {e}")
		return {"success": False, "data": {}, "error": str(e)}


async def get_alert_history (
		session: AsyncSession,
		request,
		user_id: str,
) -> Dict[str, Any]:
	"""获取告警历史"""
	try:
		alert_level = getattr(request, 'alert_level', None)
		alerts = await AlertService.get_alert_history(
			session=session,
			alert_level=alert_level,
			hours=168,
			limit=100,
		)

		return {
			"success": True,
			"data": alerts,
			"pagination": {"page": 1, "page_size": 20, "total": len(alerts)},
		}
	except Exception as e:
		logger.error(f"获取告警历史失败: {e}")
		return {"success": False, "data": [], "pagination": {}, "error": str(e)}


async def create_alert_rule (
		session: AsyncSession,
		request,
		user_id: str,
) -> Dict[str, Any]:
	"""创建告警规则（阈值）"""
	try:
		from shared.database.repositories.analysis.monitor.monitor_threshold_repo import (
			MonitorThresholdRepository,
		)

		repo = MonitorThresholdRepository(session)

		threshold = await repo.create_threshold(
			metric_name=request.name,
			metric_type=request.alert_type,
			warning_threshold=request.threshold,
			critical_threshold=request.threshold * 1.5,
			description=request.condition.get("description", ""),
			is_active=True,
		)

		return {
			"success": True,
			"data": {
				"id": threshold.id,
				"name": threshold.metric_name,
			},
		}
	except Exception as e:
		logger.error(f"创建告警规则失败: {e}")
		return {"success": False, "data": None, "error": str(e)}


async def update_alert_rule (
		session: AsyncSession,
		rule_id: str,
		request,
		user_id: str,
) -> Dict[str, Any]:
	"""更新告警规则"""
	try:
		from shared.database.repositories.analysis.monitor.monitor_threshold_repo import (
			MonitorThresholdRepository,
		)

		repo = MonitorThresholdRepository(session)

		threshold = await repo.update_threshold(
			threshold_id=rule_id,
			warning_threshold=request.threshold,
			critical_threshold=request.threshold * 1.5,
			description=request.condition.get("description", ""),
		)

		if not threshold:
			raise ValueError(f"规则 {rule_id} 不存在")

		return {
			"success": True,
			"data": {"id": rule_id, "name": request.name},
		}
	except ValueError:
		raise
	except Exception as e:
		logger.error(f"更新告警规则失败: {e}")
		return {"success": False, "data": None, "error": str(e)}


async def delete_alert_rule (
		session: AsyncSession,
		rule_id: str,
		user_id: str,
) -> Dict[str, Any]:
	"""删除告警规则"""
	try:
		from shared.database.repositories.analysis.monitor.monitor_threshold_repo import (
			MonitorThresholdRepository,
		)

		repo = MonitorThresholdRepository(session)
		deleted = await repo.update_threshold(threshold_id=rule_id, is_active=False)

		if not deleted:
			raise ValueError(f"规则 {rule_id} 不存在")

		return {"success": True}
	except ValueError:
		raise
	except Exception as e:
		logger.error(f"删除告警规则失败: {e}")
		return {"success": False, "error": str(e)}


async def trigger_manual_alert (
		session: AsyncSession,
		request,
		event_engine,
		user_id: str,
) -> Dict[str, Any]:
	"""触发手动告警 — 直接创建告警并通过事件引擎广播"""
	try:
		result = await AlertService.create_alert(
			session=session,
			alert_type=request.alert_type,
			alert_level=request.alert_level,
			title=f"[手动] {request.alert_type}",
			message=request.message,
			source_module="manual",
			metadata={"triggered_by": user_id},
		)

		alert_id = result.get("alert_id")
		if alert_id and event_engine:
			from core.events.engine_events import EngineLifecycleEvent

			event = EngineLifecycleEvent(
				engine_name="monitor",
				lifecycle_stage="monitor.alert.created",
				engine_status="running",
				details={
					"alert_id": alert_id,
					"alert_type": request.alert_type,
					"alert_level": request.alert_level,
					"title": request.message,
					"message": request.message,
				},
				priority="high",
				source="api:manual_alert",
			)
			await event_engine.put(event)

		return {"success": True, "data": {"alert_id": alert_id}}
	except Exception as e:
		logger.error(f"手动触发告警失败: {e}")
		return {"success": False, "data": {}, "error": str(e)}


async def get_health_status (
		session: AsyncSession,
		main_engine,
		user_id: str,
) -> Dict[str, Any]:
	"""获取系统综合健康状态"""
	try:
		result = await SystemMonitorService.get_health_status(
			main_engine=main_engine,
		)
		return {"success": True, "data": result}
	except Exception as e:
		logger.error(f"获取健康状态失败: {e}")
		return {"success": False, "data": {"status": "error", "error": str(e)}}


async def get_performance_stats (
		session: AsyncSession,
		event_engine,
		user_id: str,
) -> Dict[str, Any]:
	"""获取性能统计 — 从事件引擎采集延迟/吞吐指标"""
	try:
		stats: Dict[str, Any] = {}
		if event_engine:
			engine_stats = event_engine.get_statistics()
			stats = {
				"queue_size": engine_stats.get("current_queue_size", 0),
				"total_events": engine_stats.get("total_events", 0),
				"failed_events": engine_stats.get("failed_events", 0),
				"avg_latency_ms": engine_stats.get("avg_processing_time_ms", 0),
				"worker_count": engine_stats.get("worker_count", 0),
			}

		return {"success": True, "data": stats}
	except Exception as e:
		logger.error(f"获取性能统计失败: {e}")
		return {"success": False, "data": {}, "error": str(e)}


async def check_monitor_module_health (session: AsyncSession) -> Dict[str, Any]:
	"""检查监控模块自身健康状态"""
	try:
		from datetime import datetime, timezone

		active_alerts = await AlertService.get_alert_summary(session)

		return {
			"status": "healthy",
			"module": "monitor",
			"active_alerts": active_alerts,
			"timestamp": datetime.now(timezone.utc).isoformat(),
		}
	except Exception as e:
		logger.error(f"监控模块健康检查失败: {e}")
		return {
			"status": "degraded",
			"module": "monitor",
			"error": str(e),
		}
