# api/strategy.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from quant_server.api.dependencies import get_strategy_manager_engine
from quant_server.api.strategy_models import StrategyResponse, StrategyCreate

from quant_server.core.strategy_engine.engines.strategy_manager_engine import StrategyManagerEngine

router = APIRouter(prefix="/api/strategies", tags=["strategies"])

@router.get("", response_model=List[StrategyResponse])
async def get_strategies(
    strategy_manager: StrategyManagerEngine = Depends(get_strategy_manager_engine)
):
    """获取所有策略"""
    return list(strategy_manager.get_all_strategies().values())




@router.post("", response_model=StrategyResponse)
async def create_strategy(
    strategy_data: StrategyCreate,
    strategy_manager: StrategyManagerEngine = Depends(get_strategy_manager_engine)
):
    """创建新策略"""
    try:
        strategy = await strategy_manager.add_strategy(strategy_data.model_dump())
        return strategy
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建策略失败: {str(e)}")

@router.post("/{strategy_name}/start")
async def start_strategy(
    strategy_name: str,
    engine_type: str = "alpha",  # 默认使用alpha引擎
    strategy_manager: StrategyManagerEngine = Depends(get_strategy_manager_engine)
):
    """启动策略"""
    try:
        await strategy_manager.start_strategy(strategy_name, engine_type)
        return {"status": "success", "message": f"策略 {strategy_name} 已启动"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"启动策略失败: {str(e)}")

@router.post("/{strategy_name}/stop")
async def stop_strategy(
    strategy_name: str,
    strategy_manager: StrategyManagerEngine = Depends(get_strategy_manager_engine)
):
    """停止策略"""
    try:
        await strategy_manager.stop_strategy(strategy_name)
        return {"status": "success", "message": f"策略 {strategy_name} 已停止"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"停止策略失败: {str(e)}")