# -*- coding: utf-8 -*-
"""
风险监控服务

无状态服务，处理风险评估、阈值比较和风险警报生成。
被 RiskMonitorEngine 调用。
"""

import logging
from typing import Any, Dict, List, Optional

from quant_server.modules.monitor.events.types import RiskMetricsData
from quant_server.modules.monitor.utils.metric_utils import MetricUtils
from quant_server.modules.monitor.constants import AlertLevel

logger = logging.getLogger(__name__)


class RiskMonitorService:
    """风险监控服务 — 无状态"""

    @staticmethod
    async def evaluate_risk(
        risk_metrics: Dict[str, float],
        threshold_repo=None,
    ) -> Dict[str, Any]:
        """
        评估风险指标

        Args:
            risk_metrics: {"drawdown": 5.2, "position_ratio": 65.0, ...}
            threshold_repo: MonitorThresholdRepository（可选）

        Returns:
            {"breaches": [...], "overall_risk_level": "normal"|"warning"|"critical"}
        """
        breaches = []
        overall_level = "normal"

        metric_key_map = {
            "drawdown": "risk.drawdown",
            "position_ratio": "risk.position_ratio",
            "var": "risk.var",
            "leverage_ratio": "risk.leverage_ratio",
            "volatility": "risk.volatility",
            "max_loss": "risk.max_loss",
            "sharpe_ratio": "risk.sharpe_ratio",
        }

        for metric_name, value in risk_metrics.items():
            key = metric_key_map.get(metric_name, f"risk.{metric_name}")

            if metric_name in ("sharpe_ratio",):
                level, warn_thr, crit_thr = MetricUtils.compare_lower_is_worse(value, key)
            else:
                level, warn_thr, crit_thr = MetricUtils.compare_with_threshold(value, key)

            breach = {
                "metric": metric_name,
                "value": value,
                "level": level,
                "warning_threshold": warn_thr,
                "critical_threshold": crit_thr,
            }

            # 查询数据库阈值
            if threshold_repo:
                try:
                    status, msg = await threshold_repo.validate_value(
                        "risk", metric_name, value
                    )
                    if status in ("warning", "critical"):
                        breach["level"] = status
                        breach["db_message"] = msg
                except Exception:
                    pass

            if breach["level"] != "normal":
                breaches.append(breach)
                if breach["level"] == "critical" or (
                    breach["level"] == "warning" and overall_level == "normal"
                ):
                    overall_level = breach["level"]

        return {
            "breaches": breaches,
            "overall_risk_level": overall_level,
            "metrics": risk_metrics,
        }

    @staticmethod
    async def check_position_limits(
        position_data: Dict[str, Any],
        threshold_repo=None,
    ) -> Dict[str, Any]:
        """检查持仓限制"""
        alerts = []

        position_ratio = position_data.get("position_ratio", 0)
        single_position_max = position_data.get("single_position_max", 0)

        if position_ratio > 80:
            alerts.append({
                "type": "total_position_high",
                "level": AlertLevel.WARNING.value,
                "message": f"总仓位比例过高: {position_ratio}%",
                "current": position_ratio,
            })
            if position_ratio > 95:
                alerts[-1]["level"] = AlertLevel.CRITICAL.value

        if single_position_max > 30:
            alerts.append({
                "type": "single_position_high",
                "level": AlertLevel.WARNING.value,
                "message": f"单一持仓比例过高: {single_position_max}%",
                "current": single_position_max,
            })

        if threshold_repo:
            for alert in alerts:
                try:
                    status, msg = await threshold_repo.validate_value(
                        "risk", alert["type"], alert["current"]
                    )
                    if status in ("warning", "critical"):
                        alert["level"] = status
                except Exception:
                    pass

        return {
            "alerts": alerts,
            "has_alerts": len(alerts) > 0,
            "position_data": position_data,
        }

    @staticmethod
    async def calculate_risk_summary(
        risk_metrics: Dict[str, float],
        threshold_repo=None,
    ) -> Dict[str, Any]:
        """计算风险摘要"""
        evaluation = await RiskMonitorService.evaluate_risk(risk_metrics, threshold_repo)

        return {
            "overall_risk_level": evaluation["overall_risk_level"],
            "breach_count": len(evaluation["breaches"]),
            "breaches": evaluation["breaches"],
            "metrics_summary": {
                "drawdown": risk_metrics.get("drawdown", 0),
                "sharpe": risk_metrics.get("sharpe_ratio", 0),
                "volatility": risk_metrics.get("volatility", 0),
                "var": risk_metrics.get("var", 0),
            },
        }
