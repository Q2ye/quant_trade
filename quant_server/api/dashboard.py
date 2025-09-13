# api/dashboard.py 仪表盘API
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from quant_server.api.dependencies import get_db
from quant_server.api.login import get_current_user
from quant_server.db.models.business_models import AccountDailyPerformance, Position, Order, Signal

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
async def get_dashboard_overview(
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """获取仪表盘概览数据"""
    # 获取账户总资产
    account_perf = db.query(AccountDailyPerformance).filter(
        AccountDailyPerformance.user_id == current_user.id
    ).order_by(AccountDailyPerformance.trade_date.desc()).first()

    # 获取持仓信息
    positions = db.query(Position).filter(
        Position.user_id == current_user.id
    ).all()

    # 获取今日成交
    today = datetime.now().date()
    today_orders = db.query(Order).filter(
        Order.user_id == current_user.id,
        Order.submitted_at >= today
    ).all()

    # 获取最新信号
    recent_signals = db.query(Signal).filter(
        Signal.user_id == current_user.id
    ).order_by(Signal.created_at.desc()).limit(10).all()

    return {
        "total_asset": account_perf.total_asset if account_perf else 0,
        "cash": account_perf.cash if account_perf else 0,
        "market_value": account_perf.market_value if account_perf else 0,
        "daily_pnl": account_perf.daily_pnl if account_perf else 0,
        "positions": positions,
        "today_orders": today_orders,
        "recent_signals": recent_signals
    }


@router.get("/market-status")
async def get_market_status():
    """获取市场状态"""
    # 获取大盘指数、涨跌家数等市场数据
    # 简化实现，实际应从数据服务获取
    return {
        "sh_index": 3200.15,  # 上证指数
        "sz_index": 11000.42,  # 深证成指
        "cy_index": 2300.67,  # 创业板指
        "sh_change": 0.5,  # 上证涨跌幅
        "sz_change": -0.2,  # 深证涨跌幅
        "cy_change": 1.2,  # 创业板涨跌幅
        "advance_count": 1500,  # 上涨家数
        "decline_count": 1000,  # 下跌家数
        "unchanged_count": 200  # 平盘家数
    }