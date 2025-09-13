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

router.include_router(login_router)
router.include_router(strategy_router)
router.include_router(backtest_router)
router.include_router(basket_router)
router.include_router(trade_router)
router.include_router(market_router)
router.include_router(data_sync_router)
router.include_router(system_router)
router.include_router(websocket_router)
router.include_router(performance_router)
router.include_router(risk_router)
router.include_router(signal_router)
router.include_router(dashboard_router)