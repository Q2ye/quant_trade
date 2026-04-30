# -*- coding: utf-8 -*-
"""
健康检查管理器

协调各模块和引擎的健康检查，汇总健康状态。
被 SystemMonitorEngine 调用。
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthManager:
    """健康检查管理器"""

    def __init__(self):
        self._check_history: List[Dict[str, Any]] = []
        self._max_history = 100

    async def check_component(self, name: str,
                              check_fn=None,
                              timeout: float = 10.0) -> Dict[str, Any]:
        """检查单个组件健康状态"""
        start = time.monotonic()
        try:
            if check_fn:
                if asyncio.iscoroutinefunction(check_fn):
                    result = await asyncio.wait_for(check_fn(), timeout=timeout)
                else:
                    result = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, check_fn),
                        timeout=timeout,
                    )
            else:
                result = None

            duration_ms = (time.monotonic() - start) * 1000

            status = "healthy"
            message = ""
            if isinstance(result, dict):
                status = result.get("status", "healthy")
                message = result.get("message", "")

            return {
                "component": name,
                "status": status,
                "message": message,
                "duration_ms": round(duration_ms, 2),
                "details": result if isinstance(result, dict) else {},
            }
        except asyncio.TimeoutError:
            return {
                "component": name,
                "status": "unhealthy",
                "message": f"健康检查超时 ({timeout}s)",
                "duration_ms": round((time.monotonic() - start) * 1000, 2),
                "details": {},
            }
        except Exception as e:
            return {
                "component": name,
                "status": "unhealthy",
                "message": str(e),
                "duration_ms": round((time.monotonic() - start) * 1000, 2),
                "details": {},
            }

    async def run_all_checks(
        self,
        components: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        运行所有组件健康检查

        Args:
            components: {"component_name": check_fn_or_None, ...}
            timeout: 总超时时间

        Returns:
            {"overall_status": "healthy"|"degraded"|"unhealthy", "checks": [...]}
        """
        tasks = []
        names = []

        for name, check_fn in components.items():
            names.append(name)
            tasks.append(self.check_component(name, check_fn, timeout=min(timeout, 10.0)))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        checks = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                checks.append({
                    "component": names[i],
                    "status": "unhealthy",
                    "message": str(result),
                })
            else:
                checks.append(result)

        # 判定总体状态
        statuses = [c["status"] for c in checks]
        if all(s == "healthy" for s in statuses):
            overall = "healthy"
        elif any(s == "unhealthy" for s in statuses):
            overall = "unhealthy"
        else:
            overall = "degraded"

        summary = {
            "overall_status": overall,
            "checks": checks,
            "healthy_count": statuses.count("healthy"),
            "unhealthy_count": statuses.count("unhealthy"),
            "degraded_count": statuses.count("degraded"),
        }

        self._check_history.append(summary)
        if len(self._check_history) > self._max_history:
            self._check_history = self._check_history[-self._max_history:]

        return summary

    def get_check_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取健康检查历史"""
        return self._check_history[-limit:]

    async def check_database(self, session=None) -> Dict[str, Any]:
        """检查数据库连接"""
        if session is None:
            return {"status": "unknown", "message": "无数据库会话"}

        try:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
            return {"status": "healthy", "message": "数据库连接正常"}
        except Exception as e:
            return {"status": "unhealthy", "message": f"数据库连接失败: {e}"}

    async def check_event_engine(self, event_engine=None) -> Dict[str, Any]:
        """检查事件引擎状态"""
        if event_engine is None:
            return {"status": "unknown", "message": "无事件引擎"}

        try:
            stats = event_engine.get_statistics()
            queue_size = stats.get("current_queue_size", 0)
            failed = stats.get("failed_events", 0)

            if failed > 100:
                return {"status": "unhealthy",
                        "message": f"事件失败数过高: {failed}"}
            elif queue_size > 5000:
                return {"status": "degraded",
                        "message": f"事件队列积压: {queue_size}"}
            return {"status": "healthy", "message": f"队列: {queue_size}, 已处理: {stats.get('processed_events', 0)}"}
        except Exception as e:
            return {"status": "unhealthy", "message": str(e)}
