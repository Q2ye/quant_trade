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
