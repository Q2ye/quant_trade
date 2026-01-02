"""
数据验证器 - 提供数据质量、完整性和一致性验证功能

职责：
1. 数据格式验证（数据类型、范围、格式）
2. 数据完整性验证（缺失值、重复值）
3. 数据一致性验证（业务规则、逻辑关系）
4. 数据质量评分和报告

设计原则：
1. 可扩展：支持自定义验证规则
2. 可组合：验证规则可组合使用
3. 高性能：支持批量验证和异步验证
4. 可配置：验证规则可动态配置
"""

import re
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import asyncio
from concurrent.futures import ThreadPoolExecutor


class ValidationResultStatus(Enum):
	"""验证结果状态枚举"""
	VALID = "valid"  # 验证通过
	INVALID = "invalid"  # 验证不通过
	WARNING = "warning"  # 警告，数据可用但有风险
	SKIPPED = "skipped"  # 跳过验证


@dataclass
class ValidationResult:
	"""验证结果数据结构"""
	field_name: str  # 字段名
	status: ValidationResultStatus  # 验证状态
	message: str  # 验证消息
	actual_value: Any = None  # 实际值
	expected_value: Any = None  # 期望值
	rule_name: str = ""  # 规则名称
	severity: str = "error"  # 严重程度：error/warning/info
	timestamp: datetime = field(default_factory=datetime.now)  # 验证时间

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典格式"""
		return {
			"field_name": self.field_name,
			"status": self.status.value,
			"message": self.message,
			"actual_value": self.actual_value,
			"expected_value": self.expected_value,
			"rule_name": self.rule_name,
			"severity": self.severity,
			"timestamp": self.timestamp.isoformat()
		}


@dataclass
class ValidationReport:
	"""验证报告"""
	total_records: int = 0  # 总记录数
	valid_records: int = 0  # 有效记录数
	invalid_records: int = 0  # 无效记录数
	warning_records: int = 0  # 警告记录数
	validation_results: List[ValidationResult] = field(default_factory=list)  # 详细结果
	summary: Dict[str, Any] = field(default_factory=dict)  # 汇总信息
	execution_time: float = 0.0  # 执行时间(秒)

	def add_result (self, result: ValidationResult):
		"""添加验证结果"""
		self.validation_results.append(result)

		# 更新统计
		if result.status == ValidationResultStatus.VALID:
			self.valid_records += 1
		elif result.status == ValidationResultStatus.INVALID:
			self.invalid_records += 1
		elif result.status == ValidationResultStatus.WARNING:
			self.warning_records += 1

	def calculate_summary (self):
		"""计算汇总信息"""
		self.summary = {
			"total_records": self.total_records,
			"valid_records": self.valid_records,
			"invalid_records": self.invalid_records,
			"warning_records": self.warning_records,
			"valid_rate": self.valid_records / self.total_records if self.total_records > 0 else 0,
			"invalid_rate": self.invalid_records / self.total_records if self.total_records > 0 else 0,
			"warning_rate": self.warning_records / self.total_records if self.total_records > 0 else 0,
			"total_checks": len(self.validation_results),
			"by_field": self._group_by_field(),
			"by_severity": self._group_by_severity()
		}

	def _group_by_field (self) -> Dict[str, Dict]:
		"""按字段分组统计"""
		field_stats = {}
		for result in self.validation_results:
			if result.field_name not in field_stats:
				field_stats[result.field_name] = {
					"total": 0, "valid": 0, "invalid": 0, "warning": 0
				}

			stats = field_stats[result.field_name]
			stats["total"] += 1
			if result.status == ValidationResultStatus.VALID:
				stats["valid"] += 1
			elif result.status == ValidationResultStatus.INVALID:
				stats["invalid"] += 1
			elif result.status == ValidationResultStatus.WARNING:
				stats["warning"] += 1

		return field_stats

	def _group_by_severity (self) -> Dict[str, int]:
		"""按严重程度分组统计"""
		severity_stats = {"error": 0, "warning": 0, "info": 0}
		for result in self.validation_results:
			severity_stats[result.severity] = severity_stats.get(result.severity, 0) + 1
		return severity_stats

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典格式"""
		self.calculate_summary()
		return {
			"summary": self.summary,
			"results": [result.to_dict() for result in self.validation_results],
			"execution_time": self.execution_time
		}


class ValidationRule(ABC):
	"""验证规则基类"""

	def __init__ (self, field_name: str, rule_name: str = None, severity: str = "error"):
		"""
		初始化验证规则

		Args:
			field_name: 字段名
			rule_name: 规则名称
			severity: 严重程度
		"""
		self.field_name = field_name
		self.rule_name = rule_name or self.__class__.__name__
		self.severity = severity

	@abstractmethod
	def validate (self, value: Any, context: Dict = None) -> ValidationResult:
		"""
		验证单个值

		Args:
			value: 要验证的值
			context: 验证上下文（可选）

		Returns:
			ValidationResult: 验证结果
		"""
		pass

	async def async_validate (self, value: Any, context: Dict = None) -> ValidationResult:
		"""异步验证方法"""
		return self.validate(value, context)


class RequiredRule(ValidationRule):
	"""必填字段验证规则"""

	def __init__ (self, field_name: str, allow_empty_string: bool = False, **kwargs):
		"""
		初始化必填规则

		Args:
			field_name: 字段名
			allow_empty_string: 是否允许空字符串
			**kwargs: 其他参数
		"""
		super().__init__(field_name, **kwargs)
		self.allow_empty_string = allow_empty_string

	def validate (self, value: Any, context: Dict = None) -> ValidationResult:
		# 检查是否为None
		if value is None:
			return ValidationResult(
				field_name=self.field_name,
				status=ValidationResultStatus.INVALID,
				message=f"字段 '{self.field_name}' 不能为空",
				actual_value=value,
				rule_name=self.rule_name,
				severity=self.severity
			)

		# 检查空字符串
		if isinstance(value, str) and not self.allow_empty_string and value.strip() == "":
			return ValidationResult(
				field_name=self.field_name,
				status=ValidationResultStatus.INVALID,
				message=f"字段 '{self.field_name}' 不能为空字符串",
				actual_value=value,
				rule_name=self.rule_name,
				severity=self.severity
			)

		# 检查NaN（对于数值类型）
		if isinstance(value, float) and np.isnan(value):
			return ValidationResult(
				field_name=self.field_name,
				status=ValidationResultStatus.INVALID,
				message=f"字段 '{self.field_name}' 不能为NaN",
				actual_value=value,
				rule_name=self.rule_name,
				severity=self.severity
			)

		return ValidationResult(
			field_name=self.field_name,
			status=ValidationResultStatus.VALID,
			message=f"字段 '{self.field_name}' 验证通过",
			actual_value=value,
			rule_name=self.rule_name,
			severity=self.severity
		)


class TypeRule(ValidationRule):
	"""数据类型验证规则"""

	def __init__ (self, field_name: str, expected_type: Union[type, Tuple[type, ...]], **kwargs):
		"""
		初始化类型规则

		Args:
			field_name: 字段名
			expected_type: 期望的类型或类型元组
			**kwargs: 其他参数
		"""
		super().__init__(field_name, **kwargs)
		self.expected_type = expected_type

	def validate (self, value: Any, context: Dict = None) -> ValidationResult:
		if value is None:
			return ValidationResult(
				field_name=self.field_name,
				status=ValidationResultStatus.VALID,  # 空值跳过类型检查
				message=f"字段 '{self.field_name}' 为空值，跳过类型检查",
				actual_value=value,
				rule_name=self.rule_name,
				severity="info"
			)

		if not isinstance(value, self.expected_type):
			expected_type_str = self._get_type_name(self.expected_type)
			actual_type_str = self._get_type_name(type(value))

			return ValidationResult(
				field_name=self.field_name,
				status=ValidationResultStatus.INVALID,
				message=f"字段 '{self.field_name}' 类型错误：期望 {expected_type_str}，实际 {actual_type_str}",
				actual_value=value,
				expected_value=self.expected_type,
				rule_name=self.rule_name,
				severity=self.severity
			)

		return ValidationResult(
			field_name=self.field_name,
			status=ValidationResultStatus.VALID,
			message=f"字段 '{self.field_name}' 类型验证通过",
			actual_value=value,
			rule_name=self.rule_name,
			severity=self.severity
		)

	def _get_type_name (self, type_obj) -> str:
		"""获取类型名称"""
		if isinstance(type_obj, tuple):
			return " 或 ".join([t.__name__ for t in type_obj])
		return type_obj.__name__


class RangeRule(ValidationRule):
	"""数值范围验证规则"""

	def __init__ (self, field_name: str, min_value: float = None, max_value: float = None,
	              include_min: bool = True, include_max: bool = True, **kwargs):
		"""
		初始化范围规则

		Args:
			field_name: 字段名
			min_value: 最小值
			max_value: 最大值
			include_min: 是否包含最小值
			include_max: 是否包含最大值
			**kwargs: 其他参数
		"""
		super().__init__(field_name, **kwargs)
		self.min_value = min_value
		self.max_value = max_value
		self.include_min = include_min
		self.include_max = include_max

	def validate (self, value: Any, context: Dict = None) -> ValidationResult:
		if value is None:
			return ValidationResult(
				field_name=self.field_name,
				status=ValidationResultStatus.VALID,
				message=f"字段 '{self.field_name}' 为空值，跳过范围检查",
				actual_value=value,
				rule_name=self.rule_name,
				severity="info"
			)

		try:
			num_value = float(value)
		except (ValueError, TypeError):
			return ValidationResult(
				field_name=self.field_name,
				status=ValidationResultStatus.INVALID,
				message=f"字段 '{self.field_name}' 无法转换为数值",
				actual_value=value,
				rule_name=self.rule_name,
				severity=self.severity
			)

		# 检查最小值
		if self.min_value is not None:
			if self.include_min:
				if num_value < self.min_value:
					return ValidationResult(
						field_name=self.field_name,
						status=ValidationResultStatus.INVALID,
						message=f"字段 '{self.field_name}' 值 {num_value} 小于最小值 {self.min_value}",
						actual_value=num_value,
						expected_value=f">= {self.min_value}",
						rule_name=self.rule_name,
						severity=self.severity
					)
			else:
				if num_value <= self.min_value:
					return ValidationResult(
						field_name=self.field_name,
						status=ValidationResultStatus.INVALID,
						message=f"字段 '{self.field_name}' 值 {num_value} 小于等于最小值 {self.min_value}",
						actual_value=num_value,
						expected_value=f"> {self.min_value}",
						rule_name=self.rule_name,
						severity=self.severity
					)

		# 检查最大值
		if self.max_value is not None:
			if self.include_max:
				if num_value > self.max_value:
					return ValidationResult(
						field_name=self.field_name,
						status=ValidationResultStatus.INVALID,
						message=f"字段 '{self.field_name}' 值 {num_value} 大于最大值 {self.max_value}",
						actual_value=num_value,
						expected_value=f"<= {self.max_value}",
						rule_name=self.rule_name,
						severity=self.severity
					)
			else:
				if num_value >= self.max_value:
					return ValidationResult(
						field_name=self.field_name,
						status=ValidationResultStatus.INVALID,
						message=f"字段 '{self.field_name}' 值 {num_value} 大于等于最大值 {self.max_value}",
						actual_value=num_value,
						expected_value=f"< {self.max_value}",
						rule_name=self.rule_name,
						severity=self.severity
					)

		range_desc = []
		if self.min_value is not None:
			range_desc.append(f"{'>=' if self.include_min else '>'} {self.min_value}")
		if self.max_value is not None:
			range_desc.append(f"{'<=' if self.include_max else '<'} {self.max_value}")

		return ValidationResult(
			field_name=self.field_name,
			status=ValidationResultStatus.VALID,
			message=f"字段 '{self.field_name}' 范围验证通过 ({' '.join(range_desc)})",
			actual_value=num_value,
			rule_name=self.rule_name,
			severity=self.severity
		)


class PatternRule(ValidationRule):
	"""正则表达式验证规则"""

	def __init__ (self, field_name: str, pattern: str, **kwargs):
		"""
		初始化模式规则

		Args:
			field_name: 字段名
			pattern: 正则表达式模式
			**kwargs: 其他参数
		"""
		super().__init__(field_name, **kwargs)
		self.pattern = re.compile(pattern)

	def validate (self, value: Any, context: Dict = None) -> ValidationResult:
		if value is None:
			return ValidationResult(
				field_name=self.field_name,
				status=ValidationResultStatus.VALID,
				message=f"字段 '{self.field_name}' 为空值，跳过模式检查",
				actual_value=value,
				rule_name=self.rule_name,
				severity="info"
			)

		str_value = str(value)
		if not self.pattern.match(str_value):
			return ValidationResult(
				field_name=self.field_name,
				status=ValidationResultStatus.INVALID,
				message=f"字段 '{self.field_name}' 不符合模式：{self.pattern.pattern}",
				actual_value=str_value,
				expected_value=self.pattern.pattern,
				rule_name=self.rule_name,
				severity=self.severity
			)

		return ValidationResult(
			field_name=self.field_name,
			status=ValidationResultStatus.VALID,
			message=f"字段 '{self.field_name}' 模式验证通过",
			actual_value=str_value,
			rule_name=self.rule_name,
			severity=self.severity
		)


class LengthRule(ValidationRule):
	"""长度验证规则"""

	def __init__ (self, field_name: str, min_length: int = None, max_length: int = None, **kwargs):
		"""
		初始化长度规则

		Args:
			field_name: 字段名
			min_length: 最小长度
			max_length: 最大长度
			**kwargs: 其他参数
		"""
		super().__init__(field_name, **kwargs)
		self.min_length = min_length
		self.max_length = max_length

	def validate (self, value: Any, context: Dict = None) -> ValidationResult:
		if value is None:
			return ValidationResult(
				field_name=self.field_name,
				status=ValidationResultStatus.VALID,
				message=f"字段 '{self.field_name}' 为空值，跳过长度的检查",
				actual_value=value,
				rule_name=self.rule_name,
				severity="info"
			)

		# 转换为字符串获取长度
		if not hasattr(value, '__len__'):
			str_value = str(value)
			length = len(str_value)
		else:
			length = len(value)
			str_value = str(value) if not isinstance(value, (list, dict)) else value

		# 检查最小长度
		if self.min_length is not None and length < self.min_length:
			return ValidationResult(
				field_name=self.field_name,
				status=ValidationResultStatus.INVALID,
				message=f"字段 '{self.field_name}' 长度 {length} 小于最小长度 {self.min_length}",
				actual_value=str_value,
				expected_value=f"长度 >= {self.min_length}",
				rule_name=self.rule_name,
				severity=self.severity
			)

		# 检查最大长度
		if self.max_length is not None and length > self.max_length:
			return ValidationResult(
				field_name=self.field_name,
				status=ValidationResultStatus.INVALID,
				message=f"字段 '{self.field_name}' 长度 {length} 大于最大长度 {self.max_length}",
				actual_value=str_value,
				expected_value=f"长度 <= {self.max_length}",
				rule_name=self.rule_name,
				severity=self.severity
			)

		return ValidationResult(
			field_name=self.field_name,
			status=ValidationResultStatus.VALID,
			message=f"字段 '{self.field_name}' 长度验证通过 (长度: {length})",
			actual_value=str_value,
			rule_name=self.rule_name,
			severity=self.severity
		)


class CustomRule(ValidationRule):
	"""自定义验证规则"""

	def __init__ (self, field_name: str, validation_func: Callable[[Any, Dict], bool],
	              error_message: str = None, **kwargs):
		"""
		初始化自定义规则

		Args:
			field_name: 字段名
			validation_func: 验证函数，返回布尔值
			error_message: 错误消息模板
			**kwargs: 其他参数
		"""
		super().__init__(field_name, **kwargs)
		self.validation_func = validation_func
		self.error_message = error_message or f"字段 '{field_name}' 自定义验证失败"

	def validate (self, value: Any, context: Dict = None) -> ValidationResult:
		try:
			is_valid = self.validation_func(value, context or {})
			if is_valid:
				return ValidationResult(
					field_name=self.field_name,
					status=ValidationResultStatus.VALID,
					message=f"字段 '{self.field_name}' 自定义验证通过",
					actual_value=value,
					rule_name=self.rule_name,
					severity=self.severity
				)
			else:
				return ValidationResult(
					field_name=self.field_name,
					status=ValidationResultStatus.INVALID,
					message=self.error_message,
					actual_value=value,
					rule_name=self.rule_name,
					severity=self.severity
				)
		except Exception as e:
			return ValidationResult(
				field_name=self.field_name,
				status=ValidationResultStatus.INVALID,
				message=f"字段 '{self.field_name}' 自定义验证异常: {str(e)}",
				actual_value=value,
				rule_name=self.rule_name,
				severity=self.severity
			)


class DataValidator:
	"""
	数据验证器主类

	提供批量数据验证功能，支持同步和异步验证
	"""

	def __init__ (self, rules: Dict[str, List[ValidationRule]] = None):
		"""
		初始化数据验证器

		Args:
			rules: 验证规则字典，格式为 {字段名: [规则列表]}
		"""
		self.rules = rules or {}
		self.executor = ThreadPoolExecutor(max_workers=4)

	def add_rule (self, field_name: str, rule: ValidationRule):
		"""为字段添加验证规则"""
		if field_name not in self.rules:
			self.rules[field_name] = []
		self.rules[field_name].append(rule)

	def add_rules (self, field_name: str, rules: List[ValidationRule]):
		"""为字段添加多个验证规则"""
		if field_name not in self.rules:
			self.rules[field_name] = []
		self.rules[field_name].extend(rules)

	def validate_record (self, record: Dict[str, Any],
	                     context: Dict = None) -> ValidationReport:
		"""
		验证单条记录

		Args:
			record: 数据记录字典
			context: 验证上下文

		Returns:
			ValidationReport: 验证报告
		"""
		start_time = datetime.now()
		report = ValidationReport(total_records=1)

		for field_name, rules in self.rules.items():
			value = record.get(field_name)

			for rule in rules:
				result = rule.validate(value, context)
				report.add_result(result)

				# 如果严重错误，可提前终止
				if result.status == ValidationResultStatus.INVALID and result.severity == "error":
					# 可以添加逻辑决定是否继续验证其他规则
					pass

		report.execution_time = (datetime.now() - start_time).total_seconds()
		return report

	def validate_batch (self, records: List[Dict[str, Any]],
	                    context: Dict = None) -> ValidationReport:
		"""
		批量验证多条记录

		Args:
			records: 数据记录列表
			context: 验证上下文

		Returns:
			ValidationReport: 验证报告
		"""
		start_time = datetime.now()
		report = ValidationReport(total_records=len(records))

		for record in records:
			record_report = self.validate_record(record, context)
			report.validation_results.extend(record_report.validation_results)

			# 统计记录级别的有效性
			record_has_error = any(
				r.status == ValidationResultStatus.INVALID and r.severity == "error"
				for r in record_report.validation_results
			)

			record_has_warning = any(
				r.status == ValidationResultStatus.WARNING or
				(r.status == ValidationResultStatus.INVALID and r.severity == "warning")
				for r in record_report.validation_results
			)

			if record_has_error:
				report.invalid_records += 1
			elif record_has_warning:
				report.warning_records += 1
			else:
				report.valid_records += 1

		report.execution_time = (datetime.now() - start_time).total_seconds()
		return report

	async def async_validate_batch (self, records: List[Dict[str, Any]],
	                                context: Dict = None) -> ValidationReport:
		"""
		异步批量验证多条记录

		Args:
			records: 数据记录列表
			context: 验证上下文

		Returns:
			ValidationReport: 验证报告
		"""
		loop = asyncio.get_event_loop()

		# 使用线程池执行批量验证
		def run_validation ():
			return self.validate_batch(records, context)

		return await loop.run_in_executor(self.executor, run_validation)

	def validate_dataframe (self, df: pd.DataFrame,
	                        context: Dict = None) -> ValidationReport:
		"""
		验证Pandas DataFrame

		Args:
			df: Pandas DataFrame
			context: 验证上下文

		Returns:
			ValidationReport: 验证报告
		"""
		records = df.to_dict('records')
		return self.validate_batch(records, context)

	def create_validation_suite (self, config: Dict) -> 'DataValidator':
		"""
		根据配置创建验证套件

		Args:
			config: 验证配置

		Returns:
			DataValidator: 配置好的验证器
		"""
		validator = DataValidator()

		for field_config in config.get("fields", []):
			field_name = field_config["name"]
			rules = []

			# 解析规则配置
			for rule_config in field_config.get("rules", []):
				rule_type = rule_config["type"]
				rule_params = rule_config.get("params", {})

				if rule_type == "required":
					rule = RequiredRule(field_name, **rule_params)
				elif rule_type == "type":
					# 处理类型字符串
					type_str = rule_params.get("expected_type")
					if isinstance(type_str, str):
						if type_str == "int":
							expected_type = int
						elif type_str == "float":
							expected_type = float
						elif type_str == "str":
							expected_type = str
						elif type_str == "bool":
							expected_type = bool
						elif type_str == "date":
							expected_type = date
						elif type_str == "datetime":
							expected_type = datetime
						else:
							expected_type = eval(type_str)
					else:
						expected_type = type_str

					rule_params["expected_type"] = expected_type
					rule = TypeRule(field_name, **rule_params)
				elif rule_type == "range":
					rule = RangeRule(field_name, **rule_params)
				elif rule_type == "pattern":
					rule = PatternRule(field_name, **rule_params)
				elif rule_type == "length":
					rule = LengthRule(field_name, **rule_params)
				elif rule_type == "custom":
					# 自定义函数需要特殊处理
					func_str = rule_params.get("function")
					if func_str:
						# 注意：这里使用eval有安全风险，生产环境应使用其他方式
						rule_params["validation_func"] = eval(func_str)
					rule = CustomRule(field_name, **rule_params)
				else:
					continue

				rules.append(rule)

			validator.add_rules(field_name, rules)

		return validator

	def cleanup (self):
		"""清理资源"""
		self.executor.shutdown(wait=True)


# 预定义验证规则工厂
class ValidationRuleFactory:
	"""验证规则工厂类"""

	@staticmethod
	def create_stock_validation_rules () -> DataValidator:
		"""创建股票数据验证规则"""
		validator = DataValidator()

		# ts_code 验证规则
		validator.add_rules("ts_code", [
			RequiredRule("ts_code"),
			PatternRule("ts_code", r"^\d{6}\.[A-Z]{2,4}$",
			            rule_name="StockCodePattern",
			            message="股票代码格式应为: 6位数字.市场代码")
		])

		# trade_date 验证规则
		validator.add_rules("trade_date", [
			RequiredRule("trade_date"),
			PatternRule("trade_date", r"^\d{4}-\d{2}-\d{2}$",
			            rule_name="DateFormat")
		])

		# 价格字段验证规则
		price_fields = ["open", "high", "low", "close", "pre_close"]
		for field in price_fields:
			validator.add_rules(field, [
				RequiredRule(field, allow_empty_string=False),
				TypeRule(field, (int, float, Decimal)),
				RangeRule(field, min_value=0, max_value=10000,
				          rule_name="PriceRange")
			])

		# 成交量验证规则
		validator.add_rules("vol", [
			RequiredRule("vol"),
			TypeRule("vol", (int, float, Decimal)),
			RangeRule("vol", min_value=0, rule_name="VolumeNonNegative")
		])

		# 成交额验证规则
		validator.add_rules("amount", [
			RequiredRule("amount"),
			TypeRule("amount", (int, float, Decimal)),
			RangeRule("amount,", min_value=0, rule_name="AmountNonNegative")
		])

		# 涨跌幅验证规则
		validator.add_rules("pct_chg", [
			RequiredRule("pct_chg", allow_empty_string=False),
			TypeRule("pct_chg", (int, float, Decimal)),
			RangeRule("pct_chg", min_value=-20, max_value=20,
			          rule_name="PriceChangeRange")
		])

		return validator

	@staticmethod
	def create_financial_validation_rules () -> DataValidator:
		"""创建财务数据验证规则"""
		validator = DataValidator()

		# 基本字段验证
		validator.add_rules("ts_code", [
			RequiredRule("ts_code"),
			PatternRule("ts_code", r"^\d{6}\.[A-Z]{2,4}$")
		])

		validator.add_rules("end_date", [
			RequiredRule("end_date"),
			PatternRule("end_date", r"^\d{4}-\d{2}-\d{2}$")
		])

		# 财务指标验证
		financial_fields = [
			"total_revenue", "net_profit", "total_assets",
			"total_liabilities", "equity"
		]

		for field in financial_fields:
			validator.add_rules(field, [
				RequiredRule(field),
				TypeRule(field, (int, float, Decimal)),
				RangeRule(field, min_value=0, rule_name="FinancialNonNegative")
			])

		# 比率验证（允许负值）
		ratio_fields = ["roe", "roa", "gross_margin", "net_margin"]
		for field in ratio_fields:
			validator.add_rules(field, [
				RequiredRule(field),
				TypeRule(field, (int, float, Decimal)),
				RangeRule(field, min_value=-100, max_value=1000,
				          rule_name="RatioRange")
			])

		return validator


# 数据质量评分器
class DataQualityScorer:
	"""数据质量评分器"""

	def __init__ (self, weights: Dict[str, float] = None):
		"""
		初始化数据质量评分器

		Args:
			weights: 质量维度权重
		"""
		self.weights = weights or {
			"completeness": 0.3,  # 完整性
			"accuracy": 0.25,  # 准确性
			"consistency": 0.2,  # 一致性
			"timeliness": 0.15,  # 及时性
			"uniqueness": 0.1  # 唯一性
		}

	def calculate_score (self, report: ValidationReport) -> Dict[str, Any]:
		"""
		计算数据质量得分

		Args:
			report: 验证报告

		Returns:
			Dict: 质量得分详情
		"""
		total_checks = len(report.validation_results)

		if total_checks == 0:
			return {
				"overall_score": 100,
				"dimension_scores": {dim: 100 for dim in self.weights},
				"recommendations": []
			}

		# 按规则名称分类结果
		rule_results = {}
		for result in report.validation_results:
			rule_name = result.rule_name
			if rule_name not in rule_results:
				rule_results[rule_name] = []
			rule_results[rule_name].append(result)

		# 计算各维度得分（简化版本，实际应根据规则映射到维度）
		dimension_scores = {}

		# 完整性得分（基于必填字段验证）
		completeness_results = [
			r for r in report.validation_results
			if "Required" in r.rule_name
		]
		completeness_score = self._calculate_dimension_score(completeness_results)

		# 准确性得分（基于类型和范围验证）
		accuracy_results = [
			r for r in report.validation_results
			if "Type" in r.rule_name or "Range" in r.rule_name or "Pattern" in r.rule_name
		]
		accuracy_score = self._calculate_dimension_score(accuracy_results)

		# 计算总分
		dimension_scores = {
			"completeness": completeness_score,
			"accuracy": accuracy_score,
			"consistency": 85.0,  # 简化，实际应基于一致性检查
			"timeliness": 90.0,  # 简化，实际应基于时间戳检查
			"uniqueness": 95.0  # 简化，实际应基于重复性检查
		}

		# 加权总分
		overall_score = sum(
			score * self.weights[dim]
			for dim, score in dimension_scores.items()
		)

		# 生成改进建议
		recommendations = self._generate_recommendations(report)

		return {
			"overall_score": round(overall_score, 2),
			"dimension_scores": {k: round(v, 2) for k, v in dimension_scores.items()},
			"grade": self._get_quality_grade(overall_score),
			"recommendations": recommendations,
			"critical_issues": len([r for r in report.validation_results
			                        if r.status == ValidationResultStatus.INVALID
			                        and r.severity == "error"])
		}

	def _calculate_dimension_score (self, results: List[ValidationResult]) -> float:
		"""计算维度得分"""
		if not results:
			return 100.0

		valid_count = sum(1 for r in results if r.status == ValidationResultStatus.VALID)
		total_count = len(results)

		return (valid_count / total_count) * 100 if total_count > 0 else 100.0

	def _get_quality_grade (self, score: float) -> str:
		"""获取质量等级"""
		if score >= 90:
			return "A"
		elif score >= 80:
			return "B"
		elif score >= 70:
			return "C"
		elif score >= 60:
			return "D"
		else:
			return "F"

	def _generate_recommendations (self, report: ValidationReport) -> List[str]:
		"""生成改进建议"""
		recommendations = []

		# 统计主要问题
		errors_by_field = {}
		for result in report.validation_results:
			if result.status == ValidationResultStatus.INVALID:
				if result.field_name not in errors_by_field:
					errors_by_field[result.field_name] = []
				errors_by_field[result.field_name].append(result.message)

		# 生成建议
		for field, errors in errors_by_field.items():
			if len(errors) > 3:  # 某个字段有多个错误
				recommendations.append(f"字段 '{field}' 存在多个验证问题，建议优先修复")
			elif "不能为空" in errors[0]:
				recommendations.append(f"字段 '{field}' 缺失值较多，建议检查数据源")
			elif "类型错误" in errors[0]:
				recommendations.append(f"字段 '{field}' 数据类型不一致，建议统一数据格式")

		# 基于总体统计的建议
		if report.invalid_records / report.total_records > 0.1:
			recommendations.append("数据无效记录比例较高(>10%)，建议检查数据采集流程")

		if report.warning_records / report.total_records > 0.2:
			recommendations.append("数据警告记录比例较高(>20%)，建议优化数据质量")

		return recommendations


# 使用示例
if __name__ == "__main__":
	# 示例：验证股票数据
	stock_data = [
		{
			"ts_code": "000001.SZ",
			"trade_date": "2023-12-01",
			"open": 10.5,
			"high": 11.2,
			"low": 10.3,
			"close": 11.0,
			"pre_close": 10.8,
			"vol": 1000000,
			"amount": 11000000,
			"pct_chg": 1.85
		},
		{
			"ts_code": "000002.SZ",
			"trade_date": "2023-12-01",
			"open": 20.1,
			"high": 21.5,
			"low": 19.8,
			"close": 21.0,
			"pre_close": 20.5,
			"vol": 1500000,
			"amount": 31500000,
			"pct_chg": 2.44
		}
	]

	# 创建验证器
	validator = ValidationRuleFactory.create_stock_validation_rules()

	# 执行验证
	report = validator.validate_batch(stock_data)

	# 输出验证结果
	print("验证报告摘要:")
	print(f"总记录数: {report.total_records}")
	print(f"有效记录: {report.valid_records}")
	print(f"无效记录: {report.invalid_records}")
	print(f"警告记录: {report.warning_records}")

	# 计算质量得分
	scorer = DataQualityScorer()
	quality_score = scorer.calculate_score(report)
	print(f"\n数据质量得分: {quality_score['overall_score']} ({quality_score['grade']})")

	# 清理资源
	validator.cleanup()