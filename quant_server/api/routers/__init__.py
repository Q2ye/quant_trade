# -*- coding: utf-8 -*-
"""
API路由包
统一导出所有路由模块
位置：quant_server/api/routers/__init__.py
"""

from .data_router import router as data_router
from .strategy_router import router as strategy_router
# from .trade_router import router as trade_router
from .backtest_router import router as backtest_router
# from .account_router import router as account_router
# from .analysis_router import router as analysis_router
from .monitor_router import router as monitor_router
# from .system_router import router as system_router
from .health_router import router as health_router

# 定义所有可用路由
__all__ = [
    "data_router",
    "strategy_router",
    "trade_router",
    "backtest_router",
    "account_router",
    "analysis_router",
    "monitor_router",
    "system_router",
    "health_router",
]

# 路由注册顺序（影响API文档中的顺序）
ROUTERS = [
    # 1. 系统模块最先注册（提供基础服务）
    # system_router,          # 系统管理

    # 2. 数据模块（其他模块依赖数据）
    data_router,            # 数据中心

    # 3. 策略模块（核心业务）
    strategy_router,        # 策略中心、

    # 4. 回测模块（依赖策略）
    backtest_router,        # 回测工作台

    # 5. 交易模块（依赖策略和数据）
    # trade_router,           # 交易中心

    # 6. 账户模块（依赖交易）
    # account_router,         # 账户管理

    # 7. 分析模块（依赖所有业务模块）
    # analysis_router,        # 分析中心

    # 8. 监控模块（监控所有模块）
    # monitor_router,         # 监控中心

    # 9. 健康检查（最后注册）
    health_router,          # 健康检查
]