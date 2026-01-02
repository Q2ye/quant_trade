# -*- coding: utf-8 -*-
"""
# 系统配置数据仓库
# 位置：quant_server/shared/database/repositories/config_repo.py
# 职责：管理系统配置、参数、常量等数据访问
# 注意：配置数据通常为键值对形式，支持分组和版本管理
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func, text
from sqlalchemy.orm import selectinload, joinedload

from quant_server.shared.database.repositories.base import BaseRepository


# 配置项实体模型
class ConfigItem:
	"""配置项实体类"""

	def __init__ (
			self,
			key: str,
			value: Any,
			config_type: str = "string",
			group: str = "default",
			description: str = None,
			version: int = 1,
			is_encrypted: bool = False,
			is_readonly: bool = False
	):
		"""
		初始化配置项

		Args:
			key: 配置键
			value: 配置值
			config_type: 配置类型（string, int, float, bool, json, list, dict）
			group: 配置分组
			description: 配置描述
			version: 配置版本
			is_encrypted: 是否加密存储
			is_readonly: 是否只读
		"""
		self.key = key
		self.value = value
		self.config_type = config_type
		self.group = group
		self.description = description
		self.version = version
		self.is_encrypted = is_encrypted
		self.is_readonly = is_readonly
		self.created_at = datetime.utcnow()
		self.updated_at = self.created_at

	def validate (self) -> bool:
		"""验证配置值类型"""
		try:
			if self.config_type == "string":
				return isinstance(self.value, str)
			elif self.config_type == "int":
				return isinstance(self.value, int)
			elif self.config_type == "float":
				return isinstance(self.value, (int, float))
			elif self.config_type == "bool":
				return isinstance(self.value, bool)
			elif self.config_type == "json":
				import json
				json.dumps(self.value)  # 验证是否为有效JSON
				return True
			elif self.config_type == "list":
				return isinstance(self.value, list)
			elif self.config_type == "dict":
				return isinstance(self.value, dict)
			else:
				return True  # 未知类型不验证
		except:
			return False

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"key": self.key,
			"value": self.value,
			"type": self.config_type,
			"group": self.group,
			"description": self.description,
			"version": self.version,
			"is_encrypted": self.is_encrypted,
			"is_readonly": self.is_readonly,
			"created_at": self.created_at,
			"updated_at": self.updated_at
		}


class ConfigRepository:
	"""系统配置数据仓库 - 负责配置数据的管理和访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		# 内存缓存配置（热配置）
		self._config_cache: Dict[str, ConfigItem] = {}
		self._group_cache: Dict[str, Dict[str, ConfigItem]] = {}

	# ==================== 配置项操作 ====================

	async def get_config (self, key: str, use_cache: bool = True) -> Optional[Any]:
		"""
		获取配置值

		Args:
			key: 配置键
			use_cache: 是否使用缓存

		Returns:
			配置值或None
		"""
		# 首先尝试内存缓存
		if use_cache and key in self._config_cache:
			return self._config_cache[key].value

		# 查询数据库
		query = text("""
                     SELECT value, config_type, is_encrypted
                     FROM system_config
                     WHERE key = :key
                       AND is_active = true
		             """)

		result = await self.session.execute(query, {"key": key})
		row = result.fetchone()

		if not row:
			return None

		value = row.value
		config_type = row.config_type

		# 如果是加密的，需要解密
		if row.is_encrypted:
			value = await self._decrypt_value(value)

		# 类型转换
		value = self._convert_value_type(value, config_type)

		# 更新缓存
		if use_cache:
			config_item = ConfigItem(
				key=key,
				value=value,
				config_type=config_type
			)
			self._config_cache[key] = config_item

		return value

	async def set_config (
			self,
			key: str,
			value: Any,
			config_type: str = "string",
			group: str = "default",
			description: str = None,
			is_encrypted: bool = False,
			is_readonly: bool = False
	) -> bool:
		"""
		设置配置项

		Args:
			key: 配置键
			value: 配置值
			config_type: 配置类型
			group: 配置分组
			description: 配置描述
			is_encrypted: 是否加密
			is_readonly: 是否只读

		Returns:
			是否成功
		"""
		# 验证配置项
		config_item = ConfigItem(
			key=key,
			value=value,
			config_type=config_type,
			group=group,
			description=description,
			is_encrypted=is_encrypted,
			is_readonly=is_readonly
		)

		if not config_item.validate():
			raise ValueError(f"Invalid configuration value for key: {key}")

		# 准备存储值
		store_value = value

		if config_type == "json":
			import json
			store_value = json.dumps(value)
		elif config_type == "bool":
			store_value = "true" if value else "false"

		# 如果需要加密
		if is_encrypted:
			store_value = await self._encrypt_value(str(store_value))

		# 使用upsert模式
		upsert_query = text("""
                            INSERT INTO system_config (key, value, config_type, config_group,
                                                       description, version, is_encrypted, is_readonly,
                                                       is_active, created_at, updated_at)
                            VALUES (:key, :value, :config_type, :group,
                                    :description, 1, :is_encrypted, :is_readonly,
                                    true, NOW(), NOW())
                            ON CONFLICT (key)
                                DO UPDATE SET value        = EXCLUDED.value,
                                              config_type  = EXCLUDED.config_type,
                                              config_group = EXCLUDED.config_group,
                                              description  = EXCLUDED.description,
                                              is_encrypted = EXCLUDED.is_encrypted,
                                              is_readonly  = EXCLUDED.is_readonly,
                                              version      = system_config.version + 1,
                                              updated_at   = NOW()
		                    """)

		await self.session.execute(
			upsert_query,
			{
				"key": key,
				"value": store_value,
				"config_type": config_type,
				"group": group,
				"description": description,
				"is_encrypted": is_encrypted,
				"is_readonly": is_readonly
			}
		)

		# 更新缓存
		if key in self._config_cache:
			self._config_cache[key] = config_item

		# 更新分组缓存
		if group in self._group_cache and key in self._group_cache[group]:
			self._group_cache[group][key] = config_item

		return True

	async def delete_config (self, key: str, soft_delete: bool = True) -> bool:
		"""
		删除配置项

		Args:
			key: 配置键
			soft_delete: 是否软删除（标记为不活跃）

		Returns:
			是否成功
		"""
		if soft_delete:
			delete_query = text("""
                                UPDATE system_config
                                SET is_active  = false,
                                    updated_at = NOW()
                                WHERE key = :key
			                    """)
		else:
			delete_query = text("DELETE FROM system_config WHERE key = :key")

		result = await self.session.execute(delete_query, {"key": key})

		# 清理缓存
		if key in self._config_cache:
			# 从分组缓存中移除
			config_item = self._config_cache[key]
			if config_item.group in self._group_cache:
				if key in self._group_cache[config_item.group]:
					del self._group_cache[config_item.group][key]

			# 从主缓存中移除
			del self._config_cache[key]

		return result.rowcount > 0

	async def exists_config (self, key: str) -> bool:
		"""
		检查配置项是否存在

		Args:
			key: 配置键

		Returns:
			是否存在
		"""
		if key in self._config_cache:
			return True

		query = text("""
                     SELECT 1
                     FROM system_config
                     WHERE key = :key
                       AND is_active = true
                     LIMIT 1
		             """)

		result = await self.session.execute(query, {"key": key})
		return result.fetchone() is not None

	# ==================== 分组配置操作 ====================

	async def get_config_group (self, group: str, use_cache: bool = True) -> Dict[str, Any]:
		"""
		获取分组的所有配置

		Args:
			group: 分组名称
			use_cache: 是否使用缓存

		Returns:
			分组配置字典
		"""
		# 首先尝试分组缓存
		if use_cache and group in self._group_cache:
			return {k: v.value for k, v in self._group_cache[group].items()}

		# 查询数据库
		query = text("""
                     SELECT key, value, config_type, is_encrypted
                     FROM system_config
                     WHERE config_group = :group
                       AND is_active = true
		             """)

		result = await self.session.execute(query, {"group": group})
		rows = result.fetchall()

		config_dict = {}

		for row in rows:
			key = row.key
			value = row.value
			config_type = row.config_type

			# 如果是加密的，需要解密
			if row.is_encrypted:
				value = await self._decrypt_value(value)

			# 类型转换
			value = self._convert_value_type(value, config_type)

			config_dict[key] = value

			# 更新缓存
			if use_cache:
				config_item = ConfigItem(
					key=key,
					value=value,
					config_type=config_type,
					group=group
				)

				# 更新主缓存
				self._config_cache[key] = config_item

				# 更新分组缓存
				if group not in self._group_cache:
					self._group_cache[group] = {}
				self._group_cache[group][key] = config_item

		return config_dict

	async def set_config_group (
			self,
			group: str,
			config_dict: Dict[str, Any],
			config_type_map: Dict[str, str] = None
	) -> bool:
		"""
		批量设置分组配置

		Args:
			group: 分组名称
			config_dict: 配置字典
			config_type_map: 配置类型映射（可选）

		Returns:
			是否成功
		"""
		success = True

		for key, value in config_dict.items():
			config_type = "string"
			if config_type_map and key in config_type_map:
				config_type = config_type_map[key]
			elif isinstance(value, bool):
				config_type = "bool"
			elif isinstance(value, int):
				config_type = "int"
			elif isinstance(value, float):
				config_type = "float"
			elif isinstance(value, dict):
				config_type = "dict"
			elif isinstance(value, list):
				config_type = "list"

			try:
				result = await self.set_config(
					key=key,
					value=value,
					config_type=config_type,
					group=group
				)
				success = success and result
			except Exception as e:
				print(f"Failed to set config {key}: {e}")
				success = False

		return success

	async def delete_config_group (self, group: str, soft_delete: bool = True) -> int:
		"""
		删除分组的所有配置

		Args:
			group: 分组名称
			soft_delete: 是否软删除

		Returns:
			删除的配置项数量
		"""
		if soft_delete:
			delete_query = text("""
                                UPDATE system_config
                                SET is_active  = false,
                                    updated_at = NOW()
                                WHERE config_group = :group
			                    """)
		else:
			delete_query = text("DELETE FROM system_config WHERE config_group = :group")

		result = await self.session.execute(delete_query, {"group": group})

		# 清理缓存
		if group in self._group_cache:
			for key in self._group_cache[group]:
				if key in self._config_cache:
					del self._config_cache[key]
			del self._group_cache[group]

		return result.rowcount

	async def get_all_groups (self) -> List[str]:
		"""
		获取所有配置分组

		Returns:
			分组名称列表
		"""
		query = text("""
                     SELECT DISTINCT config_group
                     FROM system_config
                     WHERE is_active = true
                     ORDER BY config_group
		             """)

		result = await self.session.execute(query)
		return [row[0] for row in result.fetchall()]

	# ==================== 系统配置操作 ====================

	async def get_system_config (self) -> Dict[str, Any]:
		"""
		获取系统全局配置

		Returns:
			系统配置字典
		"""
		# 获取所有分组的配置
		groups = await self.get_all_groups()
		system_config = {}

		for group in groups:
			group_config = await self.get_config_group(group)
			system_config[group] = group_config

		return system_config

	async def reload_config_cache (self) -> bool:
		"""
		重新加载配置缓存

		Returns:
			是否成功
		"""
		try:
			# 清空缓存
			self._config_cache.clear()
			self._group_cache.clear()

			# 重新加载所有活跃配置
			query = text("""
                         SELECT key, value, config_type, config_group, is_encrypted
                         FROM system_config
                         WHERE is_active = true
			             """)

			result = await self.session.execute(query)
			rows = result.fetchall()

			for row in rows:
				key = row.key
				value = row.value
				config_type = row.config_type
				group = row.config_group

				# 如果是加密的，需要解密
				if row.is_encrypted:
					value = await self._decrypt_value(value)

				# 类型转换
				value = self._convert_value_type(value, config_type)

				# 创建配置项
				config_item = ConfigItem(
					key=key,
					value=value,
					config_type=config_type,
					group=group
				)

				# 添加到主缓存
				self._config_cache[key] = config_item

				# 添加到分组缓存
				if group not in self._group_cache:
					self._group_cache[group] = {}
				self._group_cache[group][key] = config_item

			return True
		except Exception as e:
			print(f"Failed to reload config cache: {e}")
			return False

	async def get_config_history (self, key: str, limit: int = 10) -> List[Dict[str, Any]]:
		"""
		获取配置历史记录

		Args:
			key: 配置键
			limit: 返回数量限制

		Returns:
			配置历史记录列表
		"""
		query = text("""
                     SELECT value,
                            config_type,
                            version,
                            created_at,
                            updated_at,
                            CASE WHEN is_encrypted THEN 'ENCRYPTED' ELSE value END as display_value
                     FROM system_config_history
                     WHERE key = :key
                     ORDER BY version DESC
                     LIMIT :limit
		             """)

		result = await self.session.execute(
			query,
			{"key": key, "limit": limit}
		)

		history = []
		for row in result.fetchall():
			history.append({
				"value": row.display_value,
				"type": row.config_type,
				"version": row.version,
				"created_at": row.created_at,
				"updated_at": row.updated_at
			})

		return history

	# ==================== 辅助方法 ====================

	def _convert_value_type (self, value: Any, config_type: str) -> Any:
		"""
		转换配置值类型

		Args:
			value: 原始值
			config_type: 配置类型

		Returns:
			转换后的值
		"""
		if value is None:
			return None

		try:
			if config_type == "string":
				return str(value)
			elif config_type == "int":
				return int(value)
			elif config_type == "float":
				return float(value)
			elif config_type == "bool":
				if isinstance(value, str):
					return value.lower() in ("true", "1", "yes", "y")
				return bool(value)
			elif config_type == "json":
				import json
				if isinstance(value, str):
					return json.loads(value)
				return value
			elif config_type == "list":
				if isinstance(value, str):
					import json
					return json.loads(value)
				elif isinstance(value, list):
					return value
				else:
					return [value]
			elif config_type == "dict":
				if isinstance(value, str):
					import json
					return json.loads(value)
				elif isinstance(value, dict):
					return value
				else:
					return {"value": value}
			else:
				return value
		except Exception as e:
			print(f"Failed to convert config value: {e}")
			return value

	async def _encrypt_value (self, value: str) -> str:
		"""
		加密配置值

		Args:
			value: 原始值

		Returns:
			加密后的值
		"""
		# 这里应该使用实际的加密算法
		# 示例：使用base64编码（实际应该使用AES等加密算法）
		import base64
		encoded = base64.b64encode(value.encode()).decode()
		return f"ENC:{encoded}"

	async def _decrypt_value (self, encrypted_value: str) -> str:
		"""
		解密配置值

		Args:
			encrypted_value: 加密值

		Returns:
			解密后的值
		"""
		if encrypted_value.startswith("ENC:"):
			import base64
			encoded = encrypted_value[4:]
			try:
				decoded = base64.b64decode(encoded).decode()
				return decoded
			except:
				return encrypted_value
		return encrypted_value

	# ==================== 配置验证操作 ====================

	async def validate_config (self, key: str, value: Any, config_type: str = None) -> Tuple[bool, str]:
		"""
		验证配置值

		Args:
			key: 配置键
			value: 配置值
			config_type: 配置类型（可选，自动检测）

		Returns:
			(是否有效, 错误信息)
		"""
		if config_type is None:
			# 自动检测类型
			if isinstance(value, bool):
				config_type = "bool"
			elif isinstance(value, int):
				config_type = "int"
			elif isinstance(value, float):
				config_type = "float"
			elif isinstance(value, dict):
				config_type = "dict"
			elif isinstance(value, list):
				config_type = "list"
			else:
				config_type = "string"

		try:
			config_item = ConfigItem(
				key=key,
				value=value,
				config_type=config_type
			)

			if not config_item.validate():
				return False, f"Invalid value type for config {key}"

			return True, ""
		except Exception as e:
			return False, str(e)