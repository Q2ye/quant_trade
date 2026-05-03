# quant_server/shared/database/repositories/system/auth/__init__.py
"""
认证授权领域Repository包初始化
包含用户管理、角色管理、权限管理等功能
"""

from shared.database.repositories.system.auth.user_repo import UserRepository
from shared.database.repositories.system.auth.role_repo import RoleRepository
from shared.database.repositories.system.auth.permission_repo import PermissionRepository

__all__ = [
    "UserRepository",
    "RoleRepository",
    "PermissionRepository"
]