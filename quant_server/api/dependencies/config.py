# # quant_server/api/dependencies/config.py
# """
# 配置依赖模块
#
# 提供FastAPI依赖注入的配置管理功能，基于共享层的配置管理系统。
# 支持多环境配置、热重载、配置验证等功能。
#
# Author: 量化交易系统团队
# Version: 1.0.0
# """
#
# import logging
# from typing import Any, Dict, Optional, TypeVar, Generic
# from functools import lru_cache
# from contextlib import asynccontextmanager
#
# from fastapi import Depends
# from pydantic import BaseSettings, ValidationError
#
# from quant_server.shared.config.settings import (
# 	Settings,
# 	DatabaseConfig,
# 	RedisConfig,
# 	ApiConfig,
# 	TradeConfig,
# 	DataConfig,
# 	StrategyConfig,
# 	RiskConfig,
# 	LogConfig
# )
# from quant_server.shared.config.loader import ConfigLoader
# from quant_server.shared.config.validator import ConfigValidator
# from quant_server.core.exceptions.validation_exceptions import ConfigurationError
#
# logger = logging.getLogger(__name__)
#
# # 泛型类型变量
# T = TypeVar('T', bound=BaseSettings)
#
#
# class ConfigManager:
# 	"""配置管理器"""
#
# 	def __init__ (self):
# 		"""初始化配置管理器"""
# 		self._settings: Optional[Settings] = None
# 		self._loader = ConfigLoader()
# 		self._validator = ConfigValidator()
# 		logger.info("配置管理器初始化完成")
#
# 	@property
# 	def settings (self) -> Settings:
# 		"""
# 		获取全局设置实例
#
# 		Returns:
# 			Settings: 全局设置对象
#
# 		Raises:
# 			ConfigurationError: 配置未初始化
# 		"""
# 		if self._settings is None:
# 			raise ConfigurationError("配置未初始化")
# 		return self._settings
#
# 	async def initialize (self) -> bool:
# 		"""
# 		初始化配置管理器
#
# 		Returns:
# 			bool: 初始化是否成功
# 		"""
# 		try:
# 			# 加载配置
# 			config_data = await self._loader.load_all_configs()
#
# 			# 验证配置
# 			validation_result = await self._validator.validate_all(config_data)
# 			if not validation_result.is_valid:
# 				logger.error(f"配置验证失败: {validation_result.errors}")
# 				return False
#
# 			# 创建Settings实例
# 			self._settings = Settings(**config_data)
#
# 			# 验证环境特定的配置
# 			await self._validator.validate_environment(self._settings)
#
# 			logger.info(f"配置初始化成功，环境: {self._settings.ENVIRONMENT}")
# 			logger.debug(f"数据库配置: {self._settings.DATABASE.HOST}:{self._settings.DATABASE.PORT}")
#
# 			return True
#
# 		except ValidationError as e:
# 			logger.error(f"配置验证异常: {str(e)}", exc_info=True)
# 			raise ConfigurationError(f"配置验证失败: {e.errors()}")
# 		except Exception as e:
# 			logger.error(f"配置初始化失败: {str(e)}", exc_info=True)
# 			return False
#
# 	def get_database_config (self) -> DatabaseConfig:
# 		"""获取数据库配置"""
# 		return self.settings.DATABASE
#
# 	def get_redis_config (self) -> RedisConfig:
# 		"""获取Redis配置"""
# 		return self.settings.REDIS
#
# 	def get_api_config (self) -> ApiConfig:
# 		"""获取API配置"""
# 		return self.settings.API
#
# 	def get_trade_config (self) -> TradeConfig:
# 		"""获取交易配置"""
# 		return self.settings.TRADE
#
# 	def get_data_config (self) -> DataConfig:
# 		"""获取数据配置"""
# 		return self.settings.DATA
#
# 	def get_strategy_config (self) -> StrategyConfig:
# 		"""获取策略配置"""
# 		return self.settings.STRATEGY
#
# 	def get_risk_config (self) -> RiskConfig:
# 		"""获取风控配置"""
# 		return self.settings.RISK
#
# 	def get_log_config (self) -> LogConfig:
# 		"""获取日志配置"""
# 		return self.settings.LOGGING
#
# 	def get_config_by_path (self, path: str) -> Any:
# 		"""
# 		通过路径获取配置值
#
# 		Args:
# 			path: 配置路径，如 "DATABASE.HOST"
#
# 		Returns:
# 			Any: 配置值
#
# 		Raises:
# 			KeyError: 配置路径不存在
# 		"""
# 		parts = path.split('.')
# 		value = self.settings.dict()
#
# 		for part in parts:
# 			if part not in value:
# 				raise KeyError(f"配置路径不存在: {path}")
# 			value = value[part]
#
# 		return value
#
# 	async def reload_config (self) -> bool:
# 		"""
# 		重新加载配置
#
# 		Returns:
# 			bool: 重载是否成功
# 		"""
# 		try:
# 			logger.info("开始重新加载配置...")
#
# 			# 备份当前配置
# 			old_settings = self._settings
#
# 			# 重新加载
# 			config_data = await self._loader.load_all_configs()
# 			validation_result = await self._validator.validate_all(config_data)
#
# 			if not validation_result.is_valid:
# 				logger.error(f"配置重载验证失败: {validation_result.errors}")
# 				return False
#
# 			# 更新配置
# 			self._settings = Settings(**config_data)
#
# 			logger.info("配置重载成功")
#
# 			# 记录配置变更
# 			self._log_config_changes(old_settings, self._settings)
#
# 			return True
#
# 		except Exception as e:
# 			logger.error(f"配置重载失败: {str(e)}", exc_info=True)
# 			# 恢复旧配置
# 			self._settings = old_settings
# 			return False
#
# 	def _log_config_changes (self, old_settings: Settings, new_settings: Settings):
# 		"""记录配置变更"""
# 		old_dict = old_settings.dict() if old_settings else {}
# 		new_dict = new_settings.dict()
#
# 		# 简单的配置变更检测
# 		changed_keys = []
# 		for key, new_value in new_dict.items():
# 			old_value = old_dict.get(key)
# 			if old_value != new_value:
# 				changed_keys.append(key)
#
# 		if changed_keys:
# 			logger.info(f"配置已变更: {', '.join(changed_keys)}")
#
# 	def get_config_summary (self) -> Dict[str, Any]:
# 		"""
# 		获取配置摘要
#
# 		Returns:
# 			Dict[str, Any]: 配置摘要信息
# 		"""
# 		if not self._settings:
# 			return {"status": "未初始化"}
#
# 		return {
# 			"environment": self._settings.ENVIRONMENT,
# 			"debug": self._settings.DEBUG,
# 			"database": {
# 				"type": self._settings.DATABASE.TYPE,
# 				"host": self._settings.DATABASE.HOST,
# 				"port": self._settings.DATABASE.PORT,
# 				"name": self._settings.DATABASE.NAME,
# 				"pool_size": self._settings.DATABASE.POOL_SIZE
# 			},
# 			"api": {
# 				"host": self._settings.API.HOST,
# 				"port": self._settings.API.PORT,
# 				"cors_origins": self._settings.API.CORS_ORIGINS[:3],  # 只显示前3个
# 				"rate_limit": {
# 					"enabled": self._settings.API.RATE_LIMIT.ENABLED,
# 					"max_requests": self._settings.API.RATE_LIMIT.MAX_REQUESTS
# 				}
# 			}
# 		}
#
#
# class ConfigDependencies:
# 	"""配置依赖管理类"""
#
# 	def __init__ (self):
# 		"""初始化配置依赖"""
# 		self.manager = ConfigManager()
#
# 	async def get_settings (self) -> Settings:
# 		"""
# 		获取全局设置依赖
#
# 		Returns:
# 			Settings: 全局设置对象
# 		"""
# 		if self.manager.settings is None:
# 			# 如果配置未初始化，尝试初始化
# 			success = await self.manager.initialize()
# 			if not success:
# 				raise ConfigurationError("配置初始化失败")
#
# 		return self.manager.settings
#
# 	async def get_database_config (self) -> DatabaseConfig:
# 		"""获取数据库配置依赖"""
# 		settings = await self.get_settings()
# 		return settings.DATABASE
#
# 	async def get_api_config (self) -> ApiConfig:
# 		"""获取API配置依赖"""
# 		settings = await self.get_settings()
# 		return settings.API
#
# 	async def get_trade_config (self) -> TradeConfig:
# 		"""获取交易配置依赖"""
# 		settings = await self.get_settings()
# 		return settings.TRADE
#
# 	async def get_data_config (self) -> DataConfig:
# 		"""获取数据配置依赖"""
# 		settings = await self.get_settings()
# 		return settings.DATA
#
# 	async def get_config_by_path (self, path: str) -> Any:
# 		"""
# 		通过路径获取配置依赖
#
# 		Args:
# 			path: 配置路径
#
# 		Returns:
# 			Any: 配置值
# 		"""
# 		settings = await self.get_settings()
# 		# 使用manager的方法获取路径配置
# 		return self.manager.get_config_by_path(path)
#
#
# # 创建全局配置管理器
# _config_manager = ConfigManager()
#
# # 创建依赖实例
# _config_deps = ConfigDependencies()
#
# # 导出依赖函数
# get_settings = _config_deps.get_settings
# get_database_config = _config_deps.get_database_config
# get_api_config = _config_deps.get_api_config
# get_trade_config = _config_deps.get_trade_config
# get_data_config = _config_deps.get_data_config
# get_config_by_path = _config_deps.get_config_by_path
#
# # 导出类型注解
# SettingsDep = Depends(get_settings)
# DatabaseConfigDep = Depends(get_database_config)
# ApiConfigDep = Depends(get_api_config)
# TradeConfigDep = Depends(get_trade_config)
# DataConfigDep = Depends(get_data_config)
#
#
# # 缓存配置获取（性能优化）
# @lru_cache(maxsize=128)
# def get_cached_config (path: str) -> Any:
# 	"""
# 	获取缓存的配置值（适用于频繁访问的配置）
#
# 	Args:
# 		path: 配置路径
#
# 	Returns:
# 		Any: 配置值
# 	"""
# 	return _config_manager.get_config_by_path(path)
#
#
# @asynccontextmanager
# async def config_context ():
# 	"""
# 	配置上下文管理器
#
# 	用于需要临时修改配置的场景
# 	"""
# 	# 备份当前配置
# 	original_settings = _config_manager.settings
#
# 	try:
# 		yield _config_manager
# 	finally:
# 		# 恢复原始配置
# 		_config_manager._settings = original_settings