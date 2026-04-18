# quant_server/shared/security/__init__.py
"""
安全模块包入口
提供统一的安全功能接口，包括加密、JWT、密码处理、权限验证和审计日志
"""

from .encryption import EncryptionManager, AESCipher, RSACipher
from .jwt_handler import JWTManager, create_access_token, verify_token
from .password import PasswordManager, verify_password, get_password
from .audit import AuditLogger, audit_log

__all__ = [
	# 加密
	'EncryptionManager',
	'AESCipher',
	'RSACipher',

	# JWT
	'JWTManager',
	'create_access_token',
	'verify_token',

	# 密码
	'PasswordManager',
	'verify_password',
	'get_password',

	# 审计
	'AuditLogger',
	'audit_log',
]

__version__ = '1.0.0'
__author__ = 'Quant System Team'
__description__ = '量化交易系统安全模块'