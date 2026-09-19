"""
WebSocket 路由端点
提供实时数据推送的 WebSocket 连接入口。
"""
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException

from .manager import get_ws_manager

logger = logging.getLogger(__name__)

websocket_router = APIRouter()


def _ws_auth_reject_reason(token: Optional[str]) -> Optional[str]:
    """WebSocket 连接的鉴权判定（抽成纯判定函数，便于单测）。

    修复 2026-09-17（D1）：鉴权改为**尊重 AUTH_ENABLED 开关**，与 REST 同口径。
    此前本端点无条件校验 JWT，而 REST（`api/dependencies/auth.py:78`）在
    AUTH_ENABLED=false 时整体跳过校验。结果是开发环境下 REST 永久可用、用户长期
    不重登，token 静默过期后只有 WS 每次被拒 —— WS 是当时唯一不遵守该开关的鉴权面，
    这个不一致本身就是缺陷。开关判定复用 REST 的同一处实现，避免出现第二份开关逻辑。

    Returns:
        None  → 放行（AUTH_ENABLED=false，或令牌校验通过）
        str   → 拒绝原因（调用方据此以 4401 关闭连接）
    """
    from api.dependencies.auth import _is_auth_enabled

    if not _is_auth_enabled():
        logger.debug("WebSocket 跳过鉴权（AUTH_ENABLED=false）")
        return None

    if not token:
        return "未提供认证令牌"

    try:
        from modules.system.auth.jwt_handler import verify_access_token

        verify_access_token(token=token)
        return None
    except HTTPException as e:
        # 注意：starlette 0.27 的 HTTPException 未定义 __str__，str(e) 恒为空，
        # 必须取 detail（2026-09-17 事故教训）
        return f"认证令牌无效或已过期: {getattr(e, 'detail', '')}"
    except Exception as e:
        logger.warning("WebSocket 鉴权异常: %s", e)
        return "认证失败"


@websocket_router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    channel: Optional[str] = Query(None, description="订阅频道，逗号分隔可订阅多个"),
    token: Optional[str] = Query(None, description="JWT 认证令牌"),
):
    """WebSocket 主端点

    连接后可发送 JSON 消息控制订阅：
    - {"action": "subscribe", "channel": "trade.order"}  订阅频道
    - {"action": "unsubscribe", "channel": "trade.order"}  取消订阅
    """
    # 修复 2026-08（B2）：连接鉴权——token 缺失或无效时拒绝连接
    # 修复 2026-09-17（D1）：判定改为尊重 AUTH_ENABLED（见 `_ws_auth_reject_reason`）
    # 修复 2026-09-17（D3）：拒绝路径原本**一条日志都没有**，且"未 accept 就 close"
    #   会被 ASGI 转成 HTTP 403 —— 服务端只剩裸 `403 Forbidden`、客户端只能看到
    #   1006（与服务器宕机无法区分），完全无法定位。现补日志 + 先 accept 再 close(4401)。
    _reject_reason = _ws_auth_reject_reason(token)
    if _reject_reason:
        logger.warning(
            "WebSocket 鉴权失败，拒绝连接: %s（token %s）",
            _reject_reason, "已提供" if token else "缺失",
        )
        # 必须先 accept：ASGI 语义下"未 accept 就 close"= 拒绝握手 → 客户端得到
        # HTTP 403 且读不到 reason，表现为与本错误无关的报错。
        await websocket.accept()
        await websocket.close(code=4401, reason=_reject_reason)
        return

    ws_manager = get_ws_manager()
    await ws_manager.connect(websocket)

    # 处理 URL 参数中的初始频道订阅
    if channel:
        for ch in channel.split(","):
            ch = ch.strip()
            if ch:
                await ws_manager.subscribe(websocket, ch)

    try:
        while True:
            data = await websocket.receive_text()

            # 客户端控制消息
            import json
            try:
                msg = json.loads(data)
                action = msg.get("action", "")
                ch = msg.get("channel", "")

                if action == "subscribe" and ch:
                    await ws_manager.subscribe(websocket, ch)
                    await websocket.send_text(json.dumps({
                        "type": "subscribed",
                        "channel": ch
                    }))
                elif action == "unsubscribe" and ch:
                    await ws_manager.unsubscribe(websocket, ch)
                    await websocket.send_text(json.dumps({
                        "type": "unsubscribed",
                        "channel": ch
                    }))
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"Unknown action: {action}"
                    }))
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON"
                }))

    except WebSocketDisconnect:
        logger.info("WebSocket 客户端断开连接")
    except Exception as e:
        logger.error("WebSocket 异常: %s", str(e))
    finally:
        await ws_manager.disconnect(websocket)


@websocket_router.get("/ws/health")
async def websocket_health():
    """WebSocket 健康检查"""
    ws_manager = get_ws_manager()
    return {
        "status": "healthy",
        "active_connections": ws_manager.active_connections,
        "channels": ws_manager.channel_count(),
    }
