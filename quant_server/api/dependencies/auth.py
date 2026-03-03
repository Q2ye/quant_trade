# quant_server/api/dependencies/auth.py
"""
认证依赖模块

提供FastAPI依赖注入的认证相关功能，包括JWT令牌验证、权限检查、当前用户获取等。
基于共享层的安全工具，确保认证逻辑的一致性和安全性。

Author: 量化交易系统团队
Version: 1.0.0
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.repositories.system.auth import user_repo
from quant_server.shared.security.jwt_handler import JWTManager
from quant_server.api.dependencies.database import get_db_session

logger = logging.getLogger(__name__)

# 创建HTTPBearer安全方案
security_scheme = HTTPBearer(
	bearerFormat="JWT",
	description="请提供有效的JWT令牌，格式: Bearer <token>",
	auto_error=False  # 设置为False以便手动处理错误
)


class AuthDependencies:
	"""认证依赖管理类"""

	def __init__ (self):
		"""初始化认证依赖"""
		self.jwt_manager = JWTManager()
		logger.info("认证依赖初始化完成")

	async def get_current_user (
			self,
			credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
			db_session: AsyncSession = Depends(get_db_session)
	) -> Dict[str, Any]:
		"""
		获取当前认证用户

		Args:
			credentials: HTTP授权凭证，包含JWT令牌
			db_session: 数据库会话

		Returns:
			Dict[str, Any]: 用户信息字典

		Raises:
			HTTPException: 401 - 未认证或令牌无效
						  403 - 用户被禁用
		"""
		# 检查是否有认证凭证
		if not credentials:
			logger.warning("未提供认证令牌")
			raise HTTPException(
				status_code=status.HTTP_401_UNAUTHORIZED,
				detail="需要认证令牌",
				headers={"WWW-Authenticate": "Bearer"},
			)

		token = credentials.credentials

		try:
			# 解码JWT令牌
			payload = self.jwt_manager.decode_token(token)

			# 验证令牌类型
			if payload.get("type") != "access":
				logger.warning(f"令牌类型错误: {payload.get('type')}")
				raise HTTPException(
					status_code=status.HTTP_401_UNAUTHORIZED,
					detail="无效的令牌类型",
				)

			# 检查令牌是否过期
			if datetime.fromtimestamp(payload["exp"]) < datetime.utcnow():
				logger.warning("令牌已过期")
				raise HTTPException(
					status_code=status.HTTP_401_UNAUTHORIZED,
					detail="令牌已过期",
				)

			user_id = payload.get("sub")
			if not user_id:
				logger.warning("令牌中缺少用户ID")
				raise HTTPException(
					status_code=status.HTTP_401_UNAUTHORIZED,
					detail="无效的令牌",
				)

			# 从数据库获取用户信息
			user_repository = user_repo.UserRepository(db_session)
			user = await user_repository.get_by_id(user_id)

			if not user:
				logger.warning(f"用户不存在: {user_id}")
				raise HTTPException(
					status_code=status.HTTP_401_UNAUTHORIZED,
					detail="用户不存在",
				)

			# 检查用户状态
			if not user.is_active:
				logger.warning(f"用户被禁用: {user_id}")
				raise HTTPException(
					status_code=status.HTTP_403_FORBIDDEN,
					detail="用户账户已被禁用",
				)

			# 更新最后活动时间
			await user_repository.update_last_activity(user_id)

			# 返回用户信息
			user_info = {
				"id": user.id,
				"username": user.username,
				"email": user.email,
				"full_name": user.full_name,
				"is_active": user.is_active,
				"is_superuser": user.is_superuser,
				"last_login": user.last_login,
				"created_at": user.created_at,
				"roles": [role.name for role in user.roles],
				"permissions": [perm.code for role in user.roles for perm in role.permissions]
			}

			logger.debug(f"用户认证成功: {user.username} (ID: {user.id})")
			return user_info

		except JWTManager as e:
			logger.error(f"JWT解码失败: {str(e)}")
			raise HTTPException(
				status_code=status.HTTP_401_UNAUTHORIZED,
				detail="无效的令牌格式",
			)
		except HTTPException:
			raise
		except Exception as e:
			logger.error(f"获取用户信息失败: {str(e)}", exc_info=True)
			raise HTTPException(
				status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
				detail="服务器内部错误",
			)

	async def require_permission (
			self,
			permission_codes: List[str],
			current_user: Dict[str, Any] = Depends(get_current_user)
	) -> Dict[str, Any]:
		"""
		检查用户是否拥有指定权限

		Args:
			permission_codes: 需要的权限代码列表
			current_user: 当前用户信息

		Returns:
			Dict[str, Any]: 用户信息（如果权限检查通过）

		Raises:
			HTTPException: 403 - 权限不足
		"""
		user_permissions = current_user.get("permissions", [])

		# 检查是否拥有所有需要的权限
		missing_permissions = []
		for perm_code in permission_codes:
			if perm_code not in user_permissions:
				missing_permissions.append(perm_code)

		if missing_permissions:
			logger.warning(
				f"用户 {current_user['username']} 缺少权限: {missing_permissions}"
			)
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail=f"权限不足，缺少: {', '.join(missing_permissions)}",
			)

		logger.debug(
			f"用户 {current_user['username']} 权限检查通过: {permission_codes}"
		)
		return current_user

	async def require_superuser (
			self,
			current_user: Dict[str, Any] = Depends(get_current_user)
	) -> Dict[str, Any]:
		"""
		要求超级用户权限

		Args:
			current_user: 当前用户信息

		Returns:
			Dict[str, Any]: 用户信息（如果是超级用户）

		Raises:
			HTTPException: 403 - 需要超级用户权限
		"""
		if not current_user.get("is_superuser", False):
			logger.warning(f"用户 {current_user['username']} 不是超级用户")
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="需要超级用户权限",
			)

		logger.debug(f"超级用户权限检查通过: {current_user['username']}")
		return current_user

	async def optional_auth (
			self,
			credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
			db_session: AsyncSession = Depends(get_db_session)
	) -> Optional[Dict[str, Any]]:
		"""
		可选认证依赖

		当令牌存在时返回用户信息，不存在时返回None
		适用于公开和私有混合的API端点

		Args:
			credentials: HTTP授权凭证
			db_session: 数据库会话

		Returns:
			Optional[Dict[str, Any]]: 用户信息或None
		"""
		if not credentials:
			return None

		try:
			return await self.get_current_user(credentials, db_session)
		except HTTPException:
			# 认证失败时返回None，而不是抛出异常
			return None


# 创建全局依赖实例
_auth_deps = AuthDependencies()

# 导出依赖函数（FastAPI可以直接使用这些函数）
get_current_user = _auth_deps.get_current_user
require_permission = _auth_deps.require_permission
require_superuser = _auth_deps.require_superuser
optional_auth = _auth_deps.optional_auth

# 导出类型注解（供其他模块使用）
CurrentUser = Depends(get_current_user)
PermissionRequired = lambda *perms: Depends(require_permission(list(perms)))
SuperuserRequired = Depends(require_superuser)
OptionalAuth = Depends(optional_auth)