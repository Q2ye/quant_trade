"""
账户模块包初始化文件
定义模块公开的接口和版本信息
"""
__version__ = "1.0.0"
__author__ = "Quant System Team"

from modules.account.handlers import AccountHandler
from modules.account.schemas import (
	AccountCreateRequest,
	AccountResponse,
	AccountUpdateRequest,
	AccountBalanceResponse,
	AccountPositionResponse,
	AccountSummaryResponse,
	PositionResponse,
	AccountFilter
)

# 公开的API端点路由
from .handlers import router as account_router

__all__ = [
	# 主要组件
	"AccountHandler",

	# Schemas
	"AccountCreateRequest",
	"AccountResponse",
	"AccountUpdateRequest",
	"AccountBalanceResponse",
	"AccountPositionResponse",
	"AccountSummaryResponse",
	"PositionResponse",
	"AccountFilter",

	# 路由
	"account_router",
]