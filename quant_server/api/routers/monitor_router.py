# -*- coding: utf-8 -*-
"""
监控模块API路由

位置：quant_server/api/routers/monitor_router.py

注意：/risk/* 端点已迁移到 api/routers/risk_router.py（v2.0 风控模块独立）
"""
import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
from api.dependencies.database import get_db_session
from api.dependencies.event_engine import get_event_engine
from api.dependencies.main_engine import get_main_engine
from modules.monitor.handlers import (
    get_system_metrics,
    get_business_metrics,
    get_alert_history,
    create_alert_rule,
    update_alert_rule,
    delete_alert_rule,
    trigger_manual_alert,
    get_health_status,
    get_performance_stats,
    check_monitor_module_health,
)
from modules.monitor.schemas import (
    SystemMetricsRequest,
    SystemMetricsResponse,
    BusinessMetricsRequest,
    BusinessMetricsResponse,
    AlertHistoryRequest,
    AlertHistoryResponse,
    AlertRuleRequest,
    AlertRuleResponse,
    ManualAlertRequest,
    HealthStatusResponse,
    PerformanceStatsResponse,
)
from utils.api_utils.response_formatter import success_response, error_response

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["监控中心"],
    responses={
        401: {"description": "认证失败"},
        403: {"description": "权限不足"},
        500: {"description": "服务器内部错误"},
    },
)


# ==================== 风险告警重定向 ====================
# /risk/* 端点已迁移到 api/routers/risk_router.py
# 旧端点 /quantTrade/monitor/risk/alerts 保留重定向


@router.get("/risk/alerts")
async def get_risk_alerts_redirect():
    """
    ⚠️ 已迁移：风险告警请使用 /quantTrade/risk/alerts
    """
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=301,
        content={
            "message": "风险告警端点已迁移到 /quantTrade/risk/alerts",
            "new_url": "/quantTrade/risk/alerts",
        },
    )


# ==================== 系统监控接口 ====================


@router.get("/system/metrics", response_model=SystemMetricsResponse)
async def get_system_metrics_api(
    request: SystemMetricsRequest = Depends(),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """获取系统监控指标"""
    try:
        logger.info(f"用户 {current_user.get('username')} 请求系统监控指标")
        result = await get_system_metrics(
            session=db_session,
            request=request,
            user_id=current_user.get("id"),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取系统监控指标失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统监控指标失败: {str(e)}",
        )


@router.get("/health", response_model=HealthStatusResponse)
async def get_health_status_api(
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
    main_engine=Depends(get_main_engine),
) -> dict[str, Any]:
    """获取系统健康状态"""
    try:
        logger.info(f"用户 {current_user.get('username')} 请求系统健康状态")
        result = await get_health_status(
            session=db_session,
            main_engine=main_engine,
            user_id=current_user.get("id"),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取健康状态失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取健康状态失败: {str(e)}",
        )


# ==================== 业务监控接口 ====================


@router.get("/business/metrics", response_model=BusinessMetricsResponse)
async def get_business_metrics_api(
    request: BusinessMetricsRequest = Depends(),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """获取业务监控指标"""
    try:
        logger.info(f"用户 {current_user.get('username')} 请求业务监控指标")
        result = await get_business_metrics(
            session=db_session,
            request=request,
            user_id=current_user.get("id"),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取业务监控指标失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取业务监控指标失败: {str(e)}",
        )


@router.get("/performance/stats", response_model=PerformanceStatsResponse)
async def get_performance_stats_api(
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
    event_engine=Depends(get_event_engine),
) -> dict[str, Any]:
    """获取性能统计信息"""
    try:
        logger.info(f"用户 {current_user.get('username')} 请求性能统计信息")
        result = await get_performance_stats(
            session=db_session,
            event_engine=event_engine,
            user_id=current_user.get("id"),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取性能统计失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取性能统计失败: {str(e)}",
        )


# ==================== 警报管理接口 ====================


@router.get("/alerts/history", response_model=AlertHistoryResponse)
async def get_alert_history_api(
    request: AlertHistoryRequest = Depends(),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """获取警报历史记录"""
    try:
        logger.info(f"用户 {current_user.get('username')} 请求警报历史记录")
        result = await get_alert_history(
            session=db_session,
            request=request,
            user_id=current_user.get("id"),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取警报历史失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取警报历史失败: {str(e)}",
        )


@router.post("/alerts/rules", response_model=AlertRuleResponse)
async def create_alert_rule_api(
    request: AlertRuleRequest,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """创建警报规则"""
    try:
        logger.info(f"用户 {current_user.get('username')} 创建警报规则")
        if not current_user.get("can_manage_alerts", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户没有管理警报权限",
            )
        result = await create_alert_rule(
            session=db_session,
            request=request,
            user_id=current_user.get("id"),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建警报规则失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建警报规则失败: {str(e)}",
        )


@router.put("/alerts/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule_api(
    rule_id: str,
    request: AlertRuleRequest,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """更新警报规则"""
    try:
        logger.info(f"用户 {current_user.get('username')} 更新警报规则 {rule_id}")
        if not current_user.get("can_manage_alerts", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户没有管理警报权限",
            )
        result = await update_alert_rule(
            session=db_session,
            rule_id=rule_id,
            request=request,
            user_id=current_user.get("id"),
        )
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"警报规则不存在: {rule_id}, 错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"警报规则 {rule_id} 不存在",
        )
    except Exception as e:
        logger.error(f"更新警报规则失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新警报规则失败: {str(e)}",
        )


@router.delete("/alerts/rules/{rule_id}")
async def delete_alert_rule_api(
    rule_id: str,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """删除警报规则"""
    try:
        logger.info(f"用户 {current_user.get('username')} 删除警报规则 {rule_id}")
        if not current_user.get("can_manage_alerts", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户没有管理警报权限",
            )
        await delete_alert_rule(
            session=db_session,
            rule_id=rule_id,
            user_id=current_user.get("id"),
        )
        return success_response(
            message="删除警报规则成功",
            data={"rule_id": rule_id},
        )
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"警报规则不存在: {rule_id}, 错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"警报规则 {rule_id} 不存在",
        )
    except Exception as e:
        logger.error(f"删除警报规则失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除警报规则失败: {str(e)}",
        )


@router.post("/alerts/manual")
async def trigger_manual_alert_api(
    request: ManualAlertRequest,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
    event_engine=Depends(get_event_engine),
):
    """触发手动警报"""
    try:
        logger.info(f"用户 {current_user.get('username')} 触发手动警报")
        if not current_user.get("can_trigger_alerts", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户没有触发警报权限",
            )
        result = await trigger_manual_alert(
            session=db_session,
            request=request,
            event_engine=event_engine,
            user_id=current_user.get("id"),
        )
        return success_response(
            message="手动警报触发成功",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"触发手动警报失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"触发手动警报失败: {str(e)}",
        )


# ==================== 仪表板接口 ====================


@router.get("/dashboard")
async def get_monitor_dashboard(
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
    main_engine=Depends(get_main_engine),
):
    """获取监控仪表板数据"""
    try:
        logger.info(f"用户 {current_user.get('username')} 请求监控仪表板数据")
        result = await get_health_status(
            session=db_session,
            main_engine=main_engine,
            user_id=current_user.get("id"),
        )
        return success_response(
            message="监控仪表板数据获取成功",
            data=result,
        )
    except Exception as e:
        logger.error(f"获取监控仪表板失败: {str(e)}", exc_info=True)
        return error_response(
            message="获取监控仪表板失败",
            data={"error": str(e)},
            status_code=500,
        )


# ==================== 模块管理接口 ====================


@router.get("/health/module")
async def monitor_module_health_check(
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """监控模块健康检查"""
    try:
        logger.debug(f"用户 {current_user.get('username')} 请求监控模块健康检查")
        health_status = await check_monitor_module_health(session=db_session)
        return success_response(
            data=health_status,
            message="监控模块健康检查完成",
        )
    except Exception as e:
        logger.error(f"监控模块健康检查失败: {str(e)}", exc_info=True)
        return error_response(
            message="监控模块健康检查失败",
            data={"status": "unhealthy", "error": str(e)},
            status_code=500,
        )
