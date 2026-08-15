# quant_server/core/exceptions/security_exceptions.py
"""
安全相关异常定义
包含加密、认证、授权、密码、令牌等安全相关异常
继承自QuantBaseException和BusinessException
"""

from .base import QuantBaseException
from .error_codes import (
	ErrorCode,
)

# 使用ErrorCode枚举中的安全相关错误码
SecurityErrorCode = ErrorCode
from .types import ErrorType, ErrorSeverity


class SecurityException(QuantBaseException):
	"""安全异常基类"""

	def __init__ (self,
	              message: str = "安全异常",
	              code: ErrorCode = SecurityErrorCode.SECURITY_ERROR,
	              details: dict = None,
	              severity: ErrorSeverity = ErrorSeverity.ERROR):
		"""
		初始化安全异常

		Args:
			message: 异常消息
			code: 错误码
			details: 详细信息
			severity: 错误严重程度
		"""
		super().__init__(message, code, ErrorType.AUTHENTICATION_ERROR, severity, details)

	def to_dict (self) -> dict:
		"""转换为字典格式"""
		data = super().to_dict()
		data['category'] = 'security'
		return data


class EncryptionException(SecurityException):
	"""加密相关异常基类"""

	def __init__ (self,
	              message: str = "加密异常",
	              code: ErrorCode = SecurityErrorCode.ENCRYPTION_ERROR,
	              details: dict = None,
	              severity: ErrorSeverity = ErrorSeverity.ERROR):
		"""
		初始化加密异常

		Args:
			message: 异常消息
			code: 错误码
			details: 详细信息
			severity: 错误严重程度
		"""
		super().__init__(message, code, details, severity)

	def to_dict (self) -> dict:
		"""转换为字典格式"""
		data = super().to_dict()
		data['subcategory'] = 'encryption'
		return data


class EncryptionError(EncryptionException):
	"""加密错误"""

	def __init__ (self,
	              message: str = "加密操作失败",
	              details: dict = None):
		"""
		初始化加密错误

		Args:
			message: 异常消息
			details: 详细信息
		"""
		super().__init__(message, SecurityErrorCode.ENCRYPTION_FAILED, details)


class DecryptionError(EncryptionException):
	"""解密错误"""

	def __init__ (self,
	              message: str = "解密操作失败",
	              details: dict = None):
		"""
		初始化解密错误

		Args:
			message: 异常消息
			details: 详细信息
		"""
		super().__init__(message, SecurityErrorCode.DECRYPTION_FAILED, details)


class InvalidKeyError(EncryptionException):
	"""无效密钥错误"""

	def __init__ (self,
	              message: str = "无效的密钥",
	              details: dict = None):
		"""
		初始化无效密钥错误

		Args:
			message: 异常消息
			details: 详细信息
		"""
		super().__init__(message, SecurityErrorCode.INVALID_KEY, details)


class SignatureError(EncryptionException):
	"""签名错误"""

	def __init__ (self,
	              message: str = "签名操作失败",
	              details: dict = None):
		"""
		初始化签名错误

		Args:
			message: 异常消息
			details: 详细信息
		"""
		super().__init__(message, SecurityErrorCode.SIGNATURE_ERROR, details)


class JWTException(SecurityException):
	"""JWT相关异常基类"""

	def __init__ (self,
	              message: str = "JWT异常",
	              code: ErrorCode = SecurityErrorCode.JWT_ERROR,
	              details: dict = None,
	              severity: ErrorSeverity = ErrorSeverity.ERROR):
		"""
		初始化JWT异常

		Args:
			message: 异常消息
			code: 错误码
			details: 详细信息
			severity: 错误严重程度
		"""
		super().__init__(message, code, details, severity)

	def to_dict (self) -> dict:
		"""转换为字典格式"""
		data = super().to_dict()
		data['subcategory'] = 'jwt'
		return data


class TokenExpiredError(JWTException):
	"""令牌过期错误"""

	def __init__ (self,
	              message: str = "令牌已过期",
	              details: dict = None):
		"""
		初始化令牌过期错误

		Args:
			message: 异常消息
			details: 详细信息
		"""
		super().__init__(message, SecurityErrorCode.TOKEN_EXPIRED, details)


class InvalidTokenError(JWTException):
	"""无效令牌错误"""

	def __init__ (self,
	              message: str = "无效的令牌",
	              details: dict = None):
		"""
		初始化无效令牌错误

		Args:
			message: 异常消息
			details: 详细信息
		"""
		super().__init__(message, SecurityErrorCode.INVALID_TOKEN, details)


class TokenCreationError(JWTException):
	"""令牌创建错误"""

	def __init__ (self,
	              message: str = "令牌创建失败",
	              details: dict = None):
		"""
		初始化令牌创建错误

		Args:
			message: 异常消息
			details: 详细信息
		"""
		super().__init__(message, SecurityErrorCode.TOKEN_CREATION_FAILED, details)


class PasswordException(SecurityException):
	"""密码相关异常基类"""

	def __init__ (self,
	              message: str = "密码异常",
	              code: ErrorCode = SecurityErrorCode.PASSWORD_ERROR,
	              details: dict = None,
	              severity: ErrorSeverity = ErrorSeverity.ERROR):
		"""
		初始化密码异常

		Args:
			message: 异常消息
			code: 错误码
			details: 详细信息
			severity: 错误严重程度
		"""
		super().__init__(message, code, details, severity)

	def to_dict (self) -> dict:
		"""转换为字典格式"""
		data = super().to_dict()
		data['subcategory'] = 'password'
		return data


class PasswordHashError(PasswordException):
	"""密码哈希错误"""

	def __init__ (self,
	              message: str = "密码哈希失败",
	              details: dict = None):
		"""
		初始化密码哈希错误

		Args:
			message: 异常消息
			details: 详细信息
		"""
		super().__init__(message, SecurityErrorCode.PASSWORD_FAILED, details)


class PasswordValidationError(PasswordException):
	"""密码验证错误"""

	def __init__ (self,
	              message: str = "密码验证失败",
	              details: dict = None):
		"""
		初始化密码验证错误

		Args:
			message: 异常消息
			details: 详细信息
		"""
		super().__init__(message, SecurityErrorCode.PASSWORD_VALIDATION_FAILED, details)


class WeakPasswordError(PasswordException):
	"""弱密码错误"""

	def __init__ (self,
	              message: str = "密码强度不足",
	              details: dict = None):
		"""
		初始化弱密码错误

		Args:
			message: 异常消息
			details: 详细信息
		"""
		super().__init__(message, SecurityErrorCode.WEAK_PASSWORD, details, ErrorSeverity.WARNING)


class PermissionException(SecurityException):
	"""权限相关异常基类"""

	def __init__ (self,
	              message: str = "权限异常",
	              code: ErrorCode = SecurityErrorCode.PERMISSION_ERROR,
	              details: dict = None,
	              severity: ErrorSeverity = ErrorSeverity.ERROR):
		"""
		初始化权限异常

		Args:
			message: 异常消息
			code: 错误码
			details: 详细信息
			severity: 错误严重程度
		"""
		super().__init__(message, code, details, severity)

	def to_dict (self) -> dict:
		"""转换为字典格式"""
		data = super().to_dict()
		data['subcategory'] = 'permission'
		return data


class PermissionDeniedError(PermissionException):
	"""权限拒绝错误"""

	def __init__ (self,
	              message: str = "权限不足",
	              details: dict = None,
	              user_id: str = None,
	              resource_type: str = None,
	              action: str = None,
	              resource_id: str = None):
		"""
		初始化权限拒绝错误

		Args:
			message: 异常消息
			details: 详细信息
			user_id: 用户ID
			resource_type: 资源类型
			action: 操作类型
			resource_id: 资源ID
		"""
		if details is None:
			details = {}

		if user_id is not None:
			details['user_id'] = user_id
		if resource_type is not None:
			details['resource_type'] = resource_type
		if action is not None:
			details['action'] = action
		if resource_id is not None:
			details['resource_id'] = resource_id

		super().__init__(message, SecurityErrorCode.PERMISSION_DENIED, details, ErrorSeverity.WARNING)


class RoleNotFoundError(PermissionException):
	"""角色未找到错误"""

	def __init__ (self,
	              message: str = "角色不存在",
	              details: dict = None,
	              role_id: str = None,
	              role_name: str = None):
		"""
		初始化角色未找到错误

		Args:
			message: 异常消息
			details: 详细信息
			role_id: 角色ID
			role_name: 角色名称
		"""
		if details is None:
			details = {}

		if role_id is not None:
			details['role_id'] = role_id
		if role_name is not None:
			details['role_name'] = role_name

		super().__init__(message, SecurityErrorCode.ROLE_NOT_FOUND, details)


class PermissionNotFoundError(PermissionException):
	"""权限未找到错误"""

	def __init__ (self,
	              message: str = "权限不存在",
	              details: dict = None,
	              permission_id: str = None,
	              resource_type: str = None,
	              action: str = None):
		"""
		初始化权限未找到错误

		Args:
			message: 异常消息
			details: 详细信息
			permission_id: 权限ID
			resource_type: 资源类型
			action: 操作类型
		"""
		if details is None:
			details = {}

		if permission_id is not None:
			details['permission_id'] = permission_id
		if resource_type is not None:
			details['resource_type'] = resource_type
		if action is not None:
			details['action'] = action

		super().__init__(message, SecurityErrorCode.PERMISSION_NOT_FOUND, details)


class AuthenticationException(SecurityException):
	"""认证相关异常基类"""

	def __init__ (self,
	              message: str = "认证异常",
	              code: ErrorCode = SecurityErrorCode.AUTHENTICATION_ERROR,
	              details: dict = None,
	              severity: ErrorSeverity = ErrorSeverity.ERROR):
		"""
		初始化认证异常

		Args:
			message: 异常消息
			code: 错误码
			details: 详细信息
			severity: 错误严重程度
		"""
		super().__init__(message, code, details, severity)

	def to_dict (self) -> dict:
		"""转换为字典格式"""
		data = super().to_dict()
		data['subcategory'] = 'authentication'
		return data


class AuthenticationFailedError(AuthenticationException):
	"""认证失败错误"""

	def __init__ (self,
	              message: str = "认证失败",
	              details: dict = None,
	              username: str = None,
	              reason: str = None):
		"""
		初始化认证失败错误

		Args:
			message: 异常消息
			details: 详细信息
			username: 用户名
			reason: 失败原因
		"""
		if details is None:
			details = {}

		if username is not None:
			details['username'] = username
		if reason is not None:
			details['reason'] = reason

		super().__init__(message, SecurityErrorCode.AUTHENTICATION_FAILED, details, ErrorSeverity.WARNING)


class InvalidCredentialsError(AuthenticationException):
	"""无效凭证错误"""

	def __init__ (self,
	              message: str = "无效的用户名或密码",
	              details: dict = None,
	              username: str = None):
		"""
		初始化无效凭证错误

		Args:
			message: 异常消息
			details: 详细信息
			username: 用户名
		"""
		if details is None:
			details = {}

		if username is not None:
			details['username'] = username

		super().__init__(message, SecurityErrorCode.INVALID_CREDENTIALS, details, ErrorSeverity.WARNING)


class AccountLockedError(AuthenticationException):
	"""账户锁定错误"""

	def __init__ (self,
	              message: str = "账户已被锁定",
	              details: dict = None,
	              username: str = None,
	              lock_reason: str = None,
	              lock_until: str = None):
		"""
		初始化账户锁定错误

		Args:
			message: 异常消息
			details: 详细信息
			username: 用户名
			lock_reason: 锁定原因
			lock_until: 锁定到期时间
		"""
		if details is None:
			details = {}

		if username is not None:
			details['username'] = username
		if lock_reason is not None:
			details['lock_reason'] = lock_reason
		if lock_until is not None:
			details['lock_until'] = lock_until

		super().__init__(message, SecurityErrorCode.ACCOUNT_LOCKED, details, ErrorSeverity.WARNING)


class AccountDisabledError(AuthenticationException):
	"""账户禁用错误"""

	def __init__ (self,
	              message: str = "账户已被禁用",
	              details: dict = None,
	              username: str = None,
	              disable_reason: str = None):
		"""
		初始化账户禁用错误

		Args:
			message: 异常消息
			details: 详细信息
			username: 用户名
			disable_reason: 禁用原因
		"""
		if details is None:
			details = {}

		if username is not None:
			details['username'] = username
		if disable_reason is not None:
			details['disable_reason'] = disable_reason

		super().__init__(message, SecurityErrorCode.ACCOUNT_DISABLED, details, ErrorSeverity.WARNING)


class TooManyAttemptsError(AuthenticationException):
	"""尝试次数过多错误"""

	def __init__ (self,
	              message: str = "尝试次数过多，请稍后再试",
	              details: dict = None,
	              username: str = None,
	              attempts: int = None,
	              max_attempts: int = None):
		"""
		初始化尝试次数过多错误

		Args:
			message: 异常消息
			details: 详细信息
			username: 用户名
			attempts: 尝试次数
			max_attempts: 最大尝试次数
		"""
		if details is None:
			details = {}

		if username is not None:
			details['username'] = username
		if attempts is not None:
			details['attempts'] = attempts
		if max_attempts is not None:
			details['max_attempts'] = max_attempts

		super().__init__(message, SecurityErrorCode.TOO_MANY_ATTEMPTS, details, ErrorSeverity.WARNING)


class AuthorizationException(SecurityException):
	"""授权相关异常基类"""

	def __init__ (self,
	              message: str = "授权异常",
	              code: ErrorCode = SecurityErrorCode.AUTHORIZATION_ERROR,
	              details: dict = None,
	              severity: ErrorSeverity = ErrorSeverity.ERROR):
		"""
		初始化授权异常

		Args:
			message: 异常消息
			code: 错误码
			details: 详细信息
			severity: 错误严重程度
		"""
		super().__init__(message, code, details, severity)

	def to_dict (self) -> dict:
		"""转换为字典格式"""
		data = super().to_dict()
		data['subcategory'] = 'authorization'
		return data


class AccessDeniedError(AuthorizationException):
	"""访问拒绝错误"""

	def __init__ (self,
	              message: str = "访问被拒绝",
	              details: dict = None,
	              user_id: str = None,
	              resource: str = None,
	              action: str = None):
		"""
		初始化访问拒绝错误

		Args:
			message: 异常消息
			details: 详细信息
			user_id: 用户ID
			resource: 资源
			action: 操作
		"""
		if details is None:
			details = {}

		if user_id is not None:
			details['user_id'] = user_id
		if resource is not None:
			details['resource'] = resource
		if action is not None:
			details['action'] = action

		super().__init__(message, SecurityErrorCode.ACCESS_DENIED, details, ErrorSeverity.WARNING)


class InsufficientPrivilegesError(AuthorizationException):
	"""权限不足错误"""

	def __init__ (self,
	              message: str = "权限不足",
	              details: dict = None,
	              user_id: str = None,
	              required_role: str = None,
	              required_permission: str = None):
		"""
		初始化权限不足错误

		Args:
			message: 异常消息
			details: 详细信息
			user_id: 用户ID
			required_role: 所需角色
			required_permission: 所需权限
		"""
		if details is None:
			details = {}

		if user_id is not None:
			details['user_id'] = user_id
		if required_role is not None:
			details['required_role'] = required_role
		if required_permission is not None:
			details['required_permission'] = required_permission

		super().__init__(message, SecurityErrorCode.INSUFFICIENT_PRIVILEGES, details, ErrorSeverity.WARNING)


class AuditException(SecurityException):
	"""审计相关异常基类"""

	def __init__ (self,
	              message: str = "审计异常",
	              code: ErrorCode = SecurityErrorCode.AUDIT_ERROR,
	              details: dict = None,
	              severity: ErrorSeverity = ErrorSeverity.ERROR):
		"""
		初始化审计异常

		Args:
			message: 异常消息
			code: 错误码
			details: 详细信息
			severity: 错误严重程度
		"""
		super().__init__(message, code, details, severity)

	def to_dict (self) -> dict:
		"""转换为字典格式"""
		data = super().to_dict()
		data['subcategory'] = 'audit'
		return data


class AuditLogError(AuditException):
	"""审计日志错误"""

	def __init__ (self,
	              message: str = "审计日志记录失败",
	              details: dict = None,
	              action: str = None,
	              resource_type: str = None):
		"""
		初始化审计日志错误

		Args:
			message: 异常消息
			details: 详细信息
			action: 操作类型
			resource_type: 资源类型
		"""
		if details is None:
			details = {}

		if action is not None:
			details['action'] = action
		if resource_type is not None:
			details['resource_type'] = resource_type

		super().__init__(message, SecurityErrorCode.AUDIT_LOG_FAILED, details)


class SecurityConfigException(SecurityException):
	"""安全配置异常基类"""

	def __init__ (self,
	              message: str = "安全配置异常",
	              code: ErrorCode = SecurityErrorCode.SECURITY_CONFIG_ERROR,
	              details: dict = None,
	              severity: ErrorSeverity = ErrorSeverity.ERROR):
		"""
		初始化安全配置异常

		Args:
			message: 异常消息
			code: 错误码
			details: 详细信息
			severity: 错误严重程度
		"""
		super().__init__(message, code, details, severity)

	def to_dict (self) -> dict:
		"""转换为字典格式"""
		data = super().to_dict()
		data['subcategory'] = 'config'
		return data


class InvalidSecurityConfigError(SecurityConfigException):
	"""无效安全配置错误"""

	def __init__ (self,
	              message: str = "无效的安全配置",
	              details: dict = None,
	              config_key: str = None,
	              config_value: str = None,
	              expected_type: str = None):
		"""
		初始化无效安全配置错误

		Args:
			message: 异常消息
			details: 详细信息
			config_key: 配置键
			config_value: 配置值
			expected_type: 期望类型
		"""
		if details is None:
			details = {}

		if config_key is not None:
			details['config_key'] = config_key
		if config_value is not None:
			details['config_value'] = config_value
		if expected_type is not None:
			details['expected_type'] = expected_type

		super().__init__(message, SecurityErrorCode.INVALID_SECURITY_CONFIG, details)


class MissingSecurityConfigError(SecurityConfigException):
	"""缺失安全配置错误"""

	def __init__ (self,
	              message: str = "缺少必要的安全配置",
	              details: dict = None,
	              config_key: str = None,
	              config_section: str = None):
		"""
		初始化缺失安全配置错误

		Args:
			message: 异常消息
			details: 详细信息
			config_key: 配置键
			config_section: 配置节
		"""
		if details is None:
			details = {}

		if config_key is not None:
			details['config_key'] = config_key
		if config_section is not None:
			details['config_section'] = config_section

		super().__init__(message, SecurityErrorCode.MISSING_SECURITY_CONFIG, details)
