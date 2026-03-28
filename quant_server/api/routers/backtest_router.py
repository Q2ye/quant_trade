# -*- coding: utf-8 -*-
"""
回测模块API路由
基于混合架构设计，负责将HTTP请求路由到回测模块的业务处理层
位置：quant_server/api/routers/backtest_router.py
回测模块路由
"""
from typing import Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import logging

# 导入架构依赖
from quant_server.api.dependencies.database import get_db_session
from quant_server.api.dependencies.auth import get_current_user
from quant_server.api.dependencies.event_engine import get_event_engine

# 导入响应格式化工具
from quant_server.utils.api_utils.response_formatter import success_response, error_response

# 导入回测模块的业务层处理函数
from quant_server.modules.backtest.handlers import (
    create_backtest_task,
    get_backtest_task,
    get_backtest_task_list,
    cancel_backtest_task,
    get_backtest_equity_curve,
    get_backtest_trades,
    get_backtest_positions,
    get_backtest_result,
    optimize_backtest_parameters,
    check_backtest_module_health
)

# 导入回测模块的Pydantic模型
from quant_server.modules.backtest.schemas import (
    BacktestCreateRequest,
    BacktestCreateResponse,
    BacktestDetailResponse,
    BacktestListRequest,
    BacktestListResponse,
    BacktestCancelRequest,
    BacktestEquityCurveRequest,
    BacktestEquityCurveResponse,
    BacktestTradesRequest,
    BacktestTradesResponse,
    BacktestPositionsRequest,
    BacktestPositionsResponse,
    BacktestResultResponse,
    BacktestOptimizeRequest,
    BacktestOptimizeResponse
)

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器实例
router = APIRouter(
    prefix="/backtest",
    tags=["回测工作台"],
    responses={
        401: {"description": "认证失败"},
        403: {"description": "权限不足"},
        500: {"description": "服务器内部错误"}
    }
)


# ==================== 回测任务管理接口 ====================

@router.post("/tasks", response_model=BacktestCreateResponse, status_code=201)
async def create_backtest_api (
    request: BacktestCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
    event_engine=Depends(get_event_engine)
) -> BacktestCreateResponse:
    """
    创建回测任务

    Args:
        request: 回测创建请求
        background_tasks: 后台任务
        current_user: 当前登录用户
        db_session: 数据库会话
        event_engine: 事件引擎

    Returns:
        BacktestCreateResponse: 创建的回测任务响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 创建回测任务，参数: {request.model_dump()}")

        result = await create_backtest_task(
            session=db_session,
            request=request,
            event_engine=event_engine,
            user_id=current_user.get("id"),
            background_tasks=background_tasks
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建回测任务失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建回测任务失败: {str(e)}"
        )


@router.get("/tasks", response_model=BacktestListResponse)
async def get_backtest_list_api (
    request: BacktestListRequest = Depends(),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> BacktestListResponse:
    """
    获取回测任务列表

    Args:
        request: 回测列表请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        BacktestListResponse: 回测任务列表响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求回测任务列表")

        result = await get_backtest_task_list(
            session=db_session,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取回测任务列表失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取回测任务列表失败: {str(e)}"
        )


@router.get("/tasks/{task_id}", response_model=BacktestDetailResponse)
async def get_backtest_detail_api (
    task_id: int,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> BacktestDetailResponse:
    """
    获取回测任务详情

    Args:
        task_id: 回测任务ID
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        BacktestDetailResponse: 回测任务详情响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求回测任务详情，任务ID: {task_id}")

        result = await get_backtest_task(
            session=db_session,
            task_id=task_id,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"回测任务不存在: {task_id}, 错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"回测任务 {task_id} 不存在"
        )
    except Exception as e:
        logger.error(f"获取回测任务详情失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取回测任务详情失败: {str(e)}"
        )


@router.post("/tasks/{task_id}/cancel", response_model=BacktestDetailResponse)
async def cancel_backtest_api (
    task_id: int,
    request: BacktestCancelRequest = Depends(),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> BacktestDetailResponse:
    """
    取消回测任务

    Args:
        task_id: 回测任务ID
        request: 取消请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        BacktestDetailResponse: 取消后的任务详情
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 取消回测任务 {task_id}")

        result = await cancel_backtest_task(
            session=db_session,
            task_id=task_id,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"回测任务不存在或无法取消: {task_id}, 错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"取消回测任务失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取消回测任务失败: {str(e)}"
        )


# ==================== 回测结果查询接口 ====================

@router.get("/tasks/{task_id}/equity", response_model=BacktestEquityCurveResponse)
async def get_backtest_equity_api (
    task_id: int,
    request: BacktestEquityCurveRequest = Depends(),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> BacktestEquityCurveResponse:
    """
    获取回测净值曲线

    Args:
        task_id: 回测任务ID
        request: 净值曲线请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        BacktestEquityCurveResponse: 净值曲线响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求回测净值曲线，任务ID: {task_id}")

        result = await get_backtest_equity_curve(
            session=db_session,
            task_id=task_id,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取回测净值曲线失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取回测净值曲线失败: {str(e)}"
        )


@router.get("/tasks/{task_id}/trades", response_model=BacktestTradesResponse)
async def get_backtest_trades_api (
    task_id: int,
    request: BacktestTradesRequest = Depends(),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> BacktestTradesResponse:
    """
    获取回测交易记录

    Args:
        task_id: 回测任务ID
        request: 交易记录请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        BacktestTradesResponse: 交易记录响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求回测交易记录，任务ID: {task_id}")

        result = await get_backtest_trades(
            session=db_session,
            task_id=task_id,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取回测交易记录失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取回测交易记录失败: {str(e)}"
        )


@router.get("/tasks/{task_id}/positions", response_model=BacktestPositionsResponse)
async def get_backtest_positions_api (
    task_id: int,
    request: BacktestPositionsRequest = Depends(),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> BacktestPositionsResponse:
    """
    获取回测持仓快照

    Args:
        task_id: 回测任务ID
        request: 持仓快照请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        BacktestPositionsResponse: 持仓快照响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求回测持仓快照，任务ID: {task_id}")

        result = await get_backtest_positions(
            session=db_session,
            task_id=task_id,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取回测持仓快照失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取回测持仓快照失败: {str(e)}"
        )


@router.get("/tasks/{task_id}/result", response_model=BacktestResultResponse)
async def get_backtest_result_api (
    task_id: int,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> BacktestResultResponse:
    """
    获取回测结果

    Args:
        task_id: 回测任务ID
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        BacktestResultResponse: 回测结果响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求回测结果，任务ID: {task_id}")

        result = await get_backtest_result(
            session=db_session,
            task_id=task_id,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取回测结果失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取回测结果失败: {str(e)}"
        )


# ==================== 参数优化接口 ====================

@router.post("/optimize", response_model=BacktestOptimizeResponse)
async def optimize_parameters_api (
    request: BacktestOptimizeRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
    event_engine=Depends(get_event_engine)
) -> BacktestOptimizeResponse:
    """
    参数优化

    Args:
        request: 参数优化请求
        background_tasks: 后台任务
        current_user: 当前登录用户
        db_session: 数据库会话
        event_engine: 事件引擎

    Returns:
        BacktestOptimizeResponse: 参数优化响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求参数优化，参数: {request.model_dump()}")

        result = await optimize_backtest_parameters(
            session=db_session,
            request=request,
            event_engine=event_engine,
            user_id=current_user.get("id"),
            background_tasks=background_tasks
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"参数优化失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"参数优化失败: {str(e)}"
        )


# ==================== 模块管理接口 ====================

@router.get("/health")
async def backtest_module_health_check (
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """
    回测模块健康检查

    Args:
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        JSONResponse: 健康状态
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求回测模块健康检查")

        health_status = await check_backtest_module_health(
            session=db_session,
        )

        return success_response(
            data=health_status,
            message="回测模块健康检查完成"
        )

    except Exception as e:
        logger.error(f"回测模块健康检查失败: {str(e)}", exc_info=True)
        return error_response(
            message="回测模块健康检查失败",
            data={
                "status": "unhealthy",
                "error": str(e)
            },
            status_code=500
        )
