# quant_server/core/exceptions/error_codes.py
# !/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
错误码定义

定义系统的错误码体系，按照混合架构设计进行分类：
1. 通用错误码 (1000-1999)
2. 业务错误码 (2000-3999)
3. 数据错误码 (4000-4999)
4. 系统错误码 (5000-6999)
5. 外部服务错误码 (7000-7999)
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime


class ErrorCode(str, Enum):
	"""
	错误码枚举

	采用分层结构，与混合架构设计保持一致：
	0xxx: 成功代码
	1xxx: 通用错误
	2xxx: 业务错误
	3xxx: 数据错误
	4xxx: 系统错误
	5xxx: 认证授权错误
	6xxx: 交易错误
	7xxx: 外部服务错误
	"""

	# ==================== 成功代码 (0000-0999) ====================
	SUCCESS = "0000"
	CREATED = "0001"
	ACCEPTED = "0002"
	NO_CONTENT = "0003"
	PARTIAL_CONTENT = "0004"

	# ==================== 通用错误 (1000-1999) ====================
	INTERNAL_ERROR = "1000"
	VALIDATION_ERROR = "1001"
	CONFIGURATION_ERROR = "1002"
	SERVICE_ERROR = "1003"
	NOT_IMPLEMENTED = "1004"
	DEPRECATED = "1005"
	NOT_FOUND = "1006"
	CONFLICT = "1007"
	UNPROCESSABLE_ENTITY = "1008"
	TOO_MANY_REQUESTS = "1009"
	REQUEST_TIMEOUT = "1010"

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
	TRADE_ERROR = "2010"
	EXECUTION_ERROR = "2011"
	SETTLEMENT_ERROR = "2012"
	RECONCILIATION_ERROR = "2013"

	# ==================== 数据错误 (3000-3999) ====================
	DATA_ERROR = "3000"
	DATA_NOT_FOUND = "3001"
	DATA_VALIDATION_ERROR = "3002"
	DATA_SYNC_ERROR = "3003"
	DATA_QUALITY_ERROR = "3004"
	INSUFFICIENT_DATA = "3005"
	DUPLICATE_DATA = "3006"
	DATA_FORMAT_ERROR = "3007"
	DATA_SOURCE_ERROR = "3008"
	DATA_TRANSFORMATION_ERROR = "3009"
	DATA_PARSING_ERROR = "3010"
	DATA_ENCODING_ERROR = "3011"

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
	PROCESS_ERROR = "4009"
	THREAD_ERROR = "4010"
	CONCURRENCY_ERROR = "4011"
	DEADLOCK_ERROR = "4012"
	CIRCUIT_BREAKER_OPEN = "4013"

	# ==================== 认证授权错误 (5000-5999) ====================
	# 通用安全错误
	SECURITY_ERROR = "5000"
	SECURITY_CONFIG_ERROR = "5001"

	# 加密错误 (5100-5199)
	ENCRYPTION_ERROR = "5100"
	ENCRYPTION_FAILED = "5101"
	DECRYPTION_FAILED = "5102"
	INVALID_KEY = "5103"
	SIGNATURE_ERROR = "5104"

	# JWT错误 (5200-5299)
	JWT_ERROR = "5200"
	TOKEN_EXPIRED = "5201"
	INVALID_TOKEN = "5202"
	TOKEN_CREATION_FAILED = "5203"
	TOKEN_REFRESH_FAILED = "5204"

	# 密码错误 (5300-5399)
	PASSWORD_ERROR = "5300"
	PASSWORD_HASH_FAILED = "5301"
	PASSWORD_VALIDATION_FAILED = "5302"
	WEAK_PASSWORD = "5303"
	PASSWORD_MISMATCH = "5304"

	# 权限错误 (5400-5499)
	PERMISSION_ERROR = "5400"
	PERMISSION_DENIED = "5401"
	ROLE_NOT_FOUND = "5402"
	PERMISSION_NOT_FOUND = "5403"
	INSUFFICIENT_PRIVILEGES = "5404"
	ACCESS_DENIED = "5405"

	# 认证错误 (5500-5599)
	AUTHENTICATION_ERROR = "5500"
	AUTHENTICATION_FAILED = "5501"
	INVALID_CREDENTIALS = "5502"
	ACCOUNT_LOCKED = "5503"
	ACCOUNT_DISABLED = "5504"
	TOO_MANY_ATTEMPTS = "5505"
	SESSION_EXPIRED = "5506"

	# 授权错误 (5600-5699)
	AUTHORIZATION_ERROR = "5600"

	# 审计错误 (5700-5799)
	AUDIT_ERROR = "5700"
	AUDIT_LOG_FAILED = "5701"

	# 安全配置错误 (5800-5899)
	INVALID_SECURITY_CONFIG = "5801"
	MISSING_SECURITY_CONFIG = "5802"

	# 传统认证授权错误（向后兼容）
	AUTHORIZATION_ERROR_OLD = "5001"
	AUTHENTICATION_ERROR_OLD = "5012"
	TOKEN_ERROR_OLD = "5002"
	PERMISSION_ERROR_OLD = "5003"
	RATE_LIMIT_ERROR = "5004"
	SESSION_EXPIRED_OLD = "5005"
	INVALID_CREDENTIALS_OLD = "5006"
	ACCESS_DENIED_OLD = "5007"
	TOKEN_EXPIRED_OLD = "5008"
	TOKEN_INVALID = "5009"
	TOKEN_REVOKED = "5010"
	INSUFFICIENT_PRIVILEGES_OLD = "5011"

	# ==================== 交易错误 (6000-6999) ====================
	TRADE_REJECTED = "6000"
	ORDER_REJECTED = "6001"
	ORDER_TIMEOUT = "6002"
	EXECUTION_REJECTED = "6003"
	MARKET_CLOSED = "6004"
	INVALID_PRICE = "6005"
	INSUFFICIENT_VOLUME = "6006"
	TRADE_LIMIT_EXCEEDED = "6007"
	SUSPENDED_STOCK = "6008"
	BLACKLISTED_STOCK = "6009"
	RISK_CONTROL_REJECTED = "6010"
	COMPLIANCE_REJECTED = "6011"
	BROKER_REJECTED = "6012"
	EXCHANGE_REJECTED = "6013"
	POSITION_LIMIT_EXCEEDED = "6014"
	MARGIN_CALL = "6015"

	# ==================== 外部服务错误 (7000-7999) ====================
	EXTERNAL_API_ERROR = "7000"
	TUSHARE_ERROR = "7001"
	BAOSTOCK_ERROR = "7002"
	SINA_ERROR = "7003"
	EASTMONEY_ERROR = "7004"
	BROKER_API_ERROR = "7005"
	EXCHANGE_API_ERROR = "7006"
	MARKET_DATA_ERROR = "7007"
	NEWS_API_ERROR = "7008"
	WEATHER_API_ERROR = "7009"
	EMAIL_SERVICE_ERROR = "7010"
	SMS_SERVICE_ERROR = "7011"
	PUSH_SERVICE_ERROR = "7012"

	# 事件相关错误码（新增）
	EVENT_ERROR = "EVENT_0000"
	EVENT_ENGINE_ERROR = "EVENT_1000"
	EVENT_DEFINITION_ERROR = "EVENT_1001"
	EVENT_PUBLISH_ERROR = "EVENT_2000"
	EVENT_SUBSCRIBE_ERROR = "EVENT_3000"
	EVENT_HANDLER_ERROR = "EVENT_4000"
	EVENT_ROUTING_ERROR = "EVENT_5000"
	EVENT_BUS_ERROR = "EVENT_6000"


# 错误消息映射
ERROR_MESSAGES: Dict[str, str] = {
	# 成功代码
	ErrorCode.SUCCESS: "操作成功",
	ErrorCode.CREATED: "资源创建成功",
	ErrorCode.ACCEPTED: "请求已接受",
	ErrorCode.NO_CONTENT: "操作成功，无返回内容",
	ErrorCode.PARTIAL_CONTENT: "部分内容返回",

	# 通用错误
	ErrorCode.INTERNAL_ERROR: "内部服务器错误",
	ErrorCode.VALIDATION_ERROR: "数据验证失败",
	ErrorCode.CONFIGURATION_ERROR: "配置错误",
	ErrorCode.SERVICE_ERROR: "服务错误",
	ErrorCode.NOT_IMPLEMENTED: "功能未实现",
	ErrorCode.DEPRECATED: "功能已废弃",
	ErrorCode.NOT_FOUND: "资源未找到",
	ErrorCode.CONFLICT: "资源冲突",
	ErrorCode.UNPROCESSABLE_ENTITY: "请求格式正确，但语义错误",
	ErrorCode.TOO_MANY_REQUESTS: "请求过于频繁",
	ErrorCode.REQUEST_TIMEOUT: "请求超时",

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
	ErrorCode.TRADE_ERROR: "交易错误",
	ErrorCode.EXECUTION_ERROR: "执行错误",
	ErrorCode.SETTLEMENT_ERROR: "结算错误",
	ErrorCode.RECONCILIATION_ERROR: "对账错误",

	# 数据错误
	ErrorCode.DATA_ERROR: "数据错误",
	ErrorCode.DATA_NOT_FOUND: "数据不存在",
	ErrorCode.DATA_VALIDATION_ERROR: "数据验证失败",
	ErrorCode.DATA_SYNC_ERROR: "数据同步失败",
	ErrorCode.DATA_QUALITY_ERROR: "数据质量异常",
	ErrorCode.INSUFFICIENT_DATA: "数据不足",
	ErrorCode.DUPLICATE_DATA: "数据重复",
	ErrorCode.DATA_FORMAT_ERROR: "数据格式错误",
	ErrorCode.DATA_SOURCE_ERROR: "数据源错误",
	ErrorCode.DATA_TRANSFORMATION_ERROR: "数据转换错误",
	ErrorCode.DATA_PARSING_ERROR: "数据解析错误",
	ErrorCode.DATA_ENCODING_ERROR: "数据编码错误",

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
	ErrorCode.PROCESS_ERROR: "进程错误",
	ErrorCode.THREAD_ERROR: "线程错误",
	ErrorCode.CONCURRENCY_ERROR: "并发错误",
	ErrorCode.DEADLOCK_ERROR: "死锁错误",
	ErrorCode.CIRCUIT_BREAKER_OPEN: "熔断器已打开",

	# 认证授权错误 - 新增安全相关
	ErrorCode.SECURITY_ERROR: "安全错误",
	ErrorCode.SECURITY_CONFIG_ERROR: "安全配置错误",
	ErrorCode.ENCRYPTION_ERROR: "加密错误",
	ErrorCode.ENCRYPTION_FAILED: "加密失败",
	ErrorCode.DECRYPTION_FAILED: "解密失败",
	ErrorCode.INVALID_KEY: "无效的密钥",
	ErrorCode.SIGNATURE_ERROR: "签名错误",
	ErrorCode.JWT_ERROR: "JWT错误",
	ErrorCode.TOKEN_EXPIRED: "令牌已过期",
	ErrorCode.INVALID_TOKEN: "无效的令牌",
	ErrorCode.TOKEN_CREATION_FAILED: "令牌创建失败",
	ErrorCode.TOKEN_REFRESH_FAILED: "令牌刷新失败",
	ErrorCode.PASSWORD_ERROR: "密码错误",
	ErrorCode.PASSWORD_HASH_FAILED: "密码哈希失败",
	ErrorCode.PASSWORD_VALIDATION_FAILED: "密码验证失败",
	ErrorCode.WEAK_PASSWORD: "密码强度不足",
	ErrorCode.PASSWORD_MISMATCH: "密码不匹配",
	ErrorCode.PERMISSION_ERROR: "权限错误",
	ErrorCode.PERMISSION_DENIED: "权限不足",
	ErrorCode.ROLE_NOT_FOUND: "角色不存在",
	ErrorCode.PERMISSION_NOT_FOUND: "权限不存在",
	ErrorCode.INSUFFICIENT_PRIVILEGES: "权限不足",
	ErrorCode.ACCESS_DENIED: "访问被拒绝",
	ErrorCode.AUTHENTICATION_ERROR: "认证错误",
	ErrorCode.AUTHENTICATION_FAILED: "认证失败",
	ErrorCode.INVALID_CREDENTIALS: "无效的用户名或密码",
	ErrorCode.ACCOUNT_LOCKED: "账户已被锁定",
	ErrorCode.ACCOUNT_DISABLED: "账户已被禁用",
	ErrorCode.TOO_MANY_ATTEMPTS: "尝试次数过多",
	ErrorCode.SESSION_EXPIRED: "会话已过期",
	ErrorCode.AUTHORIZATION_ERROR: "授权错误",
	ErrorCode.AUDIT_ERROR: "审计错误",
	ErrorCode.AUDIT_LOG_FAILED: "审计日志记录失败",
	ErrorCode.INVALID_SECURITY_CONFIG: "无效的安全配置",
	ErrorCode.MISSING_SECURITY_CONFIG: "缺少必要的安全配置",

	# 传统认证授权错误消息（向后兼容）
	ErrorCode.AUTHORIZATION_ERROR_OLD: "授权失败",
	ErrorCode.TOKEN_ERROR_OLD: "令牌错误",
	ErrorCode.PERMISSION_ERROR_OLD: "权限不足",
	ErrorCode.RATE_LIMIT_ERROR: "请求频率过高",
	ErrorCode.SESSION_EXPIRED_OLD: "会话已过期",
	ErrorCode.INVALID_CREDENTIALS_OLD: "无效的凭证",
	ErrorCode.ACCESS_DENIED_OLD: "访问被拒绝",
	ErrorCode.TOKEN_EXPIRED_OLD: "令牌已过期",
	ErrorCode.TOKEN_INVALID: "令牌无效",
	ErrorCode.TOKEN_REVOKED: "令牌已撤销",
	ErrorCode.INSUFFICIENT_PRIVILEGES_OLD: "权限不足",

	# 交易错误
	ErrorCode.TRADE_REJECTED: "交易被拒绝",
	ErrorCode.ORDER_REJECTED: "订单被拒绝",
	ErrorCode.ORDER_TIMEOUT: "订单超时",
	ErrorCode.EXECUTION_REJECTED: "执行被拒绝",
	ErrorCode.MARKET_CLOSED: "市场已收盘",
	ErrorCode.INVALID_PRICE: "无效的价格",
	ErrorCode.INSUFFICIENT_VOLUME: "数量不足",
	ErrorCode.TRADE_LIMIT_EXCEEDED: "交易限制超限",
	ErrorCode.SUSPENDED_STOCK: "股票已停牌",
	ErrorCode.BLACKLISTED_STOCK: "股票在黑名单中",
	ErrorCode.RISK_CONTROL_REJECTED: "风控拒绝",
	ErrorCode.COMPLIANCE_REJECTED: "合规拒绝",
	ErrorCode.BROKER_REJECTED: "券商拒绝",
	ErrorCode.EXCHANGE_REJECTED: "交易所拒绝",
	ErrorCode.POSITION_LIMIT_EXCEEDED: "持仓限制超限",
	ErrorCode.MARGIN_CALL: "保证金催缴",

	# 外部服务错误
	ErrorCode.EXTERNAL_API_ERROR: "外部API错误",
	ErrorCode.TUSHARE_ERROR: "Tushare数据源错误",
	ErrorCode.BAOSTOCK_ERROR: "Baostock数据源错误",
	ErrorCode.SINA_ERROR: "新浪数据源错误",
	ErrorCode.EASTMONEY_ERROR: "东方财富数据源错误",
	ErrorCode.BROKER_API_ERROR: "券商API错误",
	ErrorCode.EXCHANGE_API_ERROR: "交易所API错误",
	ErrorCode.MARKET_DATA_ERROR: "市场数据错误",
	ErrorCode.NEWS_API_ERROR: "新闻API错误",
	ErrorCode.WEATHER_API_ERROR: "天气API错误",
	ErrorCode.EMAIL_SERVICE_ERROR: "邮件服务错误",
	ErrorCode.SMS_SERVICE_ERROR: "短信服务错误",
	ErrorCode.PUSH_SERVICE_ERROR: "推送服务错误",

	# 事件相关错误消息（新增）
	ErrorCode.EVENT_ERROR: "事件处理错误",
	ErrorCode.EVENT_ENGINE_ERROR: "事件引擎错误",
	ErrorCode.EVENT_DEFINITION_ERROR: "事件定义错误",
	ErrorCode.EVENT_PUBLISH_ERROR: "事件发布错误",
	ErrorCode.EVENT_SUBSCRIBE_ERROR: "事件订阅错误",
	ErrorCode.EVENT_HANDLER_ERROR: "事件处理错误",
	ErrorCode.EVENT_ROUTING_ERROR: "事件路由错误",
	ErrorCode.EVENT_BUS_ERROR: "事件总线错误",
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


def get_error_details (error_code: str, **kwargs) -> Dict[str, Any]:
	"""
	获取错误的详细信息

	Args:
		error_code: 错误码
		**kwargs: 额外参数

	Returns:
		错误详情字典
	"""
	# 导入类型定义（延迟导入，避免循环依赖）
	try:
		from .types import ErrorSeverity
	except ImportError:
		# 定义简化的严重程度枚举
		class ErrorSeverity:
			DEBUG = "debug"
			INFO = "info"
			WARNING = "warning"
			ERROR = "error"
			CRITICAL = "critical"

	message = get_error_message(error_code)

	# 根据错误码前缀确定错误类型
	code_prefix = error_code[0] if error_code and error_code[0].isdigit() else 'E'
	type_mapping = {
		'0': 'success',
		'1': 'general',
		'2': 'business',
		'3': 'data',
		'4': 'system',
		'5': 'security',  # 将5xxx改为安全错误类型
		'6': 'trade',
		'7': 'external',
		'E': 'event'  # 事件错误类型
	}

	error_type = type_mapping.get(code_prefix, 'unknown')

	# 根据错误码确定严重程度
	severity_map = {
		'0': ErrorSeverity.INFO,
		'1': ErrorSeverity.ERROR,
		'2': ErrorSeverity.ERROR,
		'3': ErrorSeverity.WARNING,
		'4': ErrorSeverity.ERROR,
		'5': ErrorSeverity.WARNING,  # 安全错误通常为警告级别
		'6': ErrorSeverity.ERROR,
		'7': ErrorSeverity.ERROR,
		'E': ErrorSeverity.ERROR  # 事件错误通常为错误级别
	}

	severity = severity_map.get(code_prefix, ErrorSeverity.ERROR)

	# 对于特定的安全错误码，调整严重程度
	if error_code in [
		ErrorCode.SECURITY_ERROR,
		ErrorCode.ENCRYPTION_ERROR,
		ErrorCode.JWT_ERROR,
		ErrorCode.AUTHENTICATION_ERROR,
		ErrorCode.AUTHORIZATION_ERROR,
		ErrorCode.AUDIT_ERROR,
	]:
		severity = ErrorSeverity.ERROR

	# 对于权限拒绝等错误，设置为警告级别
	elif error_code in [
		ErrorCode.PERMISSION_DENIED,
		ErrorCode.ACCESS_DENIED,
		ErrorCode.INSUFFICIENT_PRIVILEGES,
		ErrorCode.ACCOUNT_LOCKED,
		ErrorCode.ACCOUNT_DISABLED,
	]:
		severity = ErrorSeverity.WARNING

	# 对于事件错误，调整严重程度
	elif error_code.startswith('EVENT_'):
		# 事件引擎错误通常是严重的
		if error_code == ErrorCode.EVENT_ENGINE_ERROR:
			severity = ErrorSeverity.CRITICAL
		# 事件定义错误通常是警告级别
		elif error_code == ErrorCode.EVENT_DEFINITION_ERROR:
			severity = ErrorSeverity.WARNING
		# 事件处理错误通常是错误级别
		elif error_code == ErrorCode.EVENT_HANDLER_ERROR:
			severity = ErrorSeverity.ERROR
		# 其他事件错误通常是错误级别
		else:
			severity = ErrorSeverity.ERROR

	details = {
		"code": error_code,
		"message": message,
		"type": error_type,
		"severity": severity.value if hasattr(severity, 'value') else severity,
		"timestamp": datetime.now().isoformat(),
		**kwargs
	}

	return details


def is_retryable_error (error_code: str) -> bool:
	"""
	检查错误是否可重试

	Args:
		error_code: 错误码

	Returns:
		是否可重试
	"""
	retryable_codes = {
		ErrorCode.TIMEOUT_ERROR,
		ErrorCode.NETWORK_ERROR,
		ErrorCode.EXTERNAL_SERVICE_ERROR,
		ErrorCode.RATE_LIMIT_ERROR,
		ErrorCode.TOO_MANY_REQUESTS,
		ErrorCode.REQUEST_TIMEOUT,
		ErrorCode.CIRCUIT_BREAKER_OPEN,
		ErrorCode.TOO_MANY_ATTEMPTS,  # 安全错误中的尝试次数过多，可以重试
		ErrorCode.EVENT_BUS_ERROR,    # 事件总线错误可以重试
		ErrorCode.EVENT_ENGINE_ERROR, # 事件引擎错误可以重试
	}

	# 事件错误中的特定错误可以重试
	if error_code.startswith('EVENT_'):
		# 事件发布和订阅错误通常可以重试
		if error_code in [ErrorCode.EVENT_PUBLISH_ERROR, ErrorCode.EVENT_SUBSCRIBE_ERROR]:
			return True
		# 事件处理超时错误可以重试
		if error_code == ErrorCode.EVENT_HANDLER_ERROR:
			return True

	return error_code in retryable_codes


def is_business_error (error_code: str) -> bool:
	"""
	检查是否为业务错误

	Args:
		error_code: 错误码

	Returns:
		是否为业务错误
	"""
	return error_code.startswith('2')


def is_system_error (error_code: str) -> bool:
	"""
	检查是否为系统错误

	Args:
		error_code: 错误码

	Returns:
		是否为系统错误
	"""
	return error_code.startswith('4')  # 只包含4xxx，5xxx现在是安全错误


def is_security_error (error_code: str) -> bool:
	"""
	检查是否为安全错误

	Args:
		error_code: 错误码

	Returns:
		是否为安全错误
	"""
	return error_code.startswith('5')


def is_event_error (error_code: str) -> bool:
	"""
	检查是否为事件错误

	Args:
		error_code: 错误码

	Returns:
		是否为事件错误
	"""
	return error_code.startswith('EVENT_')


def get_http_status_code (error_code: str) -> int:
	"""
	根据错误码获取HTTP状态码

	Args:
		error_code: 错误码

	Returns:
		HTTP状态码
	"""
	status_map = {
		# 通用错误
		ErrorCode.VALIDATION_ERROR: 400,
		ErrorCode.NOT_FOUND: 404,
		ErrorCode.CONFLICT: 409,
		ErrorCode.UNPROCESSABLE_ENTITY: 422,
		ErrorCode.TOO_MANY_REQUESTS: 429,
		ErrorCode.REQUEST_TIMEOUT: 408,

		# 安全错误
		ErrorCode.SECURITY_ERROR: 500,
		ErrorCode.SECURITY_CONFIG_ERROR: 500,
		ErrorCode.ENCRYPTION_ERROR: 500,
		ErrorCode.ENCRYPTION_FAILED: 500,
		ErrorCode.DECRYPTION_FAILED: 500,
		ErrorCode.INVALID_KEY: 400,
		ErrorCode.SIGNATURE_ERROR: 400,
		ErrorCode.JWT_ERROR: 401,
		ErrorCode.TOKEN_EXPIRED: 401,
		ErrorCode.INVALID_TOKEN: 401,
		ErrorCode.TOKEN_CREATION_FAILED: 500,
		ErrorCode.TOKEN_REFRESH_FAILED: 400,
		ErrorCode.PASSWORD_ERROR: 400,
		ErrorCode.PASSWORD_HASH_FAILED: 500,
		ErrorCode.PASSWORD_VALIDATION_FAILED: 400,
		ErrorCode.WEAK_PASSWORD: 400,
		ErrorCode.PASSWORD_MISMATCH: 400,
		ErrorCode.PERMISSION_ERROR: 403,
		ErrorCode.PERMISSION_DENIED: 403,
		ErrorCode.ROLE_NOT_FOUND: 404,
		ErrorCode.PERMISSION_NOT_FOUND: 404,
		ErrorCode.INSUFFICIENT_PRIVILEGES: 403,
		ErrorCode.ACCESS_DENIED: 403,
		ErrorCode.AUTHENTICATION_ERROR: 401,
		ErrorCode.AUTHENTICATION_FAILED: 401,
		ErrorCode.INVALID_CREDENTIALS: 401,
		ErrorCode.ACCOUNT_LOCKED: 403,
		ErrorCode.ACCOUNT_DISABLED: 403,
		ErrorCode.TOO_MANY_ATTEMPTS: 429,
		ErrorCode.SESSION_EXPIRED: 401,
		ErrorCode.AUTHORIZATION_ERROR: 403,
		ErrorCode.AUDIT_ERROR: 500,
		ErrorCode.AUDIT_LOG_FAILED: 500,
		ErrorCode.INVALID_SECURITY_CONFIG: 400,
		ErrorCode.MISSING_SECURITY_CONFIG: 400,

		# 传统认证授权错误
		ErrorCode.AUTHENTICATION_ERROR_OLD: 401,
		ErrorCode.AUTHORIZATION_ERROR_OLD: 403,
		ErrorCode.PERMISSION_ERROR_OLD: 403,
		ErrorCode.RATE_LIMIT_ERROR: 429,
		ErrorCode.SESSION_EXPIRED_OLD: 401,
		ErrorCode.INVALID_CREDENTIALS_OLD: 401,
		ErrorCode.ACCESS_DENIED_OLD: 403,
		ErrorCode.TOKEN_EXPIRED_OLD: 401,
		ErrorCode.TOKEN_INVALID: 401,
		ErrorCode.TOKEN_REVOKED: 401,
		ErrorCode.INSUFFICIENT_PRIVILEGES_OLD: 403,

		# 事件相关错误（新增）
		ErrorCode.EVENT_ERROR: 500,
		ErrorCode.EVENT_ENGINE_ERROR: 503,  # 服务不可用
		ErrorCode.EVENT_DEFINITION_ERROR: 400,  # 错误的请求
		ErrorCode.EVENT_PUBLISH_ERROR: 500,
		ErrorCode.EVENT_SUBSCRIBE_ERROR: 500,
		ErrorCode.EVENT_HANDLER_ERROR: 500,
		ErrorCode.EVENT_ROUTING_ERROR: 500,
		ErrorCode.EVENT_BUS_ERROR: 503,  # 服务不可用

		# 默认500错误
	}

	return status_map.get(error_code, 500)


def get_error_category (error_code: str) -> str:
	"""
	根据错误码获取错误类别

	Args:
		error_code: 错误码

	Returns:
		错误类别
	"""
	code_prefix = error_code[0] if error_code and error_code[0].isdigit() else error_code[:1]
	category_map = {
		'0': 'success',
		'1': 'general',
		'2': 'business',
		'3': 'data',
		'4': 'system',
		'5': 'security',
		'6': 'trade',
		'7': 'external',
		'E': 'event'  # 事件类别
	}

	category = category_map.get(code_prefix, 'unknown')

	# 进一步细分类别
	if category == 'security':
		# 根据子类别进一步分类
		subcode = int(error_code[1:]) if len(error_code) == 4 and error_code[1:].isdigit() else 0

		if 5000 <= subcode <= 5099:
			return 'security_general'
		elif 5100 <= subcode <= 5199:
			return 'security_encryption'
		elif 5200 <= subcode <= 5299:
			return 'security_jwt'
		elif 5300 <= subcode <= 5399:
			return 'security_password'
		elif 5400 <= subcode <= 5499:
			return 'security_permission'
		elif 5500 <= subcode <= 5599:
			return 'security_authentication'
		elif 5600 <= subcode <= 5699:
			return 'security_authorization'
		elif 5700 <= subcode <= 5799:
			return 'security_audit'
		elif 5800 <= subcode <= 5899:
			return 'security_config'
	elif category == 'event':
		# 事件错误的进一步分类
		if error_code == ErrorCode.EVENT_ERROR:
			return 'event_general'
		elif error_code == ErrorCode.EVENT_ENGINE_ERROR:
			return 'event_engine'
		elif error_code == ErrorCode.EVENT_DEFINITION_ERROR:
			return 'event_definition'
		elif error_code == ErrorCode.EVENT_PUBLISH_ERROR:
			return 'event_publish'
		elif error_code == ErrorCode.EVENT_SUBSCRIBE_ERROR:
			return 'event_subscribe'
		elif error_code == ErrorCode.EVENT_HANDLER_ERROR:
			return 'event_handler'
		elif error_code == ErrorCode.EVENT_ROUTING_ERROR:
			return 'event_routing'
		elif error_code == ErrorCode.EVENT_BUS_ERROR:
			return 'event_bus'

	return category


def get_error_codes_by_category (category: str) -> List[str]:
	"""
	根据类别获取错误码列表

	Args:
		category: 错误类别

	Returns:
		错误码列表
	"""
	# 导入ErrorCode枚举的所有值
	error_codes = []

	for code in ErrorCode:
		code_category = get_error_category(code.value)
		if code_category == category:
			error_codes.append(code.value)

	return error_codes


def get_security_error_codes () -> Dict[str, List[str]]:
	"""
	获取所有安全相关错误码，按子类别分组

	Returns:
		按子类别分组的安全错误码字典
	"""
	security_categories = [
		'security_general',
		'security_encryption',
		'security_jwt',
		'security_password',
		'security_permission',
		'security_authentication',
		'security_authorization',
		'security_audit',
		'security_config'
	]

	result = {}

	for category in security_categories:
		codes = get_error_codes_by_category(category)
		if codes:
			result[category] = codes

	return result


def get_event_error_codes () -> Dict[str, List[str]]:
	"""
	获取所有事件相关错误码，按子类别分组

	Returns:
		按子类别分组的事件错误码字典
	"""
	event_categories = [
		'event_general',
		'event_engine',
		'event_definition',
		'event_publish',
		'event_subscribe',
		'event_handler',
		'event_routing',
		'event_bus'
	]

	result = {}

	for category in event_categories:
		codes = get_error_codes_by_category(category)
		if codes:
			result[category] = codes

	return result


# 安全错误码别名映射（兼容新旧错误码）
SECURITY_ERROR_ALIASES = {
	ErrorCode.AUTHORIZATION_ERROR: ErrorCode.AUTHORIZATION_ERROR_OLD,
	ErrorCode.PERMISSION_DENIED: ErrorCode.PERMISSION_ERROR_OLD,
	ErrorCode.INVALID_CREDENTIALS: ErrorCode.INVALID_CREDENTIALS_OLD,
	ErrorCode.ACCESS_DENIED: ErrorCode.ACCESS_DENIED_OLD,
	ErrorCode.TOKEN_EXPIRED: ErrorCode.TOKEN_EXPIRED_OLD,
	ErrorCode.SESSION_EXPIRED: ErrorCode.SESSION_EXPIRED_OLD,
	ErrorCode.INSUFFICIENT_PRIVILEGES: ErrorCode.INSUFFICIENT_PRIVILEGES_OLD,
}


def get_legacy_error_code (error_code: str) -> Optional[str]:
	"""
	获取旧版本错误码（用于向后兼容）

	Args:
		error_code: 新错误码

	Returns:
		对应的旧错误码，如果没有则返回None
	"""
	return SECURITY_ERROR_ALIASES.get(error_code)