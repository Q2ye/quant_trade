"""
账户模块API请求/响应模型定义
使用Pydantic进行数据验证
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .constants import (
	ACCOUNT_TYPES,
	ACCOUNT_STATUSES,
	MAX_ACCOUNT_NAME_LENGTH,
	MAX_ACCOUNT_NUMBER_LENGTH,
	MAX_BROKER_NAME_LENGTH
)


class AccountCreateRequest(BaseModel):
	"""账户创建请求模型"""

	user_id: str = Field(..., description="用户ID")
	account_name: str = Field(..., max_length=MAX_ACCOUNT_NAME_LENGTH, description="账户名称")
	account_type: str = Field(..., description="账户类型")
	initial_balance: Decimal = Field(
		default=1000000.00,
		ge=0,
		description="初始资金"
	)
	broker: Optional[str] = Field(
		None,
		max_length=MAX_BROKER_NAME_LENGTH,
		description="券商名称"
	)
	broker_account_id: Optional[str] = Field(
		None,
		max_length=MAX_ACCOUNT_NUMBER_LENGTH,
		description="券商账户ID"
	)

	@field_validator('account_type')
	def validate_account_type (cls, v):
		"""验证账户类型"""
		if v not in ACCOUNT_TYPES:
			raise ValueError(f"账户类型必须是以下之一: {', '.join(ACCOUNT_TYPES)}")
		return v


class AccountUpdateRequest(BaseModel):
	"""账户更新请求模型"""

	account_name: Optional[str] = Field(
		None,
		max_length=MAX_ACCOUNT_NAME_LENGTH,
		description="账户名称"
	)
	status: Optional[str] = Field(None, description="账户状态")
	status_reason: Optional[str] = Field(None, max_length=500, description="状态变更原因")
	broker: Optional[str] = Field(None, max_length=MAX_BROKER_NAME_LENGTH, description="券商名称")
	broker_account_id: Optional[str] = Field(
		None,
		max_length=MAX_ACCOUNT_NUMBER_LENGTH,
		description="券商账户ID"
	)

	@field_validator('status')
	def validate_status (cls, v):
		"""验证账户状态"""
		if v is not None and v not in ACCOUNT_STATUSES:
			raise ValueError(f"账户状态必须是以下之一: {', '.join(ACCOUNT_STATUSES)}")
		return v


class AccountResponse(BaseModel):
	"""账户响应模型"""

	id: str = Field(..., description="账户ID")
	account_number: str = Field(..., description="账户号")
	account_name: str = Field(..., description="账户名称")
	user_id: str = Field(..., description="用户ID")
	account_type: str = Field(..., description="账户类型")
	broker: Optional[str] = Field(None, description="券商名称")
	broker_account_id: Optional[str] = Field(None, description="券商账户ID")
	status: str = Field(..., description="账户状态")
	status_reason: Optional[str] = Field(None, description="状态原因")
	total_balance: Decimal = Field(..., description="总资产")
	available_balance: Decimal = Field(..., description="可用资金")
	frozen_balance: Decimal = Field(..., description="冻结资金")
	market_value: Decimal = Field(..., description="持仓市值")
	initial_balance: Decimal = Field(..., description="初始资金")
	credit_line: Optional[Decimal] = Field(None, description="授信额度")
	last_trade_date: Optional[datetime] = Field(None, description="最后交易日")
	created_at: datetime = Field(..., description="创建时间")
	updated_at: datetime = Field(..., description="更新时间")

	model_config = ConfigDict(from_attributes=True)


class AccountBalanceResponse(BaseModel):
	"""账户资金余额响应模型"""

	account_id: str = Field(..., description="账户ID")
	account_number: str = Field(..., description="账户号")
	total_balance: Decimal = Field(..., description="总资产")
	available_balance: Decimal = Field(..., description="可用资金")
	frozen_balance: Decimal = Field(..., description="冻结资金")
	market_value: Decimal = Field(..., description="持仓市值")

	class Config:
		json_encoders = {
			Decimal: lambda d: float(d)
		}


class AccountPositionResponse(BaseModel):
	"""账户持仓响应模型"""

	id: str = Field(..., description="持仓ID")
	ts_code: str = Field(..., description="证券代码")
	volume: int = Field(..., ge=0, description="总持仓量")
	available_volume: int = Field(..., ge=0, description="可用持仓量")
	frozen_volume: int = Field(..., ge=0, description="冻结持仓量")
	cost_price: Decimal = Field(..., ge=0, description="成本价")
	market_value: Decimal = Field(..., ge=0, description="市值")
	last_price: Optional[Decimal] = Field(None, ge=0, description="最新价")
	pnl: Decimal = Field(..., description="浮动盈亏")
	pnl_rate: Decimal = Field(..., description="盈亏率")
	last_update: datetime = Field(..., description="最后更新时间")

	class Config:
		json_encoders = {
			datetime: lambda dt: dt.isoformat(),
			Decimal: lambda d: float(d)
		}


class PositionResponse(BaseModel):
	"""单个持仓详情响应模型"""

	id: str = Field(..., description="持仓ID")
	account_id: str = Field(..., description="账户ID")
	ts_code: str = Field(..., description="证券代码")
	volume: int = Field(..., ge=0, description="总持仓量")
	available_volume: int = Field(..., ge=0, description="可用持仓量")
	frozen_volume: int = Field(..., ge=0, description="冻结持仓量")
	cost_price: Decimal = Field(..., ge=0, description="成本价")
	market_value: Decimal = Field(..., ge=0, description="市值")
	last_price: Optional[Decimal] = Field(None, ge=0, description="最新价")
	pnl: Decimal = Field(..., description="浮动盈亏")
	pnl_rate: Decimal = Field(..., description="盈亏率")
	last_update: datetime = Field(..., description="最后更新时间")

	model_config = ConfigDict(from_attributes=True)


class AccountSummaryResponse(BaseModel):
	"""账户概览响应模型"""

	account: AccountResponse = Field(..., description="账户信息")
	total_positions: int = Field(..., ge=0, description="持仓总数")
	total_market_value: Decimal = Field(..., ge=0, description="总持仓市值")
	total_pnl: Decimal = Field(..., description="总浮动盈亏")

	class Config:
		json_encoders = {
			Decimal: lambda d: float(d)
		}


class AccountFilter(BaseModel):
	"""账户筛选参数模型"""

	user_id: Optional[str] = Field(None, description="用户ID")
	account_type: Optional[str] = Field(None, description="账户类型")
	status: Optional[str] = Field(None, description="账户状态")
	skip: int = Field(0, ge=0, description="跳过记录数")
	limit: int = Field(100, ge=1, le=1000, description="返回记录数")

	@field_validator('account_type')
	def validate_account_type (cls, v):
		if v is not None and v not in ACCOUNT_TYPES:
			raise ValueError(f"账户类型必须是以下之一: {', '.join(ACCOUNT_TYPES)}")
		return v

	@field_validator('status')
	def validate_status (cls, v):
		if v is not None and v not in ACCOUNT_STATUSES:
			raise ValueError(f"账户状态必须是以下之一: {', '.join(ACCOUNT_STATUSES)}")
		return v


class DepositRequest(BaseModel):
	"""存款请求"""
	amount: float = Field(..., gt=0, description="存款金额")


class WithdrawRequest(BaseModel):
	"""取款请求"""
	amount: float = Field(..., gt=0, description="取款金额")


from utils.api_utils.pagination_config import PaginationParams


class AccountListRequest(PaginationParams):
	"""账户列表请求"""
	user_id: Optional[str] = Field(default=None, description="用户ID筛选")
	account_type: Optional[str] = Field(default=None, description="账户类型筛选")
	status: Optional[str] = Field(default=None, description="账户状态筛选")


class AccountListResponse(BaseModel):
	"""账户列表响应"""
	success: bool = Field(default=True)
	data: List[Dict[str, Any]] = Field(default_factory=list)
	pagination: Dict[str, int] = Field(default_factory=dict)


class AccountDetailResponse(BaseModel):
	"""账户详情响应"""
	success: bool = Field(default=True)
	data: Optional[Dict[str, Any]] = Field(default=None)


class PositionListRequest(PaginationParams):
	"""持仓列表请求"""


class PositionDetailResponse(PositionResponse):
	"""单个持仓详情响应模型"""
	pass


class PositionListResponse(BaseModel):
	"""持仓列表响应"""
	success: bool = Field(default=True)
	data: List[Dict[str, Any]] = Field(default_factory=list)
	pagination: Dict[str, int] = Field(default_factory=dict)