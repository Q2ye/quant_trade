# -*- coding: utf-8 -*-
"""
JWT 处理器

提供 FastAPI 依赖注入用的 token 提取与验证，以及 token 黑名单管理。
底层 JWT 加密/签名由 shared/security/jwt_handler.py 的 JWTManager 负责。
"""

import logging
from typing import Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from quant_server.shared.security.jwt_handler import get_jwt_manager

logger = logging.getLogger(__name__)

# OAuth2 Bearer scheme
_bearer_scheme = HTTPBearer(auto_error=False)

# Token 黑名单（内存缓存，生产环境应迁移到 Redis）
_token_blacklist: set = set()


def get_token_from_header(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[str]:
    """从 Authorization: Bearer <token> 头提取 token"""
    if credentials is None:
        return None
    return credentials.credentials


def verify_access_token(token: Optional[str] = Depends(get_token_from_header)) -> Dict:
    """验证 access token 并返回 payload（FastAPI 依赖注入）

    Raises:
        HTTPException: token 无效、过期、或已在黑名单中
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭证",
        )

    if token in _token_blacklist:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已失效",
        )

    try:
        jwt_manager = get_jwt_manager()
        payload = jwt_manager.verify_token(token, token_type="access")
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token 验证失败: {str(e)}",
        )


def blacklist_token(token: str) -> None:
    """将 token 加入黑名单（用于登出）"""
    _token_blacklist.add(token)
    logger.debug(f"Token 已加入黑名单: {token[:10]}...")


def is_token_blacklisted(token: str) -> bool:
    """检查 token 是否在黑名单中"""
    return token in _token_blacklist


def clear_expired_blacklist() -> int:
    """清理黑名单中的过期 token（在定时任务中调用）

    由于 blacklist 是简单内存 set，暂不实现按过期时间清理。
    生产环境应迁移到 Redis 并利用 TTL 自动过期。
    """
    return len(_token_blacklist)
