# shared/config/settings.py
"""
系统配置管理
使用 Pydantic BaseSettings 提供类型安全、环境变量加载和验证
Pydantic V2 兼容版本
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import field_validator, Field, ValidationInfo, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

logger = logging.getLogger(__name__)


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
	POOL_SIZE: int = 10
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
	SECRET_KEY: str = "your-secret-key-here-change-in-production"
	ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
	ALGORITHM: str = "HS256"

	# JWT配置（新增）
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
		return v


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


class Settings(BaseSettings):
	"""主配置类"""

	# 环境配置
	ENVIRONMENT: Environment = Environment.DEVELOPMENT
	APP_NAME: str = "量化交易平台"
	APP_VERSION: str = "1.0.0"
	DEBUG: bool = True

	# 子配置
	DATABASE: DatabaseSettings = Field(default_factory=DatabaseSettings)
	API: APISettings = Field(default_factory=APISettings)
	REDIS: RedisSettings = Field(default_factory=RedisSettings)
	DATA_SOURCE: DataSourceSettings = Field(default_factory=DataSourceSettings)
	TRADE: TradeSettings = Field(default_factory=TradeSettings)
	NOTIFICATION: NotificationSettings = Field(default_factory=NotificationSettings)
	LOG: LogSettings = Field(default_factory=LogSettings)

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

	@field_validator("DEBUG", mode="after")
	@classmethod
	def set_debug_from_environment (cls, v: bool, info: ValidationInfo) -> bool:
		"""根据环境设置DEBUG模式"""
		env = info.data.get("ENVIRONMENT")
		if env == Environment.DEVELOPMENT:
			return True
		return v

	@model_validator(mode="after")
	def resolve_database_config (self) -> "Settings":
		"""
		根据环境变量解析数据库配置
		开发环境: 使用 DB_DEV_* 配置
		生产环境: 使用 DB_PROD_* 配置
		"""
		env = os.getenv("ENVIRONMENT", "development").lower()
		logger.info(f"当前环境: {env}")

		if env == "development":
			# 开发环境：从 DB_DEV_* 读取
			self.DATABASE.HOST = os.getenv("DB_DEV_HOST", self.DATABASE.HOST)
			self.DATABASE.PORT = int(os.getenv("DB_DEV_PORT", str(self.DATABASE.PORT)))
			self.DATABASE.USER = os.getenv("DB_DEV_USER", self.DATABASE.USER)
			self.DATABASE.PASSWORD = os.getenv("DB_DEV_PASSWORD", self.DATABASE.PASSWORD)
			self.DATABASE.NAME = os.getenv("DB_DEV_NAME", "quant_signals_dev")
			self.DATABASE.POOL_SIZE = int(os.getenv("DB_DEV_POOL_SIZE", str(self.DATABASE.POOL_SIZE)))
			self.DATABASE.MAX_OVERFLOW = int(os.getenv("DB_DEV_MAX_OVERFLOW", str(self.DATABASE.MAX_OVERFLOW)))
			logger.info(f"使用开发环境数据库配置: {self.DATABASE.NAME}")
		else:
			# 生产环境：从 DB_PROD_* 读取
			self.DATABASE.HOST = os.getenv("DB_PROD_HOST", self.DATABASE.HOST)
			self.DATABASE.PORT = int(os.getenv("DB_PROD_PORT", str(self.DATABASE.PORT)))
			self.DATABASE.USER = os.getenv("DB_PROD_USER", self.DATABASE.USER)
			self.DATABASE.PASSWORD = os.getenv("DB_PROD_PASSWORD", self.DATABASE.PASSWORD)
			self.DATABASE.NAME = os.getenv("DB_PROD_NAME", "quant_signals")
			self.DATABASE.POOL_SIZE = int(os.getenv("DB_PROD_POOL_SIZE", str(self.DATABASE.POOL_SIZE)))
			self.DATABASE.MAX_OVERFLOW = int(os.getenv("DB_PROD_MAX_OVERFLOW", str(self.DATABASE.MAX_OVERFLOW)))
			logger.info(f"使用生产环境数据库配置: {self.DATABASE.NAME}")

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

	def update_feature (self, feature_name: str, enabled2: bool) -> None:
		"""更新特性开关状态"""
		self.FEATURE_FLAGS[feature_name] = enabled2

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


@lru_cache(maxsize=1)
def get_settings () -> Settings:
	"""
	获取配置实例（缓存单例）

	Returns:
		配置实例
	"""
	return Settings()


# 全局配置实例
settings = get_settings()


# 配置初始化函数
def init_config () -> Settings:
	"""
	初始化配置并返回实例

	Returns:
		配置实例
	"""
	return get_settings()


# 配置验证函数
def validate_config () -> bool:
	"""
	验证配置是否有效

	Returns:
		配置是否有效
	"""
	try:
		# 尝试创建配置实例
		config2 = get_settings()

		# 验证必要配置
		if config2.DATA_SOURCE.TUSHARE_ENABLED and not config2.DATA_SOURCE.TUSHARE_TOKEN:
			print("警告: Tushare已启用但未配置TOKEN")

		if not config2.DATABASE.HOST or not config2.DATABASE.NAME:
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
def reload_settings () -> Settings:
	"""
	重新加载配置（清除缓存并重新读取）

	Returns:
		重新加载的配置实例
	"""
	get_settings.cache_clear()
	return get_settings()


# 配置异常处理装饰器
def with_fallback_settings (fallback_settings: Optional[Dict[str, Any]] = None):
	"""
	装饰器：为配置加载提供回退机制

	Args:
		fallback_settings: 回退配置字典
	"""

	def decorator (func):
		def wrapper (*args, **kwargs):
			try:
				return func(*args, **kwargs)
			except Exception as e:
				print(f"配置加载失败，使用回退配置: {e}")
				if fallback_settings:
					# 创建回退配置实例
					class FallbackSettings(BaseSettings):
						ENVIRONMENT: Environment = Environment.DEVELOPMENT
						APP_NAME: str = "量化交易平台"
						APP_VERSION: str = "1.0.0"
						DEBUG: bool = True

						model_config = SettingsConfigDict(
							case_sensitive=False,
							extra="ignore"
						)

					fallback = FallbackSettings()
					for key, value in fallback_settings.items():
						if hasattr(fallback, key):
							setattr(fallback, key, value)
					return fallback
				raise

		return wrapper

	return decorator


@with_fallback_settings({"APP_NAME": "量化交易平台（回退模式）"})
def load_settings_with_fallback () -> Settings:
	"""
	加载配置，使用回退机制
	"""
	return Settings()


if __name__ == "__main__":
	# 测试配置加载
	print("=" * 80)
	print("配置加载测试")
	print("=" * 80)

	# 加载配置
	config = get_settings()

	# 打印配置信息（过滤敏感信息）
	all_settings = config.get_all_settings()

	print(f"应用名称: {config.APP_NAME}")
	print(f"环境: {config.ENVIRONMENT}")
	print(f"版本: {config.APP_VERSION}")
	print(f"调试模式: {config.DEBUG}")

	print("\n数据库配置:")
	print(f"  类型: {config.DATABASE.TYPE}")
	print(f"  主机: {config.DATABASE.HOST}")
	print(f"  端口: {config.DATABASE.PORT}")
	print(f"  数据库: {config.DATABASE.NAME}")
	print(f"  用户: {config.DATABASE.USER}")
	print(f"  密码: ***REDACTED***")

	print("\nAPI配置:")
	print(f"  主机: {config.API.HOST}")
	print(f"  端口: {config.API.PORT}")
	print(f"  调试: {config.API.DEBUG}")

	print("\n数据源配置:")
	print(f"  Tushare启用: {config.DATA_SOURCE.TUSHARE_ENABLED}")
	print(f"  Tushare Token: ***REDACTED***")
	print(f"  测试环境: {config.DATA_SOURCE.TEST_ENV}")

	print("\n交易配置:")
	print(f"  模拟交易: {config.TRADE.SIMULATED_TRADING}")
	print(f"  初始资金: {config.TRADE.SIM_INITIAL_CAPITAL}")
	print(f"  最大仓位比例: {config.TRADE.MAX_POSITION_RATIO}")
	print(f"  止损百分比: {config.TRADE.STOP_LOSS_PERCENT}")

	print("\n通知配置:")
	print(f"  邮件启用: {config.NOTIFICATION.EMAIL_ENABLED}")
	print(f"  邮件接收者: {config.NOTIFICATION.EMAIL_RECEIVERS}")

	print("\n特性开关:")
	for feature, enabled in config.FEATURE_FLAGS.items():
		print(f"  {feature}: {enabled}")

	# 验证配置
	print("\n配置验证结果:", "通过" if validate_config() else "失败")
	print("=" * 80)