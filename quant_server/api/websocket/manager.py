"""
WebSocket 连接管理器
管理所有活跃的 WebSocket 连接，支持按频道广播事件。
"""
import asyncio
import json
import logging
from typing import Dict, List, Set, Optional, Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from core.exceptions import BusinessException

logger = logging.getLogger(__name__)


class WebSocketManager:
    """WebSocket 连接管理器（单例模式）

    职责：
    - 管理客户端连接的注册/注销
    - 按频道广播消息
    - 从 EventEngine 接收事件并推送到订阅频道
    """

    def __init__(self):
        # {channel: {websocket, ...}}
        self._channels: Dict[str, Set[WebSocket]] = {}
        # {websocket: {channel, ...}}  反向索引，用于断线清理
        self._ws_subscriptions: Dict[WebSocket, Set[str]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    async def connect( websocket: WebSocket) -> None:
        """接受 WebSocket 连接"""
        await websocket.accept()
        logger.info("WebSocket 客户端已连接: %s", websocket.client)

    async def disconnect(self, websocket: WebSocket) -> None:
        """断开连接并清理所有订阅"""
        async with self._lock:
            if websocket in self._ws_subscriptions:
                channels = self._ws_subscriptions.pop(websocket)
                for channel in channels:
                    if channel in self._channels:
                        self._channels[channel].discard(websocket)
                        if not self._channels[channel]:
                            del self._channels[channel]
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
        logger.info("WebSocket 客户端已断开: %s", websocket.client)

    async def subscribe(self, websocket: WebSocket, channel: str) -> None:
        """订阅频道"""
        async with self._lock:
            self._channels.setdefault(channel, set()).add(websocket)
            self._ws_subscriptions.setdefault(websocket, set()).add(channel)
        logger.info("客户端订阅频道 %s: %s", channel, websocket.client)

    async def unsubscribe(self, websocket: WebSocket, channel: str) -> None:
        """取消订阅频道"""
        async with self._lock:
            if channel in self._channels:
                self._channels[channel].discard(websocket)
                if not self._channels[channel]:
                    del self._channels[channel]
            if websocket in self._ws_subscriptions:
                self._ws_subscriptions[websocket].discard(channel)

    async def broadcast(self, channel: str, data: Any) -> None:
        """向指定频道的所有客户端广播消息"""
        if channel not in self._channels:
            return

        message = json.dumps(data, ensure_ascii=False, default=str)
        dead_connections: List[WebSocket] = []

        for ws in list(self._channels.get(channel, set())):
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(message)
            except BusinessException:
                dead_connections.append(ws)

        # 清理断开的连接
        for ws in dead_connections:
            await self.disconnect(ws)

    async def broadcast_to_all(self, data: Any) -> None:
        """向所有连接的客户端广播消息"""
        message = json.dumps(data, ensure_ascii=False, default=str)
        dead: List[WebSocket] = []

        all_ws: Set[WebSocket] = set()
        for ws_set in self._channels.values():
            all_ws.update(ws_set)

        for ws in all_ws:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(message)
            except BusinessException:
                dead.append(ws)

        for ws in dead:
            await self.disconnect(ws)

    @property
    def active_connections(self) -> int:
        """活跃连接数"""
        return len(self._ws_subscriptions)

    def channel_count(self) -> Dict[str, int]:
        """各频道订阅数"""
        return {ch: len(ws_set) for ch, ws_set in self._channels.items()}


# 模块级单例
_ws_manager: Optional[WebSocketManager] = None


def get_ws_manager() -> WebSocketManager:
    """获取 WebSocketManager 单例"""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager
