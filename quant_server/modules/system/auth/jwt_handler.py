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

from shared.security.jwt_handler import get_jwt_manager

logger = logging.getLogger(__name__)

# OAuth2 Bearer scheme
_bearer_scheme = HTTPBearer(auto_error=False)


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

    if is_token_blacklisted(token):
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


# Token 黑名单（优先 Redis，降级内存）
_redis_client = None
_token_blacklist: set = set()  # 内存降级方案
_blacklist_ttl_map: dict = {}  # token -> expiry timestamp（内存降级用）


def _get_redis():
    """获取 Redis 客户端（延迟连接）"""
    global _redis_client
    if _redis_client is None:
        try:
            from shared.cache.cache_manager import get_cache_manager
            cache_mgr = get_cache_manager()
            _redis_client = getattr(cache_mgr, '_redis', None)
        except Exception:
            _redis_client = False  # 标记为不可用
    return _redis_client if _redis_client is not False else None


def blacklist_token(token: str) -> None:
    """将 token 加入黑名单（优先 Redis TTL，降级内存）"""
    import time
    import hashlib

    redis_client = _get_redis()
    token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]

    if redis_client:
        try:
            # Redis TTL = token 剩余有效时间，最长 24 小时
            key = f"token_blacklist:{token_hash}"
            import asyncio
            # 同步方式设置 Redis key（配合 asyncio）
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(
                    redis_client.setex(key, 86400, "1")
                )
            logger.debug(f"Token 已加入 Redis 黑名单: {token[:10]}...")
            return
        except Exception as e:
            logger.warning(f"Redis 黑名单写入失败，降级内存: {e}")

    # 降级：内存存储 + 24h TTL
    _token_blacklist.add(token)
    _blacklist_ttl_map[token] = time.time() + 86400
    logger.debug(f"Token 已加入内存黑名单: {token[:10]}...")


def is_token_blacklisted(token: str) -> bool:
    """检查 token 是否在黑名单中（优先查 Redis）"""
    import time
    import hashlib

    redis_client = _get_redis()
    token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]

    if redis_client:
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 异步环境下无法同步获取 Redis 结果，降级内存检查
                pass
            else:
                # 同步环境
                import redis
                key = f"token_blacklist:{token_hash}"
                return redis_client.exists(key) > 0
        except Exception:
            pass

    # 降级：内存检查（含 TTL 过期清理）
    now = time.time()
    if token in _token_blacklist:
        if token in _blacklist_ttl_map and _blacklist_ttl_map[token] < now:
            _token_blacklist.discard(token)
            _blacklist_ttl_map.pop(token, None)
            return False
        return True
    return False


def clear_expired_blacklist() -> int:
    """清理过期的黑名单 token（内存降级方案）"""
    import time

    redis_client = _get_redis()
    if redis_client:
        # Redis TTL 自动过期，无需手动清理
        return 0

    now = time.time()
    expired = [
        t for t, exp in _blacklist_ttl_map.items() if exp < now
    ]
    for t in expired:
        _token_blacklist.discard(t)
        _blacklist_ttl_map.pop(t, None)
    return len(expired)
