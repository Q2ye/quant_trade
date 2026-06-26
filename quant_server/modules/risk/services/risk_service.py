# -*- coding: utf-8 -*-
"""
风控服务

无状态服务，提供风险评估、阈值比较和风险摘要计算。
被 RiskEngine 和 API handlers 调用。
"""

import logging
from typing import Any, Dict, List, Optional

from modules.risk.constants import RiskLevel

logger = logging.getLogger(__name__)

# 指标名 → 比较方式：默认 higher_is_worse=True（值越大越危险）
_METRIC_THRESHOLD_MAP = {
    "drawdown": ("risk.drawdown", True),
    "position_ratio": ("risk.position_ratio", True),
    "var": ("risk.var", True),
    "leverage_ratio": ("risk.leverage_ratio", True),
    "volatility": ("risk.volatility", True),
    "max_loss": ("risk.max_loss", True),
    "sharpe_ratio": ("risk.sharpe_ratio", False),  # lower is worse
}


class RiskService:
    """风控服务 — 无状态纯计算"""

    @staticmethod
    async def evaluate_risk(
        risk_metrics: Dict[str, float],
        threshold_repo=None,
    ) -> Dict[str, Any]:
        """
        评估风险指标，与阈值比较。

        Args:
            risk_metrics: {"drawdown": 5.2, "position_ratio": 65.0, ...}
            threshold_repo: MonitorThresholdRepository（可选）

        Returns:
            {"breaches": [...], "overall_risk_level": "normal"|"warning"|"critical",
             "metrics": {...}}
        """
        breaches: List[Dict[str, Any]] = []
        overall_level = RiskLevel.NORMAL.value

        for metric_name, value in risk_metrics.items():
            key, higher_is_worse = _METRIC_THRESHOLD_MAP.get(
                metric_name, (f"risk.{metric_name}", True)
            )

            level, warn_thr, crit_thr = RiskService._compare(
                value, key, higher_is_worse
            )

            breach = {
                "metric": metric_name,
                "value": value,
                "level": level,
                "warning_threshold": warn_thr,
                "critical_threshold": crit_thr,
            }

            # 查数据库阈值
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

            if breach["level"] != RiskLevel.NORMAL.value:
                breaches.append(breach)
                if breach["level"] == RiskLevel.CRITICAL.value or (
                    breach["level"] == RiskLevel.WARNING.value
                    and overall_level == RiskLevel.NORMAL.value
                ):
                    overall_level = breach["level"]

        return {
            "breaches": breaches,
            "overall_risk_level": overall_level,
            "metrics": risk_metrics,
        }

    @staticmethod
    def _compare(
        value: float,
        metric_key: str,
        higher_is_worse: bool = True,
    ):
        """
        将值与内置默认阈值比较。

        内置阈值（可通过阈值仓库覆盖）：
        - drawdown: warn 5%, critical 10%
        - position_ratio: warn 70%, critical 90%
        - var: warn 2%, critical 5%
        - leverage_ratio: warn 100%, critical 150%
        - volatility: warn 20%, critical 40%
        - max_loss: warn 3%, critical 8%
        - sharpe_ratio: warn 1.0, critical 0.5 (lower is worse)
        """
        defaults = {
            "risk.drawdown": (5.0, 10.0),
            "risk.position_ratio": (70.0, 90.0),
            "risk.var": (2.0, 5.0),
            "risk.leverage_ratio": (100.0, 150.0),
            "risk.volatility": (20.0, 40.0),
            "risk.max_loss": (3.0, 8.0),
            "risk.sharpe_ratio": (1.0, 0.5),
        }
        warn, crit = defaults.get(metric_key, (80.0, 95.0))

        if higher_is_worse:
            if value >= crit:
                return RiskLevel.CRITICAL.value, warn, crit
            if value >= warn:
                return RiskLevel.WARNING.value, warn, crit
            return RiskLevel.NORMAL.value, warn, crit
        else:
            # lower is worse (e.g., sharpe_ratio)
            if value <= crit:
                return RiskLevel.CRITICAL.value, warn, crit
            if value <= warn:
                return RiskLevel.WARNING.value, warn, crit
            return RiskLevel.NORMAL.value, warn, crit

    @staticmethod
    async def check_position_limits(
        position_data: Dict[str, Any],
        threshold_repo=None,
    ) -> Dict[str, Any]:
        """检查持仓限制"""
        alerts: List[Dict[str, Any]] = []

        position_ratio = position_data.get("position_ratio", 0)
        single_position_max = position_data.get("single_position_max", 0)

        if position_ratio > 80:
            alerts.append({
                "type": "total_position_high",
                "level": RiskLevel.WARNING.value,
                "message": f"总仓位比例过高: {position_ratio}%",
                "current": position_ratio,
            })
            if position_ratio > 95:
                alerts[-1]["level"] = RiskLevel.CRITICAL.value

        if single_position_max > 30:
            alerts.append({
                "type": "single_position_high",
                "level": RiskLevel.WARNING.value,
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
        evaluation = await RiskService.evaluate_risk(risk_metrics, threshold_repo)

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
