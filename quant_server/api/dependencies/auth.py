# quant_server/api/dependencies/auth.py
"""
认证依赖模块

提供FastAPI依赖注入的认证相关功能，包括JWT令牌验证、权限检查、当前用户获取等。
基于共享层的安全工具，确保认证逻辑的一致性和安全性。

Author: 量化交易系统团队
Version: 1.0.0
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_db_session
from core.exceptions.security_exceptions import (
	TokenExpiredError,
	InvalidTokenError
)
from shared.database.repositories.system.auth import user_repo
from shared.security.jwt_handler import JWTManager

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
			# 验证和解码JWT令牌
			payload = self.jwt_manager.verify_token(token, token_type="access")

			# 检查令牌是否过期（verify_token已经处理了过期验证，这里做双重保险）
			if datetime.fromtimestamp(payload["exp"], tz=timezone.utc) < datetime.now(timezone.utc):
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

			# 确保用户ID是字符串类型
			user_id = str(user_id)
			logger.debug(f"获取用户ID: {user_id}, 类型: {type(user_id)}")

			# 从数据库获取用户信息
			user_repository = user_repo.UserRepository(db_session)
			user = await user_repository.get_user(user_id)

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

			# 更新最后登录时间
			await user_repository.update_last_login(user_id)

			# 获取用户权限信息
			user_permissions = await user_repository.get_user_permissions(user.id)

			# 将权限信息转换为权限代码列表
			permission_codes = [
				f"{perm.module}:read" if perm.can_read else
				f"{perm.module}:write" if perm.can_write else
				f"{perm.module}:execute"
				for perm in user_permissions
			]

			# 检查用户是否具有数据同步权限
			# admin和super_admin角色拥有所有权限
			# data模块的任何权限（data_management、data:sync、data:write等）也都允许
			can_sync_data = (
					user.role in ("admin", "super_admin", "superadmin") or
					any("data" in perm.lower() for perm in permission_codes)
			)

			# 返回用户信息
			user_info = {
				"id": user.id,
				"username": user.username,
				"email": user.email,
				"real_name": user.real_name,
				"phone": user.phone,
				"role": user.role,
				"is_active": user.is_active,
				"last_login": user.last_login,
				"created_at": user.created_at,
				"permissions": permission_codes,
				"can_sync_data": can_sync_data,
			}

			logger.debug(f"用户认证成功: {user.username} (ID: {user.id})")
			return user_info

		except (TokenExpiredError, InvalidTokenError) as e:
			logger.error(f"JWT验证失败: {str(e)}")
			raise HTTPException(
				status_code=status.HTTP_401_UNAUTHORIZED,
				detail="无效的令牌",
			)

		except HTTPException:
			raise
		except Exception as e:
			logger.error(f"获取用户信息失败: {str(e)}", exc_info=True)
			raise HTTPException(
				status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
				detail="服务器内部错误",
			)

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

	@staticmethod
	async def require_permission (
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

	@staticmethod
	async def require_superuser (
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
		# 检查用户角色是否为超级用户
		user_role = current_user.get("role", "")
		if user_role not in ("super_admin", "superadmin"):
			logger.warning(f"用户 {current_user['username']} 不是超级用户，角色: {user_role}")
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="需要超级用户权限",
			)

		logger.debug(f"超级用户权限检查通过: {current_user['username']}")
		return current_user


	# 创建全局依赖实例
_auth_deps = AuthDependencies()

# 导出依赖函数（FastAPI可以直接使用这些函数）
get_current_user = _auth_deps.get_current_user
require_permission = _auth_deps.require_permission
require_superuser = _auth_deps.require_superuser
optional_auth = _auth_deps.optional_auth

# 导出类型注解（供其他模块使用）
CurrentUser = Depends(get_current_user)

# 修复PermissionRequired的定义
def PermissionRequired(*perms):
	async def _require_permission():
		return await _auth_deps.require_permission(list(perms))
	return Depends(_require_permission)

SuperuserRequired = Depends(require_superuser)
OptionalAuth = Depends(optional_auth)