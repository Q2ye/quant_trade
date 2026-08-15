# -*- coding: utf-8 -*-
"""
事件引擎依赖模块 — 薄接线层

不自行创建 EventEngine 实例，通过 set_event_engine() 接受 main.py 注入的实例。
Router 通过 Depends(get_event_engine) 获取统一的事件引擎。
"""

import logging
from typing import Optional

from core.engines.system.event_engine import EventEngine

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
