"""
日志工具包 - 提供结构化、可配置、高性能的日志功能

模块包含：
1. structured_logger.py - 结构化日志记录器：结构化日志、上下文感知、异步记录
2. log_formatter.py - 日志格式化器：格式定义、颜色渲染、多格式输出
3. log_context.py - 日志上下文管理器：上下文传播、存储、管理

设计原则：
1. 结构化：所有日志输出为结构化格式，便于解析和分析
2. 上下文感知：自动跟踪和记录请求、用户、会话等上下文信息
3. 高性能：异步记录、批量写入、缓存优化
4. 可配置：日志级别、格式、输出目标可动态配置
5. 可扩展：支持自定义处理器、过滤器、格式化器

使用示例：
    from quant_server.core.utils.logging_utils import (
        get_logger, get_context_manager, FormatterFactory,
        LogLevel, LogFormat, with_context
    )

    # 获取日志记录器
    logger = get_logger("app.module")

    # 添加上下文
    with get_context_manager().context_manager(request_id="req_123", user_id="user_456"):
        logger.info("处理请求", extra={"param": "value"})

    # 使用装饰器
    @with_context(operation="process_data")
    def process_data():
        logger.info("处理数据")
"""

from .structured_logger import (
	# 枚举和数据结构
	LogLevel,
	LogFormat,
	LogRecord,

	# 上下文管理
	LogContext,
	LogContextManager as ContextManager,

	# 日志记录器
	StructuredLogger,
	Timer,
	TimerContext,

	# 处理器工厂
	HandlerFactory,

	# 过滤器
	LogFilter,

	# 便捷函数
	get_logger,
	configure_logging,
	enable_async_logging,
	disable_async_logging,

	# 管理器
	LogManager,

)

from .log_formatter import (
	# 枚举和数据结构
	ColorMode,
	FieldType,
	FieldSpec,

	# 颜色方案
	ColorScheme,

	# 格式化器
	LogFormatter,

	# 工厂
	FormatterFactory,

	# 特定格式
	JSONFormatter,
	CSVFormatter,
	GELFFormatter,

	# 渲染器
	LogRenderer
)

from .log_context import (
	# 枚举和数据结构
	ContextType,
	ContextEntry,
	ContextSnapshot,

	# 存储
	ContextStorage,
	ThreadLocalContextStorage,
	ContextVarStorage,

	# 管理器
	LogContextManager,
	LogContextManagerInstance,

	# 便捷函数
	get_context_manager,
	get_context,
	set_context,
	update_context,
	clear_context,
	bind_request_context,
	bind_user_context,
	bind_session_context,
	create_child_context,

	# 装饰器
	with_context,
	with_async_context,

	# 上下文感知
	ContextAwareFunction,
	context_aware,

	# 过滤器
	ContextFilter
)

__all__ = [
	# 结构化日志
	'LogLevel',
	'LogFormat',
	'LogRecord',
	'LogContext',
	'StructuredLogger',
	'Timer',
	'TimerContext',
	'HandlerFactory',
	'LogFilter',
	'get_logger',
	'configure_logging',
	'enable_async_logging',
	'disable_async_logging',
	'LogManager',

	# 日志格式化
	'ColorMode',
	'FieldType',
	'FieldSpec',
	'ColorScheme',
	'LogFormatter',
	'FormatterFactory',
	'JSONFormatter',
	'CSVFormatter',
	'GELFFormatter',
	'LogRenderer',

	# 日志上下文
	'ContextType',
	'ContextEntry',
	'ContextSnapshot',
	'ContextStorage',
	'ThreadLocalContextStorage',
	'ContextVarStorage',
	'LogContextManager',
	'LogContextManagerInstance',
	'get_context_manager',
	'get_context',
	'set_context',
	'update_context',
	'clear_context',
	'bind_request_context',
	'bind_user_context',
	'bind_session_context',
	'create_child_context',
	'with_context',
	'with_async_context',
	'ContextAwareFunction',
	'context_aware',
	'ContextFilter'
]

# 版本信息
__version__ = "1.0.0"
__author__ = "量化交易系统架构团队"
__description__ = "量化交易系统日志工具包"

# 默认配置
DEFAULT_LOGGING_CONFIG = {
	"level": LogLevel.INFO,
	"format": LogFormat.JSON,
	"color_mode": ColorMode.AUTO,
	"async_enabled": False,
	"handlers": [],
	"filters": []
}

# 全局日志管理器实例
_log_manager = None
_context_manager = None


def get_global_log_manager () -> LogManager:
	"""获取全局日志管理器"""
	global _log_manager
	if _log_manager is None:
		_log_manager = LogManager()
	return _log_manager


def get_global_context_manager () -> LogContextManager:
	"""获取全局上下文管理器"""
	global _context_manager
	if _context_manager is None:
		_context_manager = LogContextManager()
	return _context_manager


# 初始化函数
def init_logging (config: dict = None):
	"""
	初始化日志系统

	Args:
		config: 日志配置
	"""
	config = config or DEFAULT_LOGGING_CONFIG.copy()

	# 配置日志管理器
	log_manager = get_global_log_manager()

	# 转换配置
	log_config = {
		"default_level": config.get("level", LogLevel.INFO).value
		if isinstance(config.get("level"), LogLevel) else config.get("level", "INFO"),
		"default_format": config.get("format", LogFormat.JSON).value
		if isinstance(config.get("format"), LogFormat) else config.get("format", "json")
	}

	log_manager.configure(log_config)

	# 配置异步日志
	if config.get("async_enabled", False):
		enable_async_logging()

	# 添加默认处理器（如果没有）
	if not config.get("handlers"):
		console_handler = HandlerFactory.create_console_handler(
			level=config.get("level", LogLevel.INFO),
			format=config.get("format", LogFormat.TEXT)
		)

		# 获取根记录器并添加处理器
		root_logger = get_logger("")
		root_logger.add_handler("console", console_handler)

	return log_manager


def shutdown_logging ():
	"""关闭日志系统"""
	log_manager = get_global_log_manager()
	log_manager.shutdown()

	context_manager = get_global_context_manager()
	context_manager.stop_cleanup()


# 便捷函数
def debug (message: str, **kwargs):
	"""记录DEBUG级别日志（使用根记录器）"""
	logger = get_logger("")
	logger.debug(message, **kwargs)


def info (message: str, **kwargs):
	"""记录INFO级别日志（使用根记录器）"""
	logger = get_logger("")
	logger.info(message, **kwargs)


def warning (message: str, **kwargs):
	"""记录WARNING级别日志（使用根记录器）"""
	logger = get_logger("")
	logger.warning(message, **kwargs)


def error (message: str, **kwargs):
	"""记录ERROR级别日志（使用根记录器）"""
	logger = get_logger("")
	logger.error(message, **kwargs)


def critical (message: str, **kwargs):
	"""记录CRITICAL级别日志（使用根记录器）"""
	logger = get_logger("")
	logger.critical(message, **kwargs)


def exception (message: str, exception: Exception, **kwargs):
	"""记录异常日志（使用根记录器）"""
	logger = get_logger("")
	logger.exception(message, exception, **kwargs)


# 性能监控装饰器
def log_performance (operation: str = None, level: LogLevel = LogLevel.INFO):
	"""
	记录函数性能的装饰器

	Args:
		operation: 操作名称（默认使用函数名）
		level: 日志级别
	"""

	def decorator (func):
		@with_context(operation=operation or func.__name__, source="performance_monitor")
		def wrapper (*args, **kwargs):
			logger = get_logger(func.__module__)

			with logger.time_it(operation or func.__name__) as timer:
				try:
					result = func(*args, **kwargs)
					timer.stop(level=level)
					return result
				except Exception as e:
					timer.stop(level=LogLevel.ERROR, exception=e)
					raise

		@with_context(operation=operation or func.__name__, source="performance_monitor")
		async def async_wrapper (*args, **kwargs):
			logger = get_logger(func.__module__)

			with logger.time_it(operation or func.__name__) as timer:
				try:
					result = await func(*args, **kwargs)
					timer.stop(level=level)
					return result
				except Exception as e:
					timer.stop(level=LogLevel.ERROR, exception=e)
					raise

		if asyncio.iscoroutinefunction(func):
			return async_wrapper
		else:
			return wrapper

	return decorator


# 导出便捷函数
__all__.extend([
	'get_global_log_manager',
	'get_global_context_manager',
	'init_logging',
	'shutdown_logging',
	'debug',
	'info',
	'warning',
	'error',
	'critical',
	'exception',
	'log_performance',
	'DEFAULT_LOGGING_CONFIG'
])

# 自动导入asyncio用于异步装饰器
import asyncio

print(f"日志工具包 {__version__} 加载完成")
print(f"包含 {len(__all__)} 个导出项")
print(f"默认配置: {DEFAULT_LOGGING_CONFIG}")



'''# 完整使用示例
from quant_server.core.utils.logging_utils import (
    get_logger, get_context_manager, init_logging,
    LogLevel, LogFormat, with_context, log_performance
)

# 1. 初始化日志系统
init_logging({
    "level": LogLevel.DEBUG,
    "format": LogFormat.JSON,
    "async_enabled": True
})

# 2. 获取日志记录器
logger = get_logger("app.module")

# 3. 使用上下文管理器
with get_context_manager().context_manager(
    request_id="req_123456",
    user_id="user_789",
    session_id="ses_abc"
):
    logger.info("开始处理请求")
    
    # 4. 记录结构化日志
    logger.debug("调试信息", extra={
        "param1": "value1",
        "param2": 123,
        "tags": ["tag1", "tag2"]
    })
    
    # 5. 记录异常
    try:
        raise ValueError("测试异常")
    except Exception as e:
        logger.exception("处理异常", e)
    
    logger.info("请求处理完成")

# 6. 使用装饰器
@with_context(operation="data_processing", source="batch_job")
@log_performance(level=LogLevel.INFO)
def process_data(events):
    """数据处理函数"""
    logger = get_logger(__name__)
    logger.info(f"处理数据，大小: {len(events)}")
    # ... 处理逻辑
    return True

# 7. 异步使用
import asyncio

@with_context(operation="async_processing", source="async_job")
async def async_process():
    logger = get_logger(__name__)
    logger.info("开始异步处理")
    await asyncio.sleep(0.1)
    logger.info("异步处理完成")

# 8. 获取统计信息
stats = logger.get_stats()
print(f"日志统计: {stats}")

# 9. 关闭日志系统
from quant_server.core.utils.logging_utils import shutdown_logging
shutdown_logging()
'''