# quant_server/shared/security/password.py
"""
密码处理模块
提供 AES-256-CBC 加密存储和密码强度校验功能
密文格式: AES256:<base64(iv+ciphertext)>
"""

import base64
import hashlib
import logging
import os
import re
from typing import Optional, Tuple, Dict

from shared.security.encryption import AESCipher
from core.exceptions.security_exceptions import (
    PasswordHashError,
    PasswordValidationError,
    WeakPasswordError
)

logger = logging.getLogger(__name__)

# AES 密文前缀，用于区分已加密密码和旧明文
_ENCRYPTED_PREFIX = "AES256:"


def _get_aes_key() -> bytes:
    """获取 AES-256 密钥，优先 AES_ENCRYPTION_KEY 环境变量，否则从 SECRET_KEY 派生"""
    key_b64 = os.getenv("AES_ENCRYPTION_KEY", "")
    if key_b64:
        return base64.b64decode(key_b64)
    secret = os.getenv("SECRET_KEY", "quant-trade-default-secret")
    return hashlib.sha256(secret.encode()).digest()


class PasswordCrypto:
    """AES-256-CBC 密码加密/解密器"""

    def __init__(self, key: Optional[bytes] = None):
        if key is None:
            key = _get_aes_key()
        self._cipher = AESCipher(key=key, key_size=256)

    def encrypt(self, plain_password: str) -> str:
        """加密明文密码，返回 AES256:<base64> 格式密文"""
        ciphertext = self._cipher.encrypt_to_base64(plain_password)
        return _ENCRYPTED_PREFIX + ciphertext

    def decrypt(self, stored_value: str) -> str:
        """解密密文为明文；若不以 AES256: 开头则原样返回（兼容旧数据）"""
        if not stored_value:
            return ""
        if stored_value.startswith(_ENCRYPTED_PREFIX):
            ciphertext = stored_value[len(_ENCRYPTED_PREFIX):]
            return self._cipher.decrypt_from_base64(ciphertext).decode('utf-8')
        return stored_value


def _is_common_password(password: str) -> bool:
    """检查是否为常见弱密码"""
    common_passwords = {
        'password', '123456', '12345678', '123456789',
        'admin', 'qwerty', 'abc123', 'password1',
        '12345', '1234567890', 'letmein', 'welcome',
        'monkey', 'dragon', 'baseball', 'football'
    }
    return password.lower() in common_passwords


def generate_secure_password(length: int = 16) -> str:
    """生成安全随机密码"""
    import secrets
    import string

    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special = '!@#$%^&*()_+-=[]{}|;:,.<>?'

    password_chars = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]
    all_chars = lowercase + uppercase + digits + special
    password_chars.extend(secrets.choice(all_chars) for _ in range(length - 4))
    secrets.SystemRandom().shuffle(password_chars)
    return ''.join(password_chars)


def get_password_score(password: str) -> int:
    """计算密码强度分数（0-100）"""
    score = 0
    if len(password) >= 8:
        score += 20
    if len(password) >= 12:
        score += 10
    if len(password) >= 16:
        score += 10
    if re.search(r'[a-z]', password):
        score += 10
    if re.search(r'[A-Z]', password):
        score += 10
    if re.search(r'[0-9]', password):
        score += 10
    if re.search(r'[^a-zA-Z0-9]', password):
        score += 10
    char_set_size = 0
    if re.search(r'[a-z]', password):
        char_set_size += 26
    if re.search(r'[A-Z]', password):
        char_set_size += 26
    if re.search(r'[0-9]', password):
        char_set_size += 10
    if re.search(r'[^a-zA-Z0-9]', password):
        char_set_size += 32
    if char_set_size > 0:
        entropy = len(password) * (char_set_size.bit_length() / 2)
        score += min(int(entropy), 20)
    if _is_common_password(password):
        score = max(0, score - 30)
    return min(score, 100)


class PasswordManager:
    """密码管理器 — 负责密码强度校验和加密存储"""

    def __init__(self,
                 min_length: int = 8,
                 require_uppercase: bool = True,
                 require_lowercase: bool = True,
                 require_numbers: bool = True,
                 require_special: bool = True,
                 aes_key: Optional[bytes] = None):
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_numbers = require_numbers
        self.require_special = require_special
        self._crypto = PasswordCrypto(key=aes_key)

    def encrypt_password(self, password: str) -> str:
        """加密密码（存储用）"""
        try:
            self.validate_password_strength(password)
            return self._crypto.encrypt(password)
        except WeakPasswordError:
            raise
        except Exception as e:
            raise PasswordHashError(f"密码加密失败: {str(e)}") from e

    def decrypt_password(self, encrypted: str) -> str:
        """解密密码（验证用）"""
        try:
            return self._crypto.decrypt(encrypted)
        except Exception as e:
            raise PasswordValidationError(f"密码解密失败: {str(e)}") from e

    def verify_password(self, plain_password: str, stored_value: str) -> bool:
        """验证密码：解密存储值后与明文比对"""
        try:
            decrypted = self.decrypt_password(stored_value)
            return decrypted == plain_password
        except Exception as e:
            raise PasswordValidationError(f"密码验证失败: {str(e)}") from e

    def validate_password_strength(self, password: str) -> Tuple[bool, list]:
        """验证密码强度，返回 (是否通过, 错误消息列表)"""
        errors = []
        if len(password) < self.min_length:
            errors.append(f"密码长度至少为{self.min_length}个字符")
        if self.require_uppercase and not re.search(r'[A-Z]', password):
            errors.append("密码必须包含至少一个大写字母")
        if self.require_lowercase and not re.search(r'[a-z]', password):
            errors.append("密码必须包含至少一个小写字母")
        if self.require_numbers and not re.search(r'[0-9]', password):
            errors.append("密码必须包含至少一个数字")
        if self.require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("密码必须包含至少一个特殊字符")
        if _is_common_password(password):
            errors.append("密码太常见，请使用更复杂的密码")
        if errors:
            raise WeakPasswordError(f"密码强度不足: {'; '.join(errors)}")
        return True, []

    def check_password_policy(self, password: str) -> Dict[str, bool]:
        """检查密码策略的各个要求"""
        return {
            "length_ok": len(password) >= self.min_length,
            "has_uppercase": bool(re.search(r'[A-Z]', password)),
            "has_lowercase": bool(re.search(r'[a-z]', password)),
            "has_number": bool(re.search(r'[0-9]', password)),
            "has_special": bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password)),
            "is_common": _is_common_password(password)
        }


# 全局实例（延迟初始化）
_password_manager = None
_password_crypto = None


def get_password_manager(config: Optional[dict] = None) -> PasswordManager:
    """获取全局 PasswordManager"""
    global _password_manager
    if _password_manager is None:
        if config is None:
            from ..config.config_manager import get_config
            settings = get_config().settings
            config = {
                'min_length': getattr(settings, 'PASSWORD_MIN_LENGTH', 8),
                'require_uppercase': getattr(settings, 'PASSWORD_REQUIRE_UPPERCASE', True),
                'require_lowercase': getattr(settings, 'PASSWORD_REQUIRE_LOWERCASE', True),
                'require_numbers': getattr(settings, 'PASSWORD_REQUIRE_NUMBERS', True),
                'require_special': getattr(settings, 'PASSWORD_REQUIRE_SPECIAL', True)
            }
        _password_manager = PasswordManager(**config)
    return _password_manager


def get_password_crypto() -> PasswordCrypto:
    """获取全局 PasswordCrypto 实例"""
    global _password_crypto
    if _password_crypto is None:
        _password_crypto = PasswordCrypto()
    return _password_crypto


# 便捷函数
def encrypt_password(password: str) -> str:
    """加密密码"""
    return get_password_manager().encrypt_password(password)


def decrypt_password(encrypted: str) -> str:
    """解密密码"""
    return get_password_crypto().decrypt(encrypted)


def verify_password(plain_password: str, stored_value: str) -> bool:
    """验证密码"""
    return get_password_manager().verify_password(plain_password, stored_value)
