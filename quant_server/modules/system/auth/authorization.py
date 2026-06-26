# -*- coding: utf-8 -*-
"""
权限验证模块
提供 RBAC 角色检查和细粒度权限验证。
"""

import logging
from typing import Dict, List

from shared.database.repositories.system.auth.user_repo import UserRepository

logger = logging.getLogger(__name__)

ADMIN_ROLES = {"admin", "super_admin", "superadmin"}


def is_admin(user_info: Dict) -> bool:

    """检查用户是否为管理员角色"""
    return user_info.get("role", "") in ADMIN_ROLES


class AuthorizationManager:
    """权限验证管理器（待合并到 PermissionManager）

    DEPRECATED: 此管理器与 managers/permission_manager.py 的 PermissionManager 职责重叠。
    保留此文件以保持向后兼容，所有调用委托给 DB 查询。
    新代码应使用 managers/permission_manager.py 的 PermissionManager（带缓存）。
    详见 docs/system模块审计与修复方案.md 问题 #9
    """

    def __init__(self, session):
        self._user_repo = UserRepository(session)

    async def has_permission(self, user_id: str, module: str, permission_type: str) -> bool:
        """检查用户对某模块是否有特定权限
        DEPRECATED: 建议使用 PermissionManager.check_permission()
        """
        return await self._user_repo.has_permission(user_id, module, permission_type)

    async def has_any_permission(self, user_id: str, permissions: List[tuple]) -> bool:
        """检查用户是否拥有任意一组权限
        DEPRECATED: 建议使用 PermissionManager.check_any_permission()
        """
        for module, perm_type in permissions:
            if await self._user_repo.has_permission(user_id, module, perm_type):
                return True
        return False
