"""
WebSocket 连接管理器
管理所有活跃的 WebSocket 连接，支持按频道广播事件。
"""
import asyncio
import json
import logging
from typing import Dict, List, Set, Optional, Any, Callable

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from core.exceptions import BusinessException

logger = logging.getLogger(__name__)

# EventEngine event_type → WebSocket channel 映射表
_EVENT_CHANNEL_MAP: Dict[str, str] = {
    # 订单状态
    "order_created": "order:status",
    "order_filled": "order:status",
    "order_cancelled": "order:status",
    "order_create": "order:status",
    "order_submit": "order:status",
    "order_update": "order:status",
    "order_fill": "order:status",
    "order_reject": "order:status",
    # 成交回报
    "execution_success": "events:execution",
    "execution_error": "events:execution",
    # 持仓变动
    "position_event": "events:positions",
    "position_update": "events:positions",
    "position_change": "events:positions",
    "position_risk": "events:positions",
    "position_limit": "events:positions",
    # 账户资金
    "account_update": "events:account",
    "capital_change": "events:account",
    "margin_call": "events:account",
    "account.balance.updated": "events:account",
    "account.asset.updated": "events:account",
    "account.position.updated": "events:positions",
    "account.position.opened": "events:positions",
    "account.position.closed": "events:positions",
    # 交易信号
    "signal.entry": "events:signals",
    "signal.exit": "events:signals",
    "signal.stop_loss": "events:signals",
    "signal.take_profit": "events:signals",
    "signal.rebalance": "events:signals",
    # 风控告警
    "trade.risk.alert": "risk:alerts",
    "trade.risk.violation": "risk:alerts",
    "trade.risk.limit": "risk:alerts",
    "trade.risk.position": "risk:alerts",
    "trade.risk.account": "risk:alerts",
    "trade.risk.check": "risk:alerts",
    "trade.risk.action": "risk:alerts",
    # 系统状态
    "system.heartbeat": "events:status",
    "system.alert": "events:status",
    "system.started": "events:status",
    "system.stopped": "events:status",
    # 数据同步（EngineLifecycleEvent 前缀 — sync_engine.py 发布路径）
    "engine.data_sync_started": "events:sync",
    "engine.data_sync_progress": "events:sync",
    "engine.data_sync_completed": "events:sync",
    "engine.data_sync_failed": "events:sync",
    "engine.data_sync_cancelled": "events:sync",
    # 数据同步（DataEventType 直接事件 — handlers.py 发布路径）
    "data.sync.started": "events:sync",
    "data.sync.progress": "events:sync",
    "data.sync.completed": "events:sync",
    "data.sync.failed": "events:sync",
    "data.sync.cancelled": "events:sync",
}


class WebSocketManager:
    """WebSocket 连接管理器（单例模式）

    职责：
    - 管理客户端连接的注册/注销
    - 按频道广播消息
    - 从 EventEngine 接收事件并推送到订阅频道
    """

    def __init__(self, event_engine=None):
        # {channel: {websocket, ...}}
        self._channels: Dict[str, Set[WebSocket]] = {}
        # {websocket: {channel, ...}}  反向索引，用于断线清理
        self._ws_subscriptions: Dict[WebSocket, Set[str]] = {}
        self._lock = asyncio.Lock()
        # EventEngine 桥接
        self._event_engine = event_engine
        self._handler_ids: Dict[str, str] = {}  # event_type → handler_id
        self._active = False

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

    async def _send_one(self, ws: WebSocket, message: str):
        """单客户端安全发送（修复 2026-08 B14）：5 秒超时，断线返回 False 不抛出"""
        import asyncio
        try:
            if ws.client_state == WebSocketState.CONNECTED:
                await asyncio.wait_for(ws.send_text(message), timeout=5.0)
            return True
        except Exception:
            return False

    async def broadcast(self, channel: str, data: Any) -> None:
        """向指定频道的所有客户端广播消息"""
        if channel not in self._channels:
            logger.debug("WS broadcast: channel=%s 无订阅者，跳过", channel)
            return

        subscribers = list(self._channels[channel])
        message = json.dumps(data, ensure_ascii=False, default=str, allow_nan=False)
        dead_connections: List[WebSocket] = []

        # 修复 2026-08（B14）：并发发送 + 每客户端超时 + 异常隔离，
        # 慢客户端不再阻塞整个频道广播；异常捕获扩展（原仅 BusinessException）
        import asyncio
        ok_flags = await asyncio.gather(
            *[self._send_one(ws, message) for ws in subscribers],
            return_exceptions=True,
        )
        for ws, ok in zip(subscribers, ok_flags):
            if ok is True:
                continue
            dead_connections.append(ws)

        sent = len(subscribers) - len(dead_connections)
        if sent > 0:
            logger.debug("WS 推送: channel=%s, 发送=%d/%d", channel, sent, len(subscribers))

        # 清理断开的连接
        for ws in dead_connections:
            await self.disconnect(ws)

    async def broadcast_to_all(self, data: Any) -> None:
        """向所有连接的客户端广播消息"""
        message = json.dumps(data, ensure_ascii=False, default=str, allow_nan=False)
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

    # ================================================================
    # EventEngine 桥接方法
    # ================================================================

    async def _on_event(self, event, channel: str) -> None:
        """EventEngine 事件回调：将事件数据广播到对应 WebSocket 频道"""
        event_data = getattr(event, "data", {})
        event_type = getattr(event, "event_type", "unknown")

        if not event_data:
            logger.debug("WS _on_event: event_type=%s data为空，跳过", event_type)
            return

        # EngineLifecycleEvent 将业务数据嵌套在 data["details"] 中，需要解包
        if isinstance(event_data, dict) and "details" in event_data:
            business_data = event_data["details"]
            # 注入 _event 标记让前端区分子类型（如 started/progress/completed）
            if isinstance(business_data, dict):
                business_data["_event"] = event_type.replace("engine.", "")
            payload = {
                "channel": channel,
                "data": business_data,
                "event_type": event_type,
                "timestamp": str(getattr(event, "created_time", "")),
            }
        else:
            payload = {
                "channel": channel,
                "data": event_data,
                "event_type": event_type,
                "timestamp": str(getattr(event, "created_time", "")),
            }

        sub_count = len(self._channels.get(channel, set()))
        if sub_count > 0:
            logger.info("WS 事件转发: event_type=%s → channel=%s, 订阅者=%d", event_type, channel, sub_count)
        else:
            logger.debug("WS 事件转发(无订阅者): event_type=%s → channel=%s", event_type, channel)
        await self.broadcast(channel, payload)

    def _make_handler(self, channel: str) -> Callable:
        """为指定 channel 创建事件处理器闭包"""
        async def handler(event):
            await self._on_event(event, channel)

        return handler

    async def initialize(self) -> None:
        """初始化 EventEngine → WebSocket 桥接

        向 EventEngine 订阅 _EVENT_CHANNEL_MAP 中定义的所有事件类型，
        收到事件后自动广播到对应 WebSocket 频道。
        """
        if not self._event_engine:
            logger.info("WebSocketManager: 未提供 event_engine，跳过事件桥接初始化")
            self._active = True
            return

        for event_type, channel in _EVENT_CHANNEL_MAP.items():
            handler = self._make_handler(channel)
            hid = self._event_engine.subscribe(event_type, handler)
            self._handler_ids[event_type] = hid

        self._active = True
        logger.info(
            "WebSocketManager 事件桥接初始化完成，已注册 %d 个事件类型",
            len(self._handler_ids),
        )

    async def start(self) -> None:
        """启动 WebSocket 管理器（占位，连接由路由层管理）"""
        self._active = True
        logger.info("WebSocketManager 已启动")

    async def stop(self) -> None:
        """停止 WebSocket 管理器，清理事件订阅"""
        self._active = False
        if self._event_engine:
            for event_type, hid in self._handler_ids.items():
                self._event_engine.unregister(event_type, hid)
            self._handler_ids.clear()
        logger.info("WebSocketManager 已停止，事件订阅已清理")

    async def broadcast_event(self, data: Any, channel: str = None) -> None:
        """广播事件数据（MainEngine 调用别名）

        Args:
            data: 事件数据
            channel: 目标频道，为 None 时广播到所有连接
        """
        if channel:
            await self.broadcast(channel, data)
        else:
            await self.broadcast_to_all(data)

    @property
    def is_active(self) -> bool:
        """管理器是否已初始化"""
        return self._active


# 模块级单例
_ws_manager: Optional[WebSocketManager] = None


def get_ws_manager(event_engine=None) -> WebSocketManager:
    """获取 WebSocketManager 单例

    Args:
        event_engine: EventEngine 实例，仅在首次创建时使用
    """
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager(event_engine=event_engine)
    return _ws_manager
