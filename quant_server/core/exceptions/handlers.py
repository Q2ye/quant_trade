# quant_server/core/exceptions/handlers.py
# !/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异常处理器

定义异常处理的策略和处理器，用于统一处理系统中的异常。
按照混合架构设计，位于核心基础设施层。
"""

import logging
import traceback
from typing import Any, Dict, Optional, Callable, List, Type
from abc import ABC, abstractmethod

from .base import BaseException, BaseAPIException
from .system_exceptions import TimeoutException, NetworkException
from .security_exceptions import (
	SecurityException,
	EncryptionException,
	JWTException,
	PasswordException,
	PermissionException,
	AuthenticationException,
	AuthorizationException,
	AuditException,
	SecurityConfigException
)
from .types import ErrorSeverity


class ExceptionHandler(ABC):
	"""异常处理器基类"""

	@abstractmethod
	def handle (self, exception: Exception, context: Optional[Dict[str, Any]] = None) -> bool:
		"""
		处理异常

		Args:
			exception: 异常对象
			context: 异常发生的上下文信息

		Returns:
			是否处理成功
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

	def handle (self, exception: Exception, context: Optional[Dict[str, Any]] = None) -> bool:
		"""
		记录异常日志

		Args:
			exception: 异常对象
			context: 上下文信息

		Returns:
			是否处理成功
		"""
		try:
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

			return True

		except Exception as e:
			# 记录异常处理器本身的错误
			self.logger.error(f"日志处理器处理异常时出错: {str(e)}")
			return False

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
			# 对于安全异常，进行特殊处理
			if isinstance(exception, SecurityException):
				# 安全异常可能需要脱敏处理
				safe_message = self._sanitize_security_message(exception.message)
				return f"🔐 {exception.__class__.__name__}: {safe_message} (Code: {exception.error_code}){context_str}"
			else:
				return f"{exception.__class__.__name__}: {exception.message} (Code: {exception.error_code}){context_str}"
		else:
			return f"{exception.__class__.__name__}: {str(exception)}{context_str}"

	def _sanitize_security_message (self, message: str) -> str:
		"""对安全异常消息进行脱敏处理"""
		# 这里可以添加脱敏逻辑，例如移除敏感信息
		# 简单示例：移除可能的密码、密钥等敏感信息
		import re

		# 移除可能的密钥
		sanitized = re.sub(r'[A-Za-z0-9+/]{40,}', '[REDACTED_KEY]', message)
		# 移除可能的密码
		sanitized = re.sub(r'password[^,]*,?', 'password=[REDACTED]', sanitized, flags=re.IGNORECASE)
		sanitized = re.sub(r'secret[^,]*,?', 'secret=[REDACTED]', sanitized, flags=re.IGNORECASE)

		return sanitized


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

	def handle (self, exception: Exception, context: Optional[Dict[str, Any]] = None) -> bool:
		"""
		发送异常通知

		Args:
			exception: 异常对象
			context: 上下文信息

		Returns:
			是否处理成功
		"""
		if not self._should_notify(exception):
			return False

		try:
			notification_message = self._format_notification_message(exception, context)

			for channel in self.notification_channels:
				try:
					channel.notify(notification_message)
				except Exception as e:
					logging.error(f"Failed to send notification via {channel}: {str(e)}")

			return True

		except Exception as e:
			logging.error(f"通知处理器处理异常时出错: {str(e)}")
			return False

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

		# 对于安全异常，即使级别较低也可能需要通知
		if isinstance(exception, SecurityException):
			# 安全异常通知策略
			security_notify_levels = {
				'encryption': ErrorSeverity.ERROR,  # 加密错误总是通知
				'jwt': ErrorSeverity.ERROR,  # JWT错误总是通知
				'authentication': ErrorSeverity.WARNING,  # 认证错误警告级别通知
				'authorization': ErrorSeverity.WARNING,  # 授权错误警告级别通知
				'permission': ErrorSeverity.WARNING,  # 权限错误警告级别通知
				'password': ErrorSeverity.ERROR,  # 密码错误总是通知
				'audit': ErrorSeverity.WARNING,  # 审计错误警告级别通知
				'config': ErrorSeverity.ERROR,  # 安全配置错误总是通知
			}

			# 根据安全异常子类型确定通知级别
			for category, level in security_notify_levels.items():
				if category in exception.__class__.__name__.lower():
					return self._compare_severity(exception.severity, level)

		# 默认比较严重程度级别
		return self._compare_severity(exception.severity, self.min_severity)

	def _compare_severity (self, exception_severity: ErrorSeverity, min_severity: ErrorSeverity) -> bool:
		"""比较严重程度级别"""
		severity_levels = {
			ErrorSeverity.DEBUG: 0,
			ErrorSeverity.INFO: 1,
			ErrorSeverity.WARNING: 2,
			ErrorSeverity.ERROR: 3,
			ErrorSeverity.CRITICAL: 4
		}

		exception_level = severity_levels.get(exception_severity, 0)
		min_level = severity_levels.get(min_severity, 0)

		return exception_level >= min_level

	def _format_notification_message (self, exception: Exception, context: Optional[Dict[str, Any]] = None) -> str:
		"""格式化通知消息"""
		if isinstance(exception, BaseException):
			# 对于安全异常，使用特殊格式
			if isinstance(exception, SecurityException):
				message = self._format_security_notification(exception, context)
			else:
				message = f"🚨 系统异常报警\n\n"
				message += f"异常类型: {exception.__class__.__name__}\n"
				message += f"错误代码: {exception.error_code}\n"
				message += f"错误消息: {exception.message}\n"
				message += f"严重程度: {exception.severity.value}\n"
				message += f"发生时间: {exception.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"

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

	def _format_security_notification (self, exception: SecurityException,
	                                   context: Optional[Dict[str, Any]] = None) -> str:
		"""格式化安全异常通知"""
		# 安全异常分类
		security_type = "安全异常"
		if isinstance(exception, EncryptionException):
			security_type = "加密异常"
		elif isinstance(exception, JWTException):
			security_type = "JWT异常"
		elif isinstance(exception, PasswordException):
			security_type = "密码异常"
		elif isinstance(exception, PermissionException):
			security_type = "权限异常"
		elif isinstance(exception, AuthenticationException):
			security_type = "认证异常"
		elif isinstance(exception, AuthorizationException):
			security_type = "授权异常"
		elif isinstance(exception, AuditException):
			security_type = "审计异常"
		elif isinstance(exception, SecurityConfigException):
			security_type = "安全配置异常"

		message = f"🔐 {security_type}报警\n\n"
		message += f"异常类型: {exception.__class__.__name__}\n"
		message += f"错误代码: {exception.error_code}\n"
		message += f"错误消息: {exception.message}\n"
		message += f"严重程度: {exception.severity.value}\n"
		message += f"发生时间: {exception.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"

		# 安全异常可能需要脱敏的上下文信息
		if context:
			message += f"\n上下文信息:\n"
			for key, value in context.items():
				# 对敏感字段进行脱敏
				if 'password' in key.lower() or 'token' in key.lower() or 'key' in key.lower():
					message += f"  {key}: [REDACTED]\n"
				else:
					message += f"  {key}: {value}\n"

		# 安全异常详情（脱敏处理）
		if exception.details:
			message += f"\n详细错误信息:\n"
			for key, value in exception.details.items():
				# 对敏感详情进行脱敏
				if any(sensitive in key.lower() for sensitive in ['password', 'token', 'key', 'secret', 'credential']):
					message += f"  {key}: [REDACTED]\n"
				elif isinstance(value, str) and len(value) > 100:
					message += f"  {key}: {value[:100]}...\n"
				else:
					message += f"  {key}: {value}\n"

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

	def handle (self, exception: Exception, context: Optional[Dict[str, Any]] = None) -> bool:
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


class SecurityExceptionHandler(ExceptionHandler):
	"""安全异常处理器"""

	def __init__ (
			self,
			enable_logging: bool = True,
			enable_notification: bool = True,
			enable_rate_limit: bool = True,
			max_auth_attempts: int = 5
	):
		"""
		初始化安全异常处理器

		Args:
			enable_logging: 是否启用日志记录
			enable_notification: 是否启用通知
			enable_rate_limit: 是否启用速率限制检查
			max_auth_attempts: 最大认证尝试次数
		"""
		self.enable_logging = enable_logging
		self.enable_notification = enable_notification
		self.enable_rate_limit = enable_rate_limit
		self.max_auth_attempts = max_auth_attempts

		# 安全异常计数器（用于速率限制）
		self.security_counters = {}

		# 内部处理器
		self.logging_handler = LoggingExceptionHandler("quant_server.security")
		self.notification_handler = NotificationExceptionHandler(min_severity=ErrorSeverity.WARNING)

	def handle (self, exception: Exception, context: Optional[Dict[str, Any]] = None) -> bool:
		"""
		处理安全异常

		Args:
			exception: 异常对象
			context: 上下文信息

		Returns:
			是否处理成功
		"""
		if not self.can_handle(exception):
			return False

		try:
			# 更新安全计数器
			self._update_security_counters(exception, context)

			# 检查是否需要触发速率限制
			if self.enable_rate_limit and self._should_rate_limit(exception, context):
				self._trigger_rate_limit(exception, context)

			# 记录日志
			if self.enable_logging:
				self.logging_handler.handle(exception, context)

			# 发送通知
			if self.enable_notification:
				self.notification_handler.handle(exception, context)

			# 对于特定的安全异常，执行特殊处理
			self._handle_specific_security_exception(exception, context)

			return True

		except Exception as e:
			logging.error(f"安全异常处理器处理异常时出错: {str(e)}")
			return False

	def can_handle (self, exception: Exception) -> bool:
		"""
		检查是否可以处理安全异常

		Args:
			exception: 异常对象

		Returns:
			如果是安全异常，则返回True
		"""
		return isinstance(exception, SecurityException)

	def _update_security_counters (self, exception: Exception, context: Optional[Dict[str, Any]] = None):
		"""更新安全异常计数器"""
		if not isinstance(exception, SecurityException):
			return

		# 根据异常类型更新计数器
		exception_type = exception.__class__.__name__
		counter_key = f"security_{exception_type}"

		if counter_key not in self.security_counters:
			self.security_counters[counter_key] = {
				'count': 0,
				'first_occurrence': None,
				'last_occurrence': None
			}

		counter = self.security_counters[counter_key]
		counter['count'] += 1

		from datetime import datetime
		now = datetime.now()

		if counter['first_occurrence'] is None:
			counter['first_occurrence'] = now

		counter['last_occurrence'] = now

		# 对于认证失败异常，记录用户信息
		if isinstance(exception, AuthenticationException):
			username = exception.details.get('username') if hasattr(exception, 'details') else None
			if username:
				user_key = f"auth_failed_{username}"
				if user_key not in self.security_counters:
					self.security_counters[user_key] = {
						'count': 0,
						'first_occurrence': None,
						'last_occurrence': None
					}

				user_counter = self.security_counters[user_key]
				user_counter['count'] += 1

				if user_counter['first_occurrence'] is None:
					user_counter['first_occurrence'] = now

				user_counter['last_occurrence'] = now

	def _should_rate_limit (self, exception: Exception, context: Optional[Dict[str, Any]] = None) -> bool:
		"""检查是否需要触发速率限制"""
		if not isinstance(exception, SecurityException):
			return False

		# 检查认证失败次数
		if isinstance(exception, AuthenticationException):
			username = exception.details.get('username') if hasattr(exception, 'details') else None
			if username:
				user_key = f"auth_failed_{username}"
				if user_key in self.security_counters:
					user_counter = self.security_counters[user_key]

					# 检查在指定时间窗口内的失败次数
					from datetime import datetime, timedelta
					time_window = timedelta(minutes=15)

					if (user_counter['last_occurrence'] - user_counter['first_occurrence']) <= time_window:
						if user_counter['count'] >= self.max_auth_attempts:
							return True

		# 检查其他安全异常的频率
		exception_type = exception.__class__.__name__
		counter_key = f"security_{exception_type}"

		if counter_key in self.security_counters:
			counter = self.security_counters[counter_key]

			# 如果在短时间内频繁出现同类型异常，触发速率限制
			from datetime import datetime, timedelta
			time_window = timedelta(minutes=5)

			if counter['last_occurrence'] and counter['first_occurrence']:
				time_diff = counter['last_occurrence'] - counter['first_occurrence']
				if time_diff <= time_window and counter['count'] >= 10:
					return True

		return False

	def _trigger_rate_limit (self, exception: Exception, context: Optional[Dict[str, Any]] = None):
		"""触发速率限制"""
		# 记录速率限制触发
		logging.warning(f"安全异常速率限制触发: {exception.__class__.__name__}")

		# 这里可以添加具体的速率限制逻辑，例如：
		# 1. 暂时锁定账户
		# 2. 限制IP访问
		# 3. 发送管理员警报

		# 记录到审计日志
		from datetime import datetime
		audit_context = {
			'exception_type': exception.__class__.__name__,
			'exception_message': exception.message,
			'timestamp': datetime.now().isoformat(),
			'action': 'rate_limit_triggered'
		}

		if context:
			audit_context.update(context)

	# 可以调用审计服务记录此事件
	# audit_service.log_security_event('rate_limit_triggered', audit_context)

	def _handle_specific_security_exception (self, exception: Exception, context: Optional[Dict[str, Any]] = None):
		"""处理特定的安全异常"""
		if isinstance(exception, AuthenticationException):
			# 认证异常特殊处理
			self._handle_authentication_exception(exception, context)
		elif isinstance(exception, PermissionException):
			# 权限异常特殊处理
			self._handle_permission_exception(exception, context)
		elif isinstance(exception, AuditException):
			# 审计异常特殊处理
			self._handle_audit_exception(exception, context)

	def _handle_authentication_exception (self, exception: AuthenticationException,
	                                      context: Optional[Dict[str, Any]] = None):
		"""处理认证异常"""
		# 这里可以添加认证异常的特殊处理逻辑
		# 例如：记录失败尝试、触发账户锁定等

		username = exception.details.get('username') if hasattr(exception, 'details') else None
		if username:
			# 记录认证失败尝试
			logging.info(f"认证失败尝试 - 用户名: {username}, 异常: {exception.message}")

	def _handle_permission_exception (self, exception: PermissionException, context: Optional[Dict[str, Any]] = None):
		"""处理权限异常"""
		# 这里可以添加权限异常的特殊处理逻辑
		# 例如：记录权限拒绝事件、发送安全警报等

		user_id = exception.details.get('user_id') if hasattr(exception, 'details') else None
		resource = exception.details.get('resource') if hasattr(exception, 'details') else None

		if user_id and resource:
			# 记录权限拒绝事件
			logging.warning(f"权限拒绝 - 用户ID: {user_id}, 资源: {resource}, 异常: {exception.message}")

	def _handle_audit_exception (self, exception: AuditException, context: Optional[Dict[str, Any]] = None):
		"""处理审计异常"""
		# 审计异常需要特别关注，因为可能意味着审计系统本身有问题

		# 记录审计系统错误
		logging.critical(f"审计系统异常: {exception.message}")

	# 这里可以触发紧急通知机制


class CompositeExceptionHandler(ExceptionHandler):
	"""组合异常处理器"""

	def __init__ (self, handlers: Optional[list] = None):
		"""
		初始化组合处理器

		Args:
			handlers: 处理器列表
		"""
		self.handlers = handlers or []

	def handle (self, exception: Exception, context: Optional[Dict[str, Any]] = None) -> bool:
		"""
		使用所有处理器处理异常

		Args:
			exception: 异常对象
			context: 上下文信息

		Returns:
			是否至少有一个处理器成功处理
		"""
		success = False

		for handler in self.handlers:
			if handler.can_handle(exception):
				try:
					result = handler.handle(exception, context)
					if result:
						success = True
				except Exception as e:
					logging.error(f"Handler {handler.__class__.__name__} failed: {str(e)}")

		return success

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
			LoggingExceptionHandler("quant_server.system"),
			NotificationExceptionHandler(min_severity=ErrorSeverity.ERROR),
			RetryExceptionHandler(
				max_retries=2,
				retry_delay=1.0,
				retryable_exceptions=[TimeoutException, NetworkException]
			)
		]
		return CompositeExceptionHandler(handlers)

	@staticmethod
	def create_security_handler () -> CompositeExceptionHandler:
		"""创建安全异常处理器"""
		handlers = [
			SecurityExceptionHandler(
				enable_logging=True,
				enable_notification=True,
				enable_rate_limit=True,
				max_auth_attempts=5
			),
			# 安全异常也需要通知
			NotificationExceptionHandler(min_severity=ErrorSeverity.WARNING),
			# 对于某些安全异常（如网络错误导致的认证失败）可以重试
			RetryExceptionHandler(
				max_retries=1,
				retry_delay=0.5,
				retryable_exceptions=[NetworkException]  # 网络错误可以重试
			)
		]
		return CompositeExceptionHandler(handlers)

	@staticmethod
	def create_trade_handler () -> CompositeExceptionHandler:
		"""创建交易异常处理器"""
		from .system_exceptions import TimeoutException, NetworkException

		handlers = [
			LoggingExceptionHandler("quant_server.trade"),
			NotificationExceptionHandler(min_severity=ErrorSeverity.ERROR),
			RetryExceptionHandler(
				max_retries=2,
				retry_delay=0.5,
				retryable_exceptions=[TimeoutException, NetworkException]
			)
		]
		return CompositeExceptionHandler(handlers)

	@staticmethod
	def create_data_handler () -> CompositeExceptionHandler:
		"""创建数据异常处理器"""
		handlers = [
			LoggingExceptionHandler("quant_server.data"),
			NotificationExceptionHandler(min_severity=ErrorSeverity.ERROR),
			RetryExceptionHandler(
				max_retries=3,
				retry_delay=1.0,
				retryable_exceptions=[TimeoutException, NetworkException]
			)
		]
		return CompositeExceptionHandler(handlers)

	@staticmethod
	def create_api_handler () -> CompositeExceptionHandler:
		"""创建API异常处理器"""
		handlers = [
			LoggingExceptionHandler("quant_server.api"),
			NotificationExceptionHandler(min_severity=ErrorSeverity.ERROR),
			# API异常通常不重试，直接返回错误
		]
		return CompositeExceptionHandler(handlers)


def handle_exception (
		exception: Exception,
		context: Optional[Dict[str, Any]] = None,
		handler: Optional[ExceptionHandler] = None
) -> bool:
	"""
	统一异常处理函数

	Args:
		exception: 异常对象
		context: 上下文信息
		handler: 异常处理器，不传则使用默认处理器

	Returns:
		是否处理成功
	"""
	if handler is None:
		# 根据异常类型选择处理器
		if isinstance(exception, SecurityException):
			handler = ExceptionHandlerFactory.create_security_handler()
		elif hasattr(exception, 'error_code') and isinstance(exception, BaseException):
			# 根据错误码选择处理器
			error_code = getattr(exception, 'error_code', '')
			if error_code.startswith('5'):  # 安全错误码
				handler = ExceptionHandlerFactory.create_security_handler()
			elif error_code.startswith('6'):  # 交易错误码
				handler = ExceptionHandlerFactory.create_trade_handler()
			elif error_code.startswith('3'):  # 数据错误码
				handler = ExceptionHandlerFactory.create_data_handler()
			elif error_code.startswith('4'):  # 系统错误码
				handler = ExceptionHandlerFactory.create_system_handler()
			elif error_code.startswith('2'):  # 业务错误码
				handler = ExceptionHandlerFactory.create_business_handler()
			else:
				handler = ExceptionHandlerFactory.create_default_handler()
		else:
			handler = ExceptionHandlerFactory.create_default_handler()

	return handler.handle(exception, context)


# 安全异常处理装饰器
def security_exception_handler (func):
	"""安全异常处理装饰器"""

	def wrapper (*args, **kwargs):
		try:
			return func(*args, **kwargs)
		except SecurityException as e:
			# 使用安全异常处理器处理
			handler = ExceptionHandlerFactory.create_security_handler()
			handler.handle(e, {
				'function': func.__name__,
				'module': func.__module__,
				'args': str(args)[:100],  # 限制长度，避免敏感信息泄露
				'kwargs': {k: '[REDACTED]' if 'password' in k.lower() or 'token' in k.lower() else v
				           for k, v in kwargs.items()}
			})
			# 重新抛出异常，让上层继续处理
			raise
		except Exception as e:
			# 其他异常使用默认处理器
			handle_exception(e, {
				'function': func.__name__,
				'module': func.__module__
			})
			raise

	return wrapper


def rate_limit_exception_handler (max_attempts: int = 5, window_minutes: int = 15):
	"""速率限制异常处理装饰器"""

	def decorator (func):
		def wrapper (*args, **kwargs):
			# 这里可以添加速率限制检查逻辑
			# 简单示例：检查函数调用频率

			import time
			current_time = time.time()

			# 使用函数名作为键
			func_key = f"{func.__module__}.{func.__name__}"

			# 这里应该使用更健壮的存储（如Redis）
			if not hasattr(wrapper, '_call_times'):
				wrapper._call_times = {}

			if func_key not in wrapper._call_times:
				wrapper._call_times[func_key] = []

			# 清理过期的调用记录
			wrapper._call_times[func_key] = [
				t for t in wrapper._call_times[func_key]
				if current_time - t < window_minutes * 60
			]

			# 检查是否超过限制
			if len(wrapper._call_times[func_key]) >= max_attempts:
				from .security_exceptions import TooManyAttemptsError
				raise TooManyAttemptsError(
					f"函数 {func.__name__} 调用过于频繁，请稍后再试",
					details={
						'max_attempts': max_attempts,
						'window_minutes': window_minutes,
						'current_attempts': len(wrapper._call_times[func_key])
					}
				)

			# 记录本次调用
			wrapper._call_times[func_key].append(current_time)

			try:
				return func(*args, **kwargs)
			except Exception as e:
				# 处理异常
				handle_exception(e, {
					'function': func.__name__,
					'module': func.__module__,
					'rate_limit_info': {
						'max_attempts': max_attempts,
						'window_minutes': window_minutes,
						'current_attempts': len(wrapper._call_times[func_key])
					}
				})
				raise

		return wrapper

	return decorator