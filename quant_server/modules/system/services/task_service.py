# -*- coding: utf-8 -*-
"""
任务服务
负责定时任务的业务逻辑：创建、查询、暂停、恢复、删除任务。

元数据持久化到 ScheduledTaskRepository（DB），handler 函数注册在内存中。
"""
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.repositories.system.ops.scheduled_task_repo import (
    ScheduledTaskRepository,
)

logger = logging.getLogger(__name__)


class TaskService:
    """任务服务 — 定时任务元数据 DB 持久化 + handler 内存注册"""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._repo = ScheduledTaskRepository(session)
        # 仅 handler 函数保留在内存（Callable 无法序列化到 DB）
        self._handlers: Dict[str, Callable[..., Any]] = {}
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        """延迟加载：首次访问时从 DB 同步任务元数据到内存索引"""
        if self._loaded:
            return
        try:
            tasks = await self._repo.get_many(is_deleted=False)
            for t in tasks:
                # 仅建立任务 ID → enabled 状态的轻量索引
                pass  # DB 是主数据源，每次查询直接访问 DB
            self._loaded = True
        except Exception as e:
            logger.error(f"加载持久化任务失败（使用内存模式）: {e}")

    async def list_tasks(self) -> List[Dict[str, Any]]:
        """列出所有未删除的任务"""
        await self._ensure_loaded()
        try:
            tasks = await self._repo.get_many(is_deleted=False)
            return [self._orm_to_dict(t) for t in tasks]
        except Exception as e:
            logger.error(f"查询任务列表失败: {e}")
            return []

    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务详情（合并内存 handler 信息）"""
        await self._ensure_loaded()
        try:
            task = await self._repo.get_by_id(task_id)
            if task is None:
                return None
            result = self._orm_to_dict(task)
            result["has_handler"] = task_id in self._handlers
            return result
        except Exception as e:
            logger.error(f"查询任务失败: {e}")
            return None

    async def register_task(
        self,
        task_id: str,
        name: str,
        task_type: str,
        cron_expression: str,
        handler: Callable[..., Any],
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """注册任务：元数据写 DB，handler 存内存"""
        await self._ensure_loaded()
        try:
            # 构建 ORM 对象并写入 DB
            from shared.database.models.system_models import ScheduledTask
            task = ScheduledTask(
                id=task_id,
                task_name=name,
                task_type=self._map_task_type(task_type),
                task_module="system",
                schedule_config={"cron": cron_expression},
                task_config=params or {},
                is_active=True,
            )
            created = await self._repo.create(task)
            # handler 保留在内存
            self._handlers[task_id] = handler
            logger.info(f"任务已注册: {task_id} ({name})")
            return self._orm_to_dict(created)
        except Exception as e:
            logger.error(f"注册任务失败: {e}")
            # 降级：内存注册（兼容旧行为）
            self._handlers[task_id] = handler
            logger.warning(f"任务 {task_id} 仅注册了 handler（DB 写入失败）")
            return None

    async def pause_task(self, task_id: str) -> bool:
        """暂停任务（DB 更新 is_active=False）"""
        try:
            success = await self._repo.deactivate_task(task_id)
            if success:
                logger.info(f"任务已暂停: {task_id}")
            return success
        except Exception as e:
            logger.error(f"暂停任务失败: {e}")
            return False

    async def resume_task(self, task_id: str) -> bool:
        """恢复任务（DB 更新 is_active=True）"""
        try:
            success = await self._repo.activate_task(task_id)
            if success:
                logger.info(f"任务已恢复: {task_id}")
            return success
        except Exception as e:
            logger.error(f"恢复任务失败: {e}")
            return False

    async def remove_task(self, task_id: str) -> bool:
        """删除任务：DB 软删除 + 清理内存 handler"""
        try:
            await self._repo.update(task_id, is_deleted=True)
            self._handlers.pop(task_id, None)
            logger.info(f"任务已删除: {task_id}")
            return True
        except Exception as e:
            logger.error(f"删除任务失败: {e}")
            self._handlers.pop(task_id, None)
            return False

    async def update_task_status(
        self, task_id: str, status: str, error: str = ""
    ) -> None:
        """更新任务最近一次执行状态（DB 持久化）"""
        try:
            await self._repo.update_task_status(
                task_id=task_id,
                status=self._map_task_status(status),
                error_message=error if error else None,
            )
        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")

    async def get_enabled_tasks(self) -> List[Dict[str, Any]]:
        """获取所有启用的任务（供调度器使用），合并内存 handler"""
        await self._ensure_loaded()
        try:
            tasks = await self._repo.get_active_tasks()
            result = []
            for t in tasks:
                d = self._orm_to_dict(t)
                d["handler"] = self._handlers.get(t.id)
                result.append(d)
            return result
        except Exception as e:
            logger.error(f"查询启用任务失败: {e}")
            return []

    # ========== 工具方法 ==========

    @staticmethod
    def _map_task_type(task_type: str) -> str:
        """映射任务类型到 DB 枚举值"""
        mapping = {
            "cron": "cron",
            "interval": "interval",
            "date": "date",
            "manual": "manual",
        }
        return mapping.get(task_type, "manual")

    @staticmethod
    def _map_task_status(status: str):
        """映射任务状态到 repo TaskStatus 枚举"""
        from shared.database.repositories.system.ops.scheduled_task_repo import (
            TaskStatus,
        )
        mapping = {
            "success": TaskStatus.SUCCESS,
            "failed": TaskStatus.FAILED,
            "skipped": TaskStatus.SKIPPED,
            "running": TaskStatus.RUNNING,
            "pending": TaskStatus.PENDING,
            "cancelled": TaskStatus.CANCELLED,
        }
        return mapping.get(status, TaskStatus.SUCCESS)

    @staticmethod
    def _orm_to_dict(task) -> Dict[str, Any]:
        """ORM 对象 → 字典"""
        return {
            "task_id": task.id,
            "name": task.task_name,
            "task_type": task.task_type,
            "task_module": task.task_module,
            "cron_expression": (
                task.schedule_config.get("cron", "")
                if task.schedule_config else ""
            ),
            "enabled": task.is_active,
            "last_run": task.last_run_at.isoformat() if task.last_run_at else None,
            "next_run": task.next_run_at.isoformat() if task.next_run_at else None,
            "last_status": task.last_run_result or "",
            "total_runs": task.total_runs or 0,
            "success_runs": task.success_runs or 0,
            "failed_runs": task.failed_runs or 0,
            "created_at": task.created_at.isoformat() if task.created_at else None,
        }
