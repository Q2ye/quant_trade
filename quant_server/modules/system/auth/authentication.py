# -*- coding: utf-8 -*-
"""
身份验证模块
负责用户身份核验，调用 shared/security/ 中的 JWT 和密码基础设施。
"""

import logging
from typing import Any, Dict, Optional

from shared.security.jwt_handler import get_jwt_manager
from shared.security.password import get_password_manager
from shared.database.repositories.system.auth.user_repo import UserRepository

logger = logging.getLogger(__name__)


class AuthenticationManager:
    """身份验证管理器 — 处理凭证校验和 token 签发"""

    def __init__(self, session):
        self._user_repo = UserRepository(session)
        self._jwt = get_jwt_manager()
        self._pwd = get_password_manager()

    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """验证用户名和密码，成功返回用户信息，失败返回 None"""
        user = await self._user_repo.authenticate_user(username, password)
        if user is None:
            return None

        if not user.is_active:
            logger.warning(f"用户 {username} 已停用，拒绝登录")
            return None

        await self._user_repo.update_last_login(user.id)

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
        }

    def create_token_pair(self, user_data: Dict[str, Any]) -> Dict[str, str]:
        """为用户签发 access + refresh token 对"""
        return self._jwt.create_token_pair({
            "sub": user_data["id"],
            "username": user_data["username"],
            "role": user_data.get("role", "user"),
        })

    def verify_access_token(self, token: str) -> Dict[str, Any]:
        """验证 access token，返回 payload"""
        return self._jwt.verify_token(token, token_type="access")

    def refresh_access_token(self, refresh_token: str) -> Dict[str, str]:
        """用 refresh token 换取新的 token 对"""
        return self._jwt.refresh_access_token(refresh_token)

    async def change_password(
        self, user_id: str, old_password: str, new_password: str
    ) -> bool:
        """修改密码（需验证旧密码）"""
        user = await self._user_repo.get_user(user_id)
        if user is None:
            return False
        if not self._pwd.verify_password(old_password, user.password):
            return False
        return await self._user_repo.update_password(user_id, new_password)

    async def validate_password_strength(self, password: str):
        """校验密码强度，返回 (is_valid, errors)"""
        return self._pwd.validate_password_strength(password)
