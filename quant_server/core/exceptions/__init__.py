# quant_server/core/exceptions/__init__.py
"""
异常模块统一导出
包含所有异常类的导入和导出，方便使用
"""

from .base import (
	BaseException,
	ValidationException,
)

from .types import (
	ErrorSeverity as ExceptionSeverity,
)

from .types import (
	ErrorSeverity,
	ErrorLevel,
)

from .business_exceptions import (
	BusinessException,
)

from .system_exceptions import (
	SystemException,
)

from .error_codes import (
	ErrorCode,
)

from .security_exceptions import (
	SecurityErrorCode,
)

from .business_exceptions import (
	DataException,
	StrategyException,
	TradeException,
	AccountException,
	AnalysisException,
	BacktestException
)

from .validation_exceptions import (
	ValidationError,
	FieldValidationError,
	SchemaValidationError,
	ParameterValidationError,
)

from .security_exceptions import (
	# 安全异常基类
	SecurityException,

	# 加密异常
	EncryptionException,
	EncryptionError,
	DecryptionError,
	InvalidKeyError,
	SignatureError,

	# JWT异常
	JWTException,
	TokenExpiredError,
	InvalidTokenError,
	TokenCreationError,

	# 密码异常
	PasswordException,
	PasswordHashError,
	PasswordValidationError,
	WeakPasswordError,

	# 权限异常
	PermissionException,
	PermissionDeniedError,
	RoleNotFoundError,
	PermissionNotFoundError,

	# 认证异常
	AuthenticationException,
	AuthenticationFailedError,
	InvalidCredentialsError,
	AccountLockedError,
	AccountDisabledError,
	TooManyAttemptsError,

	# 授权异常
	AuthorizationException,
	AccessDeniedError,
	InsufficientPrivilegesError,

	# 审计异常
	AuditException,
	AuditLogError,

	# 安全配置异常
	SecurityConfigException,
	InvalidSecurityConfigError,
	MissingSecurityConfigError,

	# 异常工厂函数
	create_security_exception
)

from .handlers import (
	ExceptionHandler
)

from .middleware import (
	ExceptionMiddleware,
)

# 事件异常导入
from .event_exceptions import (
	# 事件异常基类
	EventException,

	# 事件引擎异常
	EventEngineException,
	EventEngineNotInitializedError,
	EventEngineAlreadyRunningError,
	EventEngineStoppedError,
	EventEngineTimeoutError,

	# 事件定义异常
	EventDefinitionException,
	InvalidEventTypeError,
	EventClassNotFoundError,
	EventValidationError,

	# 事件发布异常
	EventPublishException,
	EventQueueFullError,
	EventRateLimitExceededError,
	EventSerializationError,

	# 事件订阅异常
	EventSubscribeException,
	DuplicateSubscriptionError,
	HandlerNotFoundException,
	SubscriptionLimitExceededError,

	# 事件处理异常
	EventHandlerException,
	HandlerExecutionError,
	HandlerTimeoutError,
	HandlerRetryExhaustedError,

	# 事件路由异常
	EventRoutingException,
	EventRouteNotFoundError,
	CircularRoutingError,

	# 事件总线异常
	EventBusException,
	EventBusConnectionError,
	EventBusDisconnectedError,

	# 工厂函数和辅助函数
	create_event_exception,
	is_event_exception,
	extract_event_exception_info,
	should_retry_event_exception,
	get_event_exception_retry_delay,
)

# 异常类别映射
EXCEPTION_CATEGORIES = {
	'system': SystemException,
	'business': BusinessException,
	'validation': ValidationException,
	'security': SecurityException,
	'event': EventException,  # 添加事件异常类别
	'api': BusinessException,
	'strategy': StrategyException,
	'trade': TradeException,
	'data': DataException,
	'account': AccountException,
	'analysis': AnalysisException,
	'backtest': BacktestException,
}

__all__ = [
	# 基础异常
	'BaseException',
	'BusinessException',
	'SystemException',
	'ValidationException',
	'ErrorLevel',
	'ErrorSeverity',
	'ExceptionSeverity',

	# 错误码
	'ErrorCode',
	'SecurityErrorCode',

	# 业务异常
	'DataException',
	'StrategyException',
	'TradeException',
	'AccountException',
	'AnalysisException',
	'BacktestException',

	# 验证异常
	'ValidationError',
	'FieldValidationError',
	'SchemaValidationError',
	'ParameterValidationError',

	# 安全异常
	'SecurityException',
	'EncryptionException',
	'EncryptionError',
	'DecryptionError',
	'InvalidKeyError',
	'SignatureError',
	'JWTException',
	'TokenExpiredError',
	'InvalidTokenError',
	'TokenCreationError',
	'PasswordException',
	'PasswordHashError',
	'PasswordValidationError',
	'WeakPasswordError',
	'PermissionException',
	'PermissionDeniedError',
	'RoleNotFoundError',
	'PermissionNotFoundError',
	'AuthenticationException',
	'AuthenticationFailedError',
	'InvalidCredentialsError',
	'AccountLockedError',
	'AccountDisabledError',
	'TooManyAttemptsError',
	'AuthorizationException',
	'AccessDeniedError',
	'InsufficientPrivilegesError',
	'AuditException',
	'AuditLogError',
	'SecurityConfigException',
	'InvalidSecurityConfigError',
	'MissingSecurityConfigError',
	'create_security_exception',

	# 事件异常（新增）
	'EventException',
	'EventEngineException',
	'EventEngineNotInitializedError',
	'EventEngineAlreadyRunningError',
	'EventEngineStoppedError',
	'EventEngineTimeoutError',
	'EventDefinitionException',
	'InvalidEventTypeError',
	'EventClassNotFoundError',
	'EventValidationError',
	'EventPublishException',
	'EventQueueFullError',
	'EventRateLimitExceededError',
	'EventSerializationError',
	'EventSubscribeException',
	'DuplicateSubscriptionError',
	'HandlerNotFoundException',
	'SubscriptionLimitExceededError',
	'EventHandlerException',
	'HandlerExecutionError',
	'HandlerTimeoutError',
	'HandlerRetryExhaustedError',
	'EventRoutingException',
	'EventRouteNotFoundError',
	'CircularRoutingError',
	'EventBusException',
	'EventBusConnectionError',
	'EventBusDisconnectedError',
	'create_event_exception',
	'is_event_exception',
	'extract_event_exception_info',
	'should_retry_event_exception',
	'get_event_exception_retry_delay',

	# 处理器和中间件
	'ExceptionHandler',
	'ExceptionMiddleware',

	# 映射表
	'EXCEPTION_CATEGORIES',
]

__version__ = '1.0.0'
__author__ = 'Quant System Team'
__description__ = '量化交易系统异常处理模块'