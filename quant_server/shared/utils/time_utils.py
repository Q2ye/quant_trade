# -*- coding: utf-8 -*-
"""北京时间工具——信号时间戳统一用北京时间（2026-08-17 修复时区错位）

此前信号时间用 naive datetime.now() 或 UTC，存储后被当作 UTC，
前端直接显示 UTC 字符串导致信号日错位（如 8-16 16:00 实为北京 8-17 00:00）。
统一在信号生成源头用北京时间（aware），落库/显示/追溯语义一致。
"""
from datetime import datetime, timedelta, timezone

BEIJING_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


def beijing_now() -> datetime:
    """当前北京时间（aware datetime）"""
    return datetime.now(BEIJING_TZ)
