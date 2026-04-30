#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析模块API请求/响应模型

定义分析模块的所有API接口的请求和响应模型，包括：
- 绩效分析API模型
- 风险分析API模型
- 对比分析API模型
- 归因分析API模型
- 通用分析API模型
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field, validator

from .constants import (
    AnalysisType, ReportStatus, RiskModel,
    AttributionModel, CorrelationMethod, ExportFormat
)


# ==================== 基础模型 ====================

class BaseRequest(BaseModel):
    """基础请求模型"""
    class Config:
        anystr_strip_whitespace = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(..., description="响应消息")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间戳")


class PaginatedRequest(BaseRequest):
    """分页请求模型"""
    page: int = Field(1, ge=1, description="页码，从1开始")
    page_size: int = Field(20, ge=1, le=100, description="每页记录数")
    sort_by: Optional[str] = Field(None, description="排序字段")
    sort_order: Optional[str] = Field("desc", description="排序方向: asc, desc")


class PaginatedResponse(BaseResponse):
    """分页响应模型"""
    total: int = Field(..., description="总记录数")
    total_pages: int = Field(..., description="总页数")
    current_page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页记录数")


class AsyncTaskResponse(BaseResponse):
    """异步任务响应模型"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    estimated_time: Optional[int] = Field(None, description="预计完成时间（秒）")


class AsyncTaskStatusResponse(BaseResponse):
    """异步任务状态响应模型"""
    data: Dict[str, Any] = Field(..., description="任务状态数据")


# ==================== 绩效分析API模型 ====================

class GenerateReportRequest(BaseRequest):
    """生成报告请求模型"""
    analysis_type: AnalysisType = Field(..., description="分析类型")
    target_id: str = Field(..., description="目标ID（策略ID或账户ID）")
    target_type: str = Field(..., description="目标类型: events, events, portfolio")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")
    benchmark: Optional[str] = Field(None, description="基准代码")
    metrics: List[str] = Field(default_factory=list, description="需要计算的指标")
    include_charts: bool = Field(True, description="是否包含图表")
    frequency: str = Field("daily", description="频率: daily, weekly, monthly")


class PerformanceReportResponse(BaseResponse):
    """绩效报告响应模型"""
    data: Dict[str, Any] = Field(..., description="绩效报告数据")


class PerformanceMetrics(BaseModel):
    """绩效指标模型"""
    total_return: Optional[float] = Field(None, description="累计收益率")
    annual_return: Optional[float] = Field(None, description="年化收益率")
    annual_volatility: Optional[float] = Field(None, description="年化波动率")
    sharpe_ratio: Optional[float] = Field(None, description="夏普比率")
    sortino_ratio: Optional[float] = Field(None, description="索提诺比率")
    max_drawdown: Optional[float] = Field(None, description="最大回撤")
    calmar_ratio: Optional[float] = Field(None, description="卡玛比率")
    win_rate: Optional[float] = Field(None, description="胜率")
    profit_factor: Optional[float] = Field(None, description="盈利因子")
    alpha: Optional[float] = Field(None, description="阿尔法")
    beta: Optional[float] = Field(None, description="贝塔")
    information_ratio: Optional[float] = Field(None, description="信息比率")
    tracking_error: Optional[float] = Field(None, description="跟踪误差")


# ==================== 风险分析API模型 ====================

class StressTestRequest(BaseRequest):
    """压力测试请求模型"""
    portfolio_id: str = Field(..., description="投资组合ID")
    scenarios: List[Dict[str, Any]] = Field(..., description="压力测试场景")
    risk_model: RiskModel = Field(RiskModel.HISTORICAL, description="风险模型")
    confidence_level: float = Field(0.95, ge=0.5, le=0.99, description="置信水平")
    lookback_period: int = Field(252, ge=30, le=1000, description="回看周期")


class StressTestResponse(BaseResponse):
    """压力测试响应模型"""
    data: Dict[str, Any] = Field(..., description="压力测试结果")


class RiskMetricsResponse(BaseResponse):
    """风险指标响应模型"""
    data: Dict[str, Any] = Field(..., description="风险指标数据")


class PortfolioRiskResponse(BaseResponse):
    """投资组合风险响应模型"""
    data: Dict[str, Any] = Field(..., description="投资组合风险分析结果")


class RiskMetrics(BaseModel):
    """风险指标模型"""
    volatility: Optional[float] = Field(None, description="波动率")
    var_95: Optional[float] = Field(None, description="95% VaR")
    var_99: Optional[float] = Field(None, description="99% VaR")
    conditional_var: Optional[float] = Field(None, description="条件VaR")
    expected_shortfall: Optional[float] = Field(None, description="期望损失")
    skewness: Optional[float] = Field(None, description="偏度")
    kurtosis: Optional[float] = Field(None, description="峰度")
    tail_risk: Optional[float] = Field(None, description="尾部风险")
    liquidity_risk: Optional[float] = Field(None, description="流动性风险")


# ==================== 对比分析API模型 ====================

class StrategyComparisonRequest(BaseRequest):
    """策略对比请求模型"""
    strategy_ids: List[str] = Field(..., min_items=2, description="策略ID列表")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")
    benchmark: Optional[str] = Field(None, description="基准代码")
    metrics: List[str] = Field(default_factory=list, description="对比指标")
    include_correlation: bool = Field(True, description="是否包含相关性分析")


class StrategyComparisonResponse(BaseResponse):
    """策略对比响应模型"""
    data: Dict[str, Any] = Field(..., description="策略对比结果")


class BenchmarkComparisonResponse(BaseResponse):
    """基准对比响应模型"""
    data: Dict[str, Any] = Field(..., description="基准对比结果")


class CorrelationAnalysisResponse(BaseResponse):
    """相关性分析响应模型"""
    data: Dict[str, Any] = Field(..., description="相关性分析结果")


class ComparisonMetrics(BaseModel):
    """对比指标模型"""
    strategy_id: str = Field(..., description="策略ID")
    metrics: Dict[str, float] = Field(..., description="各项指标值")
    ranking: Dict[str, int] = Field(..., description="各项指标排名")
    relative_performance: Dict[str, float] = Field(..., description="相对表现")


# ==================== 归因分析API模型 ====================

class AttributionAnalysisResponse(BaseResponse):
    """归因分析响应模型"""
    data: Dict[str, Any] = Field(..., description="归因分析结果")


class PortfolioAttributionResponse(BaseResponse):
    """投资组合归因响应模型"""
    data: Dict[str, Any] = Field(..., description="投资组合归因分析结果")


class AttributionMetrics(BaseModel):
    """归因指标模型"""
    total_attribution: float = Field(..., description="总归因收益")
    allocation_effect: Optional[float] = Field(None, description="资产配置效应")
    selection_effect: Optional[float] = Field(None, description="证券选择效应")
    interaction_effect: Optional[float] = Field(None, description="交互效应")
    factor_attributions: Optional[Dict[str, float]] = Field(None, description="因子归因")
    sector_attributions: Optional[Dict[str, float]] = Field(None, description="行业归因")


# ==================== 交易分析API模型 ====================

class TradeAnalysisRequest(BaseRequest):
    """交易分析请求模型"""
    strategy_id: Optional[str] = Field(None, description="策略ID")
    account_id: Optional[str] = Field(None, description="账户ID")
    start_date: date = Field(..., description="开始日期")
    end_date: date = Field(..., description="结束日期")
    analysis_dimension: str = Field("cost", description="分析维度: cost, execution, timing")
    include_details: bool = Field(False, description="是否包含详细交易数据")


class TradeAnalysisResponse(BaseResponse):
    """交易分析响应模型"""
    data: Dict[str, Any] = Field(..., description="交易分析结果")


class TradeMetrics(BaseModel):
    """交易指标模型"""
    total_trades: int = Field(..., description="总交易次数")
    total_volume: int = Field(..., description="总交易量")
    total_amount: float = Field(..., description="总交易金额")
    avg_trade_size: float = Field(..., description="平均交易规模")
    commission_cost: float = Field(..., description="佣金成本")
    tax_cost: float = Field(..., description="税费成本")
    slippage_cost: float = Field(..., description="滑点成本")
    total_cost: float = Field(..., description="总成本")
    cost_rate: float = Field(..., description="成本比率")
    fill_rate: Optional[float] = Field(None, description="成交率")
    execution_speed: Optional[float] = Field(None, description="执行速度（秒）")


# ==================== 通用分析API模型 ====================

class AvailableMetricsResponse(BaseResponse):
    """可用指标响应模型"""
    data: Dict[str, Any] = Field(..., description="可用指标数据")


class EquityCurveResponse(BaseResponse):
    """资产曲线响应模型"""
    data: Dict[str, Any] = Field(..., description="资产曲线数据")


class ExportReportRequest(BaseRequest):
    """导出报告请求模型"""
    report_id: str = Field(..., description="报告ID")
    report_type: AnalysisType = Field(..., description="报告类型")
    export_format: ExportFormat = Field(ExportFormat.PDF, description="导出格式")
    include_charts: bool = Field(True, description="是否包含图表")
    file_name: Optional[str] = Field(None, description="文件名")


class ExportReportResponse(BaseResponse):
    """导出报告响应模型"""
    data: Dict[str, Any] = Field(..., description="导出报告数据")


class AnalysisTask(BaseModel):
    """分析任务模型"""
    task_id: str = Field(..., description="任务ID")
    user_id: str = Field(..., description="用户ID")
    analysis_type: AnalysisType = Field(..., description="分析类型")
    target_id: str = Field(..., description="目标ID")
    status: ReportStatus = Field(ReportStatus.PENDING, description="任务状态")
    progress: float = Field(0.0, ge=0.0, le=100.0, description="进度百分比")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="任务参数")
    result: Optional[Dict[str, Any]] = Field(None, description="任务结果")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")


# ==================== 数据验证器 ====================

@validator('confidence_level')
def validate_confidence_level(cls, v):
    """验证置信水平"""
    if not 0.5 <= v <= 0.999:
        raise ValueError('置信水平必须在0.5到0.999之间')
    return v


@validator('strategy_ids')
def validate_strategy_ids(cls, v):
    """验证策略ID列表"""
    if len(v) < 2:
        raise ValueError('至少需要2个策略进行对比')
    if len(v) > 10:
        raise ValueError('最多支持10个策略同时对比')
    return v


@validator('scenarios')
def validate_scenarios(cls, v):
    """验证压力测试场景"""
    if not v:
        raise ValueError('至少需要一个压力测试场景')
    for scenario in v:
        if 'name' not in scenario:
            raise ValueError('每个场景必须包含名称')
        if 'parameters' not in scenario:
            raise ValueError('每个场景必须包含参数')
    return v