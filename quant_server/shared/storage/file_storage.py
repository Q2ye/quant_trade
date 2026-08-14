# -*- coding: utf-8 -*-
"""
文件存储服务
负责文件的上传、下载和管理
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class FileStorage:
	"""
	文件存储服务
	提供文件上传、下载和管理功能
	"""

	def __init__ (self):
		"""
		初始化文件存储服务
		"""
		# 这里可以初始化各种存储后端
		# 如本地存储、云存储等
		self.base_path = os.path.join(os.getcwd(), "storage")
		os.makedirs(self.base_path, exist_ok=True)

	def _resolve_path (self, path: str) -> str:
		"""解析并校验路径，防止路径穿越（修复 2026-08 A9）"""
		if not path or not isinstance(path, str):
			raise ValueError("非法路径")
		base = os.path.realpath(self.base_path)
		full = os.path.realpath(os.path.join(base, path))
		if not (full == base or full.startswith(base + os.sep)):
			raise ValueError("路径越界")
		return full

	def upload (
			self,
			content: bytes,
			path: str,
			content_type: str = "application/octet-stream"
	) -> str:
		"""
		上传文件到存储

		Args:
			content: 文件内容
			path: 存储路径
			content_type: 文件内容类型

		Returns:
			str: 存储URL
		"""
		try:
			# 构建完整的文件路径
			file_path = self._resolve_path(path)

			# 确保目录存在
			os.makedirs(os.path.dirname(file_path), exist_ok=True)

			# 写入文件
			with open(file_path, 'wb') as f:
				f.write(content)

			# 返回本地文件路径作为URL
			return f"file://{file_path}"

		except Exception as e:
			logger.error(f"文件上传失败: {str(e)}")
			raise

	def download (self, path: str) -> Optional[bytes]:
		"""
		从存储下载文件

		Args:
			path: 存储路径

		Returns:
			Optional[bytes]: 文件内容
		"""
		try:
			file_path = self._resolve_path(path)

			if not os.path.exists(file_path):
				return None

			with open(file_path, 'rb') as f:
				return f.read()

		except Exception as e:
			logger.error(f"文件下载失败: {str(e)}")
			return None

	def delete (self, path: str) -> bool:
		"""
		从存储删除文件

		Args:
			path: 存储路径

		Returns:
			bool: 是否删除成功
		"""
		try:
			file_path = self._resolve_path(path)

			if os.path.exists(file_path):
				os.remove(file_path)
				return True

			return False

		except Exception as e:
			logger.error(f"文件删除失败: {str(e)}")
			return False

	def exists (self, path: str) -> bool:
		"""
		检查文件是否存在

		Args:
			path: 存储路径

		Returns:
			bool: 文件是否存在
		"""
		try:
			file_path = self._resolve_path(path)
			return os.path.exists(file_path)

		except Exception as e:
			logger.error(f"检查文件存在性失败: {str(e)}")
			return False
