# -*- coding: utf-8 -*-
"""
系统模块业务 DTO（数据传输对象）

纯数据类，用于 Engine → Service → Handler 之间传递领域数据。
区别于：
- schemas.py: API 层 Pydantic 请求/响应模型
- shared/database/models/: SQLAlchemy ORM 模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class UserStatus(str, Enum):
    """用户状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"


@dataclass
class UserInfo:
    """用户信息（领域对象）"""
    user_id: str
    username: str
    email: str = ""
    display_name: str = ""
    status: UserStatus = UserStatus.ACTIVE
    roles: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class RoleInfo:
    """角色信息"""
    role_id: str
    name: str
    description: str = ""
    permissions: List[str] = field(default_factory=list)
    is_system: bool = False


@dataclass
class ConfigItem:
    """配置项"""
    key: str
    value: Any
    value_type: str = "string"  # string / int / float / bool / json
    description: str = ""
    category: str = "general"  # general / trade / risk / data
    editable: bool = True
    updated_at: Optional[datetime] = None


@dataclass
class AuthToken:
    """认证令牌"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    refresh_token: str = ""
    issued_at: Optional[datetime] = None


@dataclass
class SystemLog:
    """系统日志条目"""
    log_id: str
    level: str  # DEBUG / INFO / WARNING / ERROR / CRITICAL
    module: str
    message: str
    user_id: Optional[str] = None
    trace_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None


@dataclass
class TaskInfo:
    """定时任务信息"""
    task_id: str
    name: str
    task_type: str  # data_sync / cleanup / report / custom
    cron_expression: str = ""
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    last_status: str = ""  # success / failed / running
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectionStatus:
    """外部连接状态"""
    name: str  # database / redis / tushare / XTP
    connected: bool = False
    latency_ms: float = 0.0
    message: str = ""
    last_check: Optional[datetime] = None
