"""
结构化日志记录器 - 提供结构化、可搜索、可分析的日志功能

职责：
1. 结构化日志格式（JSON格式，便于解析和分析）
2. 上下文感知日志（自动添加请求ID、用户ID、模块名等上下文信息）
3. 日志级别管理（DEBUG, INFO, WARNING, ERROR, CRITICAL）
4. 异步日志记录（避免阻塞主线程）
5. 日志缓冲和批量写入（提高性能）
6. 日志过滤和采样（控制日志量）

设计原则：
1. 结构化：所有日志输出为结构化格式（JSON）
2. 可配置：日志级别、格式、输出目标可动态配置
3. 高性能：异步写入，避免阻塞业务逻辑
4. 可扩展：支持自定义处理器和过滤器
5. 上下文感知：自动跟踪和记录上下文信息
"""

import hashlib
import inspect
import json
import logging
import os
import queue
import sys
import threading
import time
import traceback
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
# 默认导入Python标准日志模块
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Dict, List, Any, Optional, Union, Callable, Tuple

# 尝试导入第三方结构化日志库
try:
    import structlog

    STRUCTLOG_AVAILABLE = True
except ImportError:
    structlog = None
    STRUCTLOG_AVAILABLE = False


class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @classmethod
    def from_string(cls, level_str: str) -> 'LogLevel':
        """从字符串转换为日志级别"""
        level_str = level_str.upper()
        for level in cls:
            if level.value == level_str:
                return level
        return cls.INFO

    def to_int(self) -> int:
        """转换为Python logging级别整数"""
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        return level_map.get(self.value, logging.INFO)


class LogFormat(Enum):
    """日志格式枚举"""
    JSON = "json"  # JSON格式（结构化日志）
    TEXT = "text"  # 文本格式（人类可读）
    GELF = "gelf"  # Graylog扩展日志格式
    CSV = "csv"  # CSV格式


@dataclass
class LogRecord:
    """日志记录数据结构"""
    timestamp: str  # ISO格式时间戳
    level: str  # 日志级别
    message: str  # 日志消息
    logger_name: str  # 记录器名称
    module: str  # 模块名
    function: str  # 函数名
    line_number: int  # 行号
    process_id: int  # 进程ID
    thread_id: int  # 线程ID
    thread_name: str  # 线程名
    request_id: Optional[str] = None  # 请求ID
    user_id: Optional[str] = None  # 用户ID
    session_id: Optional[str] = None  # 会话ID
    correlation_id: Optional[str] = None  # 关联ID
    duration_ms: Optional[float] = None  # 操作持续时间（毫秒）
    extra: Dict[str, Any] = field(default_factory=dict)  # 额外字段
    exception: Optional[Dict[str, Any]] = None  # 异常信息

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result: Dict[str, Any] = {
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            "logger_name": self.logger_name,
            "module": self.module,
            "function": self.function,
            "line_number": self.line_number,
            "process_id": self.process_id,
            "thread_id": self.thread_id,
            "thread_name": self.thread_name
        }

        # 添加可选字段
        if self.request_id:
            result["request_id"] = self.request_id
        if self.user_id:
            result["user_id"] = self.user_id
        if self.session_id:
            result["session_id"] = self.session_id
        if self.correlation_id:
            result["correlation_id"] = self.correlation_id
        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms

        # 添加额外字段
        if self.extra:
            result.update(self.extra)

        # 添加异常信息
        if self.exception:
            result["exception"] = self.exception

        return result

    def to_json(self, indent: Optional[int] = None) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    def to_text(self, colorize: bool = False) -> str:
        """转换为文本格式"""
        timestamp = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]

        if colorize:
            # 根据级别添加颜色
            color_codes = {
                "DEBUG": "\033[36m",  # 青色
                "INFO": "\033[32m",  # 绿色
                "WARNING": "\033[33m",  # 黄色
                "ERROR": "\033[31m",  # 红色
                "CRITICAL": "\033[35m"  # 紫色
            }
            reset = "\033[0m"
            level_color = color_codes.get(self.level, "")
            level_text = f"{level_color}{self.level:8}{reset}"
        else:
            level_text = f"{self.level:8}"

        base_msg = f"{timestamp} | {level_text} | {self.logger_name} | {self.module}:{self.function}:{self.line_number} | {self.message}"

        # 添加上下文信息
        context_parts = []
        if self.request_id:
            context_parts.append(f"req:{self.request_id[:8]}")
        if self.user_id:
            context_parts.append(f"usr:{self.user_id[:8]}")
        if self.duration_ms is not None:
            context_parts.append(f"dur:{self.duration_ms:.2f}ms")

        if context_parts:
            base_msg += f" [{' '.join(context_parts)}]"

        # 添加额外字段
        if self.extra:
            extra_str = " ".join([f"{k}={v}" for k, v in self.extra.items()])
            base_msg += f" {{{extra_str}}}"

        # 添加异常信息
        if self.exception:
            exc_msg = f"\nException: {self.exception.get('type')}: {self.exception.get('message')}"
            if self.exception.get('traceback'):
                exc_msg += f"\n{self.exception['traceback']}"
            base_msg += exc_msg

        return base_msg


class LogContext:
    """日志上下文管理器"""

    def __init__(self):
        self._context = {}
        self._stack = []

    def set(self, key: str, value: Any):
        """设置上下文值"""
        self._context[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """获取上下文值"""
        return self._context.get(key, default)

    def update(self, **kwargs):
        """批量更新上下文"""
        self._context.update(kwargs)

    def remove(self, key: str):
        """移除上下文值"""
        if key in self._context:
            del self._context[key]

    def clear(self):
        """清除所有上下文"""
        self._context.clear()

    def get_all(self) -> Dict[str, Any]:
        """获取所有上下文"""
        return self._context.copy()

    def push_context(self, **kwargs):
        """推入新的上下文层"""
        self._stack.append(self._context.copy())
        self.update(**kwargs)

    def pop_context(self):
        """弹出上下文层"""
        if self._stack:
            self._context = self._stack.pop()
        else:
            self.clear()

    def as_context_manager(self, **kwargs):
        """作为上下文管理器使用"""
        return LogContextManager(self, **kwargs)


class LogContextManager:
    """日志上下文管理器（with语句支持）"""

    def __init__(self, context: LogContext, **kwargs):
        self.context = context
        self.kwargs = kwargs

    def __enter__(self):
        self.context.push_context(**self.kwargs)
        return self.context

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.context.pop_context()


class StructuredLogger:
    """
    结构化日志记录器

    基于Python标准logging模块，提供结构化日志功能
    """

    def __init__(self, name: str, level: LogLevel = LogLevel.INFO,
                 format: LogFormat = LogFormat.JSON,
                 context: Optional[LogContext] = None):
        """
        初始化结构化日志记录器

        Args:
            name: 记录器名称
            level: 日志级别
            format: 日志格式
            context: 日志上下文
        """
        self.name = name
        self.level = level
        self.format = format
        self.context = context or LogContext()

        # 创建Python标准记录器
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level.to_int())
        self._logger.propagate = False  # 防止重复记录

        # 添加默认处理器（如果没有处理器）
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(level.to_int())
            self._logger.addHandler(handler)

        # 存储处理器映射
        self._handlers: Dict[str, logging.Handler] = {}
        self._filters: List[Callable] = []

        # 性能统计
        self._stats = {
            "total_logs": 0,
            "by_level": defaultdict(int),
            "dropped_logs": 0,
            "last_reset": time.time()
        }

        # 异步日志队列
        self._async_queue = queue.Queue(maxsize=10000)
        self._async_worker = None
        self._async_running = False

        # 缓存调用者信息以减少开销
        self._caller_cache = {}

    def add_handler(self, name: str, handler: logging.Handler):
        """添加日志处理器"""
        handler.setLevel(self.level.to_int())
        self._handlers[name] = handler
        self._logger.addHandler(handler)

    def remove_handler(self, name: str):
        """移除日志处理器"""
        if name in self._handlers:
            handler = self._handlers.pop(name)
            self._logger.removeHandler(handler)

    def add_filter(self, filter_func: Callable[[LogRecord], bool]):
        """添加日志过滤器"""
        self._filters.append(filter_func)

    def _get_caller_info(self, depth: int = 3) -> Tuple[str, str, int]:
        """
        获取调用者信息

        Args:
            depth: 调用栈深度

        Returns:
            Tuple[模块名, 函数名, 行号]
        """
        # 生成缓存键
        frame = inspect.currentframe()
        for _ in range(depth):
            if frame:
                frame = frame.f_back

        if not frame:
            return "unknown", "unknown", 0

        # 使用帧信息作为缓存键
        cache_key = (frame.f_code.co_filename, frame.f_lineno)

        if cache_key in self._caller_cache:
            return self._caller_cache[cache_key]

        # 获取调用者信息
        module = inspect.getmodule(frame)
        module_name = module.__name__ if module else "unknown"
        function_name = frame.f_code.co_name
        line_number = frame.f_lineno

        # 缓存结果
        self._caller_cache[cache_key] = (module_name, function_name, line_number)

        return module_name, function_name, line_number

    def _create_log_record(self, level: LogLevel, message: str,
                           extra: Dict[str, Any] = None,
                           exception: Optional[Exception] = None) -> LogRecord:
        """
        创建日志记录

        Args:
            level: 日志级别
            message: 日志消息
            extra: 额外字段
            exception: 异常对象

        Returns:
            LogRecord: 日志记录对象
        """
        # 获取调用者信息
        module, function, line_number = self._get_caller_info(depth=4)

        # 获取当前线程信息
        current_thread = threading.current_thread()

        # 构建日志记录
        log_record = LogRecord(
            timestamp=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            level=level.value,
            message=str(message),
            logger_name=self.name,
            module=module,
            function=function,
            line_number=line_number,
            process_id=os.getpid(),
            thread_id=current_thread.ident or 0,
            thread_name=current_thread.name,
            extra=extra or {},
        )

        # 添加上下文信息
        context_data = self.context.get_all()
        if "request_id" in context_data:
            log_record.request_id = context_data["request_id"]
        if "user_id" in context_data:
            log_record.user_id = context_data["user_id"]
        if "session_id" in context_data:
            log_record.session_id = context_data["session_id"]
        if "correlation_id" in context_data:
            log_record.correlation_id = context_data["correlation_id"]

        # 添加异常信息
        if exception:
            log_record.exception = {
                "type": type(exception).__name__,
                "message": str(exception),
                "traceback": traceback.format_exc()
            }

        # 合并额外字段（避免覆盖关键字段）
        if extra:
            for key, value in extra.items():
                if not hasattr(log_record, key) and key not in ["timestamp", "level", "message"]:
                    log_record.extra[key] = value

        return log_record

    def _should_log(self, log_record: LogRecord) -> bool:
        """
        检查是否应该记录日志（应用过滤器）

        Args:
            log_record: 日志记录

        Returns:
            bool: 是否记录
        """
        # 检查日志级别
        current_level_int = self.level.to_int()
        log_level_int = LogLevel.from_string(log_record.level).to_int()

        if log_level_int < current_level_int:
            return False

        # 应用自定义过滤器
        for filter_func in self._filters:
            try:
                if not filter_func(log_record):
                    return False
            except Exception:
                # 过滤器异常不应影响日志记录
                pass

        return True

    def _format_log_record(self, log_record: LogRecord) -> str:
        """
        格式化日志记录

        Args:
            log_record: 日志记录

        Returns:
            str: 格式化后的日志字符串
        """
        if self.format == LogFormat.JSON:
            return log_record.to_json()
        elif self.format == LogFormat.TEXT:
            # 检查是否输出到终端以决定是否着色
            colorize = sys.stdout.isatty() if hasattr(sys.stdout, 'isatty') else False
            return log_record.to_text(colorize=colorize)
        elif self.format == LogFormat.GELF:
            # Graylog扩展日志格式
            gelf_dict = {
                "version": "1.1",
                "host": os.uname().nodename if hasattr(os, 'uname') else "unknown",
                "short_message": log_record.message,
                "full_message": log_record.message,
                "timestamp": time.time(),
                "level": log_record.level,
                "_logger": log_record.logger_name,
                "_module": log_record.module,
                "_function": log_record.function,
                "_line": log_record.line_number,
            }

            # 添加上下文和额外字段作为GELF附加字段
            if log_record.request_id:
                gelf_dict["_request_id"] = log_record.request_id
            if log_record.user_id:
                gelf_dict["_user_id"] = log_record.user_id

            for key, value in log_record.extra.items():
                gelf_dict[f"_{key}"] = value

            return json.dumps(gelf_dict)
        elif self.format == LogFormat.CSV:
            # CSV格式（简化版）
            fields = [
                log_record.timestamp,
                log_record.level,
                log_record.logger_name,
                log_record.module,
                log_record.function,
                str(log_record.line_number),
                log_record.message.replace('"', '""')  # 转义引号
            ]
            return ','.join([f'"{f}"' for f in fields])
        else:
            # 默认使用文本格式
            return log_record.to_text()

    def _log(self, level: LogLevel, message: str,
             extra: Dict[str, Any] = None,
             exception: Optional[Exception] = None):
        """
        内部日志方法

        Args:
            level: 日志级别
            message: 日志消息
            extra: 额外字段
            exception: 异常对象
        """
        # 创建日志记录
        log_record = self._create_log_record(level, message, extra, exception)

        # 检查是否应该记录
        if not self._should_log(log_record):
            self._stats["dropped_logs"] += 1
            return

        # 格式化日志记录
        formatted_message = self._format_log_record(log_record)

        # 使用Python logging记录
        log_method = getattr(self._logger, level.value.lower())

        # 如果是异常日志，使用exc_info参数
        if exception:
            log_method(formatted_message, exc_info=exception)
        else:
            log_method(formatted_message)

        # 更新统计信息
        self._stats["total_logs"] += 1
        self._stats["by_level"][level.value] += 1

    def debug(self, message: str, **kwargs):
        """记录DEBUG级别日志"""
        self._log(LogLevel.DEBUG, message, kwargs.get('extra'))

    def info(self, message: str, **kwargs):
        """记录INFO级别日志"""
        self._log(LogLevel.INFO, message, kwargs.get('extra'))

    def warning(self, message: str, **kwargs):
        """记录WARNING级别日志"""
        self._log(LogLevel.WARNING, message, kwargs.get('extra'))

    def error(self, message: str, **kwargs):
        """记录ERROR级别日志"""
        exception = kwargs.get('exception')
        self._log(LogLevel.ERROR, message, kwargs.get('extra'), exception)

    def critical(self, message: str, **kwargs):
        """记录CRITICAL级别日志"""
        exception = kwargs.get('exception')
        self._log(LogLevel.CRITICAL, message, kwargs.get('extra'), exception)

    def exception(self, message: str, exception: Exception, **kwargs):
        """记录异常日志（自动包含异常信息）"""
        self._log(LogLevel.ERROR, message, kwargs.get('extra'), exception)

    def log_with_level(self, level: Union[str, LogLevel], message: str, **kwargs):
        """使用指定级别记录日志"""
        if isinstance(level, str):
            level = LogLevel.from_string(level)
        self._log(level, message, kwargs.get('extra'), kwargs.get('exception'))

    # 性能计时方法
    def time_it(self, operation: str):
        """计时上下文管理器"""
        return TimerContext(self, operation)

    def start_timer(self, operation: str) -> 'Timer':
        """开始计时器"""
        return Timer(self, operation)

    # 异步日志方法
    def start_async_logging(self):
        """启动异步日志记录"""
        if self._async_running:
            return

        self._async_running = True
        self._async_worker = threading.Thread(
            target=self._async_log_worker,
            daemon=True,
            name=f"AsyncLogger-{self.name}"
        )
        self._async_worker.start()

    def stop_async_logging(self):
        """停止异步日志记录"""
        self._async_running = False
        if self._async_worker:
            self._async_worker.join(timeout=5)
            self._async_worker = None

    def _async_log_worker(self):
        """异步日志工作线程"""
        while self._async_running or not self._async_queue.empty():
            try:
                # 从队列获取日志任务
                task = self._async_queue.get(timeout=1)
                if task is None:  # 停止信号
                    break

                level, message, extra, exception = task
                self._log(level, message, extra, exception)
                self._async_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                # 异步日志错误不应影响主程序
                warnings.warn(f"Async logger error: {e}")

    def async_debug(self, message: str, **kwargs):
        """异步记录DEBUG级别日志"""
        self._async_queue.put((LogLevel.DEBUG, message, kwargs.get('extra'), None))

    def async_info(self, message: str, **kwargs):
        """异步记录INFO级别日志"""
        self._async_queue.put((LogLevel.INFO, message, kwargs.get('extra'), None))

    def async_error(self, message: str, **kwargs):
        """异步记录ERROR级别日志"""
        exception = kwargs.get('exception')
        self._async_queue.put((LogLevel.ERROR, message, kwargs.get('extra'), exception))

    # 上下文管理
    def bind(self, **kwargs):
        """绑定上下文值"""
        self.context.update(**kwargs)
        return self

    def push_context(self, **kwargs):
        """推入新的上下文层"""
        self.context.push_context(**kwargs)

    def pop_context(self):
        """弹出上下文层"""
        self.context.pop_context()

    # 统计信息
    def get_stats(self, reset: bool = False) -> Dict[str, Any]:
        """获取统计信息"""
        stats: Dict[str, Any] = self._stats.copy()
        stats["by_level"] = dict(stats["by_level"])

        if reset:
            self._stats = {
                "total_logs": 0,
                "by_level": defaultdict(int),
                "dropped_logs": 0,
                "last_reset": time.time()
            }

        return stats


class Timer:
    """计时器类"""

    def __init__(self, logger: StructuredLogger, operation: str):
        """
        初始化计时器

        Args:
            logger: 日志记录器
            operation: 操作名称
        """
        self.logger = logger
        self.operation = operation
        self.start_time = time.time()
        self.stopped = False

    def stop(self, level: LogLevel = LogLevel.INFO, **kwargs):
        """停止计时并记录日志"""
        if self.stopped:
            return

        duration_ms = (time.time() - self.start_time) * 1000

        # 添加持续时间到额外字段
        extra = kwargs.get('extra', {})
        extra['duration_ms'] = duration_ms
        extra['operation'] = self.operation

        # 记录日志
        self.logger.log_with_level(
            level,
            f"Operation '{self.operation}' completed in {duration_ms:.2f}ms",
            extra=extra,
            **{k: v for k, v in kwargs.items() if k != 'extra'}
        )

        self.stopped = True
        return duration_ms

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 根据是否有异常决定日志级别
        level = LogLevel.ERROR if exc_type else LogLevel.INFO
        self.stop(level=level, exception=exc_val)


class TimerContext:
    """计时上下文管理器"""

    def __init__(self, logger: StructuredLogger, operation: str):
        self.logger = logger
        self.operation = operation

    def __enter__(self):
        self.timer = Timer(self.logger, self.operation)
        return self.timer

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.timer.__exit__(exc_type, exc_val, exc_tb)


# 全局日志管理器
class LogManager:
    """日志管理器（单例模式）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._loggers: Dict[str, StructuredLogger] = {}
        self._default_config = {
            "level": LogLevel.INFO,
            "format": LogFormat.JSON,
            "handlers": [],
            "filters": []
        }
        self._global_context = LogContext()
        self._async_enabled = False

        self._initialized = True

    def get_logger(self, name: str, **kwargs) -> StructuredLogger:
        """
        获取或创建日志记录器

        Args:
            name: 记录器名称
            **kwargs: 配置参数

        Returns:
            StructuredLogger: 日志记录器
        """
        if name not in self._loggers:
            # 合并配置
            config = self._default_config.copy()
            config.update(kwargs)

            # 创建日志记录器
            logger = StructuredLogger(
                name=name,
                level=config.get("level", LogLevel.INFO),
                format=config.get("format", LogFormat.JSON),
                context=self._global_context
            )

            # 添加处理器
            for handler in config.get("handlers", []):
                logger.add_handler(handler.name, handler)

            # 添加过滤器
            for filter_func in config.get("filters", []):
                logger.add_filter(filter_func)

            # 如果启用了异步日志，启动异步记录
            if self._async_enabled:
                logger.start_async_logging()

            self._loggers[name] = logger

        return self._loggers[name]

    def configure(self, config: Dict[str, Any]):
        """
        配置日志管理器

        Args:
            config: 配置字典
        """
        if "default_level" in config:
            self._default_config["level"] = LogLevel.from_string(config["default_level"])

        if "default_format" in config:
            self._default_config["format"] = LogFormat(config["default_format"])

        # 配置现有记录器
        for logger in self._loggers.values():
            if "default_level" in config:
                logger.level = LogLevel.from_string(config["default_level"])

            if "default_format" in config:
                logger.format = LogFormat(config["default_format"])

    def enable_async_logging(self):
        """启用异步日志记录"""
        self._async_enabled = True
        for logger in self._loggers.values():
            logger.start_async_logging()

    def disable_async_logging(self):
        """禁用异步日志记录"""
        self._async_enabled = False
        for logger in self._loggers.values():
            logger.stop_async_logging()

    def get_global_context(self) -> LogContext:
        """获取全局上下文"""
        return self._global_context

    def set_global_context(self, **kwargs):
        """设置全局上下文"""
        self._global_context.update(**kwargs)

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有记录器的统计信息"""
        stats: Dict[str, Dict[str, Any]] = {}
        for name, logger in self._loggers.items():
            stats[name] = logger.get_stats()
        return stats

    def shutdown(self):
        """关闭日志管理器"""
        self.disable_async_logging()

        # 刷新所有处理器
        for logger in self._loggers.values():
            for handler in logger._logger.handlers:
                handler.flush()
                handler.close()


# 便捷函数
_log_manager = LogManager()


def get_logger(name: str = "app", **kwargs) -> StructuredLogger:
    """获取日志记录器（便捷函数）"""
    return _log_manager.get_logger(name, **kwargs)


def configure_logging(config: Dict[str, Any]):
    """配置日志系统（便捷函数）"""
    _log_manager.configure(config)


def enable_async_logging():
    """启用异步日志记录（便捷函数）"""
    _log_manager.enable_async_logging()


def disable_async_logging():
    """禁用异步日志记录（便捷函数）"""
    _log_manager.disable_async_logging()


def get_global_context() -> LogContext:
    """获取全局日志上下文（便捷函数）"""
    return _log_manager.get_global_context()


# 预定义的处理器工厂
class HandlerFactory:
    """处理器工厂类"""

    @staticmethod
    def create_console_handler(level: LogLevel = LogLevel.INFO,
                               format: LogFormat = LogFormat.TEXT) -> logging.Handler:
        """创建控制台处理器"""
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level.to_int())

        # 设置格式化器
        if format == LogFormat.TEXT:
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        else:
            # 对于非文本格式，使用原始消息格式化器
            formatter = logging.Formatter('%(message)s')

        handler.setFormatter(formatter)
        handler.name = "console"
        return handler

    @staticmethod
    def create_file_handler(filename: str,
                            level: LogLevel = LogLevel.INFO,
                            max_bytes: int = 10 * 1024 * 1024,  # 10MB
                            backup_count: int = 5) -> logging.Handler:
        """创建文件处理器（按大小轮转）"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        handler = RotatingFileHandler(
            filename=filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        handler.setLevel(level.to_int())
        handler.setFormatter(logging.Formatter('%(message)s'))
        handler.name = "file"
        return handler

    @staticmethod
    def create_timed_file_handler(filename: str,
                                  level: LogLevel = LogLevel.INFO,
                                  when: str = 'midnight',
                                  interval: int = 1,
                                  backup_count: int = 30) -> logging.Handler:
        """创建文件处理器（按时间轮转）"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        handler = TimedRotatingFileHandler(
            filename=filename,
            when=when,
            interval=interval,
            backupCount=backup_count,
            encoding='utf-8'
        )
        handler.setLevel(level.to_int())
        handler.setFormatter(logging.Formatter('%(message)s'))
        handler.name = "timed_file"
        return handler

    @staticmethod
    def create_syslog_handler(address: Tuple[str, int] = ('localhost', 514),
                              level: LogLevel = LogLevel.INFO) -> logging.Handler:
        """创建Syslog处理器"""
        from logging.handlers import SysLogHandler

        handler = SysLogHandler(address=address)
        handler.setLevel(level.to_int())
        handler.setFormatter(logging.Formatter('%(message)s'))
        handler.name = "syslog"
        return handler


# 预定义的过滤器
class LogFilter:
    """日志过滤器类"""

    @staticmethod
    def create_level_filter(min_level: LogLevel, max_level: Optional[LogLevel] = None):
        """创建级别过滤器"""

        def filter_func(record: LogRecord) -> bool:
            record_level = LogLevel.from_string(record.level)
            if record_level.to_int() < min_level.to_int():
                return False
            if max_level and record_level.to_int() > max_level.to_int():
                return False
            return True

        return filter_func

    @staticmethod
    def create_module_filter(include_modules: List[str] = None,
                             exclude_modules: List[str] = None):
        """创建模块过滤器"""

        def filter_func(record: LogRecord) -> bool:
            if include_modules and record.module not in include_modules:
                return False
            if exclude_modules and record.module in exclude_modules:
                return False
            return True

        return filter_func

    @staticmethod
    def create_sampling_filter(sample_rate: float = 1.0):
        """创建采样过滤器"""

        def filter_func(record: LogRecord) -> bool:
            # 使用消息哈希决定是否采样
            message_hash = hashlib.md5(record.message.encode()).hexdigest()
            hash_int = int(message_hash[:8], 16)
            return (hash_int % 10000) < (sample_rate * 10000)

        return filter_func


# 使用示例
if __name__ == "__main__":
    print("=== 结构化日志记录器示例 ===")

    # 1. 基本使用
    logger = get_logger("example")

    logger.info("系统启动")
    logger.debug("调试信息", extra={"key": "value"})
    logger.warning("警告信息")

    # 2. 添加上下文
    with get_global_context().as_context_manager(request_id="req_123", user_id="user_456"):
        logger.info("处理请求")
        logger.error("处理错误", exception=ValueError("测试错误"))

    # 3. 计时功能
    with logger.time_it("数据库查询"):
        time.sleep(0.1)  # 模拟耗时操作

    # 4. 异步日志
    enable_async_logging()
    for i in range(10):
        logger.async_info(f"异步日志消息 {i}")
    time.sleep(1)  # 等待异步日志处理

    # 5. 获取统计信息
    stats = logger.get_stats()
    print(f"日志统计: {stats}")

    # 6. 使用文件处理器
    file_handler = HandlerFactory.create_file_handler("logs/app.log")
    file_logger = get_logger("file_logger")
    file_logger.add_handler("file", file_handler)
    file_logger.info("这条日志会写入文件")

    # 7. 关闭日志系统
    disable_async_logging()

    print("示例完成")
