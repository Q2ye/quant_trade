# -*- coding: utf-8 -*-
"""
系统配置服务

提供配置读取、写入、类型转换等纯业务逻辑。
"""

import json
from typing import Dict, Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.repositories.system.config.config_repo import ConfigRepository


class ConfigService:
	"""系统配置服务 — 无状态纯计算"""

	def __init__ (self, session: AsyncSession):
		self._repo = ConfigRepository(session)

	async def get_all_configs (self, public_only: bool = False) -> List[Dict[str, Any]]:
		configs = await (self._repo.get_public_configs() if public_only else self._repo.get_all_configs())
		return [self._orm_to_dict(c) for c in configs]

	async def get_config (self, key: str) -> Optional[Dict[str, Any]]:
		config = await self._repo.get_by_key(key)
		return self._orm_to_dict(config) if config else None

	async def get_config_value (self, key: str, default: Any = None) -> Any:
		return await self._repo.get_config_value(key, default)

	async def set_config (
			self,
			key: str,
			value: Any,
			config_type: str = "string",
			description: str = "",
			is_public: bool = False,
			updated_by: str = None,
	) -> Dict[str, Any]:
		existing = await self._repo.get_by_key(key)
		if existing:
			updated = await self._repo.update_config(
				config_key=key, config_value=value, config_type=config_type,
				description=description, is_public=is_public, updated_by=updated_by,
			)
			return self._orm_to_dict(updated)
		created = await self._repo.create_config(
			config_key=key, config_value=value, config_type=config_type,
			description=description, is_public=is_public, created_by=updated_by, updated_by=updated_by,
		)
		return self._orm_to_dict(created)

	async def update_settings (self, settings: Dict[str, Any], updated_by: str = None) -> List[Dict[str, Any]]:
		results = []
		for key, value in settings.items():
			existing = await self._repo.get_by_key(key)
			if existing:
				updated = await self._repo.update_config(
					config_key=key, config_value=value, updated_by=updated_by,
				)
				results.append(self._orm_to_dict(updated))
			else:
				config_type = self._infer_type(value)
				created = await self._repo.create_config(
					config_key=key, config_value=value, config_type=config_type,
					created_by=updated_by, updated_by=updated_by,
				)
				results.append(self._orm_to_dict(created))
		return results

	async def delete_config (self, key: str) -> bool:
		return await self._repo.delete_config(key)

	@staticmethod
	def _orm_to_dict (config) -> Dict[str, Any]:
		return {
			"id": config.id,
			"config_key": config.config_key,
			"config_value": ConfigService._parse_value(config.config_value, config.config_type),
			"config_type": config.config_type,
			"description": config.description or "",
			"is_public": config.is_public,
			"created_by": config.created_by,
			"updated_by": config.updated_by,
			"created_at": config.created_at.isoformat() if config.created_at else None,
			"updated_at": config.updated_at.isoformat() if config.updated_at else None,
		}

	@staticmethod
	def _parse_value (raw: str, config_type: str) -> Any:
		if config_type == "int":
			return int(raw)
		elif config_type == "float":
			return float(raw)
		elif config_type == "bool":
			return raw.lower() in ("true", "1", "yes", "on")
		elif config_type == "json":
			try:
				return json.loads(raw)
			except (json.JSONDecodeError, TypeError):
				return raw
		return raw

	@staticmethod
	def _infer_type (value: Any) -> str:
		if isinstance(value, bool):
			return "bool"
		elif isinstance(value, int):
			return "int"
		elif isinstance(value, float):
			return "float"
		elif isinstance(value, (dict, list)):
			return "json"
		return "string"
