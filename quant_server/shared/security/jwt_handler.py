# quant_server/shared/security/jwt_handler.py
"""
JWT处理器模块
处理JWT令牌的生成、验证和刷新
支持访问令牌和刷新令牌
"""

import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel

from ..config.settings import Settings
from quant_server.core.exceptions.security_exceptions import (
	TokenExpiredError,
	InvalidTokenError,
	TokenCreationError
)


# JWT配置模型
class JWTConfig(BaseModel):
	"""JWT配置"""
	secret_key: str
	algorithm: str = "HS256"
	access_token_expire_minutes: int = 30
	refresh_token_expire_days: int = 7
	issuer: Optional[str] = None
	audience: Optional[str] = None


class JWTManager:
	"""JWT管理器"""

	def __init__ (self, config: Optional[JWTConfig] = None):
		"""
		初始化JWT管理器

		Args:
			config: JWT配置，如果为None则从Settings读取
		"""
		if config is None:
			settings = Settings()
			config = JWTConfig(
				secret_key=settings.API.SECRET_KEY,
				algorithm=settings.API.JWT_ALGORITHM,
				access_token_expire_minutes=settings.API.ACCESS_TOKEN_EXPIRE_MINUTES,
				refresh_token_expire_days=settings.API.REFRESH_TOKEN_EXPIRE_DAYS,
				issuer=settings.API.JWT_ISSUER,
				audience=settings.API.JWT_AUDIENCE
			)

		self.config = config

	def create_access_token (
			self,
			data: Dict[str, Any],
			expires_delta: Optional[timedelta] = None
	) -> str:
		"""
		创建访问令牌

		Args:
			data: 要编码到令牌中的数据
			expires_delta: 过期时间增量，如果为None则使用配置值

		Returns:
			JWT访问令牌字符串
		"""
		try:
			to_encode = data.copy()

			# 设置过期时间
			if expires_delta:
				expire = datetime.utcnow() + expires_delta
			else:
				expire = datetime.utcnow() + timedelta(
					minutes=self.config.access_token_expire_minutes
				)

			to_encode.update({
				"exp": expire,
				"iat": datetime.utcnow(),
				"type": "access"
			})

			# 添加发行者和受众
			if self.config.issuer:
				to_encode["iss"] = self.config.issuer
			if self.config.audience:
				to_encode["aud"] = self.config.audience

			# 编码JWT
			encoded_jwt = jwt.encode(
				to_encode,
				self.config.secret_key,
				algorithm=self.config.algorithm
			)

			return encoded_jwt

		except Exception as e:
			raise TokenCreationError(f"创建访问令牌失败: {str(e)}") from e

	def create_refresh_token (
			self,
			data: Dict[str, Any],
			expires_delta: Optional[timedelta] = None
	) -> str:
		"""
		创建刷新令牌

		Args:
			data: 要编码到令牌中的数据
			expires_delta: 过期时间增量，如果为None则使用配置值

		Returns:
			JWT刷新令牌字符串
		"""
		try:
			to_encode = data.copy()

			# 设置过期时间（比访问令牌长）
			if expires_delta:
				expire = datetime.utcnow() + expires_delta
			else:
				expire = datetime.utcnow() + timedelta(
					days=self.config.refresh_token_expire_days
				)

			to_encode.update({
				"exp": expire,
				"iat": datetime.utcnow(),
				"type": "refresh"
			})

			# 添加发行者和受众
			if self.config.issuer:
				to_encode["iss"] = self.config.issuer
			if self.config.audience:
				to_encode["aud"] = self.config.audience

			# 编码JWT
			encoded_jwt = jwt.encode(
				to_encode,
				self.config.secret_key,
				algorithm=self.config.algorithm
			)

			return encoded_jwt

		except Exception as e:
			raise TokenCreationError(f"创建刷新令牌失败: {str(e)}") from e

	def create_token_pair (
			self,
			user_data: Dict[str, Any]
	) -> Dict[str, str]:
		"""
		创建令牌对（访问令牌 + 刷新令牌）

		Args:
			user_data: 用户数据

		Returns:
			包含访问令牌和刷新令牌的字典
		"""
		return {
			"access_token": self.create_access_token(user_data),
			"refresh_token": self.create_refresh_token(user_data),
			"token_type": "bearer"
		}

	def verify_token (
			self,
			token: str,
			token_type: Optional[str] = None,
			leeway: int = 0
	) -> Dict[str, Any]:
		"""
		验证JWT令牌

		Args:
			token: JWT令牌字符串
			token_type: 期望的令牌类型（'access' 或 'refresh'）
			leeway: 时间容差（秒）

		Returns:
			解码后的令牌数据

		Raises:
			TokenExpiredError: 令牌已过期
			InvalidTokenError: 令牌无效
		"""
		try:
			# 解码令牌
			payload = jwt.decode(
				token,
				self.config.secret_key,
				algorithms=[self.config.algorithm],
				options={
					"verify_exp": True,
					"verify_iss": self.config.issuer is not None,
					"verify_aud": self.config.audience is not None,
					"leeway": leeway
				},
				issuer=self.config.issuer,
				audience=self.config.audience
			)

			# 验证令牌类型
			if token_type and payload.get("type") != token_type:
				raise InvalidTokenError(f"令牌类型不匹配: 期望 {token_type}, 实际 {payload.get('type')}")

			return payload

		except jwt.ExpiredSignatureError as e:
			raise TokenExpiredError("令牌已过期") from e
		except jwt.InvalidTokenError as e:
			raise InvalidTokenError(f"无效令牌: {str(e)}") from e
		except Exception as e:
			raise InvalidTokenError(f"令牌验证失败: {str(e)}") from e

	def refresh_access_token (
			self,
			refresh_token: str
	) -> Dict[str, str]:
		"""
		使用刷新令牌获取新的访问令牌

		Args:
			refresh_token: 刷新令牌

		Returns:
			新的访问令牌
		"""
		try:
			# 验证刷新令牌
			payload = self.verify_token(refresh_token, token_type="refresh")

			# 创建新的访问令牌（移除refresh_token特定字段）
			access_token_data = {
				k: v for k, v in payload.items()
				if k not in ["exp", "iat", "type"]
			}

			new_access_token = self.create_access_token(access_token_data)

			return {
				"access_token": new_access_token,
				"token_type": "bearer"
			}

		except Exception as e:
			raise InvalidTokenError(f"刷新令牌失败: {str(e)}") from e

	def decode_token_without_verification (
			self,
			token: str
	) -> Dict[str, Any]:
		"""
		解码令牌但不验证签名（用于调试或特殊情况）

		Args:
			token: JWT令牌

		Returns:
			解码后的令牌数据
		"""
		try:
			return jwt.decode(
				token,
				self.config.secret_key,
				algorithms=[self.config.algorithm],
				options={"verify_signature": False}
			)
		except Exception as e:
			raise InvalidTokenError(f"令牌解码失败: {str(e)}") from e

	def get_token_expiry (self, token: str) -> datetime:
		"""
		获取令牌过期时间

		Args:
			token: JWT令牌

		Returns:
			令牌过期时间
		"""
		try:
			payload = self.decode_token_without_verification(token)
			exp_timestamp = payload.get("exp")

			if not exp_timestamp:
				raise InvalidTokenError("令牌不包含过期时间")

			return datetime.fromtimestamp(exp_timestamp)

		except Exception as e:
			raise InvalidTokenError(f"获取令牌过期时间失败: {str(e)}") from e

	def is_token_expired (self, token: str, leeway: int = 0) -> bool:
		"""
		检查令牌是否已过期

		Args:
			token: JWT令牌
			leeway: 时间容差（秒）

		Returns:
			True如果令牌已过期，否则False
		"""
		try:
			self.verify_token(token, leeway=leeway)
			return False
		except TokenExpiredError:
			return True
		except Exception:
			return True


# 全局JWT管理器实例（延迟初始化）
_jwt_manager = None


def get_jwt_manager (config: Optional[JWTConfig] = None) -> JWTManager:
	"""
	获取全局JWT管理器

	Args:
		config: JWT配置

	Returns:
		JWTManager实例
	"""
	global _jwt_manager

	if _jwt_manager is None:
		_jwt_manager = JWTManager(config)

	return _jwt_manager


# 便捷函数
def create_access_token (
		data: Dict[str, Any],
		expires_delta: Optional[timedelta] = None
) -> str:
	"""创建访问令牌的便捷函数"""
	return get_jwt_manager().create_access_token(data, expires_delta)


def verify_token (
		token: str,
		token_type: Optional[str] = None,
		leeway: int = 0
) -> Dict[str, Any]:
	"""验证令牌的便捷函数"""
	return get_jwt_manager().verify_token(token, token_type, leeway)