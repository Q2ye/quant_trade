"""
quant_server/main.py
量化交易系统主启动模块

使用结构化日志工具包，提供完整的上下文感知日志记录
"""
import logging

import asyncio
import contextvars
import signal
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Any

import uvicorn

from api import create_app
from core.engines.base.engine_base import EngineConfigEntity
# 导入系统核心组件和配置
from core.engines.system import (
	EventEngine, MainEngine, EngineRegistry
)
from core.events.system_events import SystemStartedEvent
from shared.config.config_manager import (
	get_config, Environment,
	reload_config, validate_config
)
# 导入结构化日志工具包
from utils.core_utils.logging_utils import (
	# 基础类型和枚举
	LogLevel, LogFormat, ColorMode,

	# 日志记录器
	get_logger,  # 上下文管理
	get_context_manager, HandlerFactory, with_context,  # 格式化器
	# 便捷函数
	info, error, log_performance,

	# 管理函数
	init_logging, shutdown_logging,
	get_global_log_manager,  # 配置
)

# 全局上下文变量
_request_context = contextvars.ContextVar('request_context', default={})
logger = get_logger(__name__)


@dataclass
class ModuleConfig:
	"""模块配置 - 基于 settings.py 的模块化配置"""
	name: str
	enabled: bool = True
	auto_start: bool = True
	dependencies: List[str] = field(default_factory=list)
	config: Dict[str, Any] = field(default_factory=dict)

	@with_context(module="module_config", source="config_loader")
	def validate(self) -> bool:
		"""验证模块配置"""
		if not self.name:
			logger.error("模块名称不能为空")
			return False

		logger.debug(f"模块配置验证通过: {self.name}", extra={
			"enabled": self.enabled,
			"dependencies": self.dependencies
		})
		return True


@dataclass
class StartupConfig:
	"""启动配置 - 基于 settings.py 的完整配置"""

	def __init__(self, config_path: Optional[str] = None):
		"""初始化启动配置"""
		# 使用指定路径加载配置，路径为空时自动发现 config.yaml
		self.config_manager = reload_config(config_path)
		# 使用 with_context 装饰器记录配置加载
		self._load_config(config_path)

	@with_context(operation="load_startup_config", source="config_manager")
	def _load_config(self, _config_path: Optional[str] = None):
		"""加载配置"""
		# 基础设置
		self.settings = self.config_manager.settings

		# 使用ConfigManager的get_config方法获取服务器配置
		config_data = self.config_manager.get_config("server")

		# 应用配置
		self._apply_config_data(config_data)

		# 记录配置来源
		logger.info("配置加载完成，使用统一配置管理器")

	@with_context(operation="apply_config_data", source="config_manager")
	def _apply_config_data(self, config_data: Dict[str, Any]):
		"""应用配置数据"""
		# 基础配置
		self.system_name = config_data.get('name', self.settings.APP_NAME)
		self.version = config_data.get('version', self.settings.APP_VERSION)
		self.mode = config_data.get('env', self.settings.ENVIRONMENT.value)

		# 更新环境模式
		env_map = {
			"development": Environment.DEVELOPMENT,
			"test": Environment.TESTING,
			"production": Environment.PRODUCTION
		}
		self.settings.ENVIRONMENT = env_map.get(self.mode, Environment.DEVELOPMENT)

		# 服务器配置
		self.host = config_data.get('server.host', self.settings.API.HOST)
		self.port = config_data.get('server.port', self.settings.API.PORT)
		self.workers = config_data.get('server.workers', 1)

		# 引擎配置
		self.auto_start_main_engine = config_data.get('engines.auto_start_main_engine', True)
		self.auto_start_event_engine = config_data.get('engines.auto_start_event_engine', True)
		self.max_workers = config_data.get('engines.max_workers', 10)
		self.queue_size = config_data.get('engines.queue_size', 10000)

		# 功能配置
		self.enable_web_socket = config_data.get('features.enable_web_socket', True)
		self.enable_monitoring = config_data.get('features.enable_monitoring', True)
		self.enable_health_check = config_data.get('features.enable_health_check', True)
		self.shutdown_timeout = config_data.get('features.shutdown_timeout', 30.0)
		self.log_level = config_data.get('log.level', self.settings.LOG.LEVEL)

		# 模块配置
		self.enabled_modules: List[str] = []
		self.module_configs: Dict[str, ModuleConfig] = {}

		# 获取模块配置
		modules_config = config_data.get('modules', {})
		for module_name, module_data in modules_config.items():
			if module_data.get('enabled', True):
				self.enabled_modules.append(module_name)

				module_config = ModuleConfig(
					name=module_name,
					enabled=module_data.get('enabled', True),
					auto_start=module_data.get('auto_start', True),
					dependencies=module_data.get('dependencies', []),
					config=module_data.get('config', {})
				)
				self.module_configs[module_name] = module_config

		logger.info("配置加载完成", extra={
			"system_name": self.system_name,
			"version": self.version,
			"mode": self.mode,
			"enabled_modules": self.enabled_modules
		})

	@with_context(operation="apply_default_config", source="config_loader")
	def _apply_default_config(self):
		"""应用默认配置"""
		# 基础配置
		self.system_name = self.settings.APP_NAME
		self.version = self.settings.APP_VERSION
		self.mode = self.settings.ENVIRONMENT.value

		# 服务器配置
		self.host = self.settings.API.HOST
		self.port = self.settings.API.PORT
		self.workers = 1

		# 引擎配置
		self.auto_start_main_engine = True
		self.auto_start_event_engine = True
		self.max_workers = 10
		self.queue_size = 10000

		# 功能配置
		self.enable_web_socket = True
		self.enable_monitoring = True
		self.enable_health_check = True
		self.shutdown_timeout = 30.0
		self.log_level = self.settings.LOG.LEVEL

		# 模块配置 - 默认启用所有模块
		default_modules = [
			"data", "strategy", "trade", "backtest",
			"account", "analysis", "monitor", "system", "risk",
			"market",
		]
		self.enabled_modules = default_modules
		self.module_configs = {}

		for module_name in default_modules:
			self.module_configs[module_name] = ModuleConfig(
				name=module_name,
				enabled=True,
				auto_start=True,
				dependencies=[],
				config={}
			)

		logger.info("使用默认配置")

	def get_system_config(self) -> Dict[str, Any]:
		"""获取系统配置字典"""
		return {
			"system": {
				"name": self.system_name,
				"version": self.version,
				"mode": self.mode,
				"debug": self.settings.DEBUG,
				"host": self.host,
				"port": self.port,
				"workers": self.workers
			},
			"engines": {
				"auto_start_main_engine": self.auto_start_main_engine,
				"auto_start_event_engine": self.auto_start_event_engine,
				"max_workers": self.max_workers,
				"queue_size": self.queue_size
			},
			"features": {
				"enable_web_socket": self.enable_web_socket,
				"enable_monitoring": self.enable_monitoring,
				"enable_health_check": self.enable_health_check
			},
			"modules": {name: {
				"enabled": module.enabled,
				"auto_start": module.auto_start,
				"dependencies": module.dependencies,
				"config": module.config
			} for name, module in self.module_configs.items()},
			"settings": {
				"database": {
					"type": self.settings.DATABASE.TYPE.value,
					"host": self.settings.DATABASE.HOST,
					"port": self.settings.DATABASE.PORT,
					"name": self.settings.DATABASE.NAME
				},
				"redis": {
					"enabled": self.settings.REDIS.ENABLED,
					"host": self.settings.REDIS.HOST,
					"port": self.settings.REDIS.PORT
				},
				"trade": {
					"simulated_trading": self.settings.TRADE.SIMULATED_TRADING
				}
			}
		}


class QuantServer:
	"""量化交易系统主服务器

	使用结构化日志工具包，提供完整的上下文感知日志记录
	"""

	def __init__(self, config_path: Optional[str] = None):
		"""初始化服务器

		Args:
			config_path: 配置文件路径
		"""
		# 初始化请求上下文
		self.request_id = f"server_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
		_request_context.set({"request_id": self.request_id})

		# 设置启动时间
		self.startup_time = datetime.now()

		# 加载配置
		with get_context_manager().context_manager(
				request_id=self.request_id,
				operation="server_init",
				source="main_server"
		):
			self.logger = get_logger(__name__)
			self.logger.info("量化交易服务器初始化开始")

			self.config = StartupConfig(config_path)

			# 初始化日志系统
			self.setup_logging()

			# 验证配置
			if not validate_config():
				self.logger.warning("配置验证失败，但继续启动...")

			# 系统组件
			self.app = None
			self.main_engine: Optional[MainEngine] = None
			self.event_engine: Optional[EventEngine] = None
			self.engine_registry: Optional[EngineRegistry] = None

			# 模块管理
			self.enabled_modules: Set[str] = set(self.config.enabled_modules)
			self.loaded_modules: Dict[str, Any] = {}

			# 系统状态
			self.is_running: bool = False

			# 打印配置信息
			self._log_configuration()

			self.logger.info("量化交易服务器初始化完成", extra={
				"environment": self.config.mode,
				"startup_time": self.startup_time.isoformat()
			})

	@with_context(operation="setup_logging", source="main_server")
	def setup_logging(self):
		"""设置日志系统"""
		# 从 ConfigLoader 获取日志配置
		log_config = {
			"level": LogLevel(self.config.config_manager.get("settings.LOG.LEVEL", "INFO").upper()),
			"format": LogFormat.JSON if self.config.mode == "production" else LogFormat.TEXT,
			"color_mode": ColorMode.NEVER if self.config.mode == "production" else ColorMode.AUTO,
			"async_enabled": True,
			"handlers": [],
			"filters": []
		}

		# 初始化日志系统
		init_logging(log_config)

		# StructuredLogger.__init__ 在首次 get_logger('') 时会自动添加一个
		# 无 formatter 的默认 StreamHandler，与 init_logging 添加的 console handler
		# 都输出到 stdout 导致每条日志显示两行。此处移除多余的默认 handler。
		import logging as _logging
		_root = _logging.getLogger('')
		for _h in list(_root.handlers):
			if not _h.formatter:
				_root.removeHandler(_h)

		# 添加文件日志处理器（按天轮转，保留30天）
		import os as _os
		_log_dir = _os.path.join(_os.path.dirname(__file__), 'logs')
		file_handler = HandlerFactory.create_timed_file_handler(
			filename=_os.path.join(_log_dir, 'quant_server.log'),
			level=LogLevel.DEBUG,
			when='midnight',
			backup_count=30
		)
		# 设置与控制台一致的格式化器（复用上方已 import 的 _logging）
		file_handler.setFormatter(_logging.Formatter(
			'%(asctime)s | %(process)-6d | %(threadName)-20s | %(levelname)-8s | %(name)s | %(message)s',
			datefmt='%Y-%m-%d %H:%M:%S'
		))
		root_logger = get_logger("")
		root_logger.add_handler("file", file_handler)

		# 获取日志管理器并记录初始化
		log_manager = get_global_log_manager()
		logger.info("日志系统初始化完成", extra={
			"level": log_config["level"].value,
			"format": log_config["format"].value,
			"async_enabled": True,
			"log_dir": _log_dir
		})

		# 记录日志管理器统计
		stats = log_manager.get_all_stats()
		logger.debug("日志管理器统计", extra={"stats": stats})

	@with_context(operation="log_configuration", source="main_server")
	def _log_configuration(self):
		"""记录配置信息"""
		# 获取系统配置（用于日志记录）
		self.config.get_system_config()

		logger.info("=" * 80)
		logger.info("📦 系统配置信息", extra={"system_name": self.config.system_name})
		logger.info("🔧 基本配置", extra={
			"version": self.config.version,
			"environment": self.config.mode,
			"debug": self.config.settings.DEBUG
		})
		logger.info("🌐 服务器配置", extra={
			"host": self.config.host,
			"port": self.config.port,
			"workers": self.config.workers
		})
		logger.info("💾 数据库配置", extra={
			"type": self.config.settings.DATABASE.TYPE.value,
			"host": self.config.settings.DATABASE.HOST,
			"port": self.config.settings.DATABASE.PORT,
			"name": self.config.settings.DATABASE.NAME
		})
		logger.info("📡 Redis配置", extra={
			"enabled": self.config.settings.REDIS.ENABLED,
			"host": self.config.settings.REDIS.HOST,
			"port": self.config.settings.REDIS.PORT
		})
		logger.info("💹 交易配置", extra={
			"mode": "模拟交易" if self.config.settings.TRADE.SIMULATED_TRADING else "实盘交易"
		})
		logger.info("📊 启用模块", extra={"modules": list(self.enabled_modules)})
		logger.info("=" * 80)

	@log_performance(operation="initialize_system", level=LogLevel.INFO)
	async def initialize(self) -> bool:
		"""初始化系统

		Returns:
			bool: 初始化是否成功
		"""
		with get_context_manager().context_manager(
				operation="system_initialization",
				stage="startup"
		):
			try:
				logger.info("开始初始化量化交易系统...")

				# 1. 初始化数据库
				from shared.database.session import initialize_database
				if not await initialize_database():
					raise RuntimeError("数据库初始化失败")

				# 2. 初始化FastAPI应用
				await self._initialize_api_app()

				# 2.1 初始化API层数据库依赖
				await self._initialize_api_database()

				# 3. 初始化事件引擎
				if self.config.auto_start_event_engine:
					await self._initialize_event_engine()

				# 3.5 初始化后台任务执行器（依赖事件引擎用于跨线程桥接）
				await self._initialize_background_executor()

				# 4. 初始化主引擎
				if self.config.auto_start_main_engine:
					await self._initialize_main_engine()

				# 5. 加载和初始化模块
				await self._initialize_modules()

				# 6. 注册生命周期事件
				await self._register_lifecycle_events()

				logger.info("量化交易系统初始化完成")
				return True

			except Exception as e:
				logger.exception("系统初始化失败", exception=e)
				return False

	@log_performance(operation="initialize_api_app", level=LogLevel.DEBUG)
	async def _initialize_api_app(self) -> None:
		"""初始化FastAPI应用"""
		with get_context_manager().context_manager(
				operation="api_app_initialization",
				component="fastapi"
		):
			logger.info("初始化FastAPI应用...")

			# 使用配置创建FastAPI应用
			self.app = create_app(
				title=self.config.system_name,
				version=self.config.version,
				description="量化交易平台API",
				docs_url="/docs" if self.config.mode != "production" else None,
				enabled_modules=self.config.enabled_modules,
				cors_origins=self.config.settings.API.CORS_ORIGINS,
			)

			logger.info("FastAPI应用初始化完成", extra={
				"title": self.config.system_name,
				"version": self.config.version,
				"docs_url": "/docs" if self.config.mode != "production" else None,
				"cors_origins_count": len(self.config.settings.API.CORS_ORIGINS)
			})

	@log_performance(operation="initialize_api_database", level=LogLevel.DEBUG)
	async def _initialize_api_database(self) -> None:
		"""初始化API层数据库依赖"""
		with get_context_manager().context_manager(
				operation="api_database_initialization",
				component="database"
		):
			logger.info("初始化API层数据库依赖...")

			try:
				from api.dependencies.database import initialize_api_database
				result = await initialize_api_database()

				if result:
					logger.info("API层数据库依赖初始化成功")
				else:
					logger.warning("API层数据库依赖初始化失败，但继续启动...")

			except Exception as e:
				logger.error(f"API层数据库依赖初始化异常: {str(e)}", exc_info=True)
		# 不阻塞启动，因为共享层数据库已经初始化成功

	@log_performance(operation="initialize_event_engine", level=LogLevel.DEBUG)
	async def _initialize_event_engine(self) -> None:
		"""初始化事件引擎"""
		with get_context_manager().context_manager(
				operation="event_engine_initialization",
				component="event_engine"
		):
			logger.info("初始化事件引擎...")

			try:
				# 创建事件引擎配置
				event_config = EngineConfigEntity(
					name="event_engine",
					engine_type="event",
					auto_start=True,
					config={
						"max_workers": self.config.max_workers,
						"queue_size": self.config.queue_size,
						"log_level": self.config.log_level
					}
				)

				# 创建事件引擎实例
				self.event_engine = EventEngine(event_config)
				await self.event_engine.start()

				# 注入到 API 依赖层
				from api.dependencies.event_engine import set_event_engine
				set_event_engine(self.event_engine)

				logger.info("事件引擎初始化完成", extra={
					"max_workers": self.config.max_workers,
					"queue_size": self.config.queue_size
				})

			except Exception as e:
				logger.exception("事件引擎初始化失败", exception=e)
				raise

	async def _initialize_background_executor(self) -> None:
		"""初始化后台任务执行器（多池线程池）"""
		try:
			from shared.utils.background_executor import (
				BackgroundTaskExecutor, set_background_executor,
			)
			bg_cfg = self.config.config_manager.get("engines.background_executor", {}) or {}
			pools_cfg = bg_cfg.get("pools", {})
			executor = BackgroundTaskExecutor(
				pools_config=pools_cfg,
				event_engine=self.event_engine,
			)
			await executor.start()
			set_background_executor(executor)
			stats = executor.get_all_stats()
			logger.info(
				"后台任务执行器初始化完成",
				extra={"pools": {n: s["max_workers"] for n, s in stats.items()}},
			)
		except Exception as e:
			logger.warning(
				"后台任务执行器初始化失败（非致命），回退到同步模式",
				extra={"error": str(e)},
			)

	@log_performance(operation="initialize_main_engine", level=LogLevel.DEBUG)

	async def _initialize_main_engine(self) -> None:
		"""初始化主引擎"""
		with get_context_manager().context_manager(
				operation="main_engine_initialization",
				component="main_engine"
		):
			logger.info("初始化主引擎...")

			try:
				# 创建主引擎配置
				main_config = EngineConfigEntity(
					name="main_engine",
					engine_type="main",
					auto_start=True,
					config=self.config.get_system_config()
				)

				# 创建主引擎实例
				self.main_engine = MainEngine(main_config, self.event_engine)
				await self.main_engine.start()

				# 注入到 API 依赖层
				from api.dependencies.main_engine import set_main_engine
				set_main_engine(self.main_engine)

				# 获取引擎注册表
				self.engine_registry = EngineRegistry()

				logger.info("主引擎初始化完成")

			except Exception as e:
				logger.exception("主引擎初始化失败", exception=e)
				raise

	@with_context(operation="initialize_modules", source="main_server")
	async def _initialize_modules(self) -> None:
		"""初始化模块"""
		if not self.enabled_modules:
			logger.info("没有启用的模块，跳过模块初始化")
			return

		logger.info(f"开始初始化模块: {', '.join(self.enabled_modules)}")

		# 按依赖关系排序模块
		sorted_modules = await self._sort_modules_by_dependency()

		for module_name in sorted_modules:
			if module_name not in self.enabled_modules:
				continue

			module_config = self.config.module_configs.get(module_name)
			if not module_config or not module_config.enabled:
				logger.info(f"模块 {module_name} 被禁用，跳过初始化")
				continue

			with get_context_manager().context_manager(
					operation=f"module_{module_name}_initialization",
					module=module_name
			):
				try:
					logger.info(f"初始化模块: {module_name}")

					# 动态导入模块
					module = await self._load_module(module_name)
					if not module:
						continue

					# 调用模块初始化函数
					if hasattr(module, 'initialize') and callable(module.initialize):
						# 合并模块配置
						module_settings = self._get_module_settings(module_name)

						# 检查函数是否是异步的
						import inspect
						if inspect.iscoroutinefunction(module.initialize):
							init_result = await module.initialize(
								main_engine=self.main_engine,
								event_engine=self.event_engine,
								config={
									**module_config.config,
									**module_settings
								}
							)
						else:
							init_result = module.initialize(
								main_engine=self.main_engine,
								event_engine=self.event_engine,
								config={
									**module_config.config,
									**module_settings
								}
							)

						if init_result:
							self.loaded_modules[module_name] = module
							logger.info(f"模块 {module_name} 初始化成功")
						else:
							logger.error(f"模块 {module_name} 初始化失败")
					else:
						logger.warning(f"模块 {module_name} 没有initialize函数，跳过初始化")

				except Exception as e:
					logger.exception(f"模块 {module_name} 初始化失败", exception=e)

	def _get_module_settings(self, module_name: str) -> Dict[str, Any]:
		"""获取模块特定的settings配置"""
		settings_map = {
			"data": {
				"tushare_token": self.config.settings.DATA_SOURCE.TUSHARE_TOKEN,
				"sync_enabled": self.config.settings.DATA_SOURCE.SYNC_ENABLED,
				"sync_schedule": self.config.settings.DATA_SOURCE.SYNC_SCHEDULE,
				"sync_batch_size": self.config.settings.DATA_SOURCE.SYNC_BATCH_SIZE,
			},
			"strategy": {
				"enable_ai_strategies": self.config.settings.get_feature("enable_ai_strategies"),
			},
			"trade": {
				"simulated_trading": self.config.settings.TRADE.SIMULATED_TRADING,
				"initial_capital": self.config.settings.TRADE.SIM_INITIAL_CAPITAL,
				"broker": self.config.settings.TRADE.BROKER,
				"risk_check_enabled": self.config.settings.TRADE.RISK_CHECK_ENABLED,
				"stop_loss_percent": self.config.settings.TRADE.STOP_LOSS_PERCENT,
			},
			"account": {
				"enable_multi_account": self.config.settings.get_feature("enable_multi_account"),
			},
			"monitor": {
				# v2.3: 通知开关以 config.yaml 为准
			},
			"system": {
				"secret_key": self.config.settings.API.SECRET_KEY,
				"access_token_expire_minutes": self.config.settings.API.ACCESS_TOKEN_EXPIRE_MINUTES,
				"algorithm": self.config.settings.API.ALGORITHM,
			}
		}

		return settings_map.get(module_name, {})

	@staticmethod
	async def _load_module(module_name: str) -> Optional[Any]:
		"""动态加载模块"""
		try:
			module_path = f"modules.{module_name}"
			import importlib
			module = importlib.import_module(module_path)
			logger.debug(f"模块加载成功: {module_name}", extra={"module_path": module_path})
			return module
		except ImportError as e:
			logger.error(f"模块加载失败: {module_name}", extra={"error": str(e)})
			return None
		except Exception as e:
			logger.exception(f"模块加载异常: {module_name}", exception=e)
			return None

	async def _sort_modules_by_dependency(self) -> List[str]:
		"""按依赖关系对模块进行排序"""
		# 构建依赖图
		graph: Dict[str, Set[str]] = {}
		for module_name in self.enabled_modules:
			module_config = self.config.module_configs.get(module_name, ModuleConfig(name=module_name))
			graph[module_name] = set(module_config.dependencies)

		# 拓扑排序
		visited: Dict[str, int] = {}
		result: List[str] = []

		def dfs(node: str) -> bool:
			if visited.get(node) == 1:
				logger.error(f"检测到循环依赖: {node}")
				return False
			if visited.get(node) == 2:
				return True

			visited[node] = 1

			# 递归处理依赖
			for dep in graph.get(node, set()):
				if dep in self.enabled_modules:
					if not dfs(dep):
						return False

			visited[node] = 2
			result.append(node)
			return True

		# 对每个未访问的节点执行DFS
		for module_node in self.enabled_modules:
			if visited.get(module_node, 0) != 0:
				continue
			if not dfs(module_node):
				logger.warning("检测到循环依赖，使用默认顺序")
				return list(self.enabled_modules)

		return result

	@with_context(operation="register_lifecycle_events", source="main_server")
	async def _register_lifecycle_events(self) -> None:
		"""注册生命周期事件"""
		if not self.app:
			return

		# 使用现代的生命周期事件处理方式（替代过时的@app.on_event）
		@self.app.router.lifespan_context
		async def lifespan_context(_app):
			# Startup
			with get_context_manager().context_manager(
					operation="fastapi_startup",
					component="fastapi",
					stage="startup"
			):
				logger.info("FastAPI应用启动...")

				# 更新运行状态
				self.is_running = True

				# 如果主引擎未自动启动，手动启动
				if not self.config.auto_start_main_engine and self.main_engine:
					await self.main_engine.start()

				# 发布系统启动事件
				if self.event_engine:
					uptime_seconds = (datetime.now() - self.startup_time).total_seconds()
					modules_loaded = list(self.loaded_modules.keys())

					system_event: SystemStartedEvent = SystemStartedEvent(
						system_name=self.config.system_name,
						version=self.config.version,
						startup_time_seconds=uptime_seconds,
						modules_loaded=modules_loaded,
						config_summary=self.config.get_system_config()
					)
					# 确保事件类型正确
					await self.event_engine.put(system_event)

				logger.info("FastAPI应用启动完成", extra={
					"startup_time": self.startup_time.isoformat(),
					"modules_loaded": len(self.loaded_modules)
				})

			yield

			# Shutdown
			with get_context_manager().context_manager(
					operation="fastapi_shutdown",
					component="fastapi",
					stage="shutdown"
			):
				logger.info("FastAPI应用关闭...")

				# 更新运行状态
				self.is_running = False

				# 发布系统关闭事件
				if self.event_engine:
					from core.events.system_events import SystemStoppedEvent
					system_event: SystemStoppedEvent = SystemStoppedEvent(
						system_name=self.config.system_name,
						shutdown_reason="正常关闭",
						uptime_seconds=(datetime.now() - self.startup_time).total_seconds(),
						graceful=True
					)
					await self.event_engine.put(system_event)

				# 关闭所有模块
				await self._shutdown_modules()

				# 关闭后台任务执行器
				await self._shutdown_background_executor()

				# 关闭主引擎
				if self.main_engine:
					await self.main_engine.stop()

				# 关闭事件引擎
				if self.event_engine:
					await self.event_engine.stop()

				# 关闭日志系统
				shutdown_logging()

				logger.info("FastAPI应用关闭完成", extra={
					"uptime_seconds": (datetime.now() - self.startup_time).total_seconds(),
					"modules_unloaded": len(self.loaded_modules)
				})

	@with_context(operation="shutdown_modules", source="main_server")
	async def _shutdown_modules(self) -> None:
		"""关闭所有模块"""
		if not self.loaded_modules:
			logger.info("没有加载的模块，跳过关闭")
			return

		logger.info("开始关闭所有模块...")

		# 按加载顺序的逆序关闭模块
		for module_name in reversed(list(self.loaded_modules.keys())):
			with get_context_manager().context_manager(
					operation=f"module_{module_name}_shutdown",
					module=module_name
			):
				try:
					module = self.loaded_modules[module_name]

					# 调用模块关闭函数
					if hasattr(module, 'shutdown') and callable(module.shutdown):
						# 检查函数是否是异步的
						import inspect
						if inspect.iscoroutinefunction(module.shutdown):
							module.shutdown()
						else:
							module.shutdown()
						logger.info(f"模块 {module_name} 关闭成功")
					else:
						logger.warning(f"模块 {module_name} 没有shutdown函数，跳过关闭")

				except Exception as e:
					logger.exception(f"模块 {module_name} 关闭失败", exception=e)

		self.loaded_modules.clear()
		logger.info("所有模块关闭完成")

	async def _shutdown_background_executor(self) -> None:
		"""关闭后台任务执行器"""
		try:
			from shared.utils.background_executor import get_background_executor
			executor = get_background_executor()
			if executor is not None:
				await executor.shutdown(timeout=60)
				logger.info("后台任务执行器已关闭")
		except Exception as e:
			logger.warning(
				"后台任务执行器关闭失败",
				extra={"error": str(e)},
			)

	@log_performance(operation="start_server", level=LogLevel.INFO)

	async def start_server(self) -> None:
		"""启动服务器"""
		if not self.app:
			error("FastAPI应用未初始化，无法启动服务器")
			return

		with get_context_manager().context_manager(
				operation="server_startup",
				component="uvicorn",
				host=self.config.host,
				port=self.config.port
		):
			try:
				logger.info("启动服务器...", extra={
					"host": self.config.host,
					"port": self.config.port,
					"workers": self.config.workers,
					"mode": self.config.mode
				})

				# 关闭 uvicorn/websockets DEBUG 日志（ping/pong 刷屏）
				logging.getLogger("websockets").setLevel(logging.WARNING)
				logging.getLogger("websockets.server").setLevel(logging.WARNING)
				logging.getLogger("uvicorn.protocols.websockets").setLevel(logging.WARNING)
				logging.getLogger("uvicorn").setLevel(logging.WARNING)

				# 配置服务器参数
				server_config = uvicorn.Config(
					app=self.app,
					host=self.config.host,
					port=self.config.port,
					workers=self.config.workers,
					log_level=self.config.log_level.lower(),
					reload=(self.config.mode == "development"),
					access_log=False,  # 关闭 uvicorn HTTP 访问日志，避免轮询日志刷屏
					timeout_keep_alive=30,
					limit_concurrency=1000,
					limit_max_requests=10000,
					proxy_headers=True,
					forwarded_allow_ips="*" if self.config.mode == "development" else None
				)

				# 创建并运行服务器
				server = uvicorn.Server(server_config)

				# 设置信号处理
				self._setup_signal_handlers(server)

				# 打印启动信息
				self._print_startup_message()

				# 启动前检查
				logger.info("开始启动uvicorn服务器...", extra={
					"host": self.config.host,
					"port": self.config.port,
					"reload_enabled": self.config.mode == "development"
				})

				# 运行服务器
				try:
					# ========== 启动成功标识 ==========
					logger.info("=" * 60)
					logger.info("✅ 量化交易系统启动成功！")
					# 使用127.0.0.1而非0.0.0.0，并移除ReDoc文档行
					logger.info(f"🌐 API文档: http://127.0.0.1:{self.config.port}/docs")
					# 记录启动的模块
					if self.loaded_modules:
						logger.info(f"🚀 已启动模块: {', '.join(self.loaded_modules.keys())}")
					else:
						logger.info("⚠️  没有启动任何模块")
					logger.info("=" * 60)
					# =================================

					await server.serve()

				except asyncio.CancelledError:
					logger.info("服务器任务被取消")
				except Exception as e:
					logger.exception("uvicorn服务器运行失败", exception=e)
					raise

			except Exception as e:
				logger.exception("服务器启动失败", exception=e)
				raise

	def _setup_signal_handlers(self, server: uvicorn.Server) -> None:
		"""设置信号处理器"""

		def signal_handler(signum, _frame):
			logger.info(f"收到信号 {signum}, 正在优雅关闭...")
			server.should_exit = True

		# 注册信号处理器
		signal.signal(signal.SIGINT, signal_handler)
		signal.signal(signal.SIGTERM, signal_handler)

		# 在开发环境中添加热重载信号（仅Unix/Linux系统）
		if self.config.mode == "development" and hasattr(signal, 'SIGUSR1'):
			def reload_handler(signum, _frame):
				logger.info(f"收到信号 {signum}, 重新加载配置...")
				self._reload_configuration()

			# 注册USR1信号用于重新加载配置（仅开发环境）
			signal.signal(signal.SIGUSR1, reload_handler)
			logger.info("已注册SIGUSR1信号处理器用于配置热重载")
		elif self.config.mode == "development":
			logger.info("当前系统不支持SIGUSR1信号，配置热重载功能不可用")

	@with_context(operation="reload_configuration", source="main_server")
	def _reload_configuration(self):
		"""重新加载配置"""
		try:
			# 重新加载配置
			reload_config()

			# 更新服务器配置
			self.config.settings = get_config().settings

			# 重新配置日志
			self.setup_logging()

			logger.info("配置重新加载完成")
		except Exception as e:
			logger.exception("重新加载配置失败", exception=e)

	def _print_startup_message(self):
		"""打印启动信息"""
		status = self.get_system_status()

		# 使用结构化日志记录启动信息
		self.logger.info("🚀 量化交易系统启动", extra={
			"system": status['system']['name'],
			"version": status['system']['version'],
			"environment": status['system']['environment'],
			"host": status['server']['host'],
			"port": status['server']['port'],
			"docs_url": f"http://{status['server']['host']}:{status['server']['port']}/docs",
			"enabled_modules": status['modules']['total_enabled'],
			"database": status['settings']['database_type'],
			"trade_mode": "模拟交易" if status['settings']['trade_simulated'] else "实盘交易"
		})

	def get_system_status(self) -> Dict[str, Any]:
		"""获取系统状态"""
		uptime = 0.0
		if self.startup_time:
			uptime = (datetime.now() - self.startup_time).total_seconds()

		status = {
			"system": {
				"name": self.config.system_name,
				"version": self.config.version,
				"environment": self.config.mode,
				"debug": self.config.settings.DEBUG,
			},
			"server": {
				"host": self.config.host,
				"port": self.config.port,
				"is_running": self.is_running,
				"uptime_seconds": uptime,
				"startup_time": self.startup_time.isoformat() if self.startup_time else None,
			},
			"modules": {
				"enabled": list(self.enabled_modules),
				"loaded": list(self.loaded_modules.keys()),
				"total_enabled": len(self.enabled_modules),
				"total_loaded": len(self.loaded_modules),
			},
			"settings": {
				"database_type": self.config.settings.DATABASE.TYPE.value,
				"redis_enabled": self.config.settings.REDIS.ENABLED,
				"data_source_tushare_enabled": self.config.settings.DATA_SOURCE.TUSHARE_ENABLED,
				"trade_simulated": self.config.settings.TRADE.SIMULATED_TRADING,
			},
			"feature_flags": self.config.settings.FEATURE_FLAGS,
		}

		logger.debug("获取系统状态", extra={"status_summary": status})
		return status

	@with_context(operation="shutdown_system", source="main_server")
	async def shutdown(self) -> None:
		"""关闭系统"""

		logger.info("开始关闭量化交易系统...")

		# 如果服务器正在运行，执行关闭逻辑
		if self.is_running:
			# 关闭所有模块
			await self._shutdown_modules()

			# 关闭主引擎
			if self.main_engine:
				await self.main_engine.stop()

			# 关闭事件引擎
			if self.event_engine:
				await self.event_engine.stop()

			# 更新状态
			self.is_running = False

		logger.info("量化交易系统关闭完成")


async def create_quant_server(
		config_path: Optional[str] = None,
		mode: Optional[str] = None
) -> QuantServer:
	"""创建量化交易服务器

	Args:
		config_path: 配置文件路径
		mode: 运行模式

	Returns:
		QuantServer: 服务器实例
	"""
	with get_context_manager().context_manager(
			operation="create_quant_server",
			config_path=config_path,
			mode=mode
	):
		try:
			logger.info("创建量化交易服务器...")

			# 创建服务器实例
			server = QuantServer(config_path)

			# 如果指定了模式，覆盖配置中的模式
			if mode:
				server.config.mode = mode

			# 初始化服务器
			success = await server.initialize()
			if not success:
				error("服务器初始化失败")
				raise RuntimeError("服务器初始化失败")

			logger.info("量化交易服务器创建成功")
			return server

		except Exception as e:
			logger.exception("创建量化交易服务器失败", exception=e)
			raise


async def main():
	"""主函数入口"""
	import argparse

	# 解析命令行参数
	parser = argparse.ArgumentParser(description="量化交易系统")
	parser.add_argument("--config", "-c", type=str, default="config.yaml",help="配置文件路径 (默认: quant_server/config.yaml)")
	parser.add_argument("--mode", "-m", type=str, choices=["development", "test", "production"],default=None, help="运行模式 (development/test/production)")
	parser.add_argument("--host", type=str, default=None, help="绑定地址")
	parser.add_argument("--port", "-p", type=int, default=None, help="绑定端口")
	parser.add_argument("--workers", "-w", type=int, default=None, help="工作进程数")
	parser.add_argument("--log-level", type=str, default=None,
	                    choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
	                    help="日志级别")

	args = parser.parse_args()

	# 创建请求上下文
	request_id = f"cli_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

	with get_context_manager().context_manager(
			request_id=request_id,
			operation="cli_main",
			source="command_line"
	):
		server = None
		try:
			# 创建服务器
			server = await create_quant_server(args.config, args.mode)

			# 覆盖命令行参数
			if args.host:
				server.config.host = args.host
			if args.port:
				server.config.port = args.port
			if args.workers:
				server.config.workers = args.workers
			if args.log_level:
				server.config.log_level = args.log_level
				# 重新配置日志
				server.setup_logging()

			# 记录启动参数
			logger.info("命令行参数解析完成", extra={
				"config": args.config,
				"mode": args.mode,
				"host": args.host,
				"port": args.port,
				"workers": args.workers,
				"log_level": args.log_level
			})

			# 启动服务器
			await server.start_server()

		except KeyboardInterrupt:
			info("收到中断信号，正在关闭...")
		except Exception as e:
			logger.exception("系统启动失败", exception=e)
			sys.exit(1)
		finally:
			# 确保关闭服务器
			if 'server' in locals():
				await server.shutdown()


if __name__ == "__main__":
	asyncio.run(main())
