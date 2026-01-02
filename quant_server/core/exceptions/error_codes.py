#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
错误码定义

定义系统的错误码体系，包括：
1. 通用错误码 (1000-1999)
2. 业务错误码 (2000-3999)
3. 数据错误码 (4000-4999)
4. 系统错误码 (5000-6999)
5. 外部服务错误码 (7000-7999)
"""

from enum import Enum
from typing import Dict


class ErrorCode(str, Enum):
	"""
	错误码枚举

	采用分层结构：
	1xxx: 通用错误
	2xxx: 业务错误
	3xxx: 数据错误
	4xxx: 系统错误
	5xxx: 外部服务错误
	6xxx: 认证授权错误
	7xxx: 交易错误
	"""

	# ==================== 通用错误 (1000-1999) ====================
	SUCCESS = "0000"
	INTERNAL_ERROR = "1000"
	VALIDATION_ERROR = "1001"
	CONFIGURATION_ERROR = "1002"
	SERVICE_ERROR = "1003"
	NOT_IMPLEMENTED = "1004"
	DEPRECATED = "1005"

	# ==================== 业务错误 (2000-2999) ====================
	BUSINESS_ERROR = "2000"
	STRATEGY_ERROR = "2001"
	ANALYSIS_ERROR = "2002"
	BACKTEST_ERROR = "2003"
	RISK_ERROR = "2004"
	ACCOUNT_ERROR = "2005"
	PORTFOLIO_ERROR = "2006"
	ORDER_ERROR = "2007"
	POSITION_NOT_FOUND = "2008"
	INSUFFICIENT_BALANCE = "2009"

	# ==================== 数据错误 (3000-3999) ====================
	DATA_ERROR = "3000"
	DATA_NOT_FOUND = "3001"
	DATA_VALIDATION_ERROR = "3002"
	DATA_SYNC_ERROR = "3003"
	DATA_QUALITY_ERROR = "3004"
	INSUFFICIENT_DATA = "3005"
	DUPLICATE_DATA = "3006"
	DATA_FORMAT_ERROR = "3007"

	# ==================== 系统错误 (4000-4999) ====================
	SYSTEM_ERROR = "4000"
	DATABASE_ERROR = "4001"
	CACHE_ERROR = "4002"
	EXTERNAL_SERVICE_ERROR = "4003"
	NETWORK_ERROR = "4004"
	TIMEOUT_ERROR = "4005"
	RESOURCE_EXHAUSTED = "4006"
	FILE_SYSTEM_ERROR = "4007"
	MEMORY_ERROR = "4008"

	# ==================== 认证授权错误 (5000-5999) ====================
	AUTHENTICATION_ERROR = "5000"
	AUTHORIZATION_ERROR = "5001"
	TOKEN_ERROR = "5002"
	PERMISSION_ERROR = "5003"
	RATE_LIMIT_ERROR = "5004"
	SESSION_EXPIRED = "5005"
	INVALID_CREDENTIALS = "5006"
	ACCESS_DENIED = "5007"

	# ==================== 交易错误 (6000-6999) ====================
	TRADE_ERROR = "6000"
	ORDER_REJECTED = "6001"
	ORDER_TIMEOUT = "6002"
	EXECUTION_ERROR = "6003"
	MARKET_CLOSED = "6004"
	INVALID_PRICE = "6005"
	INSUFFICIENT_VOLUME = "6006"
	TRADE_LIMIT_EXCEEDED = "6007"
	SUSPENDED_STOCK = "6008"
	BLACKLISTED_STOCK = "6009"


# 错误消息映射
ERROR_MESSAGES: Dict[str, str] = {
	# 通用错误
	ErrorCode.SUCCESS: "成功",
	ErrorCode.INTERNAL_ERROR: "内部服务器错误",
	ErrorCode.VALIDATION_ERROR: "数据验证失败",
	ErrorCode.CONFIGURATION_ERROR: "配置错误",
	ErrorCode.SERVICE_ERROR: "服务错误",
	ErrorCode.NOT_IMPLEMENTED: "功能未实现",
	ErrorCode.DEPRECATED: "功能已废弃",

	# 业务错误
	ErrorCode.BUSINESS_ERROR: "业务逻辑错误",
	ErrorCode.STRATEGY_ERROR: "策略执行错误",
	ErrorCode.ANALYSIS_ERROR: "分析处理错误",
	ErrorCode.BACKTEST_ERROR: "回测执行错误",
	ErrorCode.RISK_ERROR: "风控处理错误",
	ErrorCode.ACCOUNT_ERROR: "账户操作错误",
	ErrorCode.PORTFOLIO_ERROR: "投资组合错误",
	ErrorCode.ORDER_ERROR: "订单处理错误",
	ErrorCode.POSITION_NOT_FOUND: "持仓不存在",
	ErrorCode.INSUFFICIENT_BALANCE: "余额不足",

	# 数据错误
	ErrorCode.DATA_ERROR: "数据错误",
	ErrorCode.DATA_NOT_FOUND: "数据不存在",
	ErrorCode.DATA_VALIDATION_ERROR: "数据验证失败",
	ErrorCode.DATA_SYNC_ERROR: "数据同步失败",
	ErrorCode.DATA_QUALITY_ERROR: "数据质量异常",
	ErrorCode.INSUFFICIENT_DATA: "数据不足",
	ErrorCode.DUPLICATE_DATA: "数据重复",
	ErrorCode.DATA_FORMAT_ERROR: "数据格式错误",

	# 系统错误
	ErrorCode.SYSTEM_ERROR: "系统错误",
	ErrorCode.DATABASE_ERROR: "数据库错误",
	ErrorCode.CACHE_ERROR: "缓存错误",
	ErrorCode.EXTERNAL_SERVICE_ERROR: "外部服务错误",
	ErrorCode.NETWORK_ERROR: "网络错误",
	ErrorCode.TIMEOUT_ERROR: "请求超时",
	ErrorCode.RESOURCE_EXHAUSTED: "资源耗尽",
	ErrorCode.FILE_SYSTEM_ERROR: "文件系统错误",
	ErrorCode.MEMORY_ERROR: "内存错误",

	# 认证授权错误
	ErrorCode.AUTHENTICATION_ERROR: "认证失败",
	ErrorCode.AUTHORIZATION_ERROR: "授权失败",
	ErrorCode.TOKEN_ERROR: "令牌错误",
	ErrorCode.PERMISSION_ERROR: "权限不足",
	ErrorCode.RATE_LIMIT_ERROR: "请求频率过高",
	ErrorCode.SESSION_EXPIRED: "会话已过期",
	ErrorCode.INVALID_CREDENTIALS: "无效的凭证",
	ErrorCode.ACCESS_DENIED: "访问被拒绝",

	# 交易错误
	ErrorCode.TRADE_ERROR: "交易错误",
	ErrorCode.ORDER_REJECTED: "订单被拒绝",
	ErrorCode.ORDER_TIMEOUT: "订单超时",
	ErrorCode.EXECUTION_ERROR: "执行错误",
	ErrorCode.MARKET_CLOSED: "市场已收盘",
	ErrorCode.INVALID_PRICE: "无效的价格",
	ErrorCode.INSUFFICIENT_VOLUME: "数量不足",
	ErrorCode.TRADE_LIMIT_EXCEEDED: "交易限制超限",
	ErrorCode.SUSPENDED_STOCK: "股票已停牌",
	ErrorCode.BLACKLISTED_STOCK: "股票在黑名单中",
}


def get_error_message (error_code: str) -> str:
	"""
	根据错误码获取错误消息

	Args:
		error_code: 错误码

	Returns:
		错误消息，如果未找到则返回通用错误消息
	"""
	return ERROR_MESSAGES.get(error_code, "未知错误")


def get_error_details (error_code: str, **kwargs) -> Dict[str, str]:
	"""
	获取错误的详细信息

	Args:
		error_code: 错误码
		**kwargs: 额外参数

	Returns:
		错误详情字典
	"""
	message = get_error_message(error_code)
	details = {
		"code": error_code,
		"message": message,
		"type": _get_error_type(error_code),
		"severity": _get_error_severity(error_code),
		"timestamp": _get_timestamp(),
		**kwargs
	}
	return details


def _get_error_type (error_code: str) -> str:
	"""根据错误码获取错误类型"""
	code_prefix = error_code[0]
	type_mapping = {
		'1': 'general',
		'2': 'business',
		'3': 'events',
		'4': 'events',
		'5': 'auth',
		'6': 'events'
	}
	return type_mapping.get(code_prefix, 'unknown')


def _get_error_severity (error_code: str) -> str:
	"""根据错误码获取严重程度"""
	# 可以根据具体错误码定义不同的严重程度
	critical_codes = {'4006', '5007', '6009'}  # 资源耗尽、访问被拒绝、黑名单股票
	warning_codes = {'1001', '3006', '5004'}  # 验证错误、数据重复、频率限制

	if error_code in critical_codes:
		return 'critical'
	elif error_code in warning_codes:
		return 'warning'
	else:
		return 'error'


def _get_timestamp () -> str:
	"""获取当前时间戳"""
	from datetime import datetime
	return datetime.now().isoformat()