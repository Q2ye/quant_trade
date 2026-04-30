# -*- coding: utf-8 -*-
"""
指标计算工具

无状态工具类，提供各类监控指标的计算、比较和格式化功能。
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from quant_server.modules.monitor.constants import (
    DEFAULT_THRESHOLDS,
    AlertLevel,
)


class MetricUtils:
    """指标工具类 — 纯静态方法，无状态"""

    @staticmethod
    def compare_with_threshold(value: float, metric_key: str,
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
    def compare_lower_is_worse(value: float, metric_key: str,
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

    @staticmethod
    def calculate_rate(current: float, previous: float) -> float:
        """计算变化率 (%)"""
        if previous == 0:
            return 0.0
        return round((current - previous) / previous * 100, 2)

    @staticmethod
    def calculate_moving_average(values: List[float], window: int = 5) -> List[float]:
        """计算移动平均"""
        if len(values) < window:
            return [sum(values) / len(values)] if values else []
        result = []
        for i in range(len(values) - window + 1):
            result.append(round(sum(values[i:i + window]) / window, 4))
        return result

    @staticmethod
    def format_metric_value(value: float, unit: str = "") -> str:
        """格式化指标值"""
        if unit == "%":
            return f"{value:.2f}%"
        elif unit == "ms":
            return f"{value:.2f}ms"
        elif unit == "MB":
            return f"{value:.2f}MB"
        elif value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        elif value >= 1_000:
            return f"{value / 1_000:.2f}K"
        return f"{value:.2f}"

    @staticmethod
    def latency_percentile(latencies_ms: List[float],
                           percentiles: List[int] = None) -> Dict[str, float]:
        """计算延迟分位数"""
        if not latencies_ms:
            return {}
        percentiles = percentiles or [50, 90, 95, 99]
        sorted_lat = sorted(latencies_ms)
        n = len(sorted_lat)
        result = {}
        for p in percentiles:
            idx = int(n * p / 100)
            idx = min(idx, n - 1)
            result[f"p{p}"] = round(sorted_lat[idx], 2)
        result["avg"] = round(sum(sorted_lat) / n, 2)
        result["max"] = round(sorted_lat[-1], 2)
        result["min"] = round(sorted_lat[0], 2)
        return result
