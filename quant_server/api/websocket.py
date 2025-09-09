# api/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import json


router = APIRouter()


class WebSocketManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """广播消息给所有连接"""
        message_json = json.dumps(message)
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception:
                disconnected.append(connection)

        # 移除已断开的连接
        for connection in disconnected:
            self.disconnect(connection)


# 全局WebSocket管理器
websocket_manager = WebSocketManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接端点"""
    await websocket_manager.connect(websocket)

    try:
        while True:
            # 保持连接活跃，可以接收客户端消息
            data = await websocket.receive_text()

            # 处理客户端消息（可选）
            try:
                message = json.loads(data)
                # 根据消息类型处理
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)