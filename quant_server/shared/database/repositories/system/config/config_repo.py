# -*- coding: utf-8 -*-
"""
系统配置Repository
位置：quant_server/shared/database/repositories/system/config_repo.py
职责：管理系统配置数据的数据访问
注意：配置数据用于系统参数管理、功能开关和运行时配置
"""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.system_models import SystemConfig
from shared.database.repositories.base import BaseRepository


class ConfigRepository(BaseRepository):
	"""系统配置仓库 - 负责系统配置数据的数据访问"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, SystemConfig)

	async def create_config (
			self,
			config_key: str,
			config_value: Any,
			config_type: str = "string",
			description: Optional[str] = None,
			is_public: bool = False,
			created_by: Optional[str] = None,
			updated_by: Optional[str] = None
	) -> SystemConfig:
		"""
		创建系统配置

		Args:
			config_key: 配置键（唯一）
			config_value: 配置值
			config_type: 配置类型（string, int, float, bool, json）
			description: 配置描述（可选）
			is_public: 是否公开配置
			created_by: 创建人ID（可选）
			updated_by: 更新人ID（可选）

		Returns:
			SystemConfig: 创建的系统配置记录
		"""
		try:
			# 检查配置键是否已存在
			existing_config = await self.get_by_key(config_key)
			if existing_config:
				raise ValueError(f"配置键 '{config_key}' 已存在")

			# 创建系统配置记录
			system_config = SystemConfig(
				config_key=config_key,
				config_value=str(config_value),
				config_type=config_type,
				description=description,
				is_public=is_public,
				created_by=created_by,
				updated_by=updated_by
			)

			self.session.add(system_config)
			await self.session.commit()
			await self.session.refresh(system_config)

			return system_config
		except Exception as e:
			await self.session.rollback()
			raise Exception(f"创建系统配置失败: {str(e)}")

	async def get_by_key (
			self,
			config_key: str
	) -> Optional[SystemConfig]:
		"""
		根据配置键获取配置

		Args:
			config_key: 配置键

		Returns:
			SystemConfig: 系统配置记录，如果不存在则返回None
		"""
		try:
			query = select(SystemConfig).where(SystemConfig.config_key == config_key)
			result = await self.session.execute(query)
			return result.scalar_one_or_none()
		except Exception as e:
			raise Exception(f"获取配置失败: {str(e)}")

	async def get_config_value (
			self,
			config_key: str,
			default_value: Any = None
	) -> Any:
		"""
		获取配置值

		Args:
			config_key: 配置键
			default_value: 默认值（如果配置不存在）

		Returns:
			配置值，如果配置不存在则返回默认值
		"""
		try:
			config = await self.get_by_key(config_key)
			if config:
				return self._convert_value_type(config.config_value, config.config_type)
			return default_value
		except Exception as e:
			raise Exception(f"获取配置值失败: {str(e)}")

	async def update_config (
			self,
			config_key: str,
			config_value: Any,
			config_type: Optional[str] = None,
			description: Optional[str] = None,
			is_public: Optional[bool] = None,
			updated_by: Optional[str] = None
	) -> Optional[SystemConfig]:
		"""
		更新系统配置

		Args:
			config_key: 配置键
			config_value: 新的配置值
			config_type: 新的配置类型（可选）
			description: 新的配置描述（可选）
			is_public: 是否公开配置（可选）
			updated_by: 更新人ID（可选）

		Returns:
			SystemConfig: 更新的系统配置记录，如果配置不存在则返回None
		"""
		try:
			config = await self.get_by_key(config_key)
			if not config:
				return None

			config.config_value = str(config_value)
			config.updated_by = updated_by
			config.updated_at = datetime.now(timezone.utc)

			if config_type is not None:
				config.config_type = config_type
			if description is not None:
				config.description = description
			if is_public is not None:
				config.is_public = is_public

			await self.session.commit()
			await self.session.refresh(config)

			return config
		except Exception as e:
			await self.session.rollback()
			raise Exception(f"更新系统配置失败: {str(e)}")

	async def delete_config (
			self,
			config_key: str
	) -> bool:
		"""
		删除系统配置

		Args:
			config_key: 配置键

		Returns:
			bool: 是否成功删除
		"""
		try:
			config = await self.get_by_key(config_key)
			if not config:
				return False

			await self.session.delete(config)
			await self.session.commit()

			return True
		except Exception as e:
			await self.session.rollback()
			raise Exception(f"删除系统配置失败: {str(e)}")

	async def get_all_configs (
			self,
			is_public: Optional[bool] = None,
			limit: int = 1000,
			offset: int = 0
	) -> List[SystemConfig]:
		"""
		获取所有系统配置

		Args:
			is_public: 是否公开配置过滤（可选）
			limit: 返回数量限制
			offset: 偏移量

		Returns:
			系统配置列表
		"""
		try:
			query = select(SystemConfig)

			if is_public is not None:
				query = query.where(SystemConfig.is_public == is_public)

			query = query.order_by(SystemConfig.config_key).offset(offset).limit(limit)
			result = await self.session.execute(query)
			configs = result.scalars().all()

			return configs
		except Exception as e:
			raise Exception(f"获取所有系统配置失败: {str(e)}")

	async def get_public_configs (
			self,
			limit: int = 1000,
			offset: int = 0
	) -> List[SystemConfig]:
		"""
		获取公开的系统配置

		Args:
			limit: 返回数量限制
			offset: 偏移量

		Returns:
			公开的系统配置列表
		"""
		try:
			return await self.get_all_configs(is_public=True, limit=limit, offset=offset)
		except Exception as e:
			raise Exception(f"获取公开系统配置失败: {str(e)}")

	async def search_configs (
			self,
			keyword: str,
			config_type: Optional[str] = None,
			is_public: Optional[bool] = None,
			limit: int = 100,
			offset: int = 0
	) -> List[SystemConfig]:
		"""
		搜索系统配置

		Args:
			keyword: 搜索关键词
			config_type: 配置类型过滤（可选）
			is_public: 是否公开配置过滤（可选）
			limit: 返回数量限制
			offset: 偏移量

		Returns:
			匹配的系统配置列表
		"""
		try:
			query = select(SystemConfig).where(
				SystemConfig.config_key.ilike(f"%{keyword}%") |
				SystemConfig.description.ilike(f"%{keyword}%")
			)

			if config_type:
				query = query.where(SystemConfig.config_type == config_type)
			if is_public is not None:
				query = query.where(SystemConfig.is_public == is_public)

			query = query.order_by(SystemConfig.config_key).offset(offset).limit(limit)
			result = await self.session.execute(query)
			configs = result.scalars().all()

			return configs
		except Exception as e:
			raise Exception(f"搜索系统配置失败: {str(e)}")

	async def get_config_statistics (
			self
	) -> Dict[str, Any]:
		"""
		获取系统配置统计信息

		Returns:
			统计信息字典
		"""
		try:
			# 按配置类型统计
			type_stats_query = select(
				SystemConfig.config_type,
				func.count().label('count')
			).group_by(SystemConfig.config_type)

			type_result = await self.session.execute(type_stats_query)
			type_stats = [
				{"config_type": row.config_type, "count": row.count}
				for row in type_result
			]

			# 按公开状态统计
			public_stats_query = select(
				SystemConfig.is_public,
				func.count().label('count')
			).group_by(SystemConfig.is_public)

			public_result = await self.session.execute(public_stats_query)
			public_stats = [
				{"is_public": row.is_public, "count": row.count}
				for row in public_result
			]

			# 总配置数量
			total_query = select(func.count()).select_from(SystemConfig)
			total_result = await self.session.execute(total_query)
			total_count = total_result.scalar() or 0

			return {
				"total_configs": total_count,
				"type_distribution": type_stats,
				"public_distribution": public_stats
			}
		except Exception as e:
			raise Exception(f"获取系统配置统计失败: {str(e)}")

	async def batch_update_configs (
			self,
			config_updates: List[Dict[str, Any]],
			updated_by: Optional[str] = None
	) -> List[SystemConfig]:
		"""
		批量更新系统配置

		Args:
			config_updates: 配置更新列表，每个元素包含 config_key 和 config_value
			updated_by: 更新人ID（可选）

		Returns:
			更新的系统配置列表
		"""
		try:
			updated_configs = []

			for update in config_updates:
				config_key = update.get("config_key")
				config_value = update.get("config_value")

				if not config_key:
					continue

				config = await self.update_config(
					config_key=config_key,
					config_value=config_value,
					updated_by=updated_by
				)

				if config:
					updated_configs.append(config)

			return updated_configs
		except Exception as e:
			raise Exception(f"批量更新系统配置失败: {str(e)}")

	async def validate_config (
			self,
			config_key: str,
			config_value: Any,
			config_type: str
	) -> Dict[str, Any]:
		"""
		验证配置值

		Args:
			config_key: 配置键
			config_value: 配置值
			config_type: 配置类型

		Returns:
			验证结果字典
		"""
		try:
			# 基本验证
			if not config_key or not isinstance(config_key, str):
				return {"valid": False, "error": "配置键必须是非空字符串"}

			if len(config_key) > 100:
				return {"valid": False, "error": "配置键长度不能超过100个字符"}

			# 类型验证
			try:
				self._convert_value_type(config_value, config_type)
			except (ValueError, TypeError) as e:
				return {"valid": False, "error": f"配置值类型验证失败: {str(e)}"}

			return {"valid": True, "message": "配置验证通过"}
		except Exception as e:
			return {"valid": False, "error": f"配置验证异常: {str(e)}"}

	@staticmethod
	def _convert_value_type (value: Any, config_type: str) -> Any:
		"""
		转换配置值类型

		Args:
			value: 原始值
			config_type: 配置类型

		Returns:
			转换后的值
		"""
		try:
			if config_type == "string":
				return str(value)
			elif config_type == "int":
				return int(value)
			elif config_type == "float":
				return float(value)
			elif config_type == "bool":
				if isinstance(value, str):
					return value.lower() in ("true", "1", "yes", "on")
				return bool(value)
			elif config_type == "json":
				if isinstance(value, str):
					import json
					return json.loads(value)
				return value
			else:
				return str(value)
		except (ValueError, TypeError) as e:
			raise ValueError(f"无法将值 '{value}' 转换为类型 '{config_type}': {str(e)}")
