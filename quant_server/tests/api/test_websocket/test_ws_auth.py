# -*- coding: utf-8 -*-
"""WebSocket 鉴权判定测试。

背景（2026-09-17 事故）：前端反复被拒 `WebSocket /api/ws?token=... → 403`。
根因是 WS **无条件**校验 JWT，而 REST 在 `AUTH_ENABLED=false` 时整体跳过校验
（`api/dependencies/auth.py:78`）—— 开发环境里 REST 永久可用、用户长期不重登，
token 静默过期后只有 WS 每次被拒（该 token 实测已于 5 天前过期）。
且拒绝走"未 accept 就 close"，被 ASGI 转成 HTTP 403，服务端无日志、客户端读不到原因。

本测试锁定修复后的判定契约（`_ws_auth_reject_reason`）：
  AUTH_ENABLED=false            → 放行（不看 token）
  AUTH_ENABLED=true  + 无 token → 拒绝「未提供认证令牌」
  AUTH_ENABLED=true  + 过期    → 拒绝，且原因携带 detail
  AUTH_ENABLED=true  + 有效    → 放行
  AUTH_ENABLED=true  + 校验异常 → 拒绝「认证失败」（不向上抛）
"""
import pytest
from fastapi import HTTPException

from api.websocket.routers import _ws_auth_reject_reason

AUTH_MOD = "api.dependencies.auth"
JWT_MOD = "modules.system.auth.jwt_handler"


def _set_auth_enabled(monkeypatch, enabled: bool):
    monkeypatch.setattr(f"{AUTH_MOD}._is_auth_enabled", lambda: enabled)


class TestWsAuthRejectReason:
    def test_auth_disabled_allows_even_without_token(self, monkeypatch):
        """★ 本次修复核心：AUTH_ENABLED=false 时与 REST 同口径，直接放行。"""
        _set_auth_enabled(monkeypatch, False)
        called = {"n": 0}
        monkeypatch.setattr(
            f"{JWT_MOD}.verify_access_token",
            lambda token: called.__setitem__("n", called["n"] + 1),
        )
        assert _ws_auth_reject_reason(None) is None
        assert called["n"] == 0, "关闭开关时不应再走令牌校验"

    def test_auth_disabled_allows_with_expired_token(self, monkeypatch):
        """过期 token 在关闭开关时也必须放行（否则就是本次事故的重现）"""
        _set_auth_enabled(monkeypatch, False)
        monkeypatch.setattr(
            f"{JWT_MOD}.verify_access_token",
            lambda token: (_ for _ in ()).throw(HTTPException(401, "Token 验证失败: 已过期")),
        )
        assert _ws_auth_reject_reason("expired.token.here") is None

    def test_auth_enabled_without_token_rejected(self, monkeypatch):
        _set_auth_enabled(monkeypatch, True)
        assert _ws_auth_reject_reason(None) == "未提供认证令牌"

    def test_auth_enabled_with_expired_token_rejects_with_detail(self, monkeypatch):
        """拒绝原因必须携带 detail —— starlette 0.27 的 str(HTTPException) 恒为空"""
        _set_auth_enabled(monkeypatch, True)
        monkeypatch.setattr(
            f"{JWT_MOD}.verify_access_token",
            lambda token: (_ for _ in ()).throw(HTTPException(401, "Token 验证失败: Signature has expired")),
        )
        reason = _ws_auth_reject_reason("expired.token.here")
        assert reason is not None
        assert "无效或已过期" in reason
        assert "Signature has expired" in reason, "必须带上 detail，不能是空串"

    def test_auth_enabled_with_valid_token_allows(self, monkeypatch):
        _set_auth_enabled(monkeypatch, True)
        monkeypatch.setattr(
            f"{JWT_MOD}.verify_access_token",
            lambda token: {"sub": "u1", "type": "access"},
        )
        assert _ws_auth_reject_reason("valid.token.here") is None

    def test_unexpected_verify_error_is_swallowed(self, monkeypatch):
        """校验抛非 HTTPException 时不得向上抛（否则 WS 握手会变成 500 而非明确拒绝）"""
        _set_auth_enabled(monkeypatch, True)
        monkeypatch.setattr(
            f"{JWT_MOD}.verify_access_token",
            lambda token: (_ for _ in ()).throw(RuntimeError("jwt 库炸了")),
        )
        assert _ws_auth_reject_reason("whatever") == "认证失败"
