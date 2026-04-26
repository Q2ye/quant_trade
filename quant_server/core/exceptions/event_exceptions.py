#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事件相关异常定义

事件引擎、事件发布、事件订阅等相关异常的统一定义。
按照混合架构设计，位于核心基础设施层。
"""

from typing import Any, Dict, Optional, List, Set
from .base import QuantBaseException, ValidationException
from .error_codes import ErrorCode
from .types import ErrorType, ErrorSeverity


class EventException(QuantBaseException):
	"""事件异常基类"""

	def __init__ (
			self,
			message: str,
			error_code: str = ErrorCode.EVENT_ERROR,
			event_type: Optional[str] = None,
			handler_name: Optional[str] = None,
			engine_name: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件异常

		Args:
			message: 错误消息
			error_code: 错误代码
			event_type: 事件类型
			handler_name: 事件处理器名称
			engine_name: 引擎名称
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		if event_type:
			details["event_type"] = event_type
		if handler_name:
			details["handler_name"] = handler_name
		if engine_name:
			details["engine_name"] = engine_name

		super().__init__(
			message=message,
			error_code=error_code,
			error_type=ErrorType.EVENT_ERROR,
			severity=ErrorSeverity.ERROR,
			details=details,
			cause=cause
		)


# ============================================================================
# 事件引擎异常
# ============================================================================

class EventEngineException(EventException):
	"""事件引擎异常"""

	def __init__ (
			self,
			message: str,
			engine_state: Optional[str] = None,
			active_events: Optional[int] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件引擎异常

		Args:
			message: 错误消息
			engine_state: 引擎状态
			active_events: 活动事件数量
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		if engine_state:
			details["engine_state"] = engine_state
		if active_events is not None:
			details["active_events"] = active_events

		super().__init__(
			message=message,
			error_code=ErrorCode.EVENT_ENGINE_ERROR,
			engine_name="EventEngine",
			details=details,
			cause=cause
		)


class EventEngineNotInitializedError(EventEngineException):
	"""事件引擎未初始化错误"""

	def __init__ (
			self,
			operation: str,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件引擎未初始化错误

		Args:
			operation: 尝试的操作
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		details["operation"] = operation

		super().__init__(
			message=f"事件引擎未初始化，无法执行操作: {operation}",
			engine_state="UNINITIALIZED",
			details=details,
			cause=cause
		)


class EventEngineAlreadyRunningError(EventEngineException):
	"""事件引擎已在运行错误"""

	def __init__ (
			self,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""初始化事件引擎已在运行错误"""
		super().__init__(
			message="事件引擎已在运行中，无法重复启动",
			engine_state="RUNNING",
			details=details,
			cause=cause
		)


class EventEngineStoppedError(EventEngineException):
	"""事件引擎已停止错误"""

	def __init__ (
			self,
			operation: str,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件引擎已停止错误

		Args:
			operation: 尝试的操作
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		details["operation"] = operation

		super().__init__(
			message=f"事件引擎已停止，无法执行操作: {operation}",
			engine_state="STOPPED",
			details=details,
			cause=cause
		)


class EventEngineTimeoutError(EventEngineException):
	"""事件引擎超时错误"""

	def __init__ (
			self,
			timeout_seconds: float,
			operation: str,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件引擎超时错误

		Args:
			timeout_seconds: 超时时间（秒）
			operation: 超时的操作
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		details["timeout_seconds"] = timeout_seconds
		details["operation"] = operation

		super().__init__(
			message=f"事件引擎操作超时: {operation}，超时时间: {timeout_seconds}秒",
			engine_state="TIMEOUT",
			details=details,
			cause=cause
		)


# ============================================================================
# 事件定义异常
# ============================================================================

class EventDefinitionException(EventException):
	"""事件定义异常"""

	def __init__ (
			self,
			message: str,
			event_type: str,
			event_class: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件定义异常

		Args:
			message: 错误消息
			event_type: 事件类型
			event_class: 事件类名
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		details["event_class"] = event_class

		super().__init__(
			message=message,
			error_code=ErrorCode.EVENT_DEFINITION_ERROR,
			event_type=event_type,
			details=details,
			cause=cause
		)


class InvalidEventTypeError(EventDefinitionException):
	"""无效的事件类型错误"""

	def __init__ (
			self,
			event_type: str,
			valid_types: Optional[List[str]] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化无效的事件类型错误

		Args:
			event_type: 无效的事件类型
			valid_types: 有效的事件类型列表
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		if valid_types:
			details["valid_types"] = valid_types

		message = f"无效的事件类型: {event_type}"
		if valid_types:
			message += f"，有效类型: {', '.join(valid_types)}"

		super().__init__(
			message=message,
			event_type=event_type,
			details=details,
			cause=cause
		)


class EventClassNotFoundError(EventDefinitionException):
	"""事件类未找到错误"""

	def __init__ (
			self,
			event_type: str,
			module_path: str,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件类未找到错误

		Args:
			event_type: 事件类型
			module_path: 模块路径
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		details["module_path"] = module_path

		super().__init__(
			message=f"事件类未找到: {event_type}，模块路径: {module_path}",
			event_type=event_type,
			details=details,
			cause=cause
		)


class EventValidationError(ValidationException):
	"""事件验证错误"""

	def __init__ (
			self,
			event_type: str,
			field: Optional[str] = None,
			value: Optional[Any] = None,
			validation_errors: Optional[List] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件验证错误

		Args:
			event_type: 事件类型
			field: 验证失败的字段
			value: 字段值
			validation_errors: 验证错误列表
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		details["event_type"] = event_type

		message = f"事件验证失败: {event_type}"
		if field:
			message += f"，字段: {field}"

		super().__init__(
			message=message,
			field=field,
			value=value,
			validation_errors=validation_errors,
			details=details,
			cause=cause
		)


# ============================================================================
# 事件发布异常
# ============================================================================

class EventPublishException(EventException):
	"""事件发布异常"""

	def __init__ (
			self,
			message: str,
			event_type: str,
			publisher: Optional[str] = None,
			event_data: Optional[Any] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件发布异常

		Args:
			message: 错误消息
			event_type: 事件类型
			publisher: 发布者名称
			event_data: 事件数据
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		if publisher:
			details["publisher"] = publisher
		if event_data is not None:
			details["event_data"] = str(event_data)

		super().__init__(
			message=message,
			error_code=ErrorCode.EVENT_PUBLISH_ERROR,
			event_type=event_type,
			details=details,
			cause=cause
		)


class EventQueueFullError(EventPublishException):
	"""事件队列已满错误"""

	def __init__ (
			self,
			event_type: str,
			queue_size: int,
			max_size: int,
			publisher: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件队列已满错误

		Args:
			event_type: 事件类型
			queue_size: 当前队列大小
			max_size: 最大队列大小
			publisher: 发布者名称
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		details["queue_size"] = queue_size
		details["max_size"] = max_size

		super().__init__(
			message=f"事件队列已满，无法发布事件: {event_type}，当前: {queue_size}，最大: {max_size}",
			event_type=event_type,
			publisher=publisher,
			details=details,
			cause=cause
		)


class EventRateLimitExceededError(EventPublishException):
	"""事件速率限制超出错误"""

	def __init__ (
			self,
			event_type: str,
			rate_limit: int,
			time_window: int,
			publisher: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件速率限制超出错误

		Args:
			event_type: 事件类型
			rate_limit: 速率限制（事件数/时间窗口）
			time_window: 时间窗口（秒）
			publisher: 发布者名称
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		details["rate_limit"] = rate_limit
		details["time_window_seconds"] = time_window

		super().__init__(
			message=f"事件速率限制超出: {event_type}，限制: {rate_limit}次/{time_window}秒",
			event_type=event_type,
			publisher=publisher,
			details=details,
			cause=cause
		)


class EventSerializationError(EventPublishException):
	"""事件序列化错误"""

	def __init__ (
			self,
			event_type: str,
			serializer_type: str,
			event_data: Optional[Any] = None,
			publisher: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件序列化错误

		Args:
			event_type: 事件类型
			serializer_type: 序列化器类型
			event_data: 事件数据
			publisher: 发布者名称
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		details["serializer_type"] = serializer_type

		super().__init__(
			message=f"事件序列化失败: {event_type}，序列化器: {serializer_type}",
			event_type=event_type,
			publisher=publisher,
			event_data=event_data,
			details=details,
			cause=cause
		)


# ============================================================================
# 事件订阅异常
# ============================================================================

class EventSubscribeException(EventException):
	"""事件订阅异常"""

	def __init__ (
			self,
			message: str,
			event_type: str,
			subscriber: Optional[str] = None,
			handler: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件订阅异常

		Args:
			message: 错误消息
			event_type: 事件类型
			subscriber: 订阅者名称
			handler: 处理器名称
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		if subscriber:
			details["subscriber"] = subscriber
		if handler:
			details["handler"] = handler

		super().__init__(
			message=message,
			error_code=ErrorCode.EVENT_SUBSCRIBE_ERROR,
			event_type=event_type,
			handler_name=handler,
			details=details,
			cause=cause
		)


class DuplicateSubscriptionError(EventSubscribeException):
	"""重复订阅错误"""

	def __init__ (
			self,
			event_type: str,
			subscriber: str,
			handler: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化重复订阅错误

		Args:
			event_type: 事件类型
			subscriber: 订阅者名称
			handler: 处理器名称
			details: 额外详情
			cause: 原始异常
		"""
		message = f"重复订阅事件: {event_type}，订阅者: {subscriber}"
		if handler:
			message += f"，处理器: {handler}"

		super().__init__(
			message=message,
			event_type=event_type,
			subscriber=subscriber,
			handler=handler,
			details=details,
			cause=cause
		)


class HandlerNotFoundException(EventSubscribeException):
	"""事件处理器未找到错误"""

	def __init__ (
			self,
			event_type: str,
			handler: str,
			subscriber: Optional[str] = None,
			available_handlers: Optional[List[str]] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件处理器未找到错误

		Args:
			event_type: 事件类型
			handler: 处理器名称
			subscriber: 订阅者名称
			available_handlers: 可用的处理器列表
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		if available_handlers:
			details["available_handlers"] = available_handlers

		message = f"事件处理器未找到: {handler}，事件类型: {event_type}"
		if available_handlers:
			message += f"，可用处理器: {', '.join(available_handlers)}"

		super().__init__(
			message=message,
			event_type=event_type,
			subscriber=subscriber,
			handler=handler,
			details=details,
			cause=cause
		)


class SubscriptionLimitExceededError(EventSubscribeException):
	"""订阅限制超出错误"""

	def __init__ (
			self,
			event_type: str,
			current_count: int,
			max_count: int,
			subscriber: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化订阅限制超出错误

		Args:
			event_type: 事件类型
			current_count: 当前订阅数
			max_count: 最大订阅数
			subscriber: 订阅者名称
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		details["current_count"] = current_count
		details["max_count"] = max_count

		super().__init__(
			message=f"订阅限制超出: {event_type}，当前: {current_count}，最大: {max_count}",
			event_type=event_type,
			subscriber=subscriber,
			details=details,
			cause=cause
		)


# ============================================================================
# 事件处理异常
# ============================================================================

class EventHandlerException(EventException):
	"""事件处理异常"""

	def __init__ (
			self,
			message: str,
			event_type: str,
			handler: str,
			event_data: Optional[Any] = None,
			execution_time: Optional[float] = None,
			retry_count: Optional[int] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件处理异常

		Args:
			message: 错误消息
			event_type: 事件类型
			handler: 处理器名称
			event_data: 事件数据
			execution_time: 执行时间（秒）
			retry_count: 重试次数
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		if event_data is not None:
			details["event_data"] = str(event_data)
		if execution_time is not None:
			details["execution_time_seconds"] = execution_time
		if retry_count is not None:
			details["retry_count"] = retry_count

		super().__init__(
			message=message,
			error_code=ErrorCode.EVENT_HANDLER_ERROR,
			event_type=event_type,
			handler_name=handler,
			details=details,
			cause=cause
		)


class HandlerExecutionError(EventHandlerException):
	"""处理器执行错误"""

	def __init__ (
			self,
			event_type: str,
			handler: str,
			error_message: str,
			event_data: Optional[Any] = None,
			execution_time: Optional[float] = None,
			retry_count: Optional[int] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化处理器执行错误

		Args:
			event_type: 事件类型
			handler: 处理器名称
			error_message: 具体的错误消息
			event_data: 事件数据
			execution_time: 执行时间（秒）
			retry_count: 重试次数
			details: 额外详情
			cause: 原始异常
		"""
		message = f"事件处理器执行失败: {handler}，事件类型: {event_type}，错误: {error_message}"

		super().__init__(
			message=message,
			event_type=event_type,
			handler=handler,
			event_data=event_data,
			execution_time=execution_time,
			retry_count=retry_count,
			details=details,
			cause=cause
		)


class HandlerTimeoutError(EventHandlerException):
	"""处理器超时错误"""

	def __init__ (
			self,
			event_type: str,
			handler: str,
			timeout_seconds: float,
			event_data: Optional[Any] = None,
			execution_time: Optional[float] = None,
			retry_count: Optional[int] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化处理器超时错误

		Args:
			event_type: 事件类型
			handler: 处理器名称
			timeout_seconds: 超时时间（秒）
			event_data: 事件数据
			execution_time: 执行时间（秒）
			retry_count: 重试次数
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		details["timeout_seconds"] = timeout_seconds

		message = f"事件处理器执行超时: {handler}，事件类型: {event_type}，超时时间: {timeout_seconds}秒"

		super().__init__(
			message=message,
			event_type=event_type,
			handler=handler,
			event_data=event_data,
			execution_time=execution_time,
			retry_count=retry_count,
			details=details,
			cause=cause
		)


class HandlerRetryExhaustedError(EventHandlerException):
	"""处理器重试耗尽错误"""

	def __init__ (
			self,
			event_type: str,
			handler: str,
			max_retries: int,
			last_error: str,
			event_data: Optional[Any] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化处理器重试耗尽错误

		Args:
			event_type: 事件类型
			handler: 处理器名称
			max_retries: 最大重试次数
			last_error: 最后一次错误消息
			event_data: 事件数据
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		details["max_retries"] = max_retries
		details["last_error"] = last_error

		message = f"事件处理器重试耗尽: {handler}，事件类型: {event_type}，最大重试次数: {max_retries}，最后错误: {last_error}"

		super().__init__(
			message=message,
			event_type=event_type,
			handler=handler,
			event_data=event_data,
			retry_count=max_retries,
			details=details,
			cause=cause
		)


# ============================================================================
# 事件路由异常
# ============================================================================

class EventRoutingException(EventException):
	"""事件路由异常"""

	def __init__ (
			self,
			message: str,
			event_type: str,
			source: Optional[str] = None,
			destination: Optional[str] = None,
			routing_key: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件路由异常

		Args:
			message: 错误消息
			event_type: 事件类型
			source: 源地址
			destination: 目标地址
			routing_key: 路由键
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		if source:
			details["source"] = source
		if destination:
			details["destination"] = destination
		if routing_key:
			details["routing_key"] = routing_key

		super().__init__(
			message=message,
			error_code=ErrorCode.EVENT_ROUTING_ERROR,
			event_type=event_type,
			details=details,
			cause=cause
		)


class EventRouteNotFoundError(EventRoutingException):
	"""事件路由未找到错误"""

	def __init__ (
			self,
			event_type: str,
			routing_key: str,
			source: Optional[str] = None,
			available_routes: Optional[Set[str]] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件路由未找到错误

		Args:
			event_type: 事件类型
			routing_key: 路由键
			source: 源地址
			available_routes: 可用路由列表
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		if available_routes:
			details["available_routes"] = list(available_routes)

		message = f"事件路由未找到: {event_type}，路由键: {routing_key}"
		if source:
			message += f"，源地址: {source}"

		super().__init__(
			message=message,
			event_type=event_type,
			source=source,
			routing_key=routing_key,
			details=details,
			cause=cause
		)


class CircularRoutingError(EventRoutingException):
	"""循环路由错误"""

	def __init__ (
			self,
			event_type: str,
			routing_path: List[str],
			source: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化循环路由错误

		Args:
			event_type: 事件类型
			routing_path: 路由路径
			source: 源地址
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		details["routing_path"] = routing_path

		message = f"事件循环路由检测到: {event_type}，路由路径: {' -> '.join(routing_path)}"

		super().__init__(
			message=message,
			event_type=event_type,
			source=source,
			details=details,
			cause=cause
		)


# ============================================================================
# 事件总线异常
# ============================================================================

class EventBusException(EventException):
	"""事件总线异常"""

	def __init__ (
			self,
			message: str,
			bus_type: str,
			bus_id: Optional[str] = None,
			channel: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件总线异常

		Args:
			message: 错误消息
			bus_type: 总线类型
			bus_id: 总线ID
			channel: 通道名称
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		details["bus_type"] = bus_type
		if bus_id:
			details["bus_id"] = bus_id
		if channel:
			details["channel"] = channel

		super().__init__(
			message=message,
			error_code=ErrorCode.EVENT_BUS_ERROR,
			details=details,
			cause=cause
		)


class EventBusConnectionError(EventBusException):
	"""事件总线连接错误"""

	def __init__ (
			self,
			bus_type: str,
			endpoint: str,
			bus_id: Optional[str] = None,
			channel: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件总线连接错误

		Args:
			bus_type: 总线类型
			endpoint: 连接端点
			bus_id: 总线ID
			channel: 通道名称
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		details["endpoint"] = endpoint

		message = f"事件总线连接失败: {bus_type}，端点: {endpoint}"

		super().__init__(
			message=message,
			bus_type=bus_type,
			bus_id=bus_id,
			channel=channel,
			details=details,
			cause=cause
		)


class EventBusDisconnectedError(EventBusException):
	"""事件总线断开连接错误"""

	def __init__ (
			self,
			bus_type: str,
			bus_id: Optional[str] = None,
			channel: Optional[str] = None,
			reconnect_attempts: Optional[int] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化事件总线断开连接错误

		Args:
			bus_type: 总线类型
			bus_id: 总线ID
			channel: 通道名称
			reconnect_attempts: 重连尝试次数
			details: 额外详情
			cause: 原始异常
		"""
		details = details or {}
		if reconnect_attempts is not None:
			details["reconnect_attempts"] = reconnect_attempts

		message = f"事件总线连接已断开: {bus_type}"

		super().__init__(
			message=message,
			bus_type=bus_type,
			bus_id=bus_id,
			channel=channel,
			details=details,
			cause=cause
		)


# ============================================================================
# 工厂函数
# ============================================================================

def create_event_exception (
		exception_type: str,
		message: str,
		**kwargs
) -> EventException:
	"""
	创建事件异常工厂函数

	Args:
		exception_type: 异常类型
		message: 错误消息
		**kwargs: 异常参数

	Returns:
		EventException: 事件异常实例

	Raises:
		ValueError: 如果异常类型无效
	"""
	exception_map = {
		# 事件引擎异常
		"EventEngineException": EventEngineException,
		"EventEngineNotInitializedError": EventEngineNotInitializedError,
		"EventEngineAlreadyRunningError": EventEngineAlreadyRunningError,
		"EventEngineStoppedError": EventEngineStoppedError,
		"EventEngineTimeoutError": EventEngineTimeoutError,

		# 事件定义异常
		"EventDefinitionException": EventDefinitionException,
		"InvalidEventTypeError": InvalidEventTypeError,
		"EventClassNotFoundError": EventClassNotFoundError,
		"EventValidationError": EventValidationError,

		# 事件发布异常
		"EventPublishException": EventPublishException,
		"EventQueueFullError": EventQueueFullError,
		"EventRateLimitExceededError": EventRateLimitExceededError,
		"EventSerializationError": EventSerializationError,

		# 事件订阅异常
		"EventSubscribeException": EventSubscribeException,
		"DuplicateSubscriptionError": DuplicateSubscriptionError,
		"HandlerNotFoundException": HandlerNotFoundException,
		"SubscriptionLimitExceededError": SubscriptionLimitExceededError,

		# 事件处理异常
		"EventHandlerException": EventHandlerException,
		"HandlerExecutionError": HandlerExecutionError,
		"HandlerTimeoutError": HandlerTimeoutError,
		"HandlerRetryExhaustedError": HandlerRetryExhaustedError,

		# 事件路由异常
		"EventRoutingException": EventRoutingException,
		"EventRouteNotFoundError": EventRouteNotFoundError,
		"CircularRoutingError": CircularRoutingError,

		# 事件总线异常
		"EventBusException": EventBusException,
		"EventBusConnectionError": EventBusConnectionError,
		"EventBusDisconnectedError": EventBusDisconnectedError,
	}

	if exception_type not in exception_map:
		raise ValueError(f"无效的事件异常类型: {exception_type}")

	exception_class = exception_map[exception_type]
	return exception_class(message=message, **kwargs)


# ============================================================================
# 异常辅助函数
# ============================================================================

def is_event_exception (exception: Exception) -> bool:
	"""
	检查异常是否为事件异常

	Args:
		exception: 异常实例

	Returns:
		bool: 是否为事件异常
	"""
	return isinstance(exception, EventException)


def extract_event_exception_info (exception: EventException) -> Dict[str, Any]:
	"""
	提取事件异常信息

	Args:
		exception: 事件异常实例

	Returns:
		Dict[str, Any]: 异常信息字典
	"""
	return {
		"exception_type": exception.__class__.__name__,
		"error_code": exception.error_code,
		"error_type": exception.error_type.value,
		"severity": exception.severity.value,
		"message": exception.message,
		"details": exception.details,
		"timestamp": exception.timestamp.isoformat(),
		"stack_trace": exception.stack_trace,
	}


def should_retry_event_exception (exception: EventException) -> bool:
	"""
	判断事件异常是否应该重试

	Args:
		exception: 事件异常实例

	Returns:
		bool: 是否应该重试
	"""
	# 不重试的错误类型
	non_retryable_exceptions = [
		EventValidationError,
		DuplicateSubscriptionError,
		HandlerNotFoundException,
		EventRouteNotFoundError,
		CircularRoutingError,
	]

	# 检查是否为不可重试的异常
	for exc_class in non_retryable_exceptions:
		if isinstance(exception, exc_class):
			return False

	# 检查错误严重程度
	if exception.severity == ErrorSeverity.CRITICAL:
		return False

	# 其他情况可以重试
	return True


def get_event_exception_retry_delay (exception: EventException) -> float:
	"""
	获取事件异常的重试延迟时间（秒）

	Args:
		exception: 事件异常实例

	Returns:
		float: 重试延迟时间（秒）
	"""
	# 根据异常类型确定延迟时间
	if isinstance(exception, HandlerTimeoutError):
		return 5.0  # 超时错误等待时间长一些
	elif isinstance(exception, EventRateLimitExceededError):
		return 10.0  # 速率限制错误等待时间更长
	elif isinstance(exception, EventBusConnectionError):
		return 3.0  # 连接错误中等等待时间
	else:
		return 1.0  # 默认1秒