# -*- coding: utf-8 -*-
"""
系统模块API路由
基于混合架构设计，负责将HTTP请求路由到系统模块的业务处理层
位置：quant_server/api/routers/system_router.py
系统模块路由
"""
from typing import Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
import logging

# 导入架构依赖
from quant_server.api.dependencies.database import get_db_session
from quant_server.api.dependencies.auth import get_current_user

# 导入响应格式化工具
from quant_server.utils.api_utils.response_formatter import success_response, error_response

# 导入系统模块的业务层处理函数
from quant_server.modules.system.handlers import (
    get_system_status,
    get_system_logs,
    trigger_data_sync,
    get_data_sync_status,
    get_system_settings,
    update_system_settings,
    get_connection_status,
    get_system_resources,
    get_database_status,
    check_system_module_health
)

# 导入系统模块的Pydantic模型
from quant_server.modules.system.schemas import (
    SystemStatusResponse,
    SystemLogsRequest,
    SystemLogsResponse,
    DataSyncRequest,
    DataSyncResponse,
    SystemSettingsResponse,
    SystemSettingsUpdateRequest,
    ConnectionStatusResponse,
    SystemResourcesResponse,
    DatabaseStatusResponse
)

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器实例
router = APIRouter(
    prefix="/system",
    tags=["系统管理"],
    responses={
        401: {"description": "认证失败"},
        403: {"description": "权限不足"},
        500: {"description": "服务器内部错误"}
    }
)


# ==================== 系统状态接口 ====================

@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status_api (
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> SystemStatusResponse:
    """
    获取系统状态

    Args:
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        SystemStatusResponse: 系统状态响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求系统状态")

        result = await get_system_status(
            session=db_session,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取系统状态失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统状态失败: {str(e)}"
        )


@router.get("/resources", response_model=SystemResourcesResponse)
async def get_system_resources_api (
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> SystemResourcesResponse:
    """
    获取系统资源使用情况

    Args:
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        SystemResourcesResponse: 系统资源响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求系统资源")

        result = await get_system_resources(
            session=db_session,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取系统资源失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统资源失败: {str(e)}"
        )


@router.get("/connections", response_model=ConnectionStatusResponse)
async def get_connections_api (
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> ConnectionStatusResponse:
    """
    获取系统连接状态

    Args:
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        ConnectionStatusResponse: 连接状态响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求连接状态")

        result = await get_connection_status(
            session=db_session,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取连接状态失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取连接状态失败: {str(e)}"
        )


@router.get("/database", response_model=DatabaseStatusResponse)
async def get_database_api (
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> DatabaseStatusResponse:
    """
    获取数据库状态

    Args:
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        DatabaseStatusResponse: 数据库状态响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求数据库状态")

        result = await get_database_status(
            session=db_session,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取数据库状态失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据库状态失败: {str(e)}"
        )


# ==================== 系统日志接口 ====================

@router.get("/logs", response_model=SystemLogsResponse)
async def get_system_logs_api (
    request: SystemLogsRequest = Depends(),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> SystemLogsResponse:
    """
    获取系统日志

    Args:
        request: 系统日志请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        SystemLogsResponse: 系统日志响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求系统日志")

        result = await get_system_logs(
            session=db_session,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取系统日志失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统日志失败: {str(e)}"
        )


# ==================== 数据同步接口 ====================

@router.post("/data/sync", response_model=DataSyncResponse)
async def trigger_data_sync_api (
    request: DataSyncRequest,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> DataSyncResponse:
    """
    触发数据同步

    Args:
        request: 数据同步请求
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        DataSyncResponse: 数据同步响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 触发数据同步")

        # 检查用户权限
        if not current_user.get("can_sync_data", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户没有数据同步权限"
            )

        result = await trigger_data_sync(
            session=db_session,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"触发数据同步失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"触发数据同步失败: {str(e)}"
        )


@router.get("/data/sync/status", response_model=DataSyncResponse)
async def get_data_sync_status_api (
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> DataSyncResponse:
    """
    获取数据同步状态

    Args:
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        DataSyncResponse: 数据同步状态响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求数据同步状态")

        result = await get_data_sync_status(
            session=db_session,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取数据同步状态失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据同步状态失败: {str(e)}"
        )


# ==================== 系统设置接口 ====================

@router.get("/settings", response_model=SystemSettingsResponse)
async def get_settings_api (
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> SystemSettingsResponse:
    """
    获取系统设置

    Args:
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        SystemSettingsResponse: 系统设置响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求系统设置")

        result = await get_system_settings(
            session=db_session,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取系统设置失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统设置失败: {str(e)}"
        )


@router.put("/settings", response_model=SystemSettingsResponse)
async def update_settings_api (
    request: SystemSettingsUpdateRequest,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> SystemSettingsResponse:
    """
    更新系统设置

    Args:
        request: 系统设置更新请求
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        SystemSettingsResponse: 更新后的系统设置响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 更新系统设置")

        # 检查用户权限
        if not current_user.get("is_admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只有管理员可以更新系统设置"
            )

        result = await update_system_settings(
            session=db_session,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新系统设置失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新系统设置失败: {str(e)}"
        )


# ==================== 模块管理接口 ====================

@router.get("/health")
async def system_module_health_check (
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """
    系统模块健康检查

    Args:
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        JSONResponse: 健康状态
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求系统模块健康检查")

        health_status = await check_system_module_health(
            session=db_session,
        )

        return success_response(
            data=health_status,
            message="系统模块健康检查完成"
        )

    except Exception as e:
        logger.error(f"系统模块健康检查失败: {str(e)}", exc_info=True)
        return error_response(
            message="系统模块健康检查失败",
            data={
                "status": "unhealthy",
                "error": str(e)
            },
            status_code=500
        )
