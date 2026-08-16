# -*- coding: utf-8 -*-
"""进程内 SWR 缓存（stale-while-revalidate）：过期返回旧值 + 后台重算

解决"轮询撞上缓存过期 → 同步重算阻塞 3~6s"的问题：
- 缓存未过期 → 直接返回；
- 缓存过期且无在途任务 → 返回旧值 + asyncio.create_task 后台重算；
- 缓存过期但已有在途任务 → 直接返回旧值；
- 首次请求（无旧值）→ 同步计算（仅发生在进程重启后的第一次）。

单 worker（config.yaml workers=1）下语义正确。
"""
import asyncio
import time
from typing import Any, Dict, Optional, Tuple


class SwrCache:
    def __init__(self, ttl: float = 300.0):
        self.ttl = ttl
        self._entries: Dict[str, Dict[str, Any]] = {}

    def probe(self, key: str) -> Tuple[Optional[Any], bool]:
        """返回 (可立即返回的旧值, 是否需要发起后台重算)"""
        e = self._entries.get(key)
        if e is None:
            return None, False
        if time.time() - e["ts"] < e.get("ttl", self.ttl):
            return e["value"], False
        task = e.get("task")
        if task is not None and not task.done():
            return e["value"], False  # 已有后台任务在重算
        return e["value"], True

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """写入缓存；ttl 覆盖默认值（如样本不足结果用更短 TTL 以便快速自愈）"""
        e = self._entries.get(key)
        if e is None:
            e = {"ts": 0.0, "value": None, "task": None, "ttl": self.ttl}
            self._entries[key] = e
        e["ts"] = time.time()
        e["value"] = value
        e["ttl"] = ttl if ttl is not None else self.ttl

    def set_task(self, key: str, task: "asyncio.Task") -> None:
        e = self._entries.get(key)
        if e is not None:
            e["task"] = task
