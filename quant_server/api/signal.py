# api/signal.py 信号API
from fastapi import APIRouter, Depends
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from quant_server.api.dependencies import get_db
from quant_server.api.login import get_current_user
from quant_server.shared.database.models.business_models import Signal

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/")
async def get_signals(
        strategy_id: Optional[str] = None,
        symbol: Optional[str] = None,
        signal_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """获取信号记录"""
    query = db.query(Signal).filter(Signal.user_id == current_user.id)

    if strategy_id:
        query = query.filter(Signal.strategy_id == strategy_id)
    if symbol:
        query = query.filter(Signal.symbol == symbol)
    if signal_type:
        query = query.filter(Signal.signal_type == signal_type)
    if start_time:
        query = query.filter(Signal.created_at >= start_time)
    if end_time:
        query = query.filter(Signal.created_at <= end_time)

    signals = query.order_by(Signal.created_at.desc()).limit(limit).all()

    return {"signals": signals, "total_count": len(signals)}


@router.get("/strength/{symbol}")
async def get_signal_strength(
        symbol: str,
        period: int = 7,  # 天
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """获取信号强度分析"""
    start_time = datetime.now() - timedelta(days=period)

    signals = db.query(Signal).filter(
        Signal.user_id == current_user.id,
        Signal.symbol == symbol,
        Signal.created_at >= start_time
    ).order_by(Signal.created_at).all()

    # 计算信号强度统计
    buy_signals = [s for s in signals if s.direction == "BUY"]
    sell_signals = [s for s in signals if s.direction == "SELL"]

    return {
        "symbol": symbol,
        "period": period,
        "total_signals": len(signals),
        "buy_signals": len(buy_signals),
        "sell_signals": len(sell_signals),
        "avg_buy_strength": sum(s.signal_strength for s in buy_signals) / len(buy_signals) if buy_signals else 0,
        "avg_sell_strength": sum(s.signal_strength for s in sell_signals) / len(sell_signals) if sell_signals else 0
    }