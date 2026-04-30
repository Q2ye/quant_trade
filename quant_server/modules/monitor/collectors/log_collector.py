# -*- coding: utf-8 -*-
"""
日志采集器

采集和聚合模块运行日志中的错误、警告信息，
用于监控模块自身的运行状态追踪。
"""

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LogCollector:
    """日志采集器 — 无状态，内存中维护最近日志缓冲区"""

    def __init__(self, max_entries: int = 500):
        self._entries: deque = deque(maxlen=max_entries)
        self._error_count: int = 0
        self._warning_count: int = 0

    def add(self, level: str, message: str, module: str = "",
            extra: Optional[Dict[str, Any]] = None) -> None:
        """添加日志条目"""
        entry = {
            "level": level,
            "message": message,
            "module": module,
            "extra": extra or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._entries.append(entry)

        if level.upper() in ("ERROR", "CRITICAL"):
            self._error_count += 1
        elif level.upper() == "WARNING":
            self._warning_count += 1

    def get_recent(self, limit: int = 50,
                   level: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取最近日志"""
        entries = list(self._entries)
        if level:
            entries = [e for e in entries if e["level"].upper() == level.upper()]
        return entries[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """获取日志统计"""
        entries = list(self._entries)
        level_counts: Dict[str, int] = {}
        module_counts: Dict[str, int] = {}

        for entry in entries:
            lvl = entry["level"]
            level_counts[lvl] = level_counts.get(lvl, 0) + 1

            mod = entry.get("module", "unknown")
            module_counts[mod] = module_counts.get(mod, 0) + 1

        return {
            "total_entries": len(entries),
            "error_count": self._error_count,
            "warning_count": self._warning_count,
            "by_level": level_counts,
            "by_module": module_counts,
            "oldest_entry": entries[0]["timestamp"] if entries else None,
            "newest_entry": entries[-1]["timestamp"] if entries else None,
        }

    def reset(self) -> None:
        """重置缓冲区"""
        self._entries.clear()
        self._error_count = 0
        self._warning_count = 0
