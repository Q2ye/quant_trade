# api/performance.py  绩效分析API
from fastapi import APIRouter, Depends
from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session

from quant_server.api.dependencies import get_db
from quant_server.api.login import get_current_user
from quant_server.shared.database.models.business_models import StrategyDailyPerformance, AccountDailyPerformance

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/strategy/{strategy_id}")
async def get_strategy_performance(
        strategy_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """获取策略绩效数据"""
    query = db.query(StrategyDailyPerformance).filter(
        StrategyDailyPerformance.strategy_id == strategy_id
    )

    if start_date:
        query = query.filter(StrategyDailyPerformance.trade_date >= start_date)
    if end_date:
        query = query.filter(StrategyDailyPerformance.trade_date <= end_date)

    performance_data = query.order_by(StrategyDailyPerformance.trade_date).all()

    return {
        "strategy_id": strategy_id,
        "performance": performance_data,
        "total_records": len(performance_data)
    }


@router.get("/account")
async def get_account_performance(
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """获取账户绩效数据"""
    query = db.query(AccountDailyPerformance).filter(
        AccountDailyPerformance.user_id == current_user.id
    )

    if start_date:
        query = query.filter(AccountDailyPerformance.trade_date >= start_date)
    if end_date:
        query = query.filter(AccountDailyPerformance.trade_date <= end_date)

    performance_data = query.order_by(AccountDailyPerformance.trade_date).all()

    return {
        "user_id": current_user.id,
        "performance": performance_data,
        "total_records": len(performance_data)
    }


@router.get("/comparison")
async def compare_performance(
        strategy_ids: List[str],
        benchmark: str = "000300.SH",  # 沪深300
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """多策略绩效对比"""
    # 实现策略对比逻辑
    return {"message": "Performance comparison endpoint", "strategy_ids": strategy_ids}