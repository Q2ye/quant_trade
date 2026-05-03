# -*- coding: utf-8 -*-
"""
交易模块Pydantic模型
API请求/响应模型定义
"""
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, Field

from utils.api_utils.pagination_config import PaginationParams


class OrderListRequest(PaginationParams):
	"""订单列表请求"""
	status: Optional[str] = Field(default=None, description="订单状态筛选")
	ts_code: Optional[str] = Field(default=None, description="证券代码筛选")


class OrderListResponse(BaseModel):
	"""订单列表响应"""
	success: bool = Field(default=True)
	data: List[Dict[str, Any]] = Field(default_factory=list)
	pagination: Dict[str, int] = Field(default_factory=dict)


class OrderDetailResponse(BaseModel):
	"""订单详情响应"""
	success: bool = Field(default=True)
	data: Optional[Dict[str, Any]] = Field(default=None)
	message: Optional[str] = Field(default=None)


class OrderCreateRequest(BaseModel):
	"""订单创建请求"""
	ts_code: str = Field(..., description="证券代码")
	direction: str = Field(..., description="交易方向: buy/sell")
	price: float = Field(..., description="价格")
	quantity: int = Field(..., description="数量")
	order_type: str = Field(default="limit", description="订单类型: limit/market")


class OrderResponse(BaseModel):
	"""订单响应"""
	success: bool = Field(default=True)
	data: Optional[Dict[str, Any]] = Field(default=None)
	message: Optional[str] = Field(default=None)


class OrderCancelRequest(BaseModel):
	"""订单撤销请求"""
	reason: Optional[str] = Field(default=None, description="撤销原因")


class PositionListRequest(PaginationParams):
	"""持仓列表请求"""


class PositionListResponse(BaseModel):
	"""持仓列表响应"""
	success: bool = Field(default=True)
	data: List[Dict[str, Any]] = Field(default_factory=list)
	pagination: Dict[str, int] = Field(default_factory=dict)


class PositionDetailResponse(BaseModel):
	"""持仓详情响应"""
	success: bool = Field(default=True)
	data: Optional[Dict[str, Any]] = Field(default=None)
	message: Optional[str] = Field(default=None)


class SignalExecuteRequest(BaseModel):
	"""信号执行请求"""
	signal_id: str = Field(..., description="信号ID")
	ts_code: str = Field(..., description="证券代码")
	direction: str = Field(..., description="交易方向")
	quantity: int = Field(..., description="数量")
	price: Optional[float] = Field(default=None, description="价格")


class SignalExecuteResponse(BaseModel):
	"""信号执行响应"""
	success: bool = Field(default=True)
	data: Optional[Dict[str, Any]] = Field(default=None)
	message: Optional[str] = Field(default=None)


class TradeHistoryRequest(PaginationParams):
	"""交易历史请求"""
	start_date: Optional[str] = Field(default=None, description="开始日期")
	end_date: Optional[str] = Field(default=None, description="结束日期")


class TradeHistoryResponse(BaseModel):
	"""交易历史响应"""
	success: bool = Field(default=True)
	data: List[Dict[str, Any]] = Field(default_factory=list)
	pagination: Dict[str, int] = Field(default_factory=dict)


class AccountSummaryResponse(BaseModel):
	"""账户概览响应"""
	success: bool = Field(default=True)
	data: Optional[Dict[str, Any]] = Field(default=None)
	message: Optional[str] = Field(default=None)