# quant_server/shared/security/encryption.py
"""
加密工具模块
提供对称加密(AES)、非对称加密(RSA)和哈希算法
支持数据加密、解密、签名和验证
"""

import base64
import hashlib
import secrets
from typing import Optional, Union, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from core.exceptions.security_exceptions import (
	EncryptionError,
	DecryptionError,
	InvalidKeyError,
	SignatureError
)


class AESCipher:
	"""AES对称加密工具类"""

	def __init__ (self, key: Optional[bytes] = None, key_size: int = 256):
		"""
		初始化AES加密器

		Args:
			key: 加密密钥，如果为None则自动生成
			key_size: 密钥大小(128, 192, 256)
		"""
		if key is None:
			# 生成随机密钥
			self.key = secrets.token_bytes(key_size // 8)
		else:
			if len(key) != key_size // 8:
				raise InvalidKeyError(f"密钥长度必须为{key_size}位")
			self.key = key

		self.key_size = key_size
		self.backend = default_backend()

	def encrypt (self, data: Union[str, bytes], iv: Optional[bytes] = None) -> Tuple[bytes, bytes]:
		"""
		使用AES-CBC模式加密数据

		Args:
			data: 要加密的数据（字符串或字节）
			iv: 初始化向量，如果为None则自动生成

		Returns:
			(加密数据, 初始化向量)的元组
		"""
		try:
			# 转换为字节
			if isinstance(data, str):
				data = data.encode('utf-8')

			# 生成IV（如果需要）
			if iv is None:
				iv = secrets.token_bytes(16)  # AES块大小

			# 创建加密器
			cipher = Cipher(
				algorithms.AES(self.key),
				modes.CBC(iv),
				backend=self.backend
			)
			encryptor = cipher.encryptor()

			# 添加PKCS7填充
			padder = padding.PKCS7(algorithms.AES.block_size).padder()
			padded_data = padder.update(data) + padder.finalize()

			# 加密
			encrypted = encryptor.update(padded_data) + encryptor.finalize()

			return encrypted, iv

		except Exception as e:
			raise EncryptionError(f"AES加密失败: {str(e)}") from e

	def decrypt (self, encrypted_data: bytes, iv: bytes) -> bytes:
		"""
		使用AES-CBC模式解密数据

		Args:
			encrypted_data: 加密的数据
			iv: 初始化向量

		Returns:
			解密后的原始数据
		"""
		try:
			# 创建解密器
			cipher = Cipher(
				algorithms.AES(self.key),
				modes.CBC(iv),
				backend=self.backend
			)
			decryptor = cipher.decryptor()

			# 解密
			padded_data = decryptor.update(encrypted_data) + decryptor.finalize()

			# 移除PKCS7填充
			unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
			data = unpadder.update(padded_data) + unpadder.finalize()

			return data

		except Exception as e:
			raise DecryptionError(f"AES解密失败: {str(e)}") from e

	def encrypt_to_base64 (self, data: Union[str, bytes]) -> str:
		"""
		加密数据并返回base64编码的字符串

		Args:
			data: 要加密的数据

		Returns:
			base64编码的加密数据
		"""
		encrypted, iv = self.encrypt(data)
		# 格式: iv:encrypted_data
		combined = iv + encrypted
		return base64.b64encode(combined).decode('utf-8')

	def decrypt_from_base64 (self, encrypted_str: str) -> bytes:
		"""
		从base64字符串解密数据

		Args:
			encrypted_str: base64编码的加密数据

		Returns:
			解密后的数据
		"""
		combined = base64.b64decode(encrypted_str)
		iv = combined[:16]  # AES IV长度为16字节
		encrypted_data = combined[16:]
		return self.decrypt(encrypted_data, iv)


class RSACipher:
	"""RSA非对称加密工具类"""

	def __init__ (self,
	              public_key: Optional[bytes] = None,
	              private_key: Optional[bytes] = None,
	              key_size: int = 2048):
		"""
		初始化RSA加密器

		Args:
			public_key: PEM格式的公钥
			private_key: PEM格式的私钥
			key_size: 密钥大小（默认2048）
		"""
		self.key_size = key_size
		self.backend = default_backend()

		if private_key:
			self.private_key = self._load_private_key(private_key)
		else:
			self.private_key = None

		if public_key:
			self.public_key = self._load_public_key(public_key)
		else:
			self.public_key = None

	def generate_key_pair (self) -> Tuple[bytes, bytes]:
		"""
		生成RSA密钥对

		Returns:
			(私钥PEM, 公钥PEM)的元组
		"""
		private_key = rsa.generate_private_key(
			public_exponent=65537,
			key_size=self.key_size,
			backend=self.backend
		)

		private_pem = private_key.private_bytes(
			encoding=serialization.Encoding.PEM,
			format=serialization.PrivateFormat.PKCS8,
			encryption_algorithm=serialization.NoEncryption()
		)

		public_key = private_key.public_key()
		public_pem = public_key.public_bytes(
			encoding=serialization.Encoding.PEM,
			format=serialization.PublicFormat.SubjectPublicKeyInfo
		)

		self.private_key = private_key
		self.public_key = public_key

		return private_pem, public_pem

	def encrypt (self, data: Union[str, bytes]) -> bytes:
		"""
		使用公钥加密数据

		Args:
			data: 要加密的数据

		Returns:
			加密后的数据
		"""
		if not self.public_key:
			raise InvalidKeyError("未设置公钥")

		try:
			if isinstance(data, str):
				data = data.encode('utf-8')

			# RSA加密有长度限制，使用混合加密方案
			if len(data) > (self.key_size // 8 - 42):  # OAEP填充开销
				# 生成随机的AES密钥
				aes_key = secrets.token_bytes(32)
				iv = secrets.token_bytes(16)

				# 用AES加密数据
				aes_cipher = AESCipher(aes_key)
				encrypted_data, iv = aes_cipher.encrypt(data, iv)

				# 用RSA加密AES密钥
				encrypted_key = self.public_key.encrypt(
					aes_key + iv,  # 合并密钥和IV
					asym_padding.OAEP(
						mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
						algorithm=hashes.SHA256(),
						label=None
					)
				)

				return b'HYBRID:' + encrypted_key + b':' + encrypted_data
			else:
				# 直接RSA加密
				encrypted = self.public_key.encrypt(
					data,
					asym_padding.OAEP(
						mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
						algorithm=hashes.SHA256(),
						label=None
					)
				)
				return b'RSA:' + encrypted

		except Exception as e:
			raise EncryptionError(f"RSA加密失败: {str(e)}") from e

	def decrypt (self, encrypted_data: bytes) -> bytes:
		"""
		使用私钥解密数据

		Args:
			encrypted_data: 加密的数据

		Returns:
			解密后的原始数据
		"""
		if not self.private_key:
			raise InvalidKeyError("未设置私钥")

		try:
			if encrypted_data.startswith(b'HYBRID:'):
				# 混合加密模式
				parts = encrypted_data[7:].split(b':', 1)
				if len(parts) != 2:
					raise DecryptionError("无效的混合加密格式")

				encrypted_key_iv, encrypted_data = parts

				# 解密AES密钥和IV
				key_iv = self.private_key.decrypt(
					encrypted_key_iv,
					asym_padding.OAEP(
						mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
						algorithm=hashes.SHA256(),
						label=None
					)
				)

				aes_key = key_iv[:32]
				iv = key_iv[32:48]  # AES IV为16字节

				# 使用AES解密数据
				aes_cipher = AESCipher(aes_key)
				return aes_cipher.decrypt(encrypted_data, iv)

			elif encrypted_data.startswith(b'RSA:'):
				# 直接RSA加密模式
				encrypted = encrypted_data[4:]
				return self.private_key.decrypt(
					encrypted,
					asym_padding.OAEP(
						mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
						algorithm=hashes.SHA256(),
						label=None
					)
				)
			else:
				raise DecryptionError("未知的加密格式")

		except Exception as e:
			raise DecryptionError(f"RSA解密失败: {str(e)}") from e

	def sign (self, data: Union[str, bytes]) -> bytes:
		"""
		使用私钥对数据进行签名

		Args:
			data: 要签名的数据

		Returns:
			数字签名
		"""
		if not self.private_key:
			raise InvalidKeyError("未设置私钥")

		try:
			if isinstance(data, str):
				data = data.encode('utf-8')

			# 计算哈希
			digest = hashes.Hash(hashes.SHA256(), backend=self.backend)
			digest.update(data)
			message_hash = digest.finalize()

			# 签名
			signature = self.private_key.sign(
				message_hash,
				asym_padding.PSS(
					mgf=asym_padding.MGF1(hashes.SHA256()),
					salt_length=asym_padding.PSS.MAX_LENGTH
				),
				hashes.SHA256()
			)

			return signature

		except Exception as e:
			raise SignatureError(f"签名失败: {str(e)}") from e

	def verify (self, data: Union[str, bytes], signature: bytes) -> bool:
		"""
		使用公钥验证签名

		Args:
			data: 原始数据
			signature: 数字签名

		Returns:
			验证是否通过
		"""
		if not self.public_key:
			raise InvalidKeyError("未设置公钥")

		try:
			if isinstance(data, str):
				data = data.encode('utf-8')

			# 计算哈希
			digest = hashes.Hash(hashes.SHA256(), backend=self.backend)
			digest.update(data)
			message_hash = digest.finalize()

			# 验证签名
			self.public_key.verify(
				signature,
				message_hash,
				asym_padding.PSS(
					mgf=asym_padding.MGF1(hashes.SHA256()),
					salt_length=asym_padding.PSS.MAX_LENGTH
				),
				hashes.SHA256()
			)
			return True

		except InvalidSignature:
			return False
		except Exception as e:
			raise SignatureError(f"签名验证失败: {str(e)}") from e

	def _load_private_key (self, key_data: bytes):
		"""加载PEM格式的私钥"""
		from cryptography.hazmat.primitives import serialization

		return serialization.load_pem_private_key(
			key_data,
			password=None,
			backend=self.backend
		)

	def _load_public_key (self, key_data: bytes):
		"""加载PEM格式的公钥"""
		from cryptography.hazmat.primitives import serialization

		return serialization.load_pem_public_key(
			key_data,
			backend=self.backend
		)


class EncryptionManager:
	"""加密管理器，统一管理各种加密算法"""

	def __init__ (self, config: dict = None):
		"""
		初始化加密管理器

		Args:
			config: 加密配置
		"""
		self.config = config or {}
		self.aes_ciphers = {}
		self.rsa_ciphers = {}

		# 初始化默认AES密钥（从配置或环境变量读取）
		default_aes_key = self._get_config('aes_key')
		if default_aes_key:
			self.default_aes = AESCipher(
				key=base64.b64decode(default_aes_key),
				key_size=256
			)
		else:
			self.default_aes = AESCipher(key_size=256)

	def _get_config (self, key: str, default=None):
		"""获取配置"""
		return self.config.get(key, default)

	def get_aes_cipher (self, key_name: str = 'default') -> AESCipher:
		"""
		获取指定名称的AES加密器

		Args:
			key_name: 密钥名称

		Returns:
			AESCipher实例
		"""
		if key_name not in self.aes_ciphers:
			key_data = self._get_config(f'aes_key_{key_name}')
			if key_data:
				self.aes_ciphers[key_name] = AESCipher(
					key=base64.b64decode(key_data),
					key_size=256
				)
			elif key_name == 'default':
				self.aes_ciphers[key_name] = self.default_aes
			else:
				raise InvalidKeyError(f"未配置AES密钥: {key_name}")

		return self.aes_ciphers[key_name]

	def get_rsa_cipher (self, key_pair_name: str = 'default') -> RSACipher:
		"""
		获取指定名称的RSA加密器

		Args:
			key_pair_name: 密钥对名称

		Returns:
			RSACipher实例
		"""
		if key_pair_name not in self.rsa_ciphers:
			public_key = self._get_config(f'rsa_public_{key_pair_name}')
			private_key = self._get_config(f'rsa_private_{key_pair_name}')

			if public_key:
				public_key = base64.b64decode(public_key)
			if private_key:
				private_key = base64.b64decode(private_key)

			self.rsa_ciphers[key_pair_name] = RSACipher(
				public_key=public_key,
				private_key=private_key,
				key_size=2048
			)

		return self.rsa_ciphers[key_pair_name]

	@staticmethod
	def hash_data ( data: Union[str, bytes], algorithm: str = 'sha256') -> str:
		"""
		计算数据的哈希值

		Args:
			data: 要哈希的数据
			algorithm: 哈希算法（md5, sha1, sha256, sha512）

		Returns:
			十六进制哈希字符串
		"""
		if isinstance(data, str):
			data = data.encode('utf-8')

		if algorithm == 'md5':
			return hashlib.md5(data).hexdigest()
		elif algorithm == 'sha1':
			return hashlib.sha1(data).hexdigest()
		elif algorithm == 'sha256':
			return hashlib.sha256(data).hexdigest()
		elif algorithm == 'sha512':
			return hashlib.sha512(data).hexdigest()
		else:
			raise ValueError(f"不支持的哈希算法: {algorithm}")

	@staticmethod
	def hmac_sign ( data: Union[str, bytes], key: Union[str, bytes],
	               algorithm: str = 'sha256') -> str:
		"""
		使用HMAC进行消息认证

		Args:
			data: 要签名的数据
			key: HMAC密钥
			algorithm: 哈希算法

		Returns:
			HMAC签名
		"""
		if isinstance(data, str):
			data = data.encode('utf-8')
		if isinstance(key, str):
			key = key.encode('utf-8')

		if algorithm == 'sha256':
			return hashlib.sha256(key + data).hexdigest()
		elif algorithm == 'sha512':
			return hashlib.sha512(key + data).hexdigest()
		else:
			raise ValueError(f"不支持的HMAC算法: {algorithm}")


# 全局加密管理器实例（延迟初始化）
_encryption_manager = None


def get_encryption_manager (config: dict = None) -> EncryptionManager:
	"""
	获取全局加密管理器

	Args:
		config: 加密配置

	Returns:
		EncryptionManager实例
	"""
	global _encryption_manager

	if _encryption_manager is None:
		_encryption_manager = EncryptionManager(config)

	return _encryption_manager


# 导入serialization模块用于PEM格式处理
from cryptography.hazmat.primitives import serialization
