"""
API路由包
统一导出所有路由模块
位置：quant_server/api/routers/__init__.py
"""

from .data_router import router as data_router
# from .monitor_router import router as monitor_router
from .health_router import router as health_router

# 导入其他路由模块（根据实际实现添加）
# from .strategy_router import router as strategy_router
# from .trade_router import router as trade_router
# from .backtest_router import router as backtest_router
# from .account_router import router as account_router
# from .analysis_router import router as analysis_router
# from .system_router import router as system_router

# 定义所有可用路由
__all__ = [
    "data_router",
    "monitor_router",
    "health_router",
    # "strategy_router",
    # "trade_router",
    # "backtest_router",
    # "account_router",
    # "analysis_router",
    # "system_router",
]

# 路由注册顺序（影响API文档中的顺序）
ROUTERS = [
    data_router,       # 数据模块
    # strategy_router,  # 策略模块
    # trade_router,     # 交易模块
    # backtest_router,  # 回测模块
    # account_router,   # 账户模块
    # analysis_router,  # 分析模块
    # monitor_router,    # 监控模块
    health_router,     # 健康检查
    # system_router,    # 系统模块
]