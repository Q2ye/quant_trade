# -*- coding: utf-8 -*-
"""
角色服务
封装角色 CRUD 和权限分配业务逻辑。
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.repositories.system.auth.role_repo import RoleRepository
from shared.security.audit import AuditLogger, AuditAction, AuditResult

logger = logging.getLogger(__name__)


class RoleService:
    """角色管理服务"""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._role_repo = RoleRepository(session)
        self._audit = AuditLogger()

    async def list_roles(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """获取所有角色列表"""
        roles = await self._role_repo.get_all_roles(include_inactive=include_inactive)
        return [
            {
                "id": r.id,
                "role_code": r.role_code,
                "role_name": r.role_name,
                "description": r.description,
                "is_default": r.is_default,
                "permissions": r.permissions,
            }
            for r in roles
        ]

    async def get_role(self, role_id: str) -> Optional[Dict[str, Any]]:
        """获取单个角色详情"""
        role = await self._role_repo.get(role_id)
        if role is None:
            return None
        return {
            "id": role.id,
            "role_code": role.role_code,
            "role_name": role.role_name,
            "description": role.description,
            "is_default": role.is_default,
            "permissions": role.permissions,
        }

    async def create_role(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建角色"""
        role_code = data.get("role_code", "")
        existing = await self._role_repo.get_by_code(role_code)
        if existing:
            raise ValueError(f"角色代码 '{role_code}' 已存在")

        role = await self._role_repo.create(data)
        await self._audit.log_simple(
            user_id=None, username="",
            action=AuditAction.CREATE,
            resource_type="role",
            resource_id=role.id,
            description=f"创建角色: {role.role_name}",
            result=AuditResult.SUCCESS,
        )
        return {"id": role.id, "role_code": role.role_code, "role_name": role.role_name}

    async def update_role(self, role_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新角色"""
        role = await self._role_repo.update(role_id, data)
        if role is None:
            return None
        await self._audit.log_simple(
            user_id=None, username="",
            action=AuditAction.UPDATE,
            resource_type="role",
            resource_id=role_id,
            description=f"更新角色: {role.role_name}",
            result=AuditResult.SUCCESS,
        )
        return {"id": role.id, "role_code": role.role_code, "role_name": role.role_name}

    async def delete_role(self, role_id: str) -> bool:
        """删除角色"""
        result = await self._role_repo.delete(role_id, soft=True)
        if result:
            await self._audit.log_simple(
                user_id=None, username="",
                action=AuditAction.DELETE,
                resource_type="role",
                resource_id=role_id,
                description=f"删除角色: {role_id}",
                result=AuditResult.SUCCESS,
            )
        return result

    async def get_role_permissions(self, role_id: str) -> List[Dict[str, Any]]:
        """获取角色的权限列表"""
        return await self._role_repo.get_role_permissions(role_id)

    async def get_role_statistics(self) -> Dict[str, Any]:
        """获取角色统计"""
        return await self._role_repo.get_role_statistics()
