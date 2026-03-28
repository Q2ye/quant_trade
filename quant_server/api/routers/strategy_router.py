# -*- coding: utf-8 -*-
"""
策略模块API路由
基于混合架构设计，负责将HTTP请求路由到策略模块的业务处理层
位置：quant_server/api/routers/strategy_router.py
策略模块路由
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
import logging

# 导入架构依赖
from quant_server.api.dependencies.database import get_db_session
from quant_server.api.dependencies.auth import get_current_user

# 导入响应格式化工具
from quant_server.utils.api_utils.response_formatter import success_response, error_response

# 导入策略模块的业务层处理函数
from quant_server.modules.strategy.handlers import (
    get_strategy_list,
    get_strategy_detail,
    create_strategy,
    update_strategy,
    delete_strategy,
    start_strategy,
    stop_strategy,
    get_strategy_performance,
    get_strategy_status,
    check_strategy_module_health
)

# 导入策略模块的Pydantic模型
from quant_server.modules.strategy.schemas import (
    StrategyListRequest,
    StrategyListResponse,
    StrategyDetailRequest,
    StrategyDetailResponse,
    StrategyCreateRequest,
    StrategyUpdateRequest,
    StrategyResponse,
    StrategyStartRequest,
    StrategyStopRequest,
    StrategyPerformanceRequest,
    StrategyPerformanceResponse,
    StrategyStatusResponse
)

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器实例
router = APIRouter(
    prefix="/strategies",
    tags=["策略中心"],
    responses={
        401: {"description": "认证失败"},
        403: {"description": "权限不足"},
        500: {"description": "服务器内部错误"}
    }
)


# ==================== 策略管理接口 ====================

@router.get("", response_model=StrategyListResponse)
async def get_strategies_api (
    request: StrategyListRequest = Depends(),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> StrategyListResponse:
    """
    获取策略列表

    Args:
        request: 策略列表请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        StrategyListResponse: 策略列表响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求策略列表，参数: {request.model_dump()}")

        result = await get_strategy_list(
            session=db_session,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取策略列表失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取策略列表失败: {str(e)}"
        )


@router.get("/{strategy_id}", response_model=StrategyDetailResponse)
async def get_strategy_detail_api (
    strategy_id: int,
    request: StrategyDetailRequest = Depends(),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> StrategyDetailResponse:
    """
    获取策略详细信息

    Args:
        strategy_id: 策略ID
        request: 策略详情请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        StrategyDetailResponse: 策略详情响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求策略详情，策略ID: {strategy_id}")

        result = await get_strategy_detail(
            session=db_session,
            strategy_id=strategy_id,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"策略不存在: {strategy_id}, 错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"策略 {strategy_id} 不存在"
        )
    except Exception as e:
        logger.error(f"获取策略详情失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取策略详情失败: {str(e)}"
        )


@router.post("", response_model=StrategyResponse, status_code=201)
async def create_strategy_api (
    request: StrategyCreateRequest,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> StrategyResponse:
    """
    创建新策略

    Args:
        request: 策略创建请求
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        StrategyResponse: 创建的策略响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 创建策略，参数: {request.model_dump()}")

        result = await create_strategy(
            session=db_session,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建策略失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建策略失败: {str(e)}"
        )


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy_api (
    strategy_id: int,
    request: StrategyUpdateRequest,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> StrategyResponse:
    """
    更新策略信息

    Args:
        strategy_id: 策略ID
        request: 策略更新请求
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        StrategyResponse: 更新后的策略响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 更新策略 {strategy_id}，参数: {request.model_dump()}")

        result = await update_strategy(
            session=db_session,
            strategy_id=strategy_id,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"策略不存在: {strategy_id}, 错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"策略 {strategy_id} 不存在"
        )
    except Exception as e:
        logger.error(f"更新策略失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新策略失败: {str(e)}"
        )


@router.delete("/{strategy_id}", status_code=204)
async def delete_strategy_api (
    strategy_id: int,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """
    删除策略

    Args:
        strategy_id: 策略ID
        current_user: 当前登录用户
        db_session: 数据库会话
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 删除策略 {strategy_id}")

        await delete_strategy(
            session=db_session,
            strategy_id=strategy_id,
            user_id=current_user.get("id")
        )

        return success_response(
            message="策略删除成功",
            data={"strategy_id": strategy_id}
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"策略不存在: {strategy_id}, 错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"策略 {strategy_id} 不存在"
        )
    except Exception as e:
        logger.error(f"删除策略失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除策略失败: {str(e)}"
        )


# ==================== 策略执行接口 ====================

@router.post("/{strategy_id}/start", response_model=StrategyStatusResponse)
async def start_strategy_api (
    strategy_id: int,
    request: StrategyStartRequest = Depends(),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> StrategyStatusResponse:
    """
    启动策略

    Args:
        strategy_id: 策略ID
        request: 策略启动请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        StrategyStatusResponse: 策略状态响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 启动策略 {strategy_id}，参数: {request.model_dump()}")

        result = await start_strategy(
            session=db_session,
            strategy_id=strategy_id,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"策略不存在或无法启动: {strategy_id}, 错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"启动策略失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动策略失败: {str(e)}"
        )


@router.post("/{strategy_id}/stop", response_model=StrategyStatusResponse)
async def stop_strategy_api (
    strategy_id: int,
    request: StrategyStopRequest = Depends(),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> StrategyStatusResponse:
    """
    停止策略

    Args:
        strategy_id: 策略ID
        request: 策略停止请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        StrategyStatusResponse: 策略状态响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 停止策略 {strategy_id}")

        result = await stop_strategy(
            session=db_session,
            strategy_id=strategy_id,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"策略不存在或无法停止: {strategy_id}, 错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"停止策略失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"停止策略失败: {str(e)}"
        )


# ==================== 策略分析接口 ====================

@router.get("/{strategy_id}/performance", response_model=StrategyPerformanceResponse)
async def get_strategy_performance_api (
    strategy_id: int,
    request: StrategyPerformanceRequest = Depends(),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> StrategyPerformanceResponse:
    """
    获取策略绩效

    Args:
        strategy_id: 策略ID
        request: 策略绩效请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        StrategyPerformanceResponse: 策略绩效响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求策略 {strategy_id} 绩效")

        result = await get_strategy_performance(
            session=db_session,
            strategy_id=strategy_id,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取策略绩效失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取策略绩效失败: {str(e)}"
        )


@router.get("/{strategy_id}/status", response_model=StrategyStatusResponse)
async def get_strategy_status_api (
    strategy_id: int,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> StrategyStatusResponse:
    """
    获取策略运行状态

    Args:
        strategy_id: 策略ID
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        StrategyStatusResponse: 策略状态响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求策略 {strategy_id} 状态")

        result = await get_strategy_status(
            session=db_session,
            strategy_id=strategy_id,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取策略状态失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取策略状态失败: {str(e)}"
        )


# ==================== 模块管理接口 ====================

@router.get("/health")
async def strategy_module_health_check (
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """
    策略模块健康检查

    Args:
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        JSONResponse: 健康状态
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求策略模块健康检查")

        health_status = await check_strategy_module_health(
            session=db_session,
        )

        return success_response(
            data=health_status,
            message="策略模块健康检查完成"
        )

    except Exception as e:
        logger.error(f"策略模块健康检查失败: {str(e)}", exc_info=True)
        return error_response(
            message="策略模块健康检查失败",
            data={
                "status": "unhealthy",
                "error": str(e)
            },
            status_code=500
        )
