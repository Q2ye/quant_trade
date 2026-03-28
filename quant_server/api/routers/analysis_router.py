# -*- coding: utf-8 -*-
"""
分析模块API路由
基于混合架构设计，负责将HTTP请求路由到分析模块的业务处理层
位置：quant_server/api/routers/analysis_router.py
分析模块路由
"""
from typing import Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import logging

# 导入架构依赖
from quant_server.api.dependencies.database import get_db_session
from quant_server.api.dependencies.auth import get_current_user

# 导入响应格式化工具
from quant_server.utils.api_utils.response_formatter import success_response, error_response

# 导入分析模块的业务层处理函数
from quant_server.modules.analysis.handlers import (
    get_strategy_performance,
    get_account_performance,
    get_strategy_risk_metrics,
    get_portfolio_risk,
    run_stress_test,
    compare_strategies,
    compare_with_benchmark,
    analyze_correlation,
    get_strategy_attribution,
    get_portfolio_attribution,
    get_available_metrics,
    get_equity_curve,
    export_analysis_report,
    check_analysis_module_health
)

# 导入分析模块的Pydantic模型
from quant_server.modules.analysis.schemas import (
    GenerateReportRequest as PerformanceRequest,
    PerformanceReportResponse as PerformanceResponse,
    RiskMetricsResponse,
    StressTestRequest,
    StressTestResponse,
    StrategyComparisonRequest as StrategyCompareRequest,
    StrategyComparisonResponse as StrategyCompareResponse,
    BenchmarkComparisonResponse as BenchmarkCompareResponse,
    CorrelationAnalysisResponse as CorrelationResponse,
    AttributionAnalysisResponse as AttributionResponse,
    AvailableMetricsResponse as MetricsAvailableResponse,
    ExportReportRequest,
    ExportReportResponse
)

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器实例
router = APIRouter(
    prefix="/analysis",
    tags=["分析中心"],
    responses={
        401: {"description": "认证失败"},
        403: {"description": "权限不足"},
        500: {"description": "服务器内部错误"}
    }
)


# ==================== 绩效分析接口 ====================

@router.get("/performance/strategy/{strategy_id}", response_model=PerformanceResponse)
async def get_strategy_performance_api (
    strategy_id: str,
    request: PerformanceRequest = Depends(),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> PerformanceResponse:
    """
    获取策略绩效报告

    Args:
        strategy_id: 策略ID
        request: 绩效请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        PerformanceResponse: 绩效响应
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


@router.get("/performance/account/{account_id}", response_model=PerformanceResponse)
async def get_account_performance_api (
    account_id: str,
    request: PerformanceRequest = Depends(),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> PerformanceResponse:
    """
    获取账户绩效报告

    Args:
        account_id: 账户ID
        request: 绩效请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        PerformanceResponse: 绩效响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求账户 {account_id} 绩效")

        result = await get_account_performance(
            session=db_session,
            account_id=account_id,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取账户绩效失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取账户绩效失败: {str(e)}"
        )


# ==================== 风险分析接口 ====================

@router.get("/risk/strategy/{strategy_id}", response_model=RiskMetricsResponse)
async def get_strategy_risk_api (
    strategy_id: str,
    request: PerformanceRequest = Depends(),  # 使用PerformanceRequest替代
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> RiskMetricsResponse:
    """
    获取策略风险指标

    Args:
        strategy_id: 策略ID
        request: 风险指标请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        RiskMetricsResponse: 风险指标响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求策略 {strategy_id} 风险指标")

        result = await get_strategy_risk_metrics(
            session=db_session,
            strategy_id=strategy_id,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取风险指标失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取风险指标失败: {str(e)}"
        )


@router.get("/risk/portfolio/{portfolio_id}", response_model=RiskMetricsResponse)
async def get_portfolio_risk_api (
    portfolio_id: str,
    request: PerformanceRequest = Depends(),  # 使用PerformanceRequest替代
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> RiskMetricsResponse:
    """
    获取投资组合风险

    Args:
        portfolio_id: 投资组合ID
        request: 风险指标请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        RiskMetricsResponse: 风险指标响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求投资组合 {portfolio_id} 风险")

        result = await get_portfolio_risk(
            session=db_session,
            portfolio_id=portfolio_id,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取投资组合风险失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取投资组合风险失败: {str(e)}"
        )


@router.post("/risk/stress-test", response_model=StressTestResponse)
async def stress_test_api (
    request: StressTestRequest,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> StressTestResponse:
    """
    执行压力测试

    Args:
        request: 压力测试请求
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        StressTestResponse: 压力测试响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 执行压力测试")

        result = await run_stress_test(
            session=db_session,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"执行压力测试失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行压力测试失败: {str(e)}"
        )


# ==================== 对比分析接口 ====================

@router.post("/comparison/strategies", response_model=StrategyCompareResponse)
async def compare_strategies_api (
    request: StrategyCompareRequest,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> StrategyCompareResponse:
    """
    对比多个策略

    Args:
        request: 策略对比请求
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        StrategyCompareResponse: 策略对比响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 对比策略: {request.strategy_ids}")

        result = await compare_strategies(
            session=db_session,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"策略对比失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"策略对比失败: {str(e)}"
        )


@router.get("/comparison/benchmark/{strategy_id}", response_model=BenchmarkCompareResponse)
async def compare_benchmark_api (
    strategy_id: str,
    request: PerformanceRequest = Depends(),  # 使用PerformanceRequest替代
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> BenchmarkCompareResponse:
    """
    与基准对比

    Args:
        strategy_id: 策略ID
        request: 基准对比请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        BenchmarkCompareResponse: 基准对比响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求策略 {strategy_id} 与基准对比")

        result = await compare_with_benchmark(
            session=db_session,
            strategy_id=strategy_id,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"基准对比失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"基准对比失败: {str(e)}"
        )


@router.get("/correlation", response_model=CorrelationResponse)
async def correlation_api (
    request: PerformanceRequest = Depends(),  # 使用PerformanceRequest替代
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> CorrelationResponse:
    """
    相关性分析

    Args:
        request: 相关性分析请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        CorrelationResponse: 相关性分析响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求相关性分析")

        result = await analyze_correlation(
            session=db_session,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"相关性分析失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"相关性分析失败: {str(e)}"
        )


# ==================== 归因分析接口 ====================

@router.get("/attribution/strategy/{strategy_id}", response_model=AttributionResponse)
async def strategy_attribution_api (
    strategy_id: str,
    request: PerformanceRequest = Depends(),  # 使用PerformanceRequest替代
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> AttributionResponse:
    """
    获取策略归因分析

    Args:
        strategy_id: 策略ID
        request: 归因分析请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        AttributionResponse: 归因分析响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求策略 {strategy_id} 归因分析")

        result = await get_strategy_attribution(
            session=db_session,
            strategy_id=strategy_id,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取归因分析失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取归因分析失败: {str(e)}"
        )


@router.get("/attribution/portfolio/{portfolio_id}", response_model=AttributionResponse)
async def portfolio_attribution_api (
    portfolio_id: str,
    request: PerformanceRequest = Depends(),  # 使用PerformanceRequest替代
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> AttributionResponse:
    """
    获取投资组合归因分析

    Args:
        portfolio_id: 投资组合ID
        request: 归因分析请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        AttributionResponse: 归因分析响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求投资组合 {portfolio_id} 归因分析")

        result = await get_portfolio_attribution(
            session=db_session,
            portfolio_id=portfolio_id,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取归因分析失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取归因分析失败: {str(e)}"
        )


# ==================== 通用分析接口 ====================

@router.get("/metrics/available", response_model=MetricsAvailableResponse)
async def available_metrics_api (
    request: PerformanceRequest = Depends(),  # 使用PerformanceRequest替代
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> MetricsAvailableResponse:
    """
    获取可用分析指标

    Args:
        request: 可用指标请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        MetricsAvailableResponse: 可用指标响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求可用分析指标")

        result = await get_available_metrics(
            session=db_session,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取可用指标失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取可用指标失败: {str(e)}"
        )


@router.get("/equity-curve", response_model=CorrelationResponse)  # 使用CorrelationResponse替代
async def equity_curve_api (
    request: PerformanceRequest = Depends(),  # 使用PerformanceRequest替代
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> CorrelationResponse:
    """
    获取资产曲线数据

    Args:
        request: 资产曲线请求参数
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        EquityCurveResponse: 资产曲线响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求资产曲线数据")

        result = await get_equity_curve(
            session=db_session,
            request=request,
            user_id=current_user.get("id")
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取资产曲线失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取资产曲线失败: {str(e)}"
        )


# ==================== 报告导出接口 ====================

@router.post("/export", response_model=ExportReportResponse)
async def export_report_api (
    request: ExportReportRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> ExportReportResponse:
    """
    导出分析报告

    Args:
        request: 导出报告请求
        background_tasks: 后台任务
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        ExportReportResponse: 导出报告响应
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 导出分析报告")

        result = await export_analysis_report(
            session=db_session,
            request=request,
            user_id=current_user.get("id"),
            background_tasks=background_tasks
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导出报告失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导出报告失败: {str(e)}"
        )


# ==================== 模块管理接口 ====================

@router.get("/health")
async def analysis_module_health_check (
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """
    分析模块健康检查

    Args:
        current_user: 当前登录用户
        db_session: 数据库会话

    Returns:
        JSONResponse: 健康状态
    """
    try:
        logger.info(f"用户 {current_user.get('username')} 请求分析模块健康检查")

        health_status = await check_analysis_module_health(
            session=db_session,
        )

        return success_response(
            data=health_status,
            message="分析模块健康检查完成"
        )

    except Exception as e:
        logger.error(f"分析模块健康检查失败: {str(e)}", exc_info=True)
        return error_response(
            message="分析模块健康检查失败",
            data={
                "status": "unhealthy",
                "error": str(e)
            },
            status_code=500
        )
