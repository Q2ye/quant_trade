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
    if not token:
        await websocket.close(code=4401, reason="未提供认证令牌")
        return
    try:
        from modules.system.auth.jwt_handler import verify_access_token
        verify_access_token(token=token)
    except HTTPException:
        await websocket.close(code=4401, reason="认证令牌无效或已过期")
        return
    except Exception as e:
        logger.warning(f"WebSocket 鉴权异常: {e}")
        await websocket.close(code=4401, reason="认证失败")
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
