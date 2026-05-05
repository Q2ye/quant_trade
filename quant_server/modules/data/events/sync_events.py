"""
数据同步相关事件
"""
from datetime import datetime
from typing import Dict, Any, Optional

from core.events.base import BaseEvent, EventPriority
from modules.data.events.types import DataEventType


class DataSyncStartedEvent(BaseEvent):
    """数据同步开始事件"""

    def __init__(
        self,
        sync_type: str,
        source: str = "tushare",
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        # 从 kwargs 中移除 source，避免与参数中的 source 重复
        kwargs.pop("source", None)
        super().__init__(
            module="events",
            event_type=DataEventType.SYNC_STARTED.value,
            priority=EventPriority.NORMAL,
            source=source,
            **kwargs
        )

        self.data = {
            "sync_type": sync_type,
            "source": source,
            "params": params or {},
            "start_time": datetime.now().isoformat()
        }


class DataSyncProgressEvent(BaseEvent):
    """数据同步进度事件"""

    def __init__(
        self,
        sync_type: str,
        progress: float,  # 0-100
        current_item: str = "",
        total_items: int = 0,
        processed_items: int = 0,
        task_id: Optional[str] = None,
        user_id: Optional[str] = None,
        error_message: Optional[str] = None,
        message: Optional[str] = None,
        data_types: Optional[list] = None,
        current_task: Optional[str] = None,
        total_tasks: Optional[int] = None,
        completed_tasks: Optional[int] = None,
        timestamp: Optional[datetime] = None,
        source: str = "tushare",
        **kwargs
    ):
        # 从 kwargs 中移除 source，避免与参数中的 source 重复
        kwargs.pop("source", None)
        super().__init__(
            module="events",
            event_type=DataEventType.SYNC_PROGRESS.value,
            priority=EventPriority.LOW,
            source=source,
            **kwargs
        )

        self.data = {
            "sync_type": sync_type,
            "progress": progress,
            "current_item": current_item,
            "total_items": total_items,
            "processed_items": processed_items,
            "task_id": task_id,
            "user_id": user_id,
            "error_message": error_message,
            "message": message,
            "data_types": data_types or [],
            "current_task": current_task,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "timestamp": timestamp.isoformat() if timestamp else datetime.now().isoformat()
        }


class DataSyncCompletedEvent(BaseEvent):
    """数据同步完成事件"""

    event_type: str = DataEventType.SYNC_COMPLETED.value

    def __init__(
        self,
        sync_type: str,
        record_count: int,
        duration_seconds: float,
        success: bool = True,
        summary: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
        user_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        source: str = "tushare",
        **kwargs
    ):
        # 从 kwargs 中移除 source，避免与参数中的 source 重复
        kwargs.pop("source", None)
        super().__init__(
            module="events",
            event_type=DataEventType.SYNC_COMPLETED.value,
            priority=EventPriority.NORMAL,
            source=source,
            **kwargs
        )

        self.data = {
            "sync_type": sync_type,
            "record_count": record_count,
            "duration_seconds": duration_seconds,
            "success": success,
            "summary": summary or {},
            "task_id": task_id,
            "user_id": user_id,
            "timestamp": timestamp.isoformat() if timestamp else datetime.now().isoformat(),
            "completion_time": datetime.now().isoformat()
        }


class DataSyncFailedEvent(BaseEvent):
    """数据同步失败事件"""

    def __init__(
        self,
        sync_type: str,
        error_message: str,
        error_details: Optional[str] = None,
        retry_count: int = 0,
        task_id: Optional[str] = None,
        user_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        source: str = "tushare",
        **kwargs
    ):
        # 从 kwargs 中移除 source，避免与参数中的 source 重复
        kwargs.pop("source", None)
        super().__init__(
            module="events",
            event_type=DataEventType.SYNC_FAILED.value,
            priority=EventPriority.HIGH,
            source=source,
            **kwargs
        )

        self.data = {
            "sync_type": sync_type,
            "error_message": error_message,
            "error_details": error_details,
            "retry_count": retry_count,
            "task_id": task_id,
            "user_id": user_id,
            "timestamp": timestamp.isoformat() if timestamp else datetime.now().isoformat(),
            "failure_time": datetime.now().isoformat()
        }