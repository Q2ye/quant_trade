#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析模块API路由
负责绩效归因、风险分析、对比分析等API端点

版本: 1.0.0
创建时间: 2025-01-15
作者: 量化平台团队
"""

import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator
import json
import pandas as pd
import io

# 导入内部模块
from quant_server.api.dependencies import get_db, get_current_user
from quant_server.modules.analysis import schemas as analysis_schemas
from quant_server.modules.analysis.handlers import (
	PerformanceAnalysisHandler,
	RiskAnalysisHandler,
	ComparisonAnalysisHandler,
	AttributionAnalysisHandler
)
from quant_server.modules.analysis.models import (
	PerformanceReport,
	RiskMetrics,
	StrategyComparison,
	AttributionAnalysis
)
from quant_server.modules.auth.schemas import User
from quant_server.core.exceptions import AnalysisException, DataNotFoundException

# 创建分析模块路由
router = APIRouter(
	prefix="/events",
	tags=["events"],
	responses={
		404: {"description": "Analysis resource not found"},
		500: {"description": "Internal server error"}
	}
)


# ==================== 绩效分析API ====================

@router.get(
	"/performance/strategy/{strategy_id}",
	response_model=analysis_schemas.PerformanceReportResponse,
	summary="获取策略绩效报告",
	description="获取指定策略的绩效分析报告，包括收益率、夏普比率、最大回撤等指标"
)
async def get_strategy_performance (
		strategy_id: str,
		start_date: Optional[date] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
		end_date: Optional[date] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
		frequency: str = Query("daily", description="频率：daily, weekly, monthly"),
		include_trades: bool = Query(False, description="是否包含交易明细"),
		db: Session = Depends(get_db),
		current_user: User = Depends(get_current_user)
):
	"""
	获取策略绩效报告

	Args:
		strategy_id: 策略ID
		start_date: 开始日期
		end_date: 结束日期
		frequency: 数据频率
		include_trades: 是否包含交易明细
		db: 数据库会话
		current_user: 当前用户

	Returns:
		策略绩效报告
	"""
	try:
		handler = PerformanceAnalysisHandler(db, current_user.id)

		# 设置日期范围，默认为最近一年
		if not end_date:
			end_date = date.today()
		if not start_date:
			start_date = end_date - timedelta(days=365)

		# 验证日期范围
		if start_date > end_date:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="开始日期不能晚于结束日期"
			)

		# 获取绩效报告
		report = handler.get_strategy_performance(
			strategy_id=strategy_id,
			start_date=start_date,
			end_date=end_date,
			frequency=frequency,
			include_trades=include_trades
		)

		return analysis_schemas.PerformanceReportResponse(
			success=True,
			data=report,
			message="绩效报告获取成功"
		)
	except DataNotFoundException as e:
		raise HTTPException(status_code=404, detail=str(e))
	except AnalysisException as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(
			status_code=500,
			detail=f"获取绩效报告失败: {str(e)}"
		)


@router.get(
	"/performance/account/{account_id}",
	response_model=analysis_schemas.PerformanceReportResponse,
	summary="获取账户绩效报告",
	description="获取指定账户的绩效分析报告，包括资产曲线、收益率、风险指标等"
)
async def get_account_performance (
		account_id: str,
		start_date: Optional[date] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
		end_date: Optional[date] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
		benchmark: Optional[str] = Query(None, description="基准代码，如：000300.SH"),
		db: Session = Depends(get_db),
		current_user: User = Depends(get_current_user)
):
	"""
	获取账户绩效报告

	Args:
		account_id: 账户ID
		start_date: 开始日期
		end_date: 结束日期
		benchmark: 基准代码
		db: 数据库会话
		current_user: 当前用户

	Returns:
		账户绩效报告
	"""
	try:
		handler = PerformanceAnalysisHandler(db, current_user.id)

		# 设置日期范围，默认为最近一年
		if not end_date:
			end_date = date.today()
		if not start_date:
			start_date = end_date - timedelta(days=365)

		# 验证日期范围
		if start_date > end_date:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="开始日期不能晚于结束日期"
			)

		# 获取账户绩效报告
		report = handler.get_account_performance(
			account_id=account_id,
			start_date=start_date,
			end_date=end_date,
			benchmark=benchmark
		)

		return analysis_schemas.PerformanceReportResponse(
			success=True,
			data=report,
			message="账户绩效报告获取成功"
		)
	except DataNotFoundException as e:
		raise HTTPException(status_code=404, detail=str(e))
	except AnalysisException as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(
			status_code=500,
			detail=f"获取账户绩效报告失败: {str(e)}"
		)


@router.post(
	"/performance/generate-report",
	response_model=analysis_schemas.AsyncTaskResponse,
	summary="生成绩效报告",
	description="异步生成指定策略或账户的详细绩效报告"
)
async def generate_performance_report (
		request: analysis_schemas.GenerateReportRequest,
		background_tasks: BackgroundTasks,
		db: Session = Depends(get_db),
		current_user: User = Depends(get_current_user)
):
	"""
	异步生成绩效报告

	Args:
		request: 生成报告请求
		background_tasks: 后台任务
		db: 数据库会话
		current_user: 当前用户

	Returns:
		异步任务响应
	"""
	try:
		handler = PerformanceAnalysisHandler(db, current_user.id)

		# 验证请求数据
		if not request.entity_id or not request.report_type:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="entity_id 和 report_type 为必填项"
			)

		# 生成任务ID
		task_id = f"perf_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{current_user.id}"

		# 添加到后台任务
		background_tasks.add_task(
			handler.generate_performance_report_async,
			task_id=task_id,
			request=request
		)

		return analysis_schemas.AsyncTaskResponse(
			success=True,
			task_id=task_id,
			message="绩效报告生成任务已提交",
			status="pending"
		)
	except AnalysisException as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(
			status_code=500,
			detail=f"提交绩效报告生成任务失败: {str(e)}"
		)


# ==================== 风险分析API ====================

@router.get(
	"/risk/strategy/{strategy_id}",
	response_model=analysis_schemas.RiskMetricsResponse,
	summary="获取策略风险指标",
	description="获取指定策略的风险指标，包括波动率、最大回撤、VaR等"
)
async def get_strategy_risk_metrics (
		strategy_id: str,
		start_date: Optional[date] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
		end_date: Optional[date] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
		confidence_level: float = Query(0.95, description="置信水平，用于计算VaR", ge=0.5, le=0.99),
		lookback_period: int = Query(252, description="回看周期（交易日）", ge=1, le=1000),
		db: Session = Depends(get_db),
		current_user: User = Depends(get_current_user)
):
	"""
	获取策略风险指标

	Args:
		strategy_id: 策略ID
		start_date: 开始日期
		end_date: 结束日期
		confidence_level: 置信水平
		lookback_period: 回看周期
		db: 数据库会话
		current_user: 当前用户

	Returns:
		策略风险指标
	"""
	try:
		handler = RiskAnalysisHandler(db, current_user.id)

		# 设置日期范围，默认为最近一年
		if not end_date:
			end_date = date.today()
		if not start_date:
			start_date = end_date - timedelta(days=365)

		# 验证日期范围
		if start_date > end_date:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="开始日期不能晚于结束日期"
			)

		# 获取风险指标
		risk_metrics = handler.calculate_strategy_risk_metrics(
			strategy_id=strategy_id,
			start_date=start_date,
			end_date=end_date,
			confidence_level=confidence_level,
			lookback_period=lookback_period
		)

		return analysis_schemas.RiskMetricsResponse(
			success=True,
			data=risk_metrics,
			message="风险指标获取成功"
		)
	except DataNotFoundException as e:
		raise HTTPException(status_code=404, detail=str(e))
	except AnalysisException as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(
			status_code=500,
			detail=f"获取风险指标失败: {str(e)}"
		)


@router.get(
	"/risk/portfolio/{portfolio_id}",
	response_model=analysis_schemas.PortfolioRiskResponse,
	summary="获取投资组合风险",
	description="获取投资组合的风险分析，包括相关性矩阵、风险贡献度等"
)
async def get_portfolio_risk (
		portfolio_id: str,
		start_date: Optional[date] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
		end_date: Optional[date] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
		risk_model: str = Query("covariance", description="风险模型：covariance, historical, monte_carlo"),
		db: Session = Depends(get_db),
		current_user: User = Depends(get_current_user)
):
	"""
	获取投资组合风险

	Args:
		portfolio_id: 投资组合ID
		start_date: 开始日期
		end_date: 结束日期
		risk_model: 风险模型
		db: 数据库会话
		current_user: 当前用户

	Returns:
		投资组合风险分析
	"""
	try:
		handler = RiskAnalysisHandler(db, current_user.id)

		# 设置日期范围，默认为最近一年
		if not end_date:
			end_date = date.today()
		if not start_date:
			start_date = end_date - timedelta(days=365)

		# 验证日期范围
		if start_date > end_date:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="开始日期不能晚于结束日期"
			)

		# 获取投资组合风险
		portfolio_risk = handler.analyze_portfolio_risk(
			portfolio_id=portfolio_id,
			start_date=start_date,
			end_date=end_date,
			risk_model=risk_model
		)

		return analysis_schemas.PortfolioRiskResponse(
			success=True,
			data=portfolio_risk,
			message="投资组合风险分析获取成功"
		)
	except DataNotFoundException as e:
		raise HTTPException(status_code=404, detail=str(e))
	except AnalysisException as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(
			status_code=500,
			detail=f"获取投资组合风险失败: {str(e)}"
		)


@router.post(
	"/risk/stress-test",
	response_model=analysis_schemas.StressTestResponse,
	summary="执行压力测试",
	description="对策略或投资组合执行压力测试，模拟极端市场情况"
)
async def run_stress_test (
		request: analysis_schemas.StressTestRequest,
		db: Session = Depends(get_db),
		current_user: User = Depends(get_current_user)
):
	"""
	执行压力测试

	Args:
		request: 压力测试请求
		db: 数据库会话
		current_user: 当前用户

	Returns:
		压力测试结果
	"""
	try:
		handler = RiskAnalysisHandler(db, current_user.id)

		# 验证请求数据
		if not request.entity_id or not request.scenarios:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="entity_id 和 scenarios 为必填项"
			)

		# 执行压力测试
		stress_test_result = handler.run_stress_test(request)

		return analysis_schemas.StressTestResponse(
			success=True,
			data=stress_test_result,
			message="压力测试执行完成"
		)
	except AnalysisException as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(
			status_code=500,
			detail=f"执行压力测试失败: {str(e)}"
		)


# ==================== 对比分析API ====================

@router.post(
	"/comparison/strategies",
	response_model=analysis_schemas.StrategyComparisonResponse,
	summary="对比多个策略",
	description="对比多个策略的绩效和风险指标，生成对比分析报告"
)
async def compare_strategies (
		request: analysis_schemas.StrategyComparisonRequest,
		db: Session = Depends(get_db),
		current_user: User = Depends(get_current_user)
):
	"""
	对比多个策略

	Args:
		request: 策略对比请求
		db: 数据库会话
		current_user: 当前用户

	Returns:
		策略对比结果
	"""
	try:
		handler = ComparisonAnalysisHandler(db, current_user.id)

		# 验证请求数据
		if not request.strategy_ids or len(request.strategy_ids) < 2:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="至少需要两个策略ID进行对比"
			)

		# 执行策略对比
		comparison_result = handler.compare_strategies(request)

		return analysis_schemas.StrategyComparisonResponse(
			success=True,
			data=comparison_result,
			message="策略对比完成"
		)
	except AnalysisException as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(
			status_code=500,
			detail=f"策略对比失败: {str(e)}"
		)


@router.get(
	"/comparison/benchmark/{strategy_id}",
	response_model=analysis_schemas.BenchmarkComparisonResponse,
	summary="与基准对比",
	description="将策略与指定基准进行对比分析"
)
async def compare_with_benchmark (
		strategy_id: str,
		benchmark_code: str = Query(..., description="基准代码，如：000300.SH"),
		start_date: Optional[date] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
		end_date: Optional[date] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
		db: Session = Depends(get_db),
		current_user: User = Depends(get_current_user)
):
	"""
	与基准对比

	Args:
		strategy_id: 策略ID
		benchmark_code: 基准代码
		start_date: 开始日期
		end_date: 结束日期
		db: 数据库会话
		current_user: 当前用户

	Returns:
		基准对比结果
	"""
	try:
		handler = ComparisonAnalysisHandler(db, current_user.id)

		# 设置日期范围，默认为最近一年
		if not end_date:
			end_date = date.today()
		if not start_date:
			start_date = end_date - timedelta(days=365)

		# 验证日期范围
		if start_date > end_date:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="开始日期不能晚于结束日期"
			)

		# 执行基准对比
		benchmark_comparison = handler.compare_with_benchmark(
			strategy_id=strategy_id,
			benchmark_code=benchmark_code,
			start_date=start_date,
			end_date=end_date
		)

		return analysis_schemas.BenchmarkComparisonResponse(
			success=True,
			data=benchmark_comparison,
			message="基准对比完成"
		)
	except DataNotFoundException as e:
		raise HTTPException(status_code=404, detail=str(e))
	except AnalysisException as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(
			status_code=500,
			detail=f"基准对比失败: {str(e)}"
		)


@router.get(
	"/comparison/correlation",
	response_model=analysis_schemas.CorrelationAnalysisResponse,
	summary="相关性分析",
	description="分析多个策略或资产之间的相关性"
)
async def analyze_correlation (
		item_ids: List[str] = Query(..., description="策略ID或资产代码列表"),
		item_type: str = Query("events", description="项目类型：events, asset, portfolio"),
		start_date: Optional[date] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
		end_date: Optional[date] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
		correlation_method: str = Query("pearson", description="相关性计算方法：pearson, spearman, kendall"),
		db: Session = Depends(get_db),
		current_user: User = Depends(get_current_user)
):
	"""
	相关性分析

	Args:
		item_ids: 项目ID列表
		item_type: 项目类型
		start_date: 开始日期
		end_date: 结束日期
		correlation_method: 相关性计算方法
		db: 数据库会话
		current_user: 当前用户

	Returns:
		相关性分析结果
	"""
	try:
		handler = ComparisonAnalysisHandler(db, current_user.id)

		# 验证输入
		if len(item_ids) < 2:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="至少需要两个项目进行相关性分析"
			)

		# 设置日期范围，默认为最近一年
		if not end_date:
			end_date = date.today()
		if not start_date:
			start_date = end_date - timedelta(days=365)

		# 验证日期范围
		if start_date > end_date:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="开始日期不能晚于结束日期"
			)

		# 执行相关性分析
		correlation_result = handler.analyze_correlation(
			item_ids=item_ids,
			item_type=item_type,
			start_date=start_date,
			end_date=end_date,
			correlation_method=correlation_method
		)

		return analysis_schemas.CorrelationAnalysisResponse(
			success=True,
			data=correlation_result,
			message="相关性分析完成"
		)
	except AnalysisException as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(
			status_code=500,
			detail=f"相关性分析失败: {str(e)}"
		)


# ==================== 归因分析API ====================

@router.get(
	"/attribution/strategy/{strategy_id}",
	response_model=analysis_schemas.AttributionAnalysisResponse,
	summary="获取策略归因分析",
	description="对策略收益进行归因分析，识别收益来源"
)
async def get_strategy_attribution (
		strategy_id: str,
		start_date: Optional[date] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
		end_date: Optional[date] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
		attribution_model: str = Query("brinson", description="归因模型：brinson, carino, frongello"),
		db: Session = Depends(get_db),
		current_user: User = Depends(get_current_user)
):
	"""
	获取策略归因分析

	Args:
		strategy_id: 策略ID
		start_date: 开始日期
		end_date: 结束日期
		attribution_model: 归因模型
		db: 数据库会话
		current_user: 当前用户

	Returns:
		策略归因分析结果
	"""
	try:
		handler = AttributionAnalysisHandler(db, current_user.id)

		# 设置日期范围，默认为最近一年
		if not end_date:
			end_date = date.today()
		if not start_date:
			start_date = end_date - timedelta(days=365)

		# 验证日期范围
		if start_date > end_date:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="开始日期不能晚于结束日期"
			)

		# 获取归因分析
		attribution_result = handler.analyze_strategy_attribution(
			strategy_id=strategy_id,
			start_date=start_date,
			end_date=end_date,
			attribution_model=attribution_model
		)

		return analysis_schemas.AttributionAnalysisResponse(
			success=True,
			data=attribution_result,
			message="归因分析获取成功"
		)
	except DataNotFoundException as e:
		raise HTTPException(status_code=404, detail=str(e))
	except AnalysisException as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(
			status_code=500,
			detail=f"获取归因分析失败: {str(e)}"
		)


@router.get(
	"/attribution/portfolio/{portfolio_id}",
	response_model=analysis_schemas.PortfolioAttributionResponse,
	summary="获取投资组合归因分析",
	description="对投资组合收益进行多维度归因分析"
)
async def get_portfolio_attribution (
		portfolio_id: str,
		start_date: Optional[date] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
		end_date: Optional[date] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
		attribution_dimension: str = Query("sector", description="归因维度：sector, style, country, currency"),
		db: Session = Depends(get_db),
		current_user: User = Depends(get_current_user)
):
	"""
	获取投资组合归因分析

	Args:
		portfolio_id: 投资组合ID
		start_date: 开始日期
		end_date: 结束日期
		attribution_dimension: 归因维度
		db: 数据库会话
		current_user: 当前用户

	Returns:
		投资组合归因分析结果
	"""
	try:
		handler = AttributionAnalysisHandler(db, current_user.id)

		# 设置日期范围，默认为最近一年
		if not end_date:
			end_date = date.today()
		if not start_date:
			start_date = end_date - timedelta(days=365)

		# 验证日期范围
		if start_date > end_date:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="开始日期不能晚于结束日期"
			)

		# 获取投资组合归因分析
		attribution_result = handler.analyze_portfolio_attribution(
			portfolio_id=portfolio_id,
			start_date=start_date,
			end_date=end_date,
			attribution_dimension=attribution_dimension
		)

		return analysis_schemas.PortfolioAttributionResponse(
			success=True,
			data=attribution_result,
			message="投资组合归因分析获取成功"
		)
	except DataNotFoundException as e:
		raise HTTPException(status_code=404, detail=str(e))
	except AnalysisException as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(
			status_code=500,
			detail=f"获取投资组合归因分析失败: {str(e)}"
		)


# ==================== 通用分析API ====================

@router.get(
	"/metrics/available",
	response_model=analysis_schemas.AvailableMetricsResponse,
	summary="获取可用分析指标",
	description="获取系统中可用的绩效和风险指标列表"
)
async def get_available_metrics (
		metric_type: str = Query("all", description="指标类型：performance, risk, attribution, all"),
		db: Session = Depends(get_db),
		current_user: User = Depends(get_current_user)
):
	"""
	获取可用分析指标

	Args:
		metric_type: 指标类型
		db: 数据库会话
		current_user: 当前用户

	Returns:
		可用指标列表
	"""
	try:
		# 根据指标类型返回不同的指标列表
		if metric_type == "performance":
			metrics = analysis_schemas.PERFORMANCE_METRICS
		elif metric_type == "risk":
			metrics = analysis_schemas.RISK_METRICS
		elif metric_type == "attribution":
			metrics = analysis_schemas.ATTRIBUTION_METRICS
		else:
			metrics = {
				"performance": analysis_schemas.PERFORMANCE_METRICS,
				"risk": analysis_schemas.RISK_METRICS,
				"attribution": analysis_schemas.ATTRIBUTION_METRICS
			}

		return analysis_schemas.AvailableMetricsResponse(
			success=True,
			data=metrics,
			message="可用指标获取成功"
		)
	except Exception as e:
		raise HTTPException(
			status_code=500,
			detail=f"获取可用指标失败: {str(e)}"
		)


@router.get(
	"/tasks/{task_id}/status",
	response_model=analysis_schemas.AsyncTaskStatusResponse,
	summary="获取异步任务状态",
	description="获取异步分析任务的执行状态和结果"
)
async def get_async_task_status (
		task_id: str,
		db: Session = Depends(get_db),
		current_user: User = Depends(get_current_user)
):
	"""
	获取异步任务状态

	Args:
		task_id: 任务ID
		db: 数据库会话
		current_user: 当前用户

	Returns:
		异步任务状态
	"""
	try:
		# 这里需要根据实际的任务存储方式实现
		# 简化实现，返回模拟数据
		from quant_server.modules.analysis.tasks import get_task_status

		task_status = get_task_status(task_id)

		if not task_status:
			raise HTTPException(
				status_code=404,
				detail=f"任务不存在: {task_id}"
			)

		return analysis_schemas.AsyncTaskStatusResponse(
			success=True,
			data=task_status,
			message="任务状态获取成功"
		)
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(
			status_code=500,
			detail=f"获取任务状态失败: {str(e)}"
		)


@router.post(
	"/export/report",
	response_model=analysis_schemas.ExportReportResponse,
	summary="导出分析报告",
	description="将分析结果导出为指定格式的报告"
)
async def export_analysis_report (
		request: analysis_schemas.ExportReportRequest,
		db: Session = Depends(get_db),
		current_user: User = Depends(get_current_user)
):
	"""
	导出分析报告

	Args:
		request: 导出报告请求
		db: 数据库会话
		current_user: 当前用户

	Returns:
		导出报告响应
	"""
	try:
		# 根据报告类型选择处理器
		if request.report_type == "performance":
			handler = PerformanceAnalysisHandler(db, current_user.id)
		elif request.report_type == "risk":
			handler = RiskAnalysisHandler(db, current_user.id)
		elif request.report_type == "comparison":
			handler = ComparisonAnalysisHandler(db, current_user.id)
		elif request.report_type == "attribution":
			handler = AttributionAnalysisHandler(db, current_user.id)
		else:
			raise HTTPException(
				status_code=400,
				detail=f"不支持的报告类型: {request.report_type}"
			)

		# 导出报告
		export_result = handler.export_report(
			report_id=request.report_id,
			export_format=request.export_format,
			include_charts=request.include_charts
		)

		# 如果是CSV格式，返回文件下载
		if request.export_format == "csv" and "file_path" in export_result:
			return StreamingResponse(
				open(export_result["file_path"], "rb"),
				media_type="text/csv",
				headers={"Content-Disposition": f"attachment; filename={export_result['filename']}"}
			)

		return analysis_schemas.ExportReportResponse(
			success=True,
			data=export_result,
			message="报告导出成功"
		)
	except DataNotFoundException as e:
		raise HTTPException(status_code=404, detail=str(e))
	except AnalysisException as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(
			status_code=500,
			detail=f"导出报告失败: {str(e)}"
		)


# ==================== 图表数据API ====================

@router.get(
	"/charts/equity-curve",
	response_model=analysis_schemas.EquityCurveResponse,
	summary="获取资产曲线数据",
	description="获取策略或账户的资产曲线数据，用于绘制净值曲线图"
)
async def get_equity_curve (
		entity_id: str = Query(..., description="策略ID或账户ID"),
		entity_type: str = Query("events", description="实体类型：events, events"),
		start_date: Optional[date] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
		end_date: Optional[date] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
		frequency: str = Query("daily", description="频率：daily, weekly, monthly"),
		db: Session = Depends(get_db),
		current_user: User = Depends(get_current_user)
):
	"""
	获取资产曲线数据

	Args:
		entity_id: 实体ID
		entity_type: 实体类型
		start_date: 开始日期
		end_date: 结束日期
		frequency: 频率
		db: 数据库会话
		current_user: 当前用户

	Returns:
		资产曲线数据
	"""
	try:
		handler = PerformanceAnalysisHandler(db, current_user.id)

		# 设置日期范围，默认为最近一年
		if not end_date:
			end_date = date.today()
		if not start_date:
			start_date = end_date - timedelta(days=365)

		# 验证日期范围
		if start_date > end_date:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="开始日期不能晚于结束日期"
			)

		# 获取资产曲线数据
		equity_curve = handler.get_equity_curve(
			entity_id=entity_id,
			entity_type=entity_type,
			start_date=start_date,
			end_date=end_date,
			frequency=frequency
		)

		return analysis_schemas.EquityCurveResponse(
			success=True,
			data=equity_curve,
			message="资产曲线数据获取成功"
		)
	except DataNotFoundException as e:
		raise HTTPException(status_code=404, detail=str(e))
	except AnalysisException as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(
			status_code=500,
			detail=f"获取资产曲线数据失败: {str(e)}"
		)


# ==================== 健康检查API ====================

@router.get(
	"/health",
	summary="分析模块健康检查",
	description="检查分析模块的运行状态"
)
async def health_check ():
	"""
	分析模块健康检查

	Returns:
		健康状态
	"""
	try:
		# 简单的健康检查
		return {
			"status": "healthy",
			"timestamp": datetime.now().isoformat(),
			"module": "events",
			"version": "1.0.0"
		}
	except Exception as e:
		raise HTTPException(
			status_code=500,
			detail=f"健康检查失败: {str(e)}"
		)