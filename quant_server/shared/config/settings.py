# shared/config/settings.py
"""
系统配置管理
使用 Pydantic BaseSettings 提供类型安全、环境变量加载和验证
Pydantic V2 兼容版本
"""

import os
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache


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

	model_config = {
		"env_prefix": "DB_",
		"case_sensitive": False,
		"extra": "ignore"
	}

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

	# 速率限制
	RATE_LIMIT_ENABLED: bool = True
	RATE_LIMIT_REQUESTS: int = 100
	RATE_LIMIT_PERIOD: int = 60  # 秒

	model_config = {
		"env_prefix": "APP_",
		"case_sensitive": False,
		"extra": "ignore"
	}


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

	model_config = {
		"env_prefix": "REDIS_",
		"case_sensitive": False,
		"extra": "ignore"
	}

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

	# 数据同步配置
	SYNC_ENABLED: bool = True
	SYNC_AUTO: bool = False
	SYNC_TIME: str = "02:00"
	SYNC_RETENTION_DAYS: int = 365
	SYNC_SCHEDULE: str = "0 2 * * *"  # 每天凌晨2点
	SYNC_BATCH_SIZE: int = 1000

	model_config = {
		"case_sensitive": False,
		"extra": "ignore"
	}

	@field_validator("TUSHARE_TOKEN", mode="before")
	@classmethod
	def validate_tushare_token (cls, v):
		"""验证Tushare Token"""
		if not v:
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

	model_config = {
		"case_sensitive": False,
		"extra": "ignore"
	}


class NotificationSettings(BaseSettings):
	"""通知配置"""

	# 邮件通知
	EMAIL_ENABLED: bool = False
	SMTP_SERVER: str = "smtp.example.com"
	SMTP_PORT: int = 587
	EMAIL_USERNAME: str = "your_email@example.com"
	EMAIL_PASSWORD: str = "your_email_password"
	EMAIL_RECEIVERS: List[str] = ["user1@example.com", "user2@example.com"]

	# 钉钉通知
	DINGTALK_ENABLED: bool = False
	DINGTALK_WEBHOOK: str = "https://oapi.dingtalk.com/robot/send?access_token=your_token"

	# 微信通知
	WECHAT_ENABLED: bool = False
	WECHAT_CORP_ID: str = "your_corp_id"
	WECHAT_CORP_SECRET: str = "your_corp_secret"
	WECHAT_AGENT_ID: str = "1000001"

	model_config = {
		"case_sensitive": False,
		"extra": "ignore"
	}

	@field_validator("EMAIL_RECEIVERS", mode="before")
	@classmethod
	def parse_email_receivers (cls, v):
		"""解析邮件接收者列表"""
		if isinstance(v, str):
			if not v.strip():
				return []
			return [email.strip() for email in v.split(",") if email.strip()]
		return v or []


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

	model_config = {
		"env_prefix": "LOG_",
		"case_sensitive": False,
		"extra": "ignore"
	}


class Settings(BaseSettings):
	"""主配置类"""

	# 环境配置
	ENVIRONMENT: Environment = Environment.DEVELOPMENT
	APP_NAME: str = "量化交易平台"
	APP_VERSION: str = "1.0.0"
	DEBUG: bool = True

	# 子配置
	DATABASE: DatabaseSettings = DatabaseSettings()
	API: APISettings = APISettings()
	REDIS: RedisSettings = RedisSettings()
	DATA_SOURCE: DataSourceSettings = DataSourceSettings()
	TRADE: TradeSettings = TradeSettings()
	NOTIFICATION: NotificationSettings = NotificationSettings()
	LOG: LogSettings = LogSettings()

	# 特性开关
	FEATURE_FLAGS: Dict[str, bool] = {
		"enable_backtest": True,
		"enable_realtime_trading": False,
		"enable_multi_account": False,
		"enable_ai_strategies": False,
	}

	model_config = {
		"env_file": ".env",
		"env_file_encoding": "utf-8",
		"case_sensitive": False,
		"extra": "ignore",
		"env_nested_delimiter": "__",  # 支持嵌套环境变量，如 DATABASE__HOST
	}

	@field_validator("DEBUG", mode="after")
	@classmethod
	def set_debug_from_environment (cls, v, info):
		"""根据环境设置DEBUG模式"""
		env = info.data.get("ENVIRONMENT")
		if env == Environment.DEVELOPMENT:
			return True
		return v

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

	def update_feature (self, feature_name: str, enabled: bool) -> None:
		"""更新特性开关状态"""
		self.FEATURE_FLAGS[feature_name] = enabled

	def get_all_settings (self) -> Dict[str, Any]:
		"""获取所有配置（排除敏感信息）"""
		settings_dict = self.model_dump()

		# 过滤敏感信息
		sensitive_fields = ["PASSWORD", "SECRET", "TOKEN", "KEY"]

		def filter_sensitive (obj):
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
		config = get_settings()

		# 验证必要配置
		if config.DATA_SOURCE.TUSHARE_ENABLED and not config.DATA_SOURCE.TUSHARE_TOKEN:
			print("警告: Tushare已启用但未配置TOKEN")

		if not config.DATABASE.HOST or not config.DATABASE.NAME:
			print("错误: 数据库配置不完整")
			return False

		return True
	except Exception as e:
		print(f"配置验证失败: {e}")
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
		return Environment.PRODUCTION
	elif env in ["test", "testing"]:
		return Environment.TESTING
	elif env in ["stage", "staging"]:
		return Environment.STAGING
	else:
		return Environment.DEVELOPMENT


# 配置重载函数（用于动态更新配置）
def reload_settings () -> Settings:
	"""
	重新加载配置（清除缓存并重新读取）

	Returns:
		重新加载的配置实例
	"""
	get_settings.cache_clear()
	return get_settings()


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

	print("\n特性开关:")
	for feature, enabled in config.FEATURE_FLAGS.items():
		print(f"  {feature}: {enabled}")

	# 验证配置
	print("\n配置验证结果:", "通过" if validate_config() else "失败")
	print("=" * 80)