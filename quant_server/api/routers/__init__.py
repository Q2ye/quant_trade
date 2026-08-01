# -*- coding: utf-8 -*-
"""
API路由包
统一导出所有路由模块
位置：quant_server/api/routers/__init__.py
"""

from .data_router import router as data_router
from .strategy_router import router as strategy_router
from .trade_router import router as trade_router
from .basket_router import router as basket_router
from .backtest_router import router as backtest_router
from .template_router import router as template_router
from .account_router import router as account_router
from .analysis_router import router as analysis_router
from .monitor_router import router as monitor_router
from .system_router import router as system_router
from .risk_router import router as risk_router
from .health_router import router as health_router
from .market_router import router as market_router
from .composite_router import router as composite_router

# 当前已注册的路由（与 api/main.py include_router 保持一致）
__all__ = [
    "data_router",
    "strategy_router",
    "trade_router",
    "basket_router",
    "backtest_router",
    "template_router",
    "account_router",
    "analysis_router",
    "monitor_router",
    "system_router",
    "risk_router",
    "health_router",
    "market_router",
    "composite_router",
]

# 路由注册顺序（影响 API 文档中的路由展示顺序）
ROUTERS = [
    data_router,
    strategy_router,
    trade_router,
    basket_router,
    backtest_router,
    template_router,
    account_router,
    analysis_router,
    monitor_router,
    system_router,
    risk_router,
    health_router,
    market_router,
    composite_router,
]