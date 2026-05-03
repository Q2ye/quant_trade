# -*- coding: utf-8 -*-
"""
任务服务
负责定时任务的业务逻辑：创建、查询、暂停、恢复、删除任务。
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.repositories.system.config.config_repo import ConfigRepository

logger = logging.getLogger(__name__)


class TaskService:
    """任务服务 — 定时任务业务逻辑"""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._config_repo = ConfigRepository(session)
        # 内存任务注册表（生产环境应持久化到数据库 system_tasks 表）
        self._tasks: Dict[str, Dict[str, Any]] = {}

    async def list_tasks(self) -> List[Dict[str, Any]]:
        """列出所有注册任务"""
        return [
            {
                "task_id": task_id,
                "name": task["name"],
                "task_type": task.get("task_type", ""),
                "cron_expression": task.get("cron_expression", ""),
                "enabled": task.get("enabled", True),
                "last_run": task.get("last_run"),
                "next_run": task.get("next_run"),
                "last_status": task.get("last_status", ""),
            }
            for task_id, task in self._tasks.items()
        ]

    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务详情"""
        task = self._tasks.get(task_id)
        if task is None:
            return None
        return {
            "task_id": task_id,
            **{k: v for k, v in task.items() if k != "handler"},
        }

    async def register_task(
        self,
        task_id: str,
        name: str,
        task_type: str,
        cron_expression: str,
        handler: Callable[..., Any],
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """注册新任务"""
        self._tasks[task_id] = {
            "name": name,
            "task_type": task_type,
            "cron_expression": cron_expression,
            "enabled": True,
            "handler": handler,
            "params": params or {},
            "last_run": None,
            "next_run": None,
            "last_status": "",
            "created_at": datetime.now(),
        }
        logger.info(f"任务已注册: {task_id} ({name})")
        return await self.get_task(task_id)

    async def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        task = self._tasks.get(task_id)
        if task is None:
            return False
        task["enabled"] = False
        logger.info(f"任务已暂停: {task_id}")
        return True

    async def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        task = self._tasks.get(task_id)
        if task is None:
            return False
        task["enabled"] = True
        logger.info(f"任务已恢复: {task_id}")
        return True

    async def remove_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id not in self._tasks:
            return False
        del self._tasks[task_id]
        logger.info(f"任务已删除: {task_id}")
        return True

    async def update_task_status(
        self, task_id: str, status: str, error: str = ""
    ) -> None:
        """更新任务最近一次执行状态"""
        task = self._tasks.get(task_id)
        if task:
            task["last_run"] = datetime.now()
            task["last_status"] = status
            if error:
                task["last_error"] = error

    async def get_enabled_tasks(self) -> List[Dict[str, Any]]:
        """获取所有启用的任务（供调度器使用）"""
        return [
            {"task_id": tid, **{k: v for k, v in t.items()}}
            for tid, t in self._tasks.items()
            if t.get("enabled", True)
        ]
