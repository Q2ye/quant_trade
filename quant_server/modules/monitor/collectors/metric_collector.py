# -*- coding: utf-8 -*-
"""
指标采集器

提供通用的指标采集框架，支持注册自定义采集函数，
按周期采集并缓存最近 N 次指标值用于趋势分析。
"""

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricCollector:
    """通用指标采集器 — 无状态存储委托给 Engine"""

    def __init__(self, max_history: int = 100):
        self._history: Dict[str, deque] = {}
        self._max_history = max_history
        self._last_collect: Dict[str, datetime] = {}

    def record(self, metric_name: str, value: float, unit: str = "") -> None:
        """记录单个指标值"""
        if metric_name not in self._history:
            self._history[metric_name] = deque(maxlen=self._max_history)
        self._history[metric_name].append({
            "value": value,
            "unit": unit,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._last_collect[metric_name] = datetime.now(timezone.utc)

    def record_batch(self, metrics: Dict[str, Any]) -> None:
        """批量记录指标"""
        for name, entry in metrics.items():
            if isinstance(entry, (int, float)):
                self.record(name, float(entry))
            elif isinstance(entry, dict):
                self.record(name, float(entry.get("value", 0)), entry.get("unit", ""))

    def get_history(self, metric_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """获取指标历史"""
        if metric_name not in self._history:
            return []
        return list(self._history[metric_name])[-limit:]

    def get_latest(self, metric_name: str) -> Optional[Dict[str, Any]]:
        """获取最新指标值"""
        history = self.get_history(metric_name, limit=1)
        return history[0] if history else None

    def get_all_latest(self) -> Dict[str, Any]:
        """获取所有指标的最新值"""
        return {
            name: self.get_latest(name)
            for name in self._history
        }

    def get_trend(self, metric_name: str, window: int = 10) -> Dict[str, Any]:
        """获取指标趋势 — 变化方向与幅度"""
        history = self.get_history(metric_name, limit=window)
        if len(history) < 2:
            return {"direction": "stable", "change_pct": 0.0}

        values = [h["value"] for h in history]
        first = values[0]
        last = values[-1]

        change_pct = ((last - first) / first * 100) if first != 0 else 0.0

        if change_pct > 5:
            direction = "up"
        elif change_pct < -5:
            direction = "down"
        else:
            direction = "stable"

        return {
            "direction": direction,
            "change_pct": round(change_pct, 2),
            "first": first,
            "last": last,
            "samples": len(values),
        }

    def reset(self) -> None:
        """重置所有历史数据"""
        self._history.clear()
        self._last_collect.clear()
