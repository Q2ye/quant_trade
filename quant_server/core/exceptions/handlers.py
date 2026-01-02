#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异常处理器

定义异常处理的策略和处理器，用于统一处理系统中的异常。
"""

import logging
from typing import Any, Dict, Optional, Callable
from abc import ABC, abstractmethod

from .base import BaseException
from .types import ErrorSeverity


class ExceptionHandler(ABC):
	"""异常处理器基类"""

	@abstractmethod
	def handle (self, exception: Exception, context: Optional[Dict[str, Any]] = None):
		"""
		处理异常

		Args:
			exception: 异常对象
			context: 异常发生的上下文信息
		"""
		pass

	@abstractmethod
	def can_handle (self, exception: Exception) -> bool:
		"""
		检查是否可以处理该异常

		Args:
			exception: 异常对象

		Returns:
			是否可以处理
		"""
		pass


class LoggingExceptionHandler(ExceptionHandler):
	"""日志记录异常处理器"""

	def __init__ (self, logger_name: str = "quant_server.exceptions"):
		"""
		初始化日志处理器

		Args:
			logger_name: 日志记录器名称
		"""
		self.logger = logging.getLogger(logger_name)

	def handle (self, exception: Exception, context: Optional[Dict[str, Any]] = None):
		"""
		记录异常日志

		Args:
			exception: 异常对象
			context: 上下文信息
		"""
		log_message = self._format_log_message(exception, context)

		if isinstance(exception, BaseException):
			# 根据严重程度记录不同级别的日志
			if exception.severity == ErrorSeverity.DEBUG:
				self.logger.debug(log_message)
			elif exception.severity == ErrorSeverity.INFO:
				self.logger.info(log_message)
			elif exception.severity == ErrorSeverity.WARNING:
				self.logger.warning(log_message)
			elif exception.severity == ErrorSeverity.ERROR:
				self.logger.error(log_message)
			elif exception.severity == ErrorSeverity.CRITICAL:
				self.logger.critical(log_message)
		else:
			# 非BaseException，按错误级别记录
			self.logger.error(log_message)

	def can_handle (self, exception: Exception) -> bool:
		"""
		可以处理所有异常

		Args:
			exception: 异常对象

		Returns:
			True
		"""
		return True

	def _format_log_message (self, exception: Exception, context: Optional[Dict[str, Any]] = None) -> str:
		"""格式化日志消息"""
		context_str = f" | Context: {context}" if context else ""

		if isinstance(exception, BaseException):
			return f"{exception.__class__.__name__}: {exception.message} (Code: {exception.error_code}){context_str}"
		else:
			return f"{exception.__class__.__name__}: {str(exception)}{context_str}"


class NotificationExceptionHandler(ExceptionHandler):
	"""通知异常处理器"""

	def __init__ (
			self,
			notification_channels: Optional[list] = None,
			min_severity: ErrorSeverity = ErrorSeverity.ERROR
	):
		"""
		初始化通知处理器

		Args:
			notification_channels: 通知渠道列表
			min_severity: 最小通知严重程度
		"""
		self.notification_channels = notification_channels or []
		self.min_severity = min_severity

	def handle (self, exception: Exception, context: Optional[Dict[str, Any]] = None):
		"""
		发送异常通知

		Args:
			exception: 异常对象
			context: 上下文信息
		"""
		if not self._should_notify(exception):
			return

		notification_message = self._format_notification_message(exception, context)

		for channel in self.notification_channels:
			try:
				channel.notify(notification_message)
			except Exception as e:
				logging.error(f"Failed to send notification via {channel}: {str(e)}")

	def can_handle (self, exception: Exception) -> bool:
		"""
		检查是否可以处理该异常

		Args:
			exception: 异常对象

		Returns:
			如果是BaseException且严重程度足够，则返回True
		"""
		return isinstance(exception, BaseException) and self._should_notify(exception)

	def _should_notify (self, exception: Exception) -> bool:
		"""检查是否应该发送通知"""
		if not isinstance(exception, BaseException):
			return False

		# 比较严重程度级别
		severity_levels = {
			ErrorSeverity.DEBUG: 0,
			ErrorSeverity.INFO: 1,
			ErrorSeverity.WARNING: 2,
			ErrorSeverity.ERROR: 3,
			ErrorSeverity.CRITICAL: 4
		}

		exception_level = severity_levels.get(exception.severity, 0)
		min_level = severity_levels.get(self.min_severity, 0)

		return exception_level >= min_level

	def _format_notification_message (self, exception: Exception, context: Optional[Dict[str, Any]] = None) -> str:
		"""格式化通知消息"""
		if isinstance(exception, BaseException):
			message = f"🚨 系统异常报警\n\n"
			message += f"异常类型: {exception.__class__.__name__}\n"
			message += f"错误代码: {exception.error_code}\n"
			message += f"错误消息: {exception.message}\n"
			message += f"严重程度: {exception.severity.value}\n"

			if context:
				message += f"\n上下文信息:\n"
				for key, value in context.items():
					message += f"  {key}: {value}\n"

			if exception.details:
				message += f"\n详细错误信息:\n"
				for key, value in exception.details.items():
					message += f"  {key}: {value}\n"
		else:
			message = f"🚨 系统异常报警\n\n"
			message += f"异常类型: {exception.__class__.__name__}\n"
			message += f"错误消息: {str(exception)}\n"

		return message


class RetryExceptionHandler(ExceptionHandler):
	"""重试异常处理器"""

	def __init__ (
			self,
			max_retries: int = 3,
			retry_delay: float = 1.0,
			retryable_exceptions: Optional[list] = None
	):
		"""
		初始化重试处理器

		Args:
			max_retries: 最大重试次数
			retry_delay: 重试延迟（秒）
			retryable_exceptions: 可重试的异常类型列表
		"""
		self.max_retries = max_retries
		self.retry_delay = retry_delay
		self.retryable_exceptions = retryable_exceptions or []

	def handle (self, exception: Exception, context: Optional[Dict[str, Any]] = None):
		"""
		处理异常并决定是否重试

		Args:
			exception: 异常对象
			context: 上下文信息

		Returns:
			是否应该重试
		"""
		if not self.can_handle(exception):
			return False

		retry_count = context.get('retry_count', 0) if context else 0

		if retry_count < self.max_retries:
			import time
			time.sleep(self.retry_delay)
			return True
		else:
			return False

	def can_handle (self, exception: Exception) -> bool:
		"""
		检查是否可以重试该异常

		Args:
			exception: 异常对象

		Returns:
			如果是可重试的异常，则返回True
		"""
		for retryable_exception in self.retryable_exceptions:
			if isinstance(exception, retryable_exception):
				return True
		return False


class CompositeExceptionHandler(ExceptionHandler):
	"""组合异常处理器"""

	def __init__ (self, handlers: Optional[list] = None):
		"""
		初始化组合处理器

		Args:
			handlers: 处理器列表
		"""
		self.handlers = handlers or []

	def handle (self, exception: Exception, context: Optional[Dict[str, Any]] = None):
		"""
		使用所有处理器处理异常

		Args:
			exception: 异常对象
			context: 上下文信息
		"""
		for handler in self.handlers:
			if handler.can_handle(exception):
				try:
					handler.handle(exception, context)
				except Exception as e:
					logging.error(f"Handler {handler.__class__.__name__} failed: {str(e)}")

	def can_handle (self, exception: Exception) -> bool:
		"""
		检查是否有处理器可以处理该异常

		Args:
			exception: 异常对象

		Returns:
			如果有处理器可以处理，则返回True
		"""
		return any(handler.can_handle(exception) for handler in self.handlers)

	def add_handler (self, handler: ExceptionHandler):
		"""添加处理器"""
		self.handlers.append(handler)

	def remove_handler (self, handler: ExceptionHandler):
		"""移除处理器"""
		self.handlers = [h for h in self.handlers if h is not handler]


class ExceptionHandlerFactory:
	"""异常处理器工厂"""

	@staticmethod
	def create_default_handler () -> CompositeExceptionHandler:
		"""创建默认的异常处理器"""
		handlers = [
			LoggingExceptionHandler(),
			NotificationExceptionHandler()
		]
		return CompositeExceptionHandler(handlers)

	@staticmethod
	def create_business_handler () -> CompositeExceptionHandler:
		"""创建业务异常处理器"""
		handlers = [
			LoggingExceptionHandler("quant_server.business"),
			NotificationExceptionHandler(min_severity=ErrorSeverity.WARNING)
		]
		return CompositeExceptionHandler(handlers)

	@staticmethod
	def create_system_handler () -> CompositeExceptionHandler:
		"""创建系统异常处理器"""
		handlers = [
			LoggingExceptionHandler("quant_server.events"),
			NotificationExceptionHandler(min_severity=ErrorSeverity.ERROR)
		]
		return CompositeExceptionHandler(handlers)

	@staticmethod
	def create_trade_handler () -> CompositeExceptionHandler:
		"""创建交易异常处理器"""
		handlers = [
			LoggingExceptionHandler("quant_server.events"),
			NotificationExceptionHandler(min_severity=ErrorSeverity.ERROR),
			RetryExceptionHandler(
				max_retries=2,
				retry_delay=0.5,
				retryable_exceptions=[TimeoutException, NetworkException]
			)
		]
		return CompositeExceptionHandler(handlers)