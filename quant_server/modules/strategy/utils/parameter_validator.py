# -*- coding: utf-8 -*-
"""
参数验证器
负责验证策略参数的合法性，确保策略在运行前具有正确的参数配置
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Type

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
	"""验证状态枚举"""
	VALID = "valid"
	INVALID = "invalid"
	WARNING = "warning"


@dataclass
class ValidationResult:
	"""验证结果"""
	status: ValidationStatus
	message: str
	parameter_name: Optional[str] = None
	parameter_value: Optional[Any] = None


@dataclass
class ValidationReport:
	"""验证报告"""
	valid: bool
	results: List[ValidationResult]
	errors: List[ValidationResult]
	warnings: List[ValidationResult]


class ParameterValidator:
	"""
	策略参数验证器

	负责验证策略参数的合法性，支持：
	- 必填参数检查
	- 类型检查
	- 范围检查
	- 枚举值检查
	- 自定义验证规则
	"""

	def __init__ (self):
		"""初始化参数验证器"""
		self._rules = {}
		logger.info("参数验证器初始化完成")

	def validate_parameters (self, parameters: Dict[str, Any], schema: Dict[str, Dict[str, Any]]) -> ValidationReport:
		"""
		验证参数字典

		Args:
			parameters: 参数字典
			schema: 参数模式定义

		Returns:
			验证报告
		"""
		results = []
		errors = []
		warnings = []

		try:
			# 检查必填参数
			for param_name, param_schema in schema.items():
				if param_schema.get('required', False) and param_name not in parameters:
					result = ValidationResult(
						status=ValidationStatus.INVALID,
						message=f"缺少必填参数: {param_name}",
						parameter_name=param_name
					)
					results.append(result)
					errors.append(result)

			# 验证所有参数
			for param_name, param_value in parameters.items():
				if param_name in schema:
					param_schema = schema[param_name]

					# 类型验证
					if 'type' in param_schema:
						type_result = self._validate_type(param_name, param_value, param_schema['type'])
						results.append(type_result)
						if type_result.status == ValidationStatus.INVALID:
							errors.append(type_result)
						elif type_result.status == ValidationStatus.WARNING:
							warnings.append(type_result)

					# 范围验证
					if 'range' in param_schema:
						range_result = self._validate_range(param_name, param_value, param_schema['range'])
						results.append(range_result)
						if range_result.status == ValidationStatus.INVALID:
							errors.append(range_result)
						elif range_result.status == ValidationStatus.WARNING:
							warnings.append(range_result)

					# 枚举验证
					if 'enum' in param_schema:
						enum_result = self._validate_enum(param_name, param_value, param_schema['enum'])
						results.append(enum_result)
						if enum_result.status == ValidationStatus.INVALID:
							errors.append(enum_result)
						elif enum_result.status == ValidationStatus.WARNING:
							warnings.append(enum_result)
				else:
					# 未知参数警告
					warning = ValidationResult(
						status=ValidationStatus.WARNING,
						message=f"未知参数: {param_name}",
						parameter_name=param_name,
						parameter_value=param_value
					)
					results.append(warning)
					warnings.append(warning)

			# 检查验证结果
			valid = len(errors) == 0

			logger.info(f"参数验证完成，共验证 {len(parameters)} 个参数，{len(errors)} 个错误，{len(warnings)} 个警告")

			return ValidationReport(
				valid=valid,
				results=results,
				errors=errors,
				warnings=warnings
			)

		except Exception as e:
			logger.error(f"参数验证过程中发生错误: {e}")
			error_result = ValidationResult(
				status=ValidationStatus.INVALID,
				message=f"验证过程中发生错误: {str(e)}"
			)
			return ValidationReport(
				valid=False,
				results=[error_result],
				errors=[error_result],
				warnings=[]
			)

	@staticmethod
	def _validate_type (param_name: str, param_value: Any, expected_type: Union[str, Type]) -> ValidationResult:

		"""
		验证参数类型

		Args:
			param_name: 参数名称
			param_value: 参数值
			expected_type: 期望类型

		Returns:
			验证结果
		"""
		try:
			if isinstance(expected_type, str):
				# 字符串类型名称
				if expected_type == 'int' and not isinstance(param_value, int):
					return ValidationResult(
						status=ValidationStatus.INVALID,
						message=f"参数 {param_name} 类型错误，期望 int，实际 {type(param_value).__name__}",
						parameter_name=param_name,
						parameter_value=param_value
					)
				elif expected_type == 'float' and not isinstance(param_value, (int, float)):
					return ValidationResult(
						status=ValidationStatus.INVALID,
						message=f"参数 {param_name} 类型错误，期望 float，实际 {type(param_value).__name__}",
						parameter_name=param_name,
						parameter_value=param_value
					)
				elif expected_type == 'bool' and not isinstance(param_value, bool):
					return ValidationResult(
						status=ValidationStatus.INVALID,
						message=f"参数 {param_name} 类型错误，期望 bool，实际 {type(param_value).__name__}",
						parameter_name=param_name,
						parameter_value=param_value
					)
				elif expected_type == 'str' and not isinstance(param_value, str):
					return ValidationResult(
						status=ValidationStatus.INVALID,
						message=f"参数 {param_name} 类型错误，期望 str，实际 {type(param_value).__name__}",
						parameter_name=param_name,
						parameter_value=param_value
					)
				elif expected_type == 'list' and not isinstance(param_value, list):
					return ValidationResult(
						status=ValidationStatus.INVALID,
						message=f"参数 {param_name} 类型错误，期望 list，实际 {type(param_value).__name__}",
						parameter_name=param_name,
						parameter_value=param_value
					)
				elif expected_type == 'dict' and not isinstance(param_value, dict):
					return ValidationResult(
						status=ValidationStatus.INVALID,
						message=f"参数 {param_name} 类型错误，期望 dict，实际 {type(param_value).__name__}",
						parameter_name=param_name,
						parameter_value=param_value
					)
			else:
				# 实际类型对象
				if not isinstance(param_value, expected_type):
					return ValidationResult(
						status=ValidationStatus.INVALID,
						message=f"参数 {param_name} 类型错误，期望 {expected_type.__name__}，实际 {type(param_value).__name__}",
						parameter_name=param_name,
						parameter_value=param_value
					)

			return ValidationResult(
				status=ValidationStatus.VALID,
				message=f"参数 {param_name} 类型验证通过",
				parameter_name=param_name,
				parameter_value=param_value
			)

		except Exception as e:
			return ValidationResult(
				status=ValidationStatus.INVALID,
				message=f"参数 {param_name} 类型验证失败: {str(e)}",
				parameter_name=param_name,
				parameter_value=param_value
			)

	@staticmethod
	def _validate_range (param_name: str, param_value: Any, range_config: Dict[str, Any]) -> ValidationResult:

		"""
		验证参数范围

		Args:
			param_name: 参数名称
			param_value: 参数值
			range_config: 范围配置

		Returns:
			验证结果
		"""
		try:
			# 检查最小值
			if 'min' in range_config and param_value < range_config['min']:
				return ValidationResult(
					status=ValidationStatus.INVALID,
					message=f"参数 {param_name} 小于最小值 {range_config['min']}",
					parameter_name=param_name,
					parameter_value=param_value
				)

			# 检查最大值
			if 'max' in range_config and param_value > range_config['max']:
				return ValidationResult(
					status=ValidationStatus.INVALID,
					message=f"参数 {param_name} 大于最大值 {range_config['max']}",
					parameter_name=param_name,
					parameter_value=param_value
				)

			# 检查最小长度（适用于字符串、列表等）
			if 'min_length' in range_config and hasattr(param_value, '__len__'):
				if len(param_value) < range_config['min_length']:
					return ValidationResult(
						status=ValidationStatus.INVALID,
						message=f"参数 {param_name} 长度小于最小长度 {range_config['min_length']}",
						parameter_name=param_name,
						parameter_value=param_value
					)

			# 检查最大长度（适用于字符串、列表等）
			if 'max_length' in range_config and hasattr(param_value, '__len__'):
				if len(param_value) > range_config['max_length']:
					return ValidationResult(
						status=ValidationStatus.INVALID,
						message=f"参数 {param_name} 长度大于最大长度 {range_config['max_length']}",
						parameter_name=param_name,
						parameter_value=param_value
					)

			return ValidationResult(
				status=ValidationStatus.VALID,
				message=f"参数 {param_name} 范围验证通过",
				parameter_name=param_name,
				parameter_value=param_value
			)

		except Exception as e:
			return ValidationResult(
				status=ValidationStatus.INVALID,
				message=f"参数 {param_name} 范围验证失败: {str(e)}",
				parameter_name=param_name,
				parameter_value=param_value
			)

	@staticmethod
	def _validate_enum (param_name: str, param_value: Any, enum_values: List[Any]) -> ValidationResult:

		"""
		验证参数是否在枚举值中

		Args:
			param_name: 参数名称
			param_value: 参数值
			enum_values: 枚举值列表

		Returns:
			验证结果
		"""
		try:
			if param_value not in enum_values:
				return ValidationResult(
					status=ValidationStatus.INVALID,
					message=f"参数 {param_name} 值不在允许范围内，允许值: {enum_values}",
					parameter_name=param_name,
					parameter_value=param_value
				)

			return ValidationResult(
				status=ValidationStatus.VALID,
				message=f"参数 {param_name} 枚举值验证通过",
				parameter_name=param_name,
				parameter_value=param_value
			)

		except Exception as e:
			return ValidationResult(
				status=ValidationStatus.INVALID,
				message=f"参数 {param_name} 枚举值验证失败: {str(e)}",
				parameter_name=param_name,
				parameter_value=param_value
			)

	@staticmethod
	def get_default_schema (strategy_type: str) -> Dict[str, Dict[str, Any]]:

		"""
		获取默认参数模式

		Args:
			strategy_type: 策略类型

		Returns:
			默认参数模式
		"""
		default_schemas = {
			'alpha': {
				'lookback_period': {
					'type': 'int',
					'required': True,
					'range': {'min': 5, 'max': 100}
				},
				'portfolio_size': {
					'type': 'int',
					'required': True,
					'range': {'min': 10, 'max': 100}
				},
				'rebalance_frequency': {
					'type': 'int',
					'required': True,
					'range': {'min': 1, 'max': 60}
				}
			},
			'cta': {
				'fast_period': {
					'type': 'int',
					'required': True,
					'range': {'min': 5, 'max': 50}
				},
				'slow_period': {
					'type': 'int',
					'required': True,
					'range': {'min': 10, 'max': 100}
				},
				'stop_loss': {
					'type': 'float',
					'required': False,
					'range': {'min': 0.01, 'max': 0.5}
				}
			},
			'mean_reversion': {
				'lookback_period': {
					'type': 'int',
					'required': True,
					'range': {'min': 5, 'max': 100}
				},
				'std_dev_threshold': {
					'type': 'float',
					'required': True,
					'range': {'min': 0.5, 'max': 5.0}
				}
			}
		}

		return default_schemas.get(strategy_type, {})

	def validate_strategy_parameters (self, strategy_type: str, parameters: Dict[str, Any]) -> ValidationReport:
		"""
		验证策略参数

		Args:
			strategy_type: 策略类型
			parameters: 参数字典

		Returns:
			验证报告
		"""
		schema = self.get_default_schema(strategy_type)
		return self.validate_parameters(parameters, schema)


	@staticmethod
	def format_validation_report (report: ValidationReport) -> str:

		"""
		格式化验证报告

		Args:
			report: 验证报告

		Returns:
			格式化的报告字符串
		"""
		lines = [f"验证结果: {'通过' if report.valid else '失败'}", f"错误数量: {len(report.errors)}",
		         f"警告数量: {len(report.warnings)}"]

		if report.errors:
			lines.append("\n错误详情:")
			for error in report.errors:
				lines.append(f"- {error.message}")

		if report.warnings:
			lines.append("\n警告详情:")
			for warning in report.warnings:
				lines.append(f"- {warning.message}")

		return '\n'.join(lines)


# 全局参数验证器实例
parameter_validator = ParameterValidator()


def get_parameter_validator () -> ParameterValidator:
	"""
	获取参数验证器实例

	Returns:
		参数验证器实例
	"""
	return parameter_validator
