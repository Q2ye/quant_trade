# -*- coding: utf-8 -*-
"""
系统模块常量定义
"""

# 角色常量
ROLE_ADMIN = "admin"
ROLE_SUPER_ADMIN = "super_admin"
ROLE_SUPERADMIN = "superadmin"
ROLE_USER = "user"
ROLE_VIEWER = "viewer"

ADMIN_ROLES = {ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_SUPERADMIN}
ALL_ROLES = {ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_SUPERADMIN, ROLE_USER, ROLE_VIEWER}

# 权限类型
PERM_READ = "can_read"
PERM_WRITE = "can_write"
PERM_EXECUTE = "can_execute"

# 模块权限前缀
MODULES = (
    "data", "strategy", "trade", "backtest",
    "account", "analysis", "monitor", "system",
)

# 分页默认值
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 1000

# 密码策略
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

# Token 有效期（分钟）
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 天

# 登录安全
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_MINUTES = 30

# 系统配置键
CONFIG_KEY_SYSTEM_NAME = "system.name"
CONFIG_KEY_SYSTEM_VERSION = "system.version"
CONFIG_KEY_DATA_RETENTION_DAYS = "data.retention_days"
CONFIG_KEY_LOG_LEVEL = "log.level"
CONFIG_KEY_TRADE_MODE = "trade.mode"  # sim / live
