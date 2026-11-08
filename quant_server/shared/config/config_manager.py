"""
统一配置管理模块
整合 YAML 配置和 Pydantic 类型安全
"""
import json
import logging
import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

import yaml
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# v2.1 修复（2026-07-17 mock 数据污染事故）：
# 本模块多处 validator 用 os.getenv 读取 DEV_*/PROD_* 配置，但 .env 文件
# 只被 pydantic-settings 读入模型字段、不会进入进程环境变量 —— 若启动器
# （如裸命令行）未注入 .env，os.getenv 恒为 None，DATA_MODE 回退危险默认值
# "simulated" → 日终同步用 MockSource 向真实库写入模拟数据。
# 此处显式将 quant_server/.env 载入进程环境（override=False：IDE/shell 已
# 注入的环境变量优先），保证任何启动方式下 os.getenv 读到同一份配置。
# ---------------------------------------------------------------------------
try:
	from dotenv import load_dotenv

	_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
	if _ENV_FILE.exists():
		load_dotenv(_ENV_FILE, override=False)
except ImportError:  # python-dotenv 缺失时不阻断启动，但同步侧已有硬闸兜底
	logger.warning("python-dotenv 未安装，.env 不会注入进程环境变量")


class Environment(str, Enum):
	"""环境类型枚举"""
	DEVELOPMENT = "development"
	TESTING = "testing"
	STAGING = "staging"
	PRODUCTION = "production"


class DatabaseType(str, Enum):
	"""数据库类型枚举"""
	POSTGRESQL = "postgresql"
	MYSQL = "mysql"
	SQLITE = "sqlite"


class DatabaseSettings(BaseSettings):
	"""数据库配置"""

	TYPE: DatabaseType = DatabaseType.POSTGRESQL
	HOST: str = "localhost"
	PORT: int = 5432
	USER: str = "postgres"
	PASSWORD: str = "123456"
	NAME: str = "quant_signals"

	# 连接池配置
	POOL_SIZE: int = 10  # 默认值，.env DEV_DB_POOL_SIZE=50 会覆盖
	MAX_OVERFLOW: int = 5
	ECHO_SQL: bool = False
	ECHO_POOL: bool = False

	# 迁移配置
	MIGRATIONS_DIR: str = "shared/database/migrations"
	AUTO_MIGRATE: bool = False

	model_config = SettingsConfigDict(
		env_prefix="DB_",
		case_sensitive=False,
		extra="ignore"
	)

	@property
	def url (self) -> str:
		"""获取数据库连接URL"""
		if self.TYPE == DatabaseType.POSTGRESQL:
			return f"postgresql://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.NAME}"
		elif self.TYPE == DatabaseType.MYSQL:
			return f"mysql://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.NAME}"
		else:
			return f"sqlite:///{self.NAME}.db"

	@property
	def async_url (self) -> str:
		"""获取异步数据库连接URL"""
		if self.TYPE == DatabaseType.POSTGRESQL:
			return f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.NAME}"
		elif self.TYPE == DatabaseType.MYSQL:
			return f"mysql+aiomysql://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.NAME}"
		else:
			return f"sqlite+aiosqlite:///{self.NAME}.db"


class ReadOnlyDatabaseSettings(DatabaseSettings):
	"""只读数据库配置（DB_RO_*，可选）。

	仅用于研究/看板/外部工具；应用主链路仍使用 DATABASE。
	未配置 DB_RO_* 时该对象保持 None（见 ConfigSettings.resolve_database_config）。
	"""

	USER: str = "quant_ro"
	PASSWORD: str = ""
	NAME: str = "quant_signals"

	model_config = SettingsConfigDict(
		env_prefix="DB_RO_",
		case_sensitive=False,
		extra="ignore"
	)


def resolve_database_env (
	env: str,
	base: Mapping[str, Any],
	getenv: Callable[..., Optional[str]] = os.getenv,
) -> Tuple[Dict[str, Any], List[str]]:
	"""按 ENVIRONMENT 解析开发/生产数据库字段。

	纯函数：不读 self、不写日志，便于单测。返回 (resolved, missing_prod_keys)。

	- development: 读 DB_DEV_*；NAME 缺省 quant_signals（单库目标态）
	- 其他环境: 读 PROD_DB_*；NAME 缺省 quant_signals
	"""
	env = (env or "development").lower()
	if env == "development":
		return {
			"HOST": getenv("DB_DEV_HOST", base.get("HOST")),
			"PORT": int(getenv("DB_DEV_PORT") or base.get("PORT", 5432)),
			"USER": getenv("DB_DEV_USER", base.get("USER")),
			"PASSWORD": getenv("DB_DEV_PASSWORD", base.get("PASSWORD")),
			"NAME": getenv("DB_DEV_NAME", "quant_signals"),
			"POOL_SIZE": int(getenv("DB_DEV_POOL_SIZE") or base.get("POOL_SIZE", 10)),
			"MAX_OVERFLOW": int(getenv("DB_DEV_MAX_OVERFLOW") or base.get("MAX_OVERFLOW", 5)),
		}, []

	missing = [
		key for key in (
			"PROD_DB_HOST", "PROD_DB_PORT", "PROD_DB_USER",
			"PROD_DB_PASSWORD", "PROD_DB_NAME",
		)
		if getenv(key) is None
	]
	return {
		"HOST": getenv("PROD_DB_HOST", base.get("HOST")),
		"PORT": int(getenv("PROD_DB_PORT") or base.get("PORT", 5432)),
		"USER": getenv("PROD_DB_USER", base.get("USER")),
		"PASSWORD": getenv("PROD_DB_PASSWORD", base.get("PASSWORD")),
		"NAME": getenv("PROD_DB_NAME", "quant_signals"),
		"POOL_SIZE": int(getenv("PROD_DB_POOL_SIZE") or base.get("POOL_SIZE", 10)),
		"MAX_OVERFLOW": int(getenv("PROD_DB_MAX_OVERFLOW") or base.get("MAX_OVERFLOW", 5)),
	}, missing


class APISettings(BaseSettings):
	"""API配置"""

	HOST: str = "127.0.0.1"
	PORT: int = 8080
	DEBUG: bool = True

	# CORS配置
	CORS_ORIGINS: List[str] = ["http://localhost:3000"]
	CORS_ALLOW_CREDENTIALS: bool = True
	CORS_ALLOW_METHODS: List[str] = ["*"]
	CORS_ALLOW_HEADERS: List[str] = ["*"]

	# 安全配置
	# 修复 2026-08（B4）：pydantic-settings 自动读取环境变量 SECRET_KEY 覆盖此默认值；
	# 生产环境必须通过 .env 注入随机密钥（validate_config 强制校验）
	SECRET_KEY: str = "your-secret-key-here-change-in-production"
	ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
	AUTH_ENABLED: bool = True  # 是否启用令牌校验，关闭后跳过 JWT 验证（仅开发/测试用）
	ALGORITHM: str = "HS256"

	# JWT配置
	JWT_ALGORITHM: str = "HS256"  # JWT算法
	REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 刷新令牌过期天数
	JWT_ISSUER: Optional[str] = None  # JWT发行者
	JWT_AUDIENCE: Optional[str] = None  # JWT受众

	# 速率限制
	RATE_LIMIT_ENABLED: bool = True
	RATE_LIMIT_REQUESTS: int = 100
	RATE_LIMIT_PERIOD: int = 60  # 秒

	model_config = SettingsConfigDict(
		env_prefix="APP_",
		case_sensitive=False,
		extra="ignore"
	)


class RedisSettings(BaseSettings):
	"""Redis配置"""

	ENABLED: bool = False
	HOST: str = "localhost"
	PORT: int = 6379
	PASSWORD: Optional[str] = None
	DB: int = 0

	# 连接池配置
	MAX_CONNECTIONS: int = 10
	SOCKET_TIMEOUT: int = 5
	SOCKET_CONNECT_TIMEOUT: int = 5

	model_config = SettingsConfigDict(
		env_prefix="REDIS_",
		case_sensitive=False,
		extra="ignore"
	)

	@property
	def url (self) -> Optional[str]:
		"""获取Redis连接URL"""
		if not self.ENABLED:
			return None

		if self.PASSWORD:
			return f"redis://:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.DB}"
		return f"redis://{self.HOST}:{self.PORT}/{self.DB}"


class DataSourceSettings(BaseSettings):
	"""数据源配置"""

	# Tushare配置
	TUSHARE_TOKEN: str = ""
	TUSHARE_ENABLED: bool = True
	TUSHARE_MAX_RETRIES: int = 3
	TUSHARE_TIMEOUT: int = 30

	# 其他数据源配置
	BAOSTOCK_ENABLED: bool = False
	BAOSTOCK_MAX_RETRIES: int = 3
	BAOSTOCK_TIMEOUT: int = 30

	# 测试环境标志
	TEST_ENV: bool = False

	# 数据模式：simulated-模拟数据, real-真实数据
	DATA_MODE: str = "simulated"

	# 模拟数据配置
	MOCK_DATA_ENABLED: bool = True
	MOCK_STOCK_COUNT: int = 100
	MOCK_DATE_RANGE_DAYS: int = 30

	# 数据同步配置
	SYNC_ENABLED: bool = True
	SYNC_AUTO: bool = False
	SYNC_TIME: str = "02:00"
	SYNC_RETENTION_DAYS: int = 365
	SYNC_SCHEDULE: str = "0 2 * * *"  # 每天凌晨2点
	SYNC_BATCH_SIZE: int = 1000

	model_config = SettingsConfigDict(
		case_sensitive=False,
		extra="ignore"
	)

	@classmethod
	def validate_tushare_token (cls, v: Optional[str]) -> str:
		"""验证Tushare Token"""
		if not v or v == "":
			# 尝试从环境变量加载
			env_value = os.getenv("TUSHARE_TOKEN", "")
			if env_value:
				return env_value
		return v if v is not None else ""


class TradeSettings(BaseSettings):
	"""交易配置"""

	# 模拟交易配置
	SIMULATED_TRADING: bool = True
	SIM_INITIAL_CAPITAL: float = 1000000.0

	# 实盘交易配置
	BROKER: str = "XTP"
	BROKER_HOST: Optional[str] = None
	BROKER_PORT: Optional[int] = None
	BROKER_USER: Optional[str] = None
	BROKER_PASSWORD: Optional[str] = None

	# 交易限制
	MAX_POSITION_RATIO: float = 0.8
	MAX_SINGLE_POSITION_RATIO: float = 0.1
	MIN_TRADE_AMOUNT: float = 10000.0

	# 风控配置
	RISK_CHECK_ENABLED: bool = True
	STOP_LOSS_PERCENT: float = 0.1

	model_config = SettingsConfigDict(
		case_sensitive=False,
		extra="ignore"
	)


class NotificationSettings(BaseSettings):
	"""通知配置"""

	# 邮件通知
	EMAIL_ENABLED: bool = False
	SMTP_SERVER: str = "smtp.example.com"
	SMTP_PORT: int = 587
	EMAIL_USERNAME: str = ""
	EMAIL_PASSWORD: str = ""
	EMAIL_RECEIVERS: List[str] = []

	# 钉钉通知
	DINGTALK_ENABLED: bool = False
	DINGTALK_WEBHOOK: str = "https://oapi.dingtalk.com/robot/send?access_token=your_token"

	# 微信通知
	WECHAT_ENABLED: bool = False
	WECHAT_CORP_ID: str = ""
	WECHAT_CORP_SECRET: str = ""
	WECHAT_AGENT_ID: str = "1000001"

	model_config = SettingsConfigDict(
		case_sensitive=False,
		extra="ignore",
		env_prefix="NOTIFY_",
	)

	@classmethod
	def parse_email_receivers (cls, v: Any) -> List[str]:
		"""解析邮件接收者列表 - 增强版本"""
		# 如果值为 None，返回空列表
		if v is None:
			return []

		# 如果已经是列表，直接返回
		if isinstance(v, list):
			return [str(item).strip() for item in v if item is not None]

		# 如果是字符串
		if isinstance(v, str):
			v = v.strip()

			# 空字符串返回空列表
			if not v:
				return []

			# 尝试解析 JSON 格式（如 ["email1", "email2"]）
			if v.startswith('[') and v.endswith(']'):
				try:
					parsed = json.loads(v)
					if isinstance(parsed, list):
						return [str(item).strip() for item in parsed if item is not None]
				except json.JSONDecodeError:
					# JSON 解析失败，继续尝试逗号分隔
					pass

			# 按逗号分隔
			emails = []
			for email_part in v.split(','):
				email_part = email_part.strip()
				if email_part:
					# 移除可能的引号
					if (email_part.startswith('"') and email_part.endswith('"')) or \
							(email_part.startswith("'") and email_part.endswith("'")):
						email_part = email_part[1:-1]
					emails.append(email_part)

			return emails

		# 其他类型，尝试转换为列表
		try:
			return [str(item).strip() for item in list(v) if item is not None]
		except (TypeError, ValueError):
			return []


class LogSettings(BaseSettings):
	"""日志配置"""

	LEVEL: str = "INFO"
	FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
	DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

	# 文件日志配置
	FILE_ENABLED: bool = True
	FILE_PATH: str = "logs"
	FILE_MAX_SIZE: int = 100 * 1024 * 1024  # 100MB
	FILE_BACKUP_COUNT: int = 10

	# 结构化日志
	JSON_FORMAT: bool = False

	model_config = SettingsConfigDict(
		env_prefix="LOG_",
		case_sensitive=False,
		extra="ignore"
	)


class SystemSettings(BaseSettings):
	"""系统配置"""
	name: str = "一念量化"
	version: str = "1.0.0"
	enable_web_socket: bool = True
	enable_monitoring: bool = True
	enable_health_check: bool = True
	shutdown_timeout: float = 30.0
	log_level: str = "INFO"
	# 前端托管：None=自动（生产模式托管 quant_web/dist，开发模式不托管），True/False 强制
	serve_frontend: Optional[bool] = None
	# 前端构建目录，留空则使用 <repo>/quant_web/dist
	frontend_dir: Optional[str] = None
	# 日终流水线触发时间（交易日，HH:MM）
	daily_sync_time: str = "19:20"


class ServerSettings(BaseSettings):
	"""服务器配置"""
	host: str = "127.0.0.1"
	port: int = 8080
	workers: int = 1


class EnginesSettings(BaseSettings):
	"""引擎配置"""
	auto_start_main_engine: bool = True
	auto_start_event_engine: bool = True
	max_workers: int = 10
	queue_size: int = 10000


class ModulesSettings(BaseSettings):
	"""模块配置 — 字段动态由 config.yaml 定义，默认值仅兜底"""
	data: Dict[str, Any] = {
		"enabled": True, "auto_start": True, "dependencies": [],
		"config": {"data_source": "tushare", "sync_interval": 3600, "cache_ttl": 300, "load_priority": "high", "max_concurrent_research_per_user": 3}
	}
	strategy: Dict[str, Any] = {
		"enabled": True, "auto_start": True, "dependencies": ["data"],
		"config": {"max_strategies": 50, "enable_ai": True, "backtest_mode": "fast"}
	}
	backtest: Dict[str, Any] = {
		"enabled": True, "auto_start": True, "dependencies": ["strategy", "data"],
		"config": {"max_workers": 4, "enable_optimization": True}
	}
	trade: Dict[str, Any] = {}
	account: Dict[str, Any] = {}
	analysis: Dict[str, Any] = {}
	monitor: Dict[str, Any] = {}
	system: Dict[str, Any] = {}
	risk: Dict[str, Any] = {}
	market: Dict[str, Any] = {}

	model_config = SettingsConfigDict(extra="ignore")


class ConfigSettings(BaseSettings):
	"""主配置类"""

	# 环境配置
	ENVIRONMENT: Environment = Environment.DEVELOPMENT
	APP_NAME: str = "一念量化"
	APP_VERSION: str = "1.0.0"
	DEBUG: bool = True

	# 子配置
	DATABASE: DatabaseSettings = Field(default_factory=DatabaseSettings)
	DATABASE_RO: Optional[ReadOnlyDatabaseSettings] = None
	API: APISettings = Field(default_factory=APISettings)
	REDIS: RedisSettings = Field(default_factory=RedisSettings)
	DATA_SOURCE: DataSourceSettings = Field(default_factory=DataSourceSettings)
	TRADE: TradeSettings = Field(default_factory=TradeSettings)
	NOTIFICATION: NotificationSettings = Field(default_factory=NotificationSettings)
	LOG: LogSettings = Field(default_factory=LogSettings)
	SYSTEM: SystemSettings = Field(default_factory=SystemSettings)
	SERVER: ServerSettings = Field(default_factory=ServerSettings)
	ENGINES: EnginesSettings = Field(default_factory=EnginesSettings)
	MODULES: ModulesSettings = Field(default_factory=ModulesSettings)

	# 特性开关
	FEATURE_FLAGS: Dict[str, bool] = {
		"enable_backtest": True,
		"enable_realtime_trading": False,
		"enable_multi_account": False,
		"enable_ai_strategies": False,
	}

	model_config = SettingsConfigDict(
		env_file=".env",
		env_file_encoding="utf-8",
		case_sensitive=False,
		extra="ignore",
		env_nested_delimiter="__",  # 支持嵌套环境变量，如 DATABASE__HOST
	)

	@classmethod
	@field_validator("DEBUG", mode="after")
	def set_debug_from_environment (cls, v: bool, info: Any) -> bool:
		"""根据环境设置DEBUG模式"""
		env = info.data.get("ENVIRONMENT")
		if env == Environment.DEVELOPMENT:
			return True
		return v

	@model_validator(mode="after")
	def resolve_datasource_config (self) -> "ConfigSettings":
		"""
		根据环境变量解析数据源配置
		开发环境: 使用 DEV_DATA_MODE / DEV_MOCK_* 配置，Token 优先 DEV_TUSHARE_TOKEN 否则回退 PROD_TUSHARE_TOKEN
		生产环境: 使用 PROD_DATA_MODE / PROD_TUSHARE_* 配置
		"""
		env = os.getenv("ENVIRONMENT", "development").lower()
		logger.info(f"解析数据源配置，当前环境: {env}")

		ds = self.DATA_SOURCE

		if env == "development":
			ds.DATA_MODE = os.getenv("DEV_DATA_MODE", ds.DATA_MODE)
			ds.MOCK_DATA_ENABLED = os.getenv("DEV_MOCK_DATA_ENABLED", str(ds.MOCK_DATA_ENABLED)).lower() in ("true", "1", "yes")
			ds.MOCK_STOCK_COUNT = int(os.getenv("DEV_MOCK_STOCK_COUNT", str(ds.MOCK_STOCK_COUNT)))
			ds.MOCK_DATE_RANGE_DAYS = int(os.getenv("DEV_MOCK_DATE_RANGE_DAYS", str(ds.MOCK_DATE_RANGE_DAYS)))
			# Token: 优先 DEV_TUSHARE_TOKEN，回退 PROD_TUSHARE_TOKEN（开发共用生产数据源token）
			token = os.getenv("DEV_TUSHARE_TOKEN", "")
			if not token:
				token = os.getenv("PROD_TUSHARE_TOKEN", ds.TUSHARE_TOKEN)
			ds.TUSHARE_TOKEN = token
			logger.info(
				"开发环境数据源: DATA_MODE=%s MOCK=%s TOKEN=%s",
				ds.DATA_MODE,
				ds.MOCK_DATA_ENABLED,
				"***" if ds.TUSHARE_TOKEN else "未配置",
			)
		else:
			ds.DATA_MODE = os.getenv("PROD_DATA_MODE", ds.DATA_MODE)
			ds.TUSHARE_TOKEN = os.getenv("PROD_TUSHARE_TOKEN", ds.TUSHARE_TOKEN)
			ds.TUSHARE_ENABLED = os.getenv("PROD_TUSHARE_ENABLED", str(ds.TUSHARE_ENABLED)).lower() in ("true", "1", "yes")
			logger.info(
				"生产环境数据源: DATA_MODE=%s TOKEN=%s",
				ds.DATA_MODE,
				"***" if ds.TUSHARE_TOKEN else "未配置",
			)

		return self

	@model_validator(mode="after")
	def resolve_database_config (self) -> "ConfigSettings":
		"""根据 ENVIRONMENT 解析数据库配置（纯逻辑见 resolve_database_env）。

		开发环境读 DB_DEV_*，生产环境读 PROD_DB_*。
		⚠️ 2026-09-19 修复：生产分支原读 `DB_PROD_*`（与 .env 的 `PROD_DB_*` 相反），
		导致全部静默回退到开发库凭证；现统一读 `PROD_DB_*`，缺失时打 WARNING。
		"""
		env = os.getenv("ENVIRONMENT", "development").lower()
		logger.info(f"当前环境: {env}")

		base = {
			"HOST": self.DATABASE.HOST,
			"PORT": self.DATABASE.PORT,
			"USER": self.DATABASE.USER,
			"PASSWORD": self.DATABASE.PASSWORD,
			"NAME": self.DATABASE.NAME,
			"POOL_SIZE": self.DATABASE.POOL_SIZE,
			"MAX_OVERFLOW": self.DATABASE.MAX_OVERFLOW,
		}
		values, missing = resolve_database_env(env, base)
		for key, value in values.items():
			setattr(self.DATABASE, key, value)

		if env == "development":
			logger.info(f"使用开发环境数据库配置: {self.DATABASE.NAME}")
		else:
			if missing:
				logger.warning(
					"生产环境缺少 %d 个 `PROD_DB_*` 配置（%s）→ 已回退到 `.env` 的 `DB_*`"
					"（**开发库那套凭证**）与硬编码库名。若生产库不在同一实例/同凭证，会连到错误的库。",
					len(missing), ", ".join(missing))
			logger.info(f"使用生产环境数据库配置: {self.DATABASE.NAME}")

		# 可选只读 DSN：仅当显式配置 DB_RO_HOST/NAME/USER 时实例化
		if any(os.getenv(key) is not None for key in ("DB_RO_HOST", "DB_RO_NAME", "DB_RO_USER")):
			self.DATABASE_RO = ReadOnlyDatabaseSettings()

		return self

	def is_development (self) -> bool:
		"""是否开发环境"""
		return self.ENVIRONMENT == Environment.DEVELOPMENT

	def is_testing (self) -> bool:
		"""是否测试环境"""
		return self.ENVIRONMENT == Environment.TESTING

	def is_production (self) -> bool:
		"""是否生产环境"""
		return self.ENVIRONMENT == Environment.PRODUCTION

	def get_feature (self, feature_name: str) -> bool:
		"""获取特性开关状态"""
		return self.FEATURE_FLAGS.get(feature_name, False)

	def update_feature (self, feature_name: str, is_enabled: bool) -> None:
		"""更新特性开关状态"""
		self.FEATURE_FLAGS[feature_name] = is_enabled

	def get_all_settings (self) -> Dict[str, Any]:
		"""获取所有配置（排除敏感信息）"""
		settings_dict = self.model_dump()

		# 过滤敏感信息
		sensitive_fields = ["PASSWORD", "SECRET", "TOKEN", "KEY"]

		def filter_sensitive (obj: Any) -> Any:
			if isinstance(obj, dict):
				filtered = {}
				for key, value in obj.items():
					if any(sensitive in key.upper() for sensitive in sensitive_fields):
						filtered[key] = "***REDACTED***"
					else:
						filtered[key] = filter_sensitive(value)
				return filtered
			elif isinstance(obj, list):
				return [filter_sensitive(item) for item in obj]
			else:
				return obj

		return filter_sensitive(settings_dict)


class ConfigManager:
	"""
	统一配置管理器
	
	负责加载和管理系统配置，支持从环境变量和配置文件获取配置。
	配置优先级：环境变量 > 配置文件 > 默认值
	"""

	def __init__ (self, config_file: Optional[str] = None):
		"""初始化配置管理器"""
		self._env = os.getenv("ENVIRONMENT", "development").lower()
		self._config_file = config_file or self._find_config_yaml()
		self._settings = self._load_settings(self._config_file)

	@staticmethod
	def _find_config_yaml () -> Optional[str]:
		"""自动发现 config.yaml 位置"""
		# 相对当前模块所在包目录 (shared/config/../../../ → quant_server/)
		package_root = Path(__file__).resolve().parent.parent.parent
		candidates = [
			"config.yaml",
			str(package_root / "config.yaml"),
		]
		for path in candidates:
			if Path(path).exists():
				return path
		return None

	@staticmethod
	def _load_settings (config_file: Optional[str] = None) -> ConfigSettings:
		"""
		加载配置，优先从 YAML 文件读取，否则使用默认值
		"""
		yaml_config = ConfigManager._load_yaml(config_file) if config_file else None

		if yaml_config:
			kwargs: Dict[str, Any] = {}
			section_map = {
				"system": "SYSTEM",
				"server": "SERVER",
				"engines": "ENGINES",
				"modules": "MODULES",
				"api": "API",
			}
			settings_cls_map = {
				"SYSTEM": SystemSettings,
				"SERVER": ServerSettings,
				"ENGINES": EnginesSettings,
				"MODULES": ModulesSettings,
				"API": APISettings,
			}
			for yaml_key, settings_key in section_map.items():
				if yaml_key in yaml_config and isinstance(yaml_config[yaml_key], dict):
					cls = settings_cls_map[settings_key]
					kwargs[settings_key] = cls(**yaml_config[yaml_key])

			# 确保 API 配置存在，并将 yaml server.port 同步到 API.PORT
			if "API" not in kwargs:
				kwargs["API"] = APISettings()
			if "server" in yaml_config and "port" in yaml_config["server"]:
				kwargs["API"] = kwargs["API"].model_copy(update={"PORT": yaml_config["server"]["port"]})

			return ConfigSettings(**kwargs)

		return ConfigSettings()

	@staticmethod
	def _load_yaml (config_path: str) -> Optional[Dict[str, Any]]:
		"""解析 config.yaml 并返回当前环境的合并配置"""
		try:
			path = Path(config_path)
			if not path.is_absolute():
				if not path.exists():
					alt = ConfigManager._find_config_yaml()
					if alt:
						path = Path(alt)

			if not path.exists():
				return None

			with open(path, "r", encoding="utf-8") as f:
				raw = yaml.safe_load(f)

			if not raw or not isinstance(raw, dict):
				return None

			env = os.getenv("ENVIRONMENT", "development").lower()

			config: Dict[str, Any] = {}
			defaults = raw.get("defaults", {})
			if isinstance(defaults, dict):
				config.update(defaults)

			env_section = raw.get("environments", {}).get(env, {})
			if isinstance(env_section, dict):
				for key, value in env_section.items():
					if key in ("env", "config_source"):
						continue
					if key in config and isinstance(value, dict) and isinstance(config[key], dict):
						config[key].update(value)
					else:
						config[key] = value

			logger.info(f"已加载配置文件: {path} (环境: {env})")
			return config

		except Exception:
			import traceback
			traceback.print_exc()
			return None

	def reload (self, config_file: Optional[str] = None):
		"""重新加载配置"""
		if config_file:
			self._config_file = config_file
		self._env = os.getenv("ENVIRONMENT", "development").lower()
		self._settings = self._load_settings(self._config_file)

	def get (self, key: str, default: Any = None) -> Any:
		"""
		安全获取配置值
		
		Args:
			key: 配置键名，支持点号分隔的嵌套路径
			default: 默认值
			
		Returns:
			配置值或默认值
		"""
		# 优先从环境变量获取
		env_key = key.replace(".", "_").upper()
		if env_key in os.environ:
			return os.environ[env_key]

		# 从配置对象获取
		keys = key.split(".")
		value = self._settings

		try:
			for k in keys:
				value = getattr(value, k)
			return value
		except (AttributeError, KeyError):
			return default

	def __getitem__ (self, key: str) -> Any:
		"""字典式访问"""
		return self.get(key)

	@property
	def settings (self) -> ConfigSettings:
		"""获取配置实例"""
		return self._settings

	@property
	def env (self) -> str:
		"""获取当前环境"""
		return self._env

	def get_config (self, config_type: str = "all") -> Dict[str, Any]:
		"""
		获取指定类型的配置
		
		Args:
			config_type: 配置类型，可选值：all, system, server, database, api, trade
			
		Returns:
			配置字典
		"""
		settings_dict = self._settings.model_dump()

		if config_type == "system":
			return {
				"system_name": settings_dict.get("APP_NAME"),
				"version": settings_dict.get("APP_VERSION"),
				"environment": settings_dict.get("ENVIRONMENT", {}).get("value"),
				"host": settings_dict.get("API", {}).get("HOST"),
				"port": settings_dict.get("API", {}).get("PORT"),
				"debug": settings_dict.get("DEBUG")
			}
		elif config_type == "server":
			return {
				'name': self.get('APP_NAME'),
				'version': self.get('APP_VERSION'),
				'env': self.get('ENVIRONMENT.value'),
				'server': {
					'host': self.get('API.HOST'),
					'port': self.get('API.PORT'),
					'workers': self.get('SERVER.workers')
				},
				'engines': {
					'auto_start_main_engine': self.get('ENGINES.auto_start_main_engine'),
					'auto_start_event_engine': self.get('ENGINES.auto_start_event_engine'),
					'max_workers': self.get('ENGINES.max_workers'),
					'queue_size': self.get('ENGINES.queue_size')
				},
				'features': {
					'enable_web_socket': self.get('SYSTEM.enable_web_socket'),
					'enable_monitoring': self.get('SYSTEM.enable_monitoring'),
					'enable_health_check': self.get('SYSTEM.enable_health_check'),
					'shutdown_timeout': self.get('SYSTEM.shutdown_timeout')
				},
				'log': {
					'level': self.get('LOG.LEVEL')
				},
				'system': {
					'serve_frontend': self.get('SYSTEM.serve_frontend'),
					'frontend_dir': self.get('SYSTEM.frontend_dir'),
					'daily_sync_time': self.get('SYSTEM.daily_sync_time'),
				},
				'modules': {
					k: v for k, v in self.get('MODULES').model_dump().items()
					if isinstance(v, dict) and v
				}
			}
		elif config_type == "database":
			return self.get_database_config()
		elif config_type == "api":
			return self.get_api_config()
		elif config_type == "trade":
			return self.get_trade_config()
		else:
			return settings_dict

	def get_database_config (self) -> Dict[str, Any]:
		"""
		获取数据库配置
		
		Returns:
			数据库配置字典
		"""
		return {
			"type": self.get("DATABASE.TYPE"),
			"host": self.get("DATABASE.HOST"),
			"port": self.get("DATABASE.PORT"),
			"user": self.get("DATABASE.USER"),
			"password": self.get("DATABASE.PASSWORD"),
			"name": self.get("DATABASE.NAME")
		}

	def get_api_config (self) -> Dict[str, Any]:
		"""
		获取 API 配置
		
		Returns:
			API 配置字典
		"""
		return {
			"host": self.get("API.HOST"),
			"port": self.get("API.PORT"),
			"debug": self.get("API.DEBUG")
		}

	def get_trade_config (self) -> Dict[str, Any]:
		"""
		获取交易配置
		
		Returns:
			交易配置字典
		"""
		return {
			"simulated": self.get("TRADE.SIMULATED_TRADING"),
			"initial_capital": self.get("TRADE.SIM_INITIAL_CAPITAL"),
			"max_position_ratio": self.get("TRADE.MAX_POSITION_RATIO")
		}


@lru_cache(maxsize=1)
def get_config (config_file: Optional[str] = None) -> ConfigManager:
	"""
	获取配置管理器实例（缓存单例）

	Args:
		config_file: 可选的 YAML 配置文件路径，留空则自动发现

	Returns:
		配置管理器实例
	"""
	return ConfigManager(config_file=config_file)


# 全局配置实例（自动发现 config.yaml）
config = get_config()


# 配置初始化函数
def init_config (config_file: Optional[str] = None) -> ConfigManager:
	"""
	初始化配置并返回实例
	"""
	return get_config(config_file)


# 配置验证函数
def validate_config () -> bool:
	"""
	验证配置是否有效

	Returns:
		配置是否有效
	"""
	try:
		# 尝试创建配置实例
		config_instance = get_config()

		# 验证必要配置
		if config_instance.settings.DATA_SOURCE.TUSHARE_ENABLED and not config_instance.settings.DATA_SOURCE.TUSHARE_TOKEN:
			print("警告: Tushare已启用但未配置TOKEN")

		# 修复 2026-08（B4）：JWT 密钥校验——生产环境禁止使用公开占位符
		_secret = getattr(config_instance.settings.API, "SECRET_KEY", "")
		if not _secret or _secret == "your-secret-key-here-change-in-production":
			if detect_environment() == "production":
				print("错误: 生产环境必须通过环境变量 SECRET_KEY 注入随机密钥")
				return False
			print("警告: 使用默认 JWT 密钥（仅限开发环境）")

		if not config_instance.settings.DATABASE.HOST or not config_instance.settings.DATABASE.NAME:
			print("错误: 数据库配置不完整")
			return False

		return True
	except Exception as e:
		print(f"配置验证失败: {e}")
		import traceback
		traceback.print_exc()
		return False


# 环境检测函数
def detect_environment () -> str:
	"""
	检测当前运行环境

	Returns:
		环境名称
	"""
	env = os.getenv("ENVIRONMENT", "").lower()
	if env in ["prod", "production"]:
		return Environment.PRODUCTION.value
	elif env in ["test", "testing"]:
		return Environment.TESTING.value
	elif env in ["stage", "staging"]:
		return Environment.STAGING.value
	else:
		return Environment.DEVELOPMENT.value


# 配置重载函数（用于动态更新配置）
def reload_config (config_file: Optional[str] = None) -> ConfigManager:
	"""
	重新加载配置（清除缓存并重新读取）

	Args:
		config_file: 可选的 YAML 配置文件路径
	"""
	global config
	get_config.cache_clear()
	config = get_config(config_file)
	return config
