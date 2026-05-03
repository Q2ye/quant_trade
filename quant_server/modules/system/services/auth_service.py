# -*- coding: utf-8 -*-
"""
认证服务
编排用户注册、登录、登出、Token 刷新等认证流程。
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.repositories.system.auth.user_repo import UserRepository
from shared.security.audit import AuditLogger, AuditAction, AuditResult, AuditLevel

from ..auth.authentication import AuthenticationManager

logger = logging.getLogger(__name__)


class AuthService:
    """认证服务 — 编排认证业务逻辑"""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._user_repo = UserRepository(session)
        self._auth = AuthenticationManager(session)
        self._audit = AuditLogger()

    async def login(
        self, username: str, password: str,
        ip_address: str = "", user_agent: str = "",
    ) -> Optional[Dict[str, Any]]:
        """用户登录，返回 user_info + token_pair"""
        user_info = await self._auth.authenticate_user(username, password)
        if user_info is None:
            await self._audit.log_security_event(
                event_type="login_failed",
                user_id=None,
                username=username,
                description=f"用户 {username} 登录失败",
                details={"reason": "invalid_credentials"},
                ip_address=ip_address,
                user_agent=user_agent,
                level=AuditLevel.WARNING,
            )
            return None

        token_pair = self._auth.create_token_pair(user_info)

        await self._audit.log_user_action(
            action=AuditAction.LOGIN,
            user_id=user_info["id"],
            username=user_info["username"],
            description=f"用户 {username} 登录成功",
            ip_address=ip_address,
            user_agent=user_agent,
            result=AuditResult.SUCCESS,
        )

        return {"user": user_info, **token_pair}

    async def register(
        self, username: str, password: str,
        email: str = "", phone: str = "", real_name: str = "",
        ip_address: str = "", user_agent: str = "",
    ) -> Dict[str, Any]:
        """用户注册

        Raises:
            ValueError: 用户名已存在或密码强度不足
        """
        existing = await self._user_repo.get_user_by_username(username)
        if existing:
            raise ValueError(f"用户名 '{username}' 已被使用")

        if email:
            existing_email = await self._user_repo.get_user_by_email(email)
            if existing_email:
                raise ValueError(f"邮箱 '{email}' 已被注册")

        is_valid, errors = await self._auth.validate_password_strength(password)
        if not is_valid:
            raise ValueError(f"密码强度不足: {'; '.join(errors)}")

        user = await self._user_repo.create_user({
            "username": username,
            "password": password,
            "email": email,
            "phone": phone,
            "real_name": real_name,
            "role": "user",
            "is_active": True,
        })

        await self._audit.log_user_action(
            action=AuditAction.CREATE,
            user_id=user.id,
            username=user.username,
            resource_type="user",
            resource_id=user.id,
            description=f"新用户注册: {username}",
            ip_address=ip_address,
            user_agent=user_agent,
            result=AuditResult.SUCCESS,
        )

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
        }

    async def refresh_token(self, refresh_token: str) -> Dict[str, str]:
        """刷新 token 对

        Raises:
            ValueError: refresh token 无效或过期
        """
        try:
            return self._auth.refresh_access_token(refresh_token)
        except Exception as e:
            raise ValueError(f"Token 刷新失败: {str(e)}")

    async def change_password(
        self, user_id: str, old_password: str, new_password: str,
    ) -> bool:
        """修改密码"""
        is_valid, errors = await self._auth.validate_password_strength(new_password)
        if not is_valid:
            raise ValueError(f"新密码强度不足: {'; '.join(errors)}")

        result = await self._auth.change_password(user_id, old_password, new_password)

        if result:
            await self._audit.log_security_event(
                event_type="password_changed",
                user_id=user_id,
                username="",
                description="用户修改密码",
                details={},
                level=AuditLevel.INFO,
            )

        return result
