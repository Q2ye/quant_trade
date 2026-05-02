# -*- coding: utf-8 -*-
"""
权限管理器
负责 RBAC 权限缓存、权限变更通知和权限校验优化。
"""

import logging
from typing import Dict, List, Set

from quant_server.shared.database.repositories.system.auth.user_repo import UserRepository

logger = logging.getLogger(__name__)

ADMIN_ROLES: Set[str] = {"admin", "super_admin", "superadmin"}
ALL_MODULES = ("data", "strategy", "trade", "backtest", "account", "analysis", "monitor", "system")
ALL_PERM_TYPES = {"can_read", "can_write", "can_execute"}


def is_admin (role: str) -> bool:
	"""检查角色是否为管理员"""
	return role in ADMIN_ROLES


class PermissionManager:
	"""RBAC 权限管理器 — 权限缓存与校验"""

	def __init__ (self, session_factory):
		self._session_factory = session_factory
		self._user_perm_cache: Dict[str, Dict[str, Set[str]]] = {}

	async def check_permission (self, user_id: str, module: str,
	                            permission_type: str) -> bool:
		"""检查用户对某模块是否有特定权限"""
		perms = await self.get_user_permissions(user_id)
		module_perms = perms.get(module, set())
		return permission_type in module_perms

	async def check_any_permission (self, user_id: str,
	                                permissions: List[tuple]) -> bool:
		"""检查用户是否拥有任意一组权限"""
		perms = await self.get_user_permissions(user_id)
		for module, perm_type in permissions:
			if perm_type in perms.get(module, set()):
				return True
		return False

	async def get_user_permissions (self, user_id: str) -> Dict[str, Set[str]]:
		"""获取用户权限（优先从缓存）"""
		if user_id in self._user_perm_cache:
			return self._user_perm_cache[user_id]

		async with self._session_factory() as session:
			repo = UserRepository(session)
			user = await repo.get_user(user_id)
			if user is None:
				return {}

			role = getattr(user, "role", "user")

			# 管理员拥有全部权限
			if role in ADMIN_ROLES:
				perms = {m: ALL_PERM_TYPES for m in ALL_MODULES}
			else:
				# 非管理员：从 DB 读取用户级权限
				perm_objs = await repo.get_user_permissions(user_id)
				perms: Dict[str, Set[str]] = {}
				for p in perm_objs:
					mod = getattr(p, "module", "")
					ptype = getattr(p, "permission_type", "")
					if mod not in perms:
						perms[mod] = set()
					perms[mod].add(ptype)
				if not perms:
					perms = {"data": {"can_read"}}

		self._user_perm_cache[user_id] = perms
		return perms

	async def invalidate_user_cache (self, user_id: str) -> None:
		"""失效用户权限缓存（角色变更后调用）"""
		self._user_perm_cache.pop(user_id, None)
		logger.debug(f"用户权限缓存已失效: {user_id}")

	async def invalidate_all_cache (self) -> None:
		"""失效全部权限缓存"""
		count = len(self._user_perm_cache)
		self._user_perm_cache.clear()
		logger.info(f"全部权限缓存已失效，清理了 {count} 个")
