# -*- coding: utf-8 -*-
"""
API 依赖注入模块 — 统一薄接线层

为 FastAPI router 提供 Depends() 可注入对象。
所有基础设施实例（DB Pool、EventEngine、MainEngine）由 main.py 创建并注入。
"""

# ── 认证 ──
from .auth import get_current_user, require_permission, require_superuser, optional_auth

# ── 数据库会话 ──
from .database import get_db_session

# ── 事件引擎 ──
from .event_engine import get_event_engine, set_event_engine, EventPriority, publish_system_event

# ── 主引擎 ──
from .main_engine import get_main_engine, set_main_engine

# ── 配置 ──
from .config import get_settings

__all__ = [
    "get_current_user",
    "require_permission",
    "require_superuser",
    "optional_auth",
    "get_db_session",
    "get_event_engine",
    "set_event_engine",
    "EventPriority",
    "publish_system_event",
    "get_main_engine",
    "set_main_engine",
    "get_settings",
]
