# quant_server/api/dependencies/auth.py
"""
认证依赖模块

提供FastAPI依赖注入的认证相关功能，包括JWT令牌验证、权限检查、当前用户获取等。
基于共享层的安全工具，确保认证逻辑的一致性和安全性。

Author: 量化交易系统团队
Version: 1.0.0
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_db_session
from core.exceptions.security_exceptions import (
	TokenExpiredError,
	InvalidTokenError
)
from shared.config.config_manager import get_config
from shared.database.models.business_models import SysUser
from shared.database.repositories.system.auth import user_repo
from shared.security.jwt_handler import JWTManager

logger = logging.getLogger(__name__)


def _is_auth_enabled() -> bool:
    """延迟读取认证开关，确保 main.py 已通过 reload_config 加载 YAML 配置"""
    return get_config().settings.API.AUTH_ENABLED

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
		# 认证开关：关闭时尝试使用DB中已有用户，若无则自动创建种子用户
		if not _is_auth_enabled():
			try:
				user_repository = user_repo.UserRepository(db_session)
				result = await db_session.execute(
					select(SysUser).where(SysUser.role == "admin").limit(1)
				)
				user = result.scalar_one_or_none()
				if user:
					logger.debug(f"Auth disabled — using existing user: {user.username} (ID: {user.id})")
					return {
						"id": user.id,
						"username": user.username,
						"email": user.email,
						"real_name": user.real_name,
						"phone": user.phone,
						"role": user.role,
						"is_active": user.is_active,
						"last_login": user.last_login,
						"created_at": user.created_at,
						"permissions": ["*:*"],
						"can_sync_data": True,
					}

				# No user exists — create a seed dev user
				# 修复 2026-08（B5）：明文密码 → 随机 bcrypt 哈希
				dev_id = str(uuid.uuid4())
				try:
					# 修复 2026-08：原 import 路径 modules.system.auth.password_manager 不存在，
					# 导致此处永远回退明文；种子密码需满足强度校验（大写/小写/数字/特殊字符），
					# 开发模式（AUTH_ENABLED=false）登录不校验密码，仅保证存储为 bcrypt 哈希
					from shared.security.password import get_password_manager
					_seed_pwd = get_password_manager().encrypt_password(
						"DevSeed!" + uuid.uuid4().hex[:16]
					)
				except Exception as e:
					logger.warning(f"种子用户密码加密失败，回退随机明文存储: {e}")
					_seed_pwd = "dev-seed-" + uuid.uuid4().hex[:16]
				dev_user = SysUser(
					id=dev_id,
					username="superadmin",
					password=_seed_pwd,
					email="dev@quant-trade.local",
					real_name="开发者",
					phone="",
					role="admin",
					is_active=True,
					created_at=datetime.now(timezone.utc),
				)
				db_session.add(dev_user)
				await db_session.commit()
				await db_session.refresh(dev_user)
				logger.info(f"Created seed dev user: developer (ID: {dev_id})")
				return {
					"id": dev_id,
					"username": dev_user.username,
					"email": dev_user.email,
					"real_name": dev_user.real_name,
					"phone": dev_user.phone,
					"role": dev_user.role,
					"is_active": dev_user.is_active,
					"last_login": dev_user.last_login,
					"created_at": dev_user.created_at,
					"permissions": ["*:*"],
					"can_sync_data": True,
				}
			except Exception as e:
				# 修复 2026-08（B5）：DB 故障时 fail-open → fail-closed 503
				logger.error(f"Auth disabled but DB user lookup/creation failed: {e}")
				raise HTTPException(
					status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
					detail="认证服务不可用，请稍后重试",
				)

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
			logger.error(f"JWT验证失败: {'服务器内部错误'}")
			raise HTTPException(
				status_code=status.HTTP_401_UNAUTHORIZED,
				detail="无效的令牌",
			)

		except HTTPException:
			raise
		except Exception as e:
			logger.error(f"获取用户信息失败: {'服务器内部错误'}", exc_info=True)
			raise HTTPException(
				status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
				detail="服务器内部错误",
			)

	# 创建全局依赖实例
_auth_deps = AuthDependencies()

# 导出依赖函数（FastAPI可以直接使用这些函数）
get_current_user = _auth_deps.get_current_user
