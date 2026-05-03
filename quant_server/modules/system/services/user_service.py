# -*- coding: utf-8 -*-
"""
用户服务
封装用户 CRUD、搜索、统计等业务逻辑。
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.repositories.system.auth.user_repo import UserRepository
from shared.security.audit import AuditLogger, AuditAction, AuditResult

logger = logging.getLogger(__name__)


class UserService:
	"""用户管理服务"""

	def __init__ (self, session: AsyncSession):
		self._session = session
		self._user_repo = UserRepository(session)
		self._audit = AuditLogger()

	async def get_user (self, user_id: str) -> Optional[Dict[str, Any]]:
		"""获取单个用户详情"""
		user = await self._user_repo.get_user(user_id)
		if user is None:
			return None
		permissions = await self._user_repo.get_user_permissions(user_id)
		return {
			"id": user.id,
			"username": user.username,
			"email": user.email,
			"phone": user.phone,
			"real_name": user.real_name,
			"role": user.role,
			"is_active": user.is_active,
			"last_login": user.last_login.isoformat() if user.last_login else None,
			"created_at": user.created_at.isoformat() if user.created_at else None,
			"permissions": [
				{"module": p.module, "can_read": p.can_read,
				 "can_write": p.can_write, "can_execute": p.can_execute}
				for p in permissions
			],
		}

	async def list_users (
			self, skip: int = 0, limit: int = 100,
			active_only: bool = False, keyword: str = "",
			role: str = "",
	) -> Dict[str, Any]:
		"""分页获取用户列表"""
		if keyword or role:
			users = await self._user_repo.search_users(
				keyword=keyword or None,
				role=role or None,
				is_active=True if active_only else None,
				skip=skip, limit=limit,
			)
			total = await self._user_repo.search_users_count(
				keyword=keyword or None,
				role=role or None,
				is_active=True if active_only else None,
			)
		else:
			users = await self._user_repo.get_users(
				skip=skip, limit=limit, active_only=active_only,
			)
			total = await self._user_repo.count_users(active_only=active_only)

		return {
			"items": [
				{
					"id": u.id, "username": u.username, "email": u.email,
					"role": u.role, "is_active": u.is_active,
					"last_login": u.last_login.isoformat() if u.last_login else None,
					"created_at": u.created_at.isoformat() if u.created_at else None,
				}
				for u in users
			],
			"total": total,
			"skip": skip,
			"limit": limit,
		}

	async def create_user (self, data: Dict[str, Any], operator_id: str = "") -> Dict[str, Any]:
		"""创建用户（管理员操作）"""
		username = data.get("username", "")
		existing = await self._user_repo.get_user_by_username(username)
		if existing:
			raise ValueError(f"用户名 '{username}' 已被使用")

		user = await self._user_repo.create_user(data)

		await self._audit.log_user_action(
			action=AuditAction.CREATE,
			user_id=operator_id,
			username="",
			resource_type="user",
			resource_id=user.id,
			description=f"管理员创建用户: {username}",
			result=AuditResult.SUCCESS,
		)

		return {"id": user.id, "username": user.username, "role": user.role}

	async def update_user (
			self, user_id: str, data: Dict[str, Any], operator_id: str = "",
	) -> Optional[Dict[str, Any]]:
		"""更新用户信息"""
		user = await self._user_repo.update_user(user_id, data)
		if user is None:
			return None

		await self._audit.log_user_action(
			action=AuditAction.UPDATE,
			user_id=operator_id,
			username="",
			resource_type="user",
			resource_id=user_id,
			description=f"更新用户: {user.username}",
			result=AuditResult.SUCCESS,
		)

		return {"id": user.id, "username": user.username, "role": user.role}

	async def delete_user (self, user_id: str, operator_id: str = "") -> bool:
		"""软删除用户"""
		result = await self._user_repo.delete_user(user_id, soft=True)
		if result:
			await self._audit.log_user_action(
				action=AuditAction.DELETE,
				user_id=operator_id,
				username="",
				resource_type="user",
				resource_id=user_id,
				description=f"删除用户: {user_id}",
				result=AuditResult.SUCCESS,
			)
		return result

	async def get_statistics (self) -> Dict[str, Any]:
		"""获取用户统计信息"""
		return await self._user_repo.get_user_statistics()

	async def activate_user (self, user_id: str) -> bool:
		"""激活用户"""
		return await self._user_repo.activate_user(user_id)

	async def deactivate_user (self, user_id: str) -> bool:
		"""停用用户"""
		return await self._user_repo.deactivate_user(user_id)

	async def change_role (self, user_id: str, new_role: str) -> bool:
		"""修改用户角色"""
		return await self._user_repo.change_user_role(user_id, new_role)
