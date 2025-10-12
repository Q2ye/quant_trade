# api/__init__.py
from fastapi import APIRouter

from .login import router as login_router
from .strategy import router as strategy_router
from .backtest import router as backtest_router
from .basket import router as basket_router
from .trade import router as trade_router
from .market import router as market_router
from .data_sync import router as data_sync_router
from .system import router as system_router
from .websocket import router as websocket_router
from .performance import router as performance_router
from .risk import router as risk_router
from .signal import router as signal_router
from .dashboard import router as dashboard_router

router = APIRouter()

quantTrade = APIRouter(prefix="/quant-trade")
quantTrade.include_router(login_router)
quantTrade.include_router(strategy_router)
quantTrade.include_router(backtest_router)
quantTrade.include_router(basket_router)
quantTrade.include_router(trade_router)
quantTrade.include_router(market_router)
quantTrade.include_router(data_sync_router)
quantTrade.include_router(system_router)
quantTrade.include_router(websocket_router)
quantTrade.include_router(performance_router)
quantTrade.include_router(risk_router)
quantTrade.include_router(signal_router)
quantTrade.include_router(dashboard_router)

router.include_router(quantTrade)