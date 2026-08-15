# quant_server/core/exceptions/__init__.py
"""
异常模块统一导出
包含所有异常类的导入和导出，方便使用
"""

from .base import (
	QuantBaseException,
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
    DataNotFoundException,
    StrategyException,
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
)

from .handlers import (
	ExceptionHandler
)

from .middleware import (
	ExceptionMiddleware,
)

# 异常类别映射
EXCEPTION_CATEGORIES = {
	'system': SystemException,
	'business': BusinessException,
	'validation': ValidationException,
	'security': SecurityException,
	'api': BusinessException,
	'strategy': StrategyException,
}

__all__ = [
	# 基础异常
	'QuantBaseException',
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
	'StrategyException',
	'DataNotFoundException',

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

	# 处理器和中间件
	'ExceptionHandler',
	'ExceptionMiddleware',

	# 映射表
	'EXCEPTION_CATEGORIES',
]

__version__ = '1.0.0'
__author__ = 'Quant System Team'
__description__ = '量化交易系统异常处理模块'
