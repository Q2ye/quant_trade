# -*- coding: utf-8 -*-
"""
指标计算工具

无状态工具类，提供各类监控指标的计算、比较和格式化功能。
"""

from typing import Any, Dict, List, Optional, Tuple

from modules.monitor.constants import (
	DEFAULT_THRESHOLDS,
	AlertLevel,
)


class MetricUtils:
	"""指标工具类 — 纯静态方法，无状态"""

	@staticmethod
	def compare_with_threshold (value: float, metric_key: str,
	                            custom_thresholds: Optional[Dict[str, Any]] = None
	                            ) -> Tuple[str, float, float]:
		"""
		将指标值与阈值比较，返回 (level, warning_threshold, critical_threshold)

		level: "normal" | "warning" | "critical"
		"""
		thresholds = custom_thresholds or DEFAULT_THRESHOLDS
		config = thresholds.get(metric_key, {})

		warning = config.get("warning", 80.0)
		critical = config.get("critical", 95.0)

		if value >= critical:
			return AlertLevel.CRITICAL.value, warning, critical
		elif value >= warning:
			return AlertLevel.WARNING.value, warning, critical
		return "normal", warning, critical

	@staticmethod
	def compare_lower_is_worse (value: float, metric_key: str,
	                            custom_thresholds: Optional[Dict[str, Any]] = None
	                            ) -> Tuple[str, float, float]:
		"""
		对于越低越差的指标（如剩余资金比例），warning/critical 阈值代表下限
		"""
		thresholds = custom_thresholds or DEFAULT_THRESHOLDS
		config = thresholds.get(metric_key, {})

		warning = config.get("warning", 20.0)
		critical = config.get("critical", 5.0)

		if value <= critical:
			return AlertLevel.CRITICAL.value, warning, critical
		elif value <= warning:
			return AlertLevel.WARNING.value, warning, critical
		return "normal", warning, critical
