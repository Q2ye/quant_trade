# quant_server/shared/security/password.py
"""
密码处理模块
提供密码哈希、验证和强度检查功能
使用bcrypt进行安全的密码哈希
"""

import re
from typing import Optional, Tuple, Dict

from passlib.context import CryptContext

from quant_server.core.exceptions.security_exceptions import (
	PasswordHashError,
	PasswordValidationError,
	WeakPasswordError
)


def _is_common_password (password: str) -> bool:
	"""检查是否为常见弱密码"""
	common_passwords = {
		'password', '123456', '12345678', '123456789',
		'admin', 'qwerty', 'abc123', 'password1',
		'12345', '1234567890', 'letmein', 'welcome',
		'monkey', 'dragon', 'baseball', 'football'
	}

	return password.lower() in common_passwords


def generate_secure_password (length: int = 16) -> str:
	"""
	生成安全随机密码

	Args:
		length: 密码长度

	Returns:
		生成的随机密码
	"""
	import secrets
	import string

	# 定义字符集
	lowercase = string.ascii_lowercase
	uppercase = string.ascii_uppercase
	digits = string.digits
	special = '!@#$%^&*()_+-=[]{}|;:,.<>?'

	# 确保每种类型至少有一个字符
	password_chars = [
		secrets.choice(lowercase),
		secrets.choice(uppercase),
		secrets.choice(digits),
		secrets.choice(special)
	]

	# 填充剩余长度
	all_chars = lowercase + uppercase + digits + special
	password_chars.extend(secrets.choice(all_chars) for _ in range(length - 4))

	# 随机打乱
	secrets.SystemRandom().shuffle(password_chars)

	return ''.join(password_chars)


def get_password_score (password: str) -> int:
	"""
	计算密码强度分数（0-100）

	Args:
		password: 要评分的密码

	Returns:
		密码强度分数
	"""
	score = 0

	# 长度分数
	if len(password) >= 8:
		score += 20
	if len(password) >= 12:
		score += 10
	if len(password) >= 16:
		score += 10

	# 字符种类分数
	if re.search(r'[a-z]', password):
		score += 10
	if re.search(r'[A-Z]', password):
		score += 10
	if re.search(r'[0-9]', password):
		score += 10
	if re.search(r'[^a-zA-Z0-9]', password):
		score += 10

	# 熵分数（基于字符种类）
	char_set_size = 0
	if re.search(r'[a-z]', password):
		char_set_size += 26
	if re.search(r'[A-Z]', password):
		char_set_size += 26
	if re.search(r'[0-9]', password):
		char_set_size += 10
	if re.search(r'[^a-zA-Z0-9]', password):
		char_set_size += 32

	# 计算熵并转换为分数
	if char_set_size > 0:
		entropy = len(password) * (char_set_size.bit_length() / 2)
		score += min(int(entropy), 20)

	# 常见密码扣分
	if _is_common_password(password):
		score = max(0, score - 30)

	return min(score, 100)


class PasswordManager:
	"""密码管理器"""

	def __init__ (self,
	              bcrypt_rounds: int = 12,
	              min_length: int = 8,
	              require_uppercase: bool = True,
	              require_lowercase: bool = True,
	              require_numbers: bool = True,
	              require_special: bool = True):
		"""
		初始化密码管理器

		Args:
			bcrypt_rounds: bcrypt哈希轮数（越高越安全但越慢）
			min_length: 密码最小长度
			require_uppercase: 是否需要大写字母
			require_lowercase: 是否需要小写字母
			require_numbers: 是否需要数字
			require_special: 是否需要特殊字符
		"""
		self.bcrypt_rounds = bcrypt_rounds
		self.min_length = min_length
		self.require_uppercase = require_uppercase
		self.require_lowercase = require_lowercase
		self.require_numbers = require_numbers
		self.require_special = require_special

		# 创建密码上下文
		self.pwd_context = CryptContext(
			schemes=["bcrypt"],
			deprecated="auto",
			bcrypt__rounds=bcrypt_rounds
		)

	def get_password (self, password: str) -> str:
		"""
		生成密码哈希

		Args:
			password: 明文密码

		Returns:
			哈希后的密码

		Raises:
			WeakPasswordError: 密码强度不足
			PasswordHashError: 密码哈希失败
		"""
		try:
			# 验证密码强度
			self.validate_password_strength(password)

			# 生成哈希
			hashed = self.pwd_context.hash(password)
			return hashed

		except WeakPasswordError:
			raise
		except Exception as e:
			raise PasswordHashError(f"密码哈希失败: {str(e)}") from e

	def verify_password (self, plain_password: str, hashed_password: str) -> bool:
		"""
		验证密码

		Args:
			plain_password: 明文密码
			hashed_password: 哈希密码

		Returns:
			True如果密码匹配，否则False
		"""
		try:
			return self.pwd_context.verify(plain_password, hashed_password)
		except Exception as e:
			raise PasswordValidationError(f"密码验证失败: {str(e)}") from e

	def validate_password_strength (self, password: str) -> Tuple[bool, list]:
		"""
		验证密码强度

		Args:
			password: 要验证的密码

		Returns:
			(是否通过, 错误消息列表)的元组
		"""
		errors = []

		# 检查长度
		if len(password) < self.min_length:
			errors.append(f"密码长度至少为{self.min_length}个字符")

		# 检查大写字母
		if self.require_uppercase and not re.search(r'[A-Z]', password):
			errors.append("密码必须包含至少一个大写字母")

		# 检查小写字母
		if self.require_lowercase and not re.search(r'[a-z]', password):
			errors.append("密码必须包含至少一个小写字母")

		# 检查数字
		if self.require_numbers and not re.search(r'[0-9]', password):
			errors.append("密码必须包含至少一个数字")

		# 检查特殊字符
		if self.require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
			errors.append("密码必须包含至少一个特殊字符")

		# 检查常见弱密码
		if _is_common_password(password):
			errors.append("密码太常见，请使用更复杂的密码")

		if errors:
			raise WeakPasswordError(f"密码强度不足: {'; '.join(errors)}")

		return True, []

	def needs_rehash (self, hashed_password: str) -> bool:
		"""
		检查密码是否需要重新哈希（例如，当哈希参数变更时）

		Args:
			hashed_password: 哈希密码

		Returns:
			True如果需要重新哈希，否则False
		"""
		return self.pwd_context.needs_update(hashed_password)

	def check_password_policy (self, password: str) -> Dict[str, bool]:
		"""
		检查密码策略的各个要求

		Args:
			password: 要检查的密码

		Returns:
			包含各项检查结果的字典
		"""
		return {
			"length_ok": len(password) >= self.min_length,
			"has_uppercase": bool(re.search(r'[A-Z]', password)),
			"has_lowercase": bool(re.search(r'[a-z]', password)),
			"has_number": bool(re.search(r'[0-9]', password)),
			"has_special": bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password)),
			"is_common": _is_common_password(password)
		}


# 全局密码管理器实例（延迟初始化）
_password_manager = None


def get_password_manager (config: Optional[dict] = None) -> PasswordManager:
	"""
	获取全局密码管理器

	Args:
		config: 密码管理器配置

	Returns:
		PasswordManager实例
	"""
	global _password_manager

	if _password_manager is None:
		if config is None:
			from ..config.config_manager import get_config
			settings = get_config().settings
			config = {
				'bcrypt_rounds': getattr(settings, 'BCRYPT_ROUNDS', 12),
				'min_length': getattr(settings, 'PASSWORD_MIN_LENGTH', 8),
				'require_uppercase': getattr(settings, 'PASSWORD_REQUIRE_UPPERCASE', True),
				'require_lowercase': getattr(settings, 'PASSWORD_REQUIRE_LOWERCASE', True),
				'require_numbers': getattr(settings, 'PASSWORD_REQUIRE_NUMBERS', True),
				'require_special': getattr(settings, 'PASSWORD_REQUIRE_SPECIAL', True)
			}

		_password_manager = PasswordManager(**config)

	return _password_manager


# 便捷函数
def get_password (password: str) -> str:
	"""获取密码哈希的便捷函数"""
	return get_password_manager().get_password(password)


def verify_password (plain_password: str, hashed_password: str) -> bool:
	"""验证密码的便捷函数"""
	return get_password_manager().verify_password(plain_password, hashed_password)
