# quant_server/shared/security/__init__.py
"""
安全模块包入口
提供统一的安全功能接口，包括加密、JWT、密码处理、权限验证和审计日志
（2026-08 D 批清理：RSACipher/EncryptionManager/死密码函数/audit_log 装饰器已删）
"""

from .encryption import AESCipher
from .jwt_handler import JWTManager, create_access_token, verify_token
from .password import (
    PasswordManager,
    PasswordCrypto,
    get_password_crypto,
    get_password_manager,
)
from .audit import AuditLogger

__all__ = [
	# 加密
	'AESCipher',

	# JWT
	'JWTManager',
	'create_access_token',
	'verify_token',

	# 密码
	'PasswordManager',
	'PasswordCrypto',
	'get_password_crypto',
	'get_password_manager',

	# 审计
	'AuditLogger',
]

__version__ = '1.0.0'
__author__ = 'Quant System Team'
__description__ = '量化交易系统安全模块'
