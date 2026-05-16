# -*- coding: utf-8 -*-
"""
分析模块API路由
基于混合架构设计，负责将HTTP请求路由到分析模块的业务处理层
位置：quant_server/api/routers/analysis_router.py
分析模块路由
"""
import logging
from datetime import date
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
# 导入架构依赖
from api.dependencies.database import get_db_session
# 导入分析模块的业务层处理
from modules.analysis.handlers import (
	AnalysisHandler,
	check_analysis_module_health,
)
# 导入分析模块的Pydantic模型
from modules.analysis.schemas import (
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
	EquityCurveResponse,
	ExportReportRequest,
	ExportReportResponse
)
from modules.analysis.constants import AnalysisType

# 导入响应格式化工具
from utils.api_utils.response_formatter import success_response, error_response

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器实例
router = APIRouter(
	tags=["分析中心"],
	responses={
		401: {"description": "认证失败"},
		403: {"description": "权限不足"},
		500: {"description": "服务器内部错误"}
	}
)

# 预声明 Depends 实例，避免 Pydantic v2 与 Depends() 类型检查冲突
PerformanceRequestDep = Depends(PerformanceRequest)  # type: ignore[arg-type]


async def _analysis_query_params(
	start_date: date | None = None,
	end_date: date | None = None,
	benchmark: str | None = None,
	target_id: str = '',
	target_type: str = 'strategy',
	frequency: str = 'daily',
	include_charts: bool = True,
) -> PerformanceRequest:
	"""GET 端点查询参数依赖 — 为必填字段提供默认值，避免 422 错误"""
	return PerformanceRequest(
		analysis_type=AnalysisType.PERFORMANCE,
		target_id=target_id,
		target_type=target_type,
		start_date=start_date,
		end_date=end_date,
		benchmark=benchmark,
		frequency=frequency,
		include_charts=include_charts,
	)


# GET 端点统一使用的查询参数依赖
AnalysisQueryDep = Depends(_analysis_query_params)

# ==================== 绩效分析接口 ====================

@router.get("/performance/strategy/{strategy_id}", response_model=PerformanceResponse)
async def get_strategy_performance_api (
		strategy_id: str,
		request: PerformanceRequest = AnalysisQueryDep,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
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

		handler = AnalysisHandler(db_session)
		result = await handler.get_strategy_performance(
			strategy_id=strategy_id,
			request=request,
			_user_id=current_user.get("id")
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
		request: PerformanceRequest = AnalysisQueryDep,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
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

		handler = AnalysisHandler(db_session)
		result = await handler.get_account_performance(
			account_id=account_id,
			request=request,
			_user_id=current_user.get("id")
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
		request: PerformanceRequest = AnalysisQueryDep,  # 使用PerformanceRequest替代
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
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

		handler = AnalysisHandler(db_session)
		result = await handler.get_strategy_risk_metrics(
			strategy_id=strategy_id,
			request=request,
			_user_id=current_user.get("id")
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
		request: PerformanceRequest = AnalysisQueryDep,  # 使用PerformanceRequest替代
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
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

		handler = AnalysisHandler(db_session)
		result = await handler.get_portfolio_risk(
			portfolio_id=portfolio_id,
			request=request,
			_user_id=current_user.get("id")
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
) -> Dict[str, Any]:
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

		handler = AnalysisHandler(db_session)
		result = await handler.run_stress_test(
			request=request,
			_user_id=current_user.get("id")
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
) -> Dict[str, Any]:
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

		handler = AnalysisHandler(db_session)
		result = await handler.compare_strategies(
			request=request,
			_user_id=current_user.get("id")
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
		request: PerformanceRequest = AnalysisQueryDep,  # 使用PerformanceRequest替代
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
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

		handler = AnalysisHandler(db_session)
		result = await handler.compare_with_benchmark(
			strategy_id=strategy_id,
			request=request,
			_user_id=current_user.get("id")
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
		request: PerformanceRequest = AnalysisQueryDep,  # 使用PerformanceRequest替代
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
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

		handler = AnalysisHandler(db_session)
		result = await handler.analyze_correlation(
			request=request,
			_user_id=current_user.get("id")
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
		request: PerformanceRequest = AnalysisQueryDep,  # 使用PerformanceRequest替代
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
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

		handler = AnalysisHandler(db_session)
		result = await handler.get_strategy_attribution(
			strategy_id=strategy_id,
			request=request,
			_user_id=current_user.get("id")
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
		request: PerformanceRequest = AnalysisQueryDep,  # 使用PerformanceRequest替代
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
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

		handler = AnalysisHandler(db_session)
		result = await handler.get_portfolio_attribution(
			portfolio_id=portfolio_id,
			request=request,
			_user_id=current_user.get("id")
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
		request: PerformanceRequest = AnalysisQueryDep,  # 使用PerformanceRequest替代
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
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

		handler = AnalysisHandler(db_session)
		result = await handler.get_available_metrics(
			strategy_id=getattr(request, 'strategy_id', ''),
			request=request,
			_user_id=current_user.get("id")
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


@router.get("/equity-curve", response_model=EquityCurveResponse)
async def equity_curve_api (
		request: PerformanceRequest = AnalysisQueryDep,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
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

		handler = AnalysisHandler(db_session)
		result = await handler.get_equity_curve(
			strategy_id=getattr(request, 'strategy_id', ''),
			request=request,
			_user_id=current_user.get("id")
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
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
	"""
	导出分析报告

	Args:
		request: 导出报告请求
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		ExportReportResponse: 导出报告响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 导出分析报告")

		handler = AnalysisHandler(db_session)
		result = await handler.export_analysis_report(
			request=request,
			_user_id=current_user.get("id")
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
