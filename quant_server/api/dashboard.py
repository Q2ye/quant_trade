# api/dashboard.py 仪表盘API
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from quant_server.api.dependencies import get_db, get_data_service
from quant_server.api.login import get_current_user, User
from quant_server.shared.database.models.business_models import AccountDailyPerformance, Position, Order, Signal

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
async def get_dashboard_overview(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
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
async def get_market_status(data_service=Depends(get_data_service)):
    """获取市场状态"""
    # 获取大盘指数、涨跌家数等市场数据
    # 获取上证指数
    sh_index_data = data_service.index_daily.get_latest_by_code("000001.SH")
    # 获取深证成指
    sz_index_data = data_service.index_daily.get_latest_by_code("399001.SZ")
    # 获取创业板指
    cy_index_data = data_service.index_daily.get_latest_by_code("399006.SZ")

    # 获取市场涨跌家数（需要实现相应的方法）
    market_stats = data_service.get_market_advance_decline()

    return {
        "sh_index": sh_index_data.close if sh_index_data else 0,
        "sz_index": sz_index_data.close if sz_index_data else 0,
        "cy_index": cy_index_data.close if cy_index_data else 0,
        "sh_change": sh_index_data.pct_chg if sh_index_data else 0,
        "sz_change": sz_index_data.pct_chg if sz_index_data else 0,
        "cy_change": cy_index_data.pct_chg if cy_index_data else 0,
        "advance_count": market_stats.get("advance", 0),
        "decline_count": market_stats.get("decline", 0),
        "unchanged_count": market_stats.get("unchanged", 0)
    }
