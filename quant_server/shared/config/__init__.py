# shared/config/__init__.py
"""
配置模块初始化
"""

from .config_manager import (
    ConfigManager,
    get_config,
    init_config,
    validate_config,
    detect_environment,
    reload_config,
    config
)

from .constants import (
    ErrorCode,
    OrderStatus,
    OrderType,
    OrderDirection,
    StrategyType,
    Market,
    TIME_CONSTANTS,
    TRADING_HOURS,
    DATA_FREQUENCY,
    TECHNICAL_INDICATORS,
    CACHE_KEY_PREFIX,
    PAGINATION_DEFAULTS,
    FILE_PATHS,
    REGEX_PATTERNS
)

__all__ = [
    # ConfigManager
    "ConfigManager",
    "get_config",
    "init_config",
    "validate_config",
    "detect_environment",
    "reload_config",
    "config",

    # Constants
    "ErrorCode",
    "OrderStatus",
    "OrderType",
    "OrderDirection",
    "StrategyType",
    "Market",
    "TIME_CONSTANTS",
    "TRADING_HOURS",
    "DATA_FREQUENCY",
    "TECHNICAL_INDICATORS",
    "CACHE_KEY_PREFIX",
    "PAGINATION_DEFAULTS",
    "FILE_PATHS",
    "REGEX_PATTERNS"
]
