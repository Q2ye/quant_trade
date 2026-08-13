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


# ==================== 手动成交录入 ====================

class TradeFeeItem(BaseModel):
	"""单笔费用（未填项为 null，由后端按统一费率自动计算）"""
	commission: Optional[float] = Field(default=None, description="佣金")
	stamp_duty: Optional[float] = Field(default=None, description="印花税")
	transfer_fee: Optional[float] = Field(default=None, description="过户费")


class TradeRecordRequest(BaseModel):
	"""手动成交录入请求 — 用户在券商端完成交易后回系统记账"""
	signal_id: Optional[str] = Field(default=None, description="关联信号ID（可选）")
	strategy_id: Optional[str] = Field(default=None, description="关联策略ID（可选）")
	ts_code: str = Field(..., description="证券代码，如 300001.SZ")
	direction: str = Field(..., description="交易方向: buy / sell")
	price: float = Field(..., description="实际成交价")
	quantity: int = Field(..., gt=0, description="成交数量（股）")
	trade_date: str = Field(..., description="成交日期，格式 YYYY-MM-DD")
	fees: Optional[TradeFeeItem] = Field(
		default=None,
		description="费用（选填）。不填则按 A 股标准费率自动计算"
	)


class TradeRecordResponse(BaseModel):
	"""手动成交录入响应"""
	success: bool = Field(default=True)
	data: Optional[Dict[str, Any]] = Field(default=None)
	message: Optional[str] = Field(default=None)


class BatchTradeRecordRequest(BaseModel):
	"""批量成交录入请求"""
	trades: List[TradeRecordRequest] = Field(..., min_length=1, description="成交列表")


class BatchTradeRecordResponse(BaseModel):
	"""批量成交录入响应"""
	success: bool = Field(default=True)
	data: Optional[Dict[str, Any]] = Field(default=None)
	message: Optional[str] = Field(default=None)


# ==================== 信号管理 ====================

class SignalReviewRequest(BaseModel):
	"""信号审核请求"""
	action: str = Field(..., description="审核动作: approved / rejected")
	comment: Optional[str] = Field(default=None, description="审核备注")


class SignalReviewResponse(BaseModel):
	"""信号审核响应"""
	success: bool = Field(default=True)
	data: Optional[Dict[str, Any]] = Field(default=None)
	message: Optional[str] = Field(default=None)


class SignalListRequest(PaginationParams):
	"""信号列表请求"""
	status: Optional[str] = Field(default=None, description="信号状态筛选: pending/approved/rejected/executed")
	signal_type: Optional[str] = Field(default=None, description="信号类型筛选: buy/sell")


class SignalListResponse(BaseModel):
	"""信号列表响应"""
	success: bool = Field(default=True)
	data: List[Dict[str, Any]] = Field(default_factory=list)
	pagination: Dict[str, int] = Field(default_factory=dict)


class RoundTripRequest(BaseModel):
	"""买卖配对追溯请求"""
	account_id: str = Field(..., description="账户ID")
	ts_code: Optional[str] = Field(default=None, description="证券代码（可选，不传返回全部）")


class RoundTripResponse(BaseModel):
	"""买卖配对追溯响应"""
	success: bool = Field(default=True)
	data: Optional[Dict[str, Any]] = Field(default=None)
	message: Optional[str] = Field(default=None)