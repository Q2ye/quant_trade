# api/backtest.py
import datetime
import logging
import time
import uuid
from enum import Enum
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from quant_server.api.dependencies import get_main_engine, get_db
from quant_server.core.strategy_engine.main_engine import MainEngine
from quant_server.db.models.business_models import (
    BacktestTask, BacktestEquityCurve, BacktestTrade, BacktestPosition
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

# 内存中的任务存储（生产环境应考虑使用Redis或数据库）
backtest_tasks: Dict[str, BacktestTask] = {}


class BacktestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BacktestConfig(BaseModel):
    """回测配置模型"""
    strategy_name: str
    symbols: List[str]
    start_date: str  # 格式: YYYY-MM-DD
    end_date: str  # 格式: YYYY-MM-DD
    initial_capital: float = 1000000.0
    commission_rate: float = 0.0003
    slippage_rate: float = 0.0001
    name: Optional[str] = None
    description: Optional[str] = None


@router.post("/run", response_model=Dict[str, str])
async def run_backtest(
        backtest_config: BacktestConfig,
        background_tasks: BackgroundTasks,
        main_engine: MainEngine = Depends(get_main_engine),
        db: Session = Depends(get_db)
):
    """运行回测"""
    try:
        # 1. 创建任务记录
        task_id = str(uuid.uuid4())

        # 获取当前用户ID（需要实现认证系统）
        # 这里假设从请求上下文中获取用户ID
        user_id = 1  # 临时值，实际应从认证信息中获取

        # 创建数据库记录
        db_task = BacktestTask(
            id=task_id,
            user_id=user_id,
            strategy_id=backtest_config.strategy_name,  # 这里需要根据策略名称获取策略ID
            name=backtest_config.name or f"回测任务-{backtest_config.strategy_name}",
            description=backtest_config.description,
            status=BacktestStatus.PENDING,
            config=backtest_config.model_dump(),
            created_at=datetime.datetime.now(),
        )

        db.add(db_task)
        db.commit()

        # 2. 将任务提交到后台
        background_tasks.add_task(
            execute_backtest_task,
            task_id,
            main_engine,
            backtest_config.model_dump(),
            db
        )

        return {"status": "started", "message": "回测任务已开始", "task_id": task_id}

    except Exception as e:
        logger.error(f"启动回测失败: {str(e)}")
        raise HTTPException(status_code=400, detail=f"启动回测失败: {str(e)}")


@router.get("/tasks", response_model=List[Dict[str, Any]])
async def list_backtest_tasks(
        skip: int = 0,
        limit: int = 20,
        status: Optional[BacktestStatus] = None,
        db: Session = Depends(get_db)
):
    """获取回测任务列表"""
    try:
        query = db.query(BacktestTask)

        if status:
            query = query.filter(BacktestTask.status == status)

        tasks = query.order_by(BacktestTask.created_at.desc()).offset(skip).limit(limit).all()

        return [{
            "id": task.id,
            "name": task.name,
            "strategy_id": task.strategy_id,
            "status": task.status,
            "progress": task.progress,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at
        } for task in tasks]

    except Exception as e:
        logger.error(f"获取回测任务列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取回测任务列表失败: {str(e)}")


@router.get("/tasks/{task_id}", response_model=Dict[str, Any])
async def get_backtest_task(
        task_id: str,
        db: Session = Depends(get_db)
):
    """获取回测任务详情"""
    try:
        task = db.query(BacktestTask).filter(BacktestTask.id == task_id).first()

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        return {
            "id": task.id,
            "name": task.name,
            "description": task.description,
            "strategy_id": task.strategy_id,
            "status": task.status,
            "progress": task.progress,
            "config": task.config,
            "result": task.result,
            "error_message": task.error_message,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取回测任务详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取回测任务详情失败: {str(e)}")


@router.get("/tasks/{task_id}/equity", response_model=List[Dict[str, Any]])
async def get_backtest_equity(
        task_id: str,
        db: Session = Depends(get_db)
):
    """获取回测净值曲线"""
    try:
        task = db.query(BacktestTask).filter(BacktestTask.id == task_id).first()

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        if task.status != BacktestStatus.COMPLETED:
            raise HTTPException(status_code=425, detail="任务未完成")

        equity_data = db.query(BacktestEquityCurve).filter(
            BacktestEquityCurve.task_id == task_id
        ).order_by(BacktestEquityCurve.trade_date).all()

        return [{
            "trade_date": curve.trade_date,
            "equity": curve.equity,
            "cash": curve.cash,
            "market_value": curve.market_value
        } for curve in equity_data]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取回测净值曲线失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取回测净值曲线失败: {str(e)}")


@router.get("/tasks/{task_id}/trades", response_model=List[Dict[str, Any]])
async def get_backtest_trades(
        task_id: str,
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db)
):
    """获取回测交易记录"""
    try:
        task = db.query(BacktestTask).filter(BacktestTask.id == task_id).first()

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        if task.status != BacktestStatus.COMPLETED:
            raise HTTPException(status_code=425, detail="任务未完成")

        trades = db.query(BacktestTrade).filter(
            BacktestTrade.task_id == task_id
        ).order_by(BacktestTrade.trade_time.desc()).offset(skip).limit(limit).all()

        return [{
            "trade_time": trade.trade_time,
            "ts_code": trade.ts_code,
            "direction": trade.direction,
            "price": trade.price,
            "volume": trade.volume,
            "value": trade.value,
            "commission": trade.commission,
            "tax": trade.tax
        } for trade in trades]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取回测交易记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取回测交易记录失败: {str(e)}")


@router.get("/tasks/{task_id}/positions", response_model=List[Dict[str, Any]])
async def get_backtest_positions(
        task_id: str,
        date: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """获取回测持仓快照"""
    try:
        task = db.query(BacktestTask).filter(BacktestTask.id == task_id).first()

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        if task.status != BacktestStatus.COMPLETED:
            raise HTTPException(status_code=425, detail="任务未完成")

        query = db.query(BacktestPosition).filter(BacktestPosition.task_id == task_id)

        if date:
            query = query.filter(BacktestPosition.trade_date == date)

        positions = query.order_by(BacktestPosition.trade_date.desc()).all()

        return [{
            "trade_date": pos.trade_date,
            "ts_code": pos.ts_code,
            "volume": pos.volume,
            "cost_price": pos.cost_price,
            "market_value": pos.market_value
        } for pos in positions]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取回测持仓快照失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取回测持仓快照失败: {str(e)}")


@router.delete("/tasks/{task_id}")
async def cancel_backtest_task(
        task_id: str,
        db: Session = Depends(get_db)
):
    """取消回测任务"""
    try:
        task = db.query(BacktestTask).filter(BacktestTask.id == task_id).first()

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        if task.status not in [BacktestStatus.PENDING, BacktestStatus.RUNNING]:
            raise HTTPException(status_code=400, detail="只能取消等待中或运行中的任务")

        # 更新任务状态
        task.status = BacktestStatus.CANCELLED
        task.completed_at = time.time()
        db.commit()

        return {"status": "success", "message": "任务已取消"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消回测任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取消回测任务失败: {str(e)}")


# 后台任务执行函数
async def execute_backtest_task(
        task_id: str,
        main_engine: MainEngine,
        config: Dict[str, Any],
        db: Session
):
    """执行回测任务"""
    task = db.query(BacktestTask).filter(BacktestTask.id == task_id).first()
    if not task:
        return

    try:
        # 更新任务状态为运行中
        task.status = BacktestStatus.RUNNING
        task.started_at = time.time()
        db.commit()

        strategy_manager = main_engine.get_engine("strategy_manager")
        result = await strategy_manager.run_backtest(
            config["strategy_name"],
            config
        )

        # 存储结果
        task.status = BacktestStatus.COMPLETED
        task.result = result
        task.completed_at = time.time()
        db.commit()

    except Exception as e:
        logger.error(f"回测任务 {task_id} 执行失败: {str(e)}", exc_info=True)
        task.status = BacktestStatus.FAILED
        task.error_message = str(e)
        task.completed_at = time.time()
        db.commit()