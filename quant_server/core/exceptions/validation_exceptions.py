#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证异常定义

定义数据验证相关的异常，包括字段验证、参数验证、业务规则验证等。
按照混合架构设计，位于核心基础设施层。
"""

from typing import Any, Dict, Optional, List

from .base import QuantBaseException
from .error_codes import ErrorCode
from .types import ErrorType, ErrorSeverity


class ValidationError(QuantBaseException):
	"""验证异常基类"""

	def __init__ (
			self,
			message: str,
			validation_type: Optional[str] = None,
			validation_errors: Optional[List[Dict[str, Any]]] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化验证异常

		Args:
			message: 验证错误消息
			validation_type: 验证类型
			validation_errors: 验证错误列表
			details: 额外详情
			cause: 原始异常
		"""
		if validation_type or validation_errors:
			details = details or {}
			if validation_type:
				details["validation_type"] = validation_type
			if validation_errors:
				details["validation_errors"] = validation_errors

		super().__init__(
			message=message,
			error_code=ErrorCode.VALIDATION_ERROR,
			error_type=ErrorType.VALIDATION_ERROR,
			severity=ErrorSeverity.WARNING,
			details=details,
			cause=cause
		)


class SchemaValidationError(ValidationError):
	"""Schema验证异常"""

	def __init__ (
			self,
			message: str,
			schema_name: Optional[str] = None,
			schema_errors: Optional[List[Dict[str, Any]]] = None,
			data: Optional[Dict[str, Any]] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化Schema验证异常

		Args:
			message: Schema验证错误消息
			schema_name: Schema名称
			schema_errors: Schema错误列表
			data: 验证数据
			details: 额外详情
			cause: 原始异常
		"""
		if schema_name or schema_errors or data:
			details = details or {}
			if schema_name:
				details["schema_name"] = schema_name
			if schema_errors:
				details["schema_errors"] = schema_errors
			if data:
				details["data"] = data

		super().__init__(
			message=message,
			validation_type="schema",
			validation_errors=schema_errors,
			details=details,
			cause=cause
		)


class FieldValidationError(ValidationError):
	"""字段验证异常"""

	def __init__ (
			self,
			message: str,
			field_name: Optional[str] = None,
			field_value: Optional[Any] = None,
			field_type: Optional[str] = None,
			validation_rule: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化字段验证异常

		Args:
			message: 字段验证错误消息
			field_name: 字段名称
			field_value: 字段值
			field_type: 字段类型
			validation_rule: 验证规则
			details: 额外详情
			cause: 原始异常
		"""
		if field_name or field_value or field_type or validation_rule:
			details = details or {}
			if field_name:
				details["field_name"] = field_name
			if field_value:
				details["field_value"] = field_value
			if field_type:
				details["field_type"] = field_type
			if validation_rule:
				details["validation_rule"] = validation_rule

		super().__init__(
			message=message,
			validation_type="field",
			details=details,
			cause=cause
		)


class ParameterValidationError(ValidationError):
	"""参数验证异常"""

	def __init__ (
			self,
			message: str,
			parameter_name: Optional[str] = None,
			parameter_value: Optional[Any] = None,
			parameter_type: Optional[str] = None,
			allowed_values: Optional[List[Any]] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化参数验证异常

		Args:
			message: 参数验证错误消息
			parameter_name: 参数名称
			parameter_value: 参数值
			parameter_type: 参数类型
			allowed_values: 允许的值列表
			details: 额外详情
			cause: 原始异常
		"""
		if parameter_name or parameter_value or parameter_type or allowed_values:
			details = details or {}
			if parameter_name:
				details["parameter_name"] = parameter_name
			if parameter_value:
				details["parameter_value"] = parameter_value
			if parameter_type:
				details["parameter_type"] = parameter_type
			if allowed_values:
				details["allowed_values"] = allowed_values

		super().__init__(
			message=message,
			validation_type="parameter",
			details=details,
			cause=cause
		)


class DataValidationError(ValidationError):
	"""数据验证异常"""

	def __init__ (
			self,
			message: str,
			data_type: Optional[str] = None,
			data_source: Optional[str] = None,
			validation_rules: Optional[List[str]] = None,
			invalid_data: Optional[List[Dict[str, Any]]] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化数据验证异常

		Args:
			message: 数据验证错误消息
			data_type: 数据类型
			data_source: 数据源
			validation_rules: 验证规则列表
			invalid_data: 无效数据列表
			details: 额外详情
			cause: 原始异常
		"""
		if data_type or data_source or validation_rules or invalid_data:
			details = details or {}
			if data_type:
				details["data_type"] = data_type
			if data_source:
				details["data_source"] = data_source
			if validation_rules:
				details["validation_rules"] = validation_rules
			if invalid_data:
				details["invalid_data"] = invalid_data

		super().__init__(
			message=message,
			validation_type="data",
			details=details,
			cause=cause
		)


class BusinessRuleValidationError(ValidationError):
	"""业务规则验证异常"""

	def __init__ (
			self,
			message: str,
			rule_name: Optional[str] = None,
			rule_description: Optional[str] = None,
			rule_condition: Optional[str] = None,
			rule_violation: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化业务规则验证异常

		Args:
			message: 业务规则验证错误消息
			rule_name: 规则名称
			rule_description: 规则描述
			rule_condition: 规则条件
			rule_violation: 规则违反详情
			details: 额外详情
			cause: 原始异常
		"""
		if rule_name or rule_description or rule_condition or rule_violation:
			details = details or {}
			if rule_name:
				details["rule_name"] = rule_name
			if rule_description:
				details["rule_description"] = rule_description
			if rule_condition:
				details["rule_condition"] = rule_condition
			if rule_violation:
				details["rule_violation"] = rule_violation

		super().__init__(
			message=message,
			validation_type="business_rule",
			details=details,
			cause=cause
		)
