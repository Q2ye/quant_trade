# -*- coding: utf-8 -*-
"""
告警事件

当 AlertEngine 创建告警、发送通知或更新状态时发布。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from modules.monitor.constants import AlertLevel, AlertType


@dataclass
class AlertMonitorEvent:
    """告警监控事件"""

    event_type: str
    source: str = "monitor.alert_engine"
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: str = "high"

    @classmethod
    def alert_created(cls, alert_id: str, alert_type: AlertType, alert_level: AlertLevel,
                      title: str, message: str, source_module: str = "monitor") -> "AlertMonitorEvent":
        return cls(
            event_type="monitor.alert.created",
            priority="critical" if alert_level == AlertLevel.CRITICAL else "high",
            data={
                "alert_id": alert_id,
                "alert_type": alert_type.value if isinstance(alert_type, AlertType) else alert_type,
                "alert_level": alert_level.value if isinstance(alert_level, AlertLevel) else alert_level,
                "title": title,
                "message": message,
                "source_module": source_module,
            },
        )

    @classmethod
    def notification_sent(cls, alert_id: str, channels: List[str]) -> "AlertMonitorEvent":
        return cls(
            event_type="monitor.alert.notification.sent",
            priority="normal",
            data={"alert_id": alert_id, "channels": channels},
        )

    @classmethod
    def notification_failed(cls, alert_id: str, channel: str, error: str) -> "AlertMonitorEvent":
        return cls(
            event_type="monitor.alert.notification.failed",
            priority="high",
            data={"alert_id": alert_id, "channel": channel, "error": error},
        )

    @classmethod
    def acknowledged(cls, alert_id: str, user_id: str) -> "AlertMonitorEvent":
        return cls(
            event_type="monitor.alert.acknowledged",
            priority="normal",
            data={"alert_id": alert_id, "user_id": user_id},
        )

    @classmethod
    def resolved(cls, alert_id: str, user_id: str) -> "AlertMonitorEvent":
        return cls(
            event_type="monitor.alert.resolved",
            priority="normal",
            data={"alert_id": alert_id, "user_id": user_id},
        )
