# -*- coding: utf-8 -*-
"""
事件引擎依赖模块 — 薄接线层

不自行创建 EventEngine 实例，通过 set_event_engine() 接受 main.py 注入的实例。
Router 通过 Depends(get_event_engine) 获取统一的事件引擎。
"""

import logging
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import Depends

from quant_server.core.engines.system.event_engine import EventEngine
from quant_server.core.events.engine_events import SystemEvent

logger = logging.getLogger(__name__)

# ========== 模块级单例（由 main.py 注入） ==========
_event_engine: Optional[EventEngine] = None


def set_event_engine (engine: EventEngine) -> None:
	"""注入 EventEngine 实例（由 main.py 在初始化后调用）"""
	global _event_engine
	_event_engine = engine
	logger.info("EventEngine 实例已注入到 API 依赖层")


async def get_event_engine () -> EventEngine:
	"""获取事件引擎（FastAPI Depends 兼容）

	Raises:
		RuntimeError: 引擎尚未注入
	"""
	if _event_engine is None:
		raise RuntimeError("EventEngine 尚未初始化，请确认 main.py 已调用 set_event_engine()")
	return _event_engine


# ========== 事件优先级（本地定义，避免循环依赖） ==========

class EventPriority(Enum):
	LOW = 1
	NORMAL = 2
	HIGH = 3
	CRITICAL = 4


# ========== 便捷发布函数（供 main_engine dep 使用） ==========

async def publish_system_event (
		event_type: str,
		data: Dict[str, Any],
		priority: EventPriority = EventPriority.NORMAL,
) -> str:
	"""发布系统事件"""
	engine = await get_event_engine()
	event = SystemEvent(
		event_type=event_type,
		data=data,
		priority=priority.value,
		source="system",
	)
	await engine.put(event)
	return event.event_id


# 兼容旧导入
EventEngineDep = Depends(get_event_engine)
