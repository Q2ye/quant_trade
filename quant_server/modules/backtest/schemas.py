# -*- coding: utf-8 -*-
"""
回测模块Pydantic模型
API请求/响应模型定义
"""
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, Field

from utils.api_utils.pagination_config import PaginationParams


class BacktestCreateRequest(BaseModel):
	"""回测创建请求"""
	name: str = Field(..., description="回测名称")
	strategy_id: str = Field(..., description="策略ID")
	start_date: str = Field(..., description="开始日期")
	end_date: str = Field(..., description="结束日期")
	initial_capital: float = Field(default=1000000.0, description="初始资金")
	commission_rate: float = Field(default=0.0001, description="佣金费率（万一免五）")
	slippage_rate: float = Field(default=0.0001, description="滑点费率")
	symbols: Optional[List[str]] = Field(default=None, description="股票代码列表，不填则依赖策略自身股票池")
	benchmark: Optional[str] = Field(default=None, description="基准指数代码，如 000300.SH（沪深300）")
	parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="回测参数，包含市场参数和策略参数")


class StrategyCompositeConfig(BaseModel):
	"""组合回测 — 单个策略配置"""
	strategy_id: str = Field(..., description="策略ID")
	allocator_id: str = Field(default="", description="分配器中的权重键，默认等于 strategy_id")
	parameters: Optional[Dict[str, Any]] = Field(default=None, description="策略参数覆写")


class BacktestCompositeCreateRequest(BaseModel):
	"""组合回测创建请求 — 多策略共享资金池"""
	name: str = Field(..., description="回测名称")
	strategy_configs: List[StrategyCompositeConfig] = Field(..., min_length=2, description="策略配置列表（≥2个）")
	start_date: str = Field(..., description="开始日期")
	end_date: str = Field(..., description="结束日期")
	initial_capital: float = Field(default=1000000.0, description="初始资金")
	commission_rate: float = Field(default=0.0001, description="佣金费率")
	slippage_rate: float = Field(default=0.0001, description="滑点费率")
	symbols: Optional[List[str]] = Field(default=None, description="股票代码列表")
	benchmark: Optional[str] = Field(default=None, description="基准指数代码")
	force_regime: Optional[int] = Field(default=None, ge=0, le=2, description="P0 固定Regime: 0=BEAR 1=RANGE 2=BULL，不填默认RANGE")
	allocator_params: Optional[Dict[str, Any]] = Field(default=None, description="CapitalAllocator参数")


class BacktestCreateResponse(BaseModel):
	"""回测创建响应"""
	success: bool = Field(default=True)
	data: Optional[Dict[str, Any]] = Field(default=None)


class BacktestDetailResponse(BaseModel):
	"""回测详情响应"""
	success: bool = Field(default=True)
	data: Optional[Dict[str, Any]] = Field(default=None)


class BacktestListRequest(PaginationParams):
	"""回测列表请求"""
	status: Optional[str] = Field(default=None, description="状态筛选")
	strategy_id: Optional[str] = Field(default=None, description="按策略ID筛选")
	start_date: Optional[str] = Field(default=None, description="创建时间起（ISO 格式）")
	end_date: Optional[str] = Field(default=None, description="创建时间止（ISO 格式）")


class BacktestListResponse(BaseModel):
	"""回测列表响应"""
	success: bool = Field(default=True)
	data: List[Dict[str, Any]] = Field(default_factory=list)
	pagination: Dict[str, int] = Field(default_factory=dict)


class BacktestCancelRequest(BaseModel):
	"""回测取消请求"""
	reason: Optional[str] = Field(default=None, description="取消原因")


class BacktestEquityCurveRequest(BaseModel):
	"""回测净值曲线请求"""
	frequency: str = Field(default="daily", description="频率: daily/weekly/monthly")


class BacktestEquityCurveResponse(BaseModel):
	"""回测净值曲线响应"""
	success: bool = Field(default=True)
	data: List[Dict[str, Any]] = Field(default_factory=list)


class BacktestTradesRequest(BaseModel):
	"""回测交易记录请求"""


class BacktestTradesResponse(BaseModel):
	"""回测交易记录响应"""
	success: bool = Field(default=True)
	data: List[Dict[str, Any]] = Field(default_factory=list)
	pagination: Dict[str, int] = Field(default_factory=dict)


class BacktestPositionsRequest(BaseModel):
	"""回测持仓快照请求"""
	date: Optional[str] = Field(default=None, description="日期")


class BacktestPositionsResponse(BaseModel):
	"""回测持仓快照响应"""
	success: bool = Field(default=True)
	data: List[Dict[str, Any]] = Field(default_factory=list)


class BacktestResultResponse(BaseModel):
	"""回测结果响应"""
	success: bool = Field(default=True)
	data: Optional[Dict[str, Any]] = Field(default=None)


class BacktestOptimizeRequest(BaseModel):
	"""参数优化请求"""
	strategy_id: str = Field(..., description="策略ID")
	parameters: Dict[str, Any] = Field(..., description="参数范围")
	optimization_method: str = Field(default="grid", description="优化方法: grid/bayesian/genetic")


class BacktestOptimizeResponse(BaseModel):
	"""参数优化响应"""
	success: bool = Field(default=True)
	data: Optional[Dict[str, Any]] = Field(default=None)


# v3.3: 独立场景回测
class ScenarioRunRequest(BaseModel):
	"""独立场景回测请求"""
	name: str = Field(..., description="场景名称")
	code: str = Field(..., description="策略代码")
	parameters: Optional[Dict[str, Any]] = Field(default={}, description="参数覆写")
	config: Optional[Dict[str, Any]] = Field(default={}, description="回测配置 (start_date/end_date/initial_capital/benchmark)")
	template_id: Optional[str] = Field(default=None, description="来源模板ID")
	source_strategy_id: Optional[str] = Field(default=None, description="来源策略ID")


class ScenarioPromoteRequest(BaseModel):
	"""场景晋升请求"""
	scenario_id: str = Field(..., description="场景ID")
	strategy_name: Optional[str] = Field(default=None, description="策略名称（不填则用场景名）")