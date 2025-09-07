# quant_server/api/__init__.py
from fastapi import APIRouter

from .market import router as market_router
from .strategy import router as strategy_router
from .basket import router as basket_router
from .trade import router as trade_router
from .system import router as system_router
from .login import router as login_router
from .data_sync import router as data_sync_router
api_router = APIRouter()

api_router.include_router(market_router)
api_router.include_router(strategy_router)
api_router.include_router(basket_router)
api_router.include_router(trade_router)
api_router.include_router(system_router)
api_router.include_router(login_router)
api_router.include_router(data_sync_router)

# 添加一个简单的健康检查端点
@api_router.get("/health")
async def health_check():
    return {"status": "healthy"}