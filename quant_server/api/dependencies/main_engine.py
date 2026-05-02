# -*- coding: utf-8 -*-
"""
主引擎依赖模块 — 薄接线层

不自行创建 MainEngine 实例，通过 set_main_engine() 接受 main.py 注入的实例。
Router 通过 Depends(get_main_engine) 获取统一的主引擎。
"""

import logging
from typing import Optional

from fastapi import Depends

from quant_server.core.engines.system.main_engine import MainEngine

logger = logging.getLogger(__name__)

# ========== 模块级单例（由 main.py 注入） ==========
_main_engine: Optional[MainEngine] = None


def set_main_engine(engine: MainEngine) -> None:
    """注入 MainEngine 实例（由 main.py 在初始化后调用）"""
    global _main_engine
    _main_engine = engine
    logger.info("MainEngine 实例已注入到 API 依赖层")


async def get_main_engine() -> MainEngine:
    """获取主引擎（FastAPI Depends 兼容）

    Raises:
        RuntimeError: 引擎尚未注入
    """
    if _main_engine is None:
        raise RuntimeError("MainEngine 尚未初始化，请确认 main.py 已调用 set_main_engine()")
    return _main_engine


MainEngineDep = Depends(get_main_engine)
