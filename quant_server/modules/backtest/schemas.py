# -*- coding: utf-8 -*-
"""
回测模块Pydantic模型
API请求/响应模型定义
"""
from pydantic import BaseModel, Field
from quant_server.utils.api_utils.pagination_config import PaginationParams

from typing import Optional, List, Any, Dict
from datetime import datetime


class BacktestCreateRequest(BaseModel):
    """回测创建请求"""
    name: str = Field(..., description="回测名称")
    strategy_id: int = Field(..., description="策略ID")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    initial_capital: float = Field(default=1000000.0, description="初始资金")
    commission_rate: float = Field(default=0.0003, description="佣金费率")
    slippage_rate: float = Field(default=0.0001, description="滑点费率")


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
    strategy_id: int = Field(..., description="策略ID")
    parameters: Dict[str, Any] = Field(..., description="参数范围")
    optimization_method: str = Field(default="grid", description="优化方法: grid/bayesian/genetic")


class BacktestOptimizeResponse(BaseModel):
    """参数优化响应"""
    success: bool = Field(default=True)
    data: Optional[Dict[str, Any]] = Field(default=None)
