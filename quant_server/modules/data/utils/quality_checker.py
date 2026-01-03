"""
数据质量检查器

负责检查数据质量，包括：
1. 完整性检查
2. 一致性检查
3. 准确性检查
4. 及时性检查

设计原则：
- 模块化：每个检查项独立
- 可配置：支持自定义检查规则
- 可扩展：易于添加新的检查项
- 自动化：支持批量自动检查
"""

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
import re
import logging
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class QualityIssueLevel(str, Enum):
	"""质量问题等级枚举"""
	CRITICAL = "critical"  # 严重问题
	HIGH = "high"  # 高优先级问题
	MEDIUM = "medium"  # 中优先级问题
	LOW = "low"  # 低优先级问题
	INFO = "info"  # 信息性问题


class QualityCheckType(str, Enum):
	"""质量检查类型枚举"""
	COMPLETENESS = "completeness"  # 完整性检查
	CONSISTENCY = "consistency"  # 一致性检查
	ACCURACY = "accuracy"  # 准确性检查
	TIMELINESS = "timeliness"  # 及时性检查
	VALIDITY = "validity"  # 有效性检查


class DataQualityChecker:
	"""
	数据质量检查器

	提供全面的数据质量检查功能，识别和报告数据质量问题
	"""

	# 默认检查配置
	DEFAULT_CHECKS = {
		QualityCheckType.COMPLETENESS: [
			"check_missing_values",
			"check_missing_columns",
			"check_empty_dataset"
		],
		QualityCheckType.CONSISTENCY: [
			"check_data_types",
			"check_value_ranges",
			"check_duplicates"
		],
		QualityCheckType.ACCURACY: [
			"check_outliers",
			"check_business_rules",
			"check_cross_reference"
		],
		QualityCheckType.TIMELINESS: [
			"check_freshness",
			"check_update_frequency"
		],
		QualityCheckType.VALIDITY: [
			"check_format_validity",
			"check_referential_integrity"
		]
	}

	# 股票数据质量规则
	STOCK_DATA_RULES = {
		"price_range": {
			"min": 0.01,
			"max": 100000,
			"issue_level": QualityIssueLevel.HIGH
		},
		"volume_range": {
			"min": 0,
			"max": 1e12,
			"issue_level": QualityIssueLevel.MEDIUM
		},
		"change_pct_range": {
			"min": -0.3,  # -30%
			"max": 0.3,  # +30%
			"issue_level": QualityIssueLevel.HIGH
		},
		"required_columns": [
			"symbol", "date", "open", "high", "low", "close", "volume"
		]
	}

	def __init__ (self, config: Optional[Dict] = None):
		"""
		初始化数据质量检查器

		Args:
			config: 配置参数
		"""
		self.config = config or {}
		self.logger = logger

		# 加载自定义检查规则
		self.checks_config = self.DEFAULT_CHECKS.copy()
		if "checks" in self.config:
			self.checks_config.update(self.config["checks"])

		# 数据规则
		self.data_rules = self.STOCK_DATA_RULES.copy()
		if "data_rules" in self.config:
			self.data_rules.update(self.config["data_rules"])

	def check_quality (
			self,
			data: pd.DataFrame,
			data_type: str,
			check_types: Optional[List[QualityCheckType]] = None,
			**kwargs
	) -> Dict[str, Any]:
		"""
		检查数据质量

		Args:
			data: 待检查的数据
			data_type: 数据类型
			check_types: 检查类型列表，为None时检查所有类型
			**kwargs: 额外参数

		Returns:
			质量检查结果
		"""
		try:
			self.logger.info(f"开始检查数据质量: {data_type}")

			# 确定要执行的检查类型
			if check_types is None:
				check_types = list(self.checks_config.keys())

			# 执行检查
			issues = []
			statistics = {}

			for check_type in check_types:
				if check_type in self.checks_config:
					check_results = self._execute_checks(
						data, data_type, check_type, **kwargs
					)
					issues.extend(check_results.get("issues", []))

					# 合并统计信息
					if "statistics" in check_results:
						statistics.update(check_results["statistics"])

			# 计算质量分数
			quality_score = self._calculate_quality_score(issues, data)

			# 生成报告
			report = self._generate_quality_report(
				data_type=data_type,
				issues=issues,
				statistics=statistics,
				quality_score=quality_score,
				check_types=check_types
			)

			self.logger.info(f"数据质量检查完成: {data_type}, 得分: {quality_score:.2f}")

			return report

		except Exception as e:
			self.logger.error(f"数据质量检查失败: {e}", exc_info=True)
			return self._generate_error_report(str(e))

	def _execute_checks (
			self,
			data: pd.DataFrame,
			data_type: str,
			check_type: QualityCheckType,
			**kwargs
	) -> Dict[str, Any]:
		"""
		执行指定类型的检查

		Args:
			data: 待检查的数据
			data_type: 数据类型
			check_type: 检查类型
			**kwargs: 额外参数

		Returns:
			检查结果
		"""
		issues = []
		statistics = {}

		# 获取该类型的检查项
		check_functions = self.checks_config.get(check_type, [])

		for check_func_name in check_functions:
			try:
				# 获取检查函数
				check_func = getattr(self, check_func_name, None)
				if check_func:
					# 执行检查
					result = check_func(data, data_type, **kwargs)

					if isinstance(result, dict):
						if "issues" in result:
							issues.extend(result["issues"])
						if "statistics" in result:
							statistics.update(result["statistics"])

			except Exception as e:
				self.logger.warning(f"执行检查 {check_func_name} 失败: {e}")

		return {
			"issues": issues,
			"statistics": statistics,
			"check_type": check_type.value,
			"check_count": len(check_functions)
		}

	# ==================== 完整性检查函数 ====================

	def check_missing_values (
			self,
			data: pd.DataFrame,
			data_type: str,
			**kwargs
	) -> Dict[str, Any]:
		"""
		检查缺失值

		Args:
			data: 待检查的数据
			data_type: 数据类型
			**kwargs: 额外参数

		Returns:
			检查结果
		"""
		issues = []
		statistics = {}

		# 计算每列的缺失值比例
		missing_stats = {}
		for column in data.columns:
			missing_count = data[column].isna().sum()
			total_count = len(data)
			missing_pct = (missing_count / total_count * 100) if total_count > 0 else 0

			missing_stats[column] = {
				"missing_count": int(missing_count),
				"missing_percentage": round(missing_pct, 2)
			}

			# 报告问题
			if missing_pct > 0:
				issue_level = self._determine_missing_value_issue_level(missing_pct)

				issues.append({
					"check_type": QualityCheckType.COMPLETENESS.value,
					"issue_type": "missing_values",
					"issue_level": issue_level.value,
					"column": column,
					"message": f"列 {column} 有 {missing_count} 个缺失值 ({missing_pct:.2f}%)",
					"details": {
						"missing_count": missing_count,
						"missing_percentage": missing_pct,
						"total_count": total_count
					}
				})

		statistics["missing_values"] = missing_stats

		return {
			"issues": issues,
			"statistics": statistics
		}

	def check_missing_columns (
			self,
			data: pd.DataFrame,
			data_type: str,
			**kwargs
	) -> Dict[str, Any]:
		"""
		检查缺失的列

		Args:
			data: 待检查的数据
			data_type: 数据类型
			**kwargs: 额外参数

		Returns:
			检查结果
		"""
		issues = []
		statistics = {}

		# 获取该数据类型的必需列
		required_columns = self._get_required_columns(data_type)

		if required_columns:
			missing_columns = [col for col in required_columns if col not in data.columns]

			if missing_columns:
				issues.append({
					"check_type": QualityCheckType.COMPLETENESS.value,
					"issue_type": "missing_columns",
					"issue_level": QualityIssueLevel.HIGH.value,
					"message": f"缺少必需列: {', '.join(missing_columns)}",
					"details": {
						"missing_columns": missing_columns,
						"required_columns": required_columns,
						"actual_columns": list(data.columns)
					}
				})

			statistics["column_completeness"] = {
				"required_count": len(required_columns),
				"missing_count": len(missing_columns),
				"completeness_percentage": round(
					(len(required_columns) - len(missing_columns)) / len(required_columns) * 100, 2
				) if required_columns else 100
			}

		return {
			"issues": issues,
			"statistics": statistics
		}

	def check_empty_dataset (
			self,
			data: pd.DataFrame,
			data_type: str,
			**kwargs
	) -> Dict[str, Any]:
		"""
		检查空数据集

		Args:
			data: 待检查的数据
			data_type: 数据类型
			**kwargs: 额外参数

		Returns:
			检查结果
		"""
		issues = []
		statistics = {}

		if data.empty:
			issues.append({
				"check_type": QualityCheckType.COMPLETENESS.value,
				"issue_type": "empty_dataset",
				"issue_level": QualityIssueLevel.CRITICAL.value,
				"message": "数据集为空",
				"details": {
					"row_count": 0,
					"column_count": len(data.columns)
				}
			})

		statistics["dataset_size"] = {
			"row_count": len(data),
			"column_count": len(data.columns),
			"is_empty": data.empty
		}

		return {
			"issues": issues,
			"statistics": statistics
		}

	# ==================== 一致性检查函数 ====================

	def check_data_types (
			self,
			data: pd.DataFrame,
			data_type: str,
			**kwargs
	) -> Dict[str, Any]:
		"""
		检查数据类型一致性

		Args:
			data: 待检查的数据
			data_type: 数据类型
			**kwargs: 额外参数

		Returns:
			检查结果
		"""
		issues = []
		statistics = {}

		expected_types = self._get_expected_data_types(data_type)

		if expected_types:
			type_issues = []

			for column, expected_type in expected_types.items():
				if column in data.columns:
					actual_type = str(data[column].dtype)

					# 简化类型检查
					type_matches = self._check_type_match(actual_type, expected_type)

					if not type_matches:
						type_issues.append({
							"column": column,
							"expected_type": expected_type,
							"actual_type": actual_type
						})

			if type_issues:
				issues.append({
					"check_type": QualityCheckType.CONSISTENCY.value,
					"issue_type": "data_type_mismatch",
					"issue_level": QualityIssueLevel.MEDIUM.value,
					"message": f"发现 {len(type_issues)} 个数据类型不匹配",
					"details": {
						"type_issues": type_issues
					}
				})

			statistics["data_types"] = {
				"checked_columns": len(expected_types),
				"type_mismatches": len(type_issues),
				"match_percentage": round(
					(len(expected_types) - len(type_issues)) / len(expected_types) * 100, 2
				) if expected_types else 100
			}

		return {
			"issues": issues,
			"statistics": statistics
		}

	def check_value_ranges (
			self,
			data: pd.DataFrame,
			data_type: str,
			**kwargs
	) -> Dict[str, Any]:
		"""
		检查数值范围

		Args:
			data: 待检查的数据
			data_type: 数据类型
			**kwargs: 额外参数

		Returns:
			检查结果
		"""
		issues = []
		statistics = {}

		range_rules = self._get_value_range_rules(data_type)

		if range_rules:
			range_issues = []

			for column, rule in range_rules.items():
				if column in data.columns and data[column].dtype in [np.float64, np.int64]:
					# 检查最小值
					if "min" in rule:
						below_min = data[data[column] < rule["min"]]
						if not below_min.empty:
							range_issues.append({
								"column": column,
								"issue": "below_minimum",
								"min": rule["min"],
								"count": len(below_min),
								"examples": below_min[column].head().tolist()
							})

					# 检查最大值
					if "max" in rule:
						above_max = data[data[column] > rule["max"]]
						if not above_max.empty:
							range_issues.append({
								"column": column,
								"issue": "above_maximum",
								"max": rule["max"],
								"count": len(above_max),
								"examples": above_max[column].head().tolist()
							})

			if range_issues:
				issues.append({
					"check_type": QualityCheckType.CONSISTENCY.value,
					"issue_type": "value_out_of_range",
					"issue_level": QualityIssueLevel.HIGH.value,
					"message": f"发现 {len(range_issues)} 个数值范围问题",
					"details": {
						"range_issues": range_issues
					}
				})

			statistics["value_ranges"] = {
				"checked_columns": len(range_rules),
				"range_issues": len(range_issues)
			}

		return {
			"issues": issues,
			"statistics": statistics
		}

	def check_duplicates (
			self,
			data: pd.DataFrame,
			data_type: str,
			**kwargs
	) -> Dict[str, Any]:
		"""
		检查重复数据

		Args:
			data: 待检查的数据
			data_type: 数据类型
			**kwargs: 额外参数

		Returns:
			检查结果
		"""
		issues = []
		statistics = {}

		# 确定唯一键
		unique_keys = self._get_unique_keys(data_type)

		if unique_keys:
			# 检查所有必需键是否存在
			missing_keys = [key for key in unique_keys if key not in data.columns]

			if not missing_keys:
				# 检查重复
				duplicates = data[data.duplicated(subset=unique_keys, keep=False)]
				duplicate_count = len(duplicates)

				if duplicate_count > 0:
					issues.append({
						"check_type": QualityCheckType.CONSISTENCY.value,
						"issue_type": "duplicate_records",
						"issue_level": QualityIssueLevel.HIGH.value,
						"message": f"发现 {duplicate_count} 个重复记录",
						"details": {
							"unique_keys": unique_keys,
							"duplicate_count": duplicate_count,
							"duplicate_percentage": round(duplicate_count / len(data) * 100, 2)
						}
					})

				statistics["duplicates"] = {
					"unique_keys": unique_keys,
					"duplicate_count": duplicate_count,
					"duplicate_percentage": round(duplicate_count / len(data) * 100, 2) if len(data) > 0 else 0
				}

		return {
			"issues": issues,
			"statistics": statistics
		}

	# ==================== 准确性检查函数 ====================

	def check_outliers (
			self,
			data: pd.DataFrame,
			data_type: str,
			method: str = "iqr",
			threshold: float = 3.0,
			**kwargs
	) -> Dict[str, Any]:
		"""
		检查异常值

		Args:
			data: 待检查的数据
			data_type: 数据类型
			method: 异常值检测方法 (iqr, zscore, percentile)
			threshold: 检测阈值
			**kwargs: 额外参数

		Returns:
			检查结果
		"""
		issues = []
		statistics = {}

		numeric_columns = data.select_dtypes(include=[np.number]).columns

		if len(numeric_columns) > 0:
			outlier_issues = []

			for column in numeric_columns:
				# 移除缺失值
				values = data[column].dropna()

				if len(values) > 0:
					outliers = self._detect_outliers(values, method, threshold)

					if outliers is not None and len(outliers) > 0:
						outlier_issues.append({
							"column": column,
							"outlier_count": len(outliers),
							"outlier_percentage": round(len(outliers) / len(values) * 100, 2),
							"method": method,
							"threshold": threshold,
							"outlier_values": outliers.head().tolist() if len(outliers) > 5 else outliers.tolist()
						})

			if outlier_issues:
				issues.append({
					"check_type": QualityCheckType.ACCURACY.value,
					"issue_type": "outliers_detected",
					"issue_level": QualityIssueLevel.MEDIUM.value,
					"message": f"在 {len(outlier_issues)} 个列中检测到异常值",
					"details": {
						"outlier_issues": outlier_issues,
						"detection_method": method,
						"threshold": threshold
					}
				})

			statistics["outliers"] = {
				"checked_columns": len(numeric_columns),
				"columns_with_outliers": len(outlier_issues),
				"detection_method": method
			}

		return {
			"issues": issues,
			"statistics": statistics
		}

	def check_business_rules (
			self,
			data: pd.DataFrame,
			data_type: str,
			**kwargs
	) -> Dict[str, Any]:
		"""
		检查业务规则

		Args:
			data: 待检查的数据
			data_type: 数据类型
			**kwargs: 额外参数

		Returns:
			检查结果
		"""
		issues = []
		statistics = {}

		business_rules = self._get_business_rules(data_type)

		if business_rules and isinstance(data, pd.DataFrame):
			rule_violations = []

			for rule_name, rule_func in business_rules.items():
				try:
					violations = rule_func(data)
					if violations is not None and len(violations) > 0:
						rule_violations.append({
							"rule_name": rule_name,
							"violation_count": len(violations),
							"violations": violations.head().to_dict('records') if len(
								violations) > 5 else violations.to_dict('records')
						})
				except Exception as e:
					self.logger.warning(f"执行业务规则 {rule_name} 失败: {e}")

			if rule_violations:
				issues.append({
					"check_type": QualityCheckType.ACCURACY.value,
					"issue_type": "business_rule_violation",
					"issue_level": QualityIssueLevel.HIGH.value,
					"message": f"发现 {len(rule_violations)} 个业务规则违反",
					"details": {
						"rule_violations": rule_violations
					}
				})

			statistics["business_rules"] = {
				"checked_rules": len(business_rules),
				"violated_rules": len(rule_violations)
			}

		return {
			"issues": issues,
			"statistics": statistics
		}

	def check_cross_reference (
			self,
			data: pd.DataFrame,
			data_type: str,
			reference_data: Optional[pd.DataFrame] = None,
			**kwargs
	) -> Dict[str, Any]:
		"""
		交叉引用检查

		Args:
			data: 待检查的数据
			data_type: 数据类型
			reference_data: 参考数据
			**kwargs: 额外参数

		Returns:
			检查结果
		"""
		issues = []
		statistics = {}

		if reference_data is not None and isinstance(data, pd.DataFrame):
			# 检查数据完整性
			reference_issues = []

			# 检查symbol是否在参考数据中
			if "symbol" in data.columns and "symbol" in reference_data.columns:
				unique_symbols = data["symbol"].unique()
				missing_symbols = [
					symbol for symbol in unique_symbols
					if symbol not in reference_data["symbol"].values
				]

				if missing_symbols:
					reference_issues.append({
						"check": "symbol_reference",
						"missing_count": len(missing_symbols),
						"missing_symbols": missing_symbols[:10]  # 只显示前10个
					})

			if reference_issues:
				issues.append({
					"check_type": QualityCheckType.ACCURACY.value,
					"issue_type": "cross_reference_issue",
					"issue_level": QualityIssueLevel.MEDIUM.value,
					"message": f"发现 {len(reference_issues)} 个交叉引用问题",
					"details": {
						"reference_issues": reference_issues
					}
				})

			statistics["cross_reference"] = {
				"reference_data_columns": list(reference_data.columns),
				"reference_issues": len(reference_issues)
			}

		return {
			"issues": issues,
			"statistics": statistics
		}

	# ==================== 及时性检查函数 ====================

	def check_freshness (
			self,
			data: pd.DataFrame,
			data_type: str,
			expected_freshness_hours: int = 24,
			**kwargs
	) -> Dict[str, Any]:
		"""
		检查数据新鲜度

		Args:
			data: 待检查的数据
			data_type: 数据类型
			expected_freshness_hours: 预期新鲜度（小时）
			**kwargs: 额外参数

		Returns:
			检查结果
		"""
		issues = []
		statistics = {}

		# 查找时间字段
		time_columns = [col for col in data.columns if
		                any(keyword in col.lower() for keyword in ['date', 'time', 'timestamp'])]

		if time_columns:
			freshness_issues = []
			now = datetime.now()

			for time_col in time_columns:
				try:
					# 转换为datetime
					if data[time_col].dtype == 'object':
						times = pd.to_datetime(data[time_col], errors='coerce')
					else:
						times = data[time_col]

					# 找到最新时间
					if times.notna().any():
						latest_time = times.max()

						if isinstance(latest_time, pd.Timestamp):
							latest_time = latest_time.to_pydatetime()

						# 计算时间差
						time_diff = now - latest_time
						hours_diff = time_diff.total_seconds() / 3600

						if hours_diff > expected_freshness_hours:
							freshness_issues.append({
								"time_column": time_col,
								"latest_time": latest_time.isoformat() if hasattr(latest_time, 'isoformat') else str(
									latest_time),
								"hours_since_update": round(hours_diff, 2),
								"expected_freshness_hours": expected_freshness_hours
							})

						statistics["freshness"] = {
							"time_column": time_col,
							"latest_time": latest_time.isoformat() if hasattr(latest_time, 'isoformat') else str(
								latest_time),
							"hours_since_update": round(hours_diff, 2),
							"expected_freshness_hours": expected_freshness_hours
						}

				except Exception as e:
					self.logger.warning(f"检查时间列 {time_col} 的新鲜度失败: {e}")

			if freshness_issues:
				issues.append({
					"check_type": QualityCheckType.TIMELINESS.value,
					"issue_type": "data_stale",
					"issue_level": QualityIssueLevel.MEDIUM.value,
					"message": f"数据新鲜度不足，最新数据已超过 {expected_freshness_hours} 小时",
					"details": {
						"freshness_issues": freshness_issues
					}
				})

		return {
			"issues": issues,
			"statistics": statistics
		}

	def check_update_frequency (
			self,
			data: pd.DataFrame,
			data_type: str,
			expected_frequency: str = "daily",
			**kwargs
	) -> Dict[str, Any]:
		"""
		检查数据更新频率

		Args:
			data: 待检查的数据
			data_type: 数据类型
			expected_frequency: 预期频率 (daily, hourly, weekly, etc.)
			**kwargs: 额外参数

		Returns:
			检查结果
		"""
		issues = []
		statistics = {}

		# 查找时间字段
		time_columns = [col for col in data.columns if
		                any(keyword in col.lower() for keyword in ['date', 'time', 'timestamp'])]

		if time_columns and len(data) > 1:
			frequency_issues = []

			for time_col in time_columns:
				try:
					# 转换为datetime
					if data[time_col].dtype == 'object':
						times = pd.to_datetime(data[time_col], errors='coerce')
					else:
						times = data[time_col]

					# 计算时间间隔
					if times.notna().sum() > 1:
						sorted_times = times.dropna().sort_values()
						time_diffs = sorted_times.diff().dropna()

						if len(time_diffs) > 0:
							# 转换为小时
							time_diffs_hours = time_diffs.apply(lambda x: x.total_seconds() / 3600)

							avg_interval = time_diffs_hours.mean()
							std_interval = time_diffs_hours.std()

							# 检查是否符合预期频率
							expected_interval = self._get_expected_interval_hours(expected_frequency)

							if expected_interval > 0:
								interval_ratio = avg_interval / expected_interval

								if interval_ratio > 1.5 or interval_ratio < 0.5:
									frequency_issues.append({
										"time_column": time_col,
										"expected_frequency": expected_frequency,
										"actual_avg_interval_hours": round(avg_interval, 2),
										"interval_std_hours": round(std_interval, 2),
										"interval_ratio": round(interval_ratio, 2)
									})

							statistics["update_frequency"] = {
								"time_column": time_col,
								"expected_frequency": expected_frequency,
								"actual_avg_interval_hours": round(avg_interval, 2),
								"interval_std_hours": round(std_interval, 2),
								"data_points": len(sorted_times)
							}

				except Exception as e:
					self.logger.warning(f"检查时间列 {time_col} 的更新频率失败: {e}")

			if frequency_issues:
				issues.append({
					"check_type": QualityCheckType.TIMELINESS.value,
					"issue_type": "update_frequency_issue",
					"issue_level": QualityIssueLevel.LOW.value,
					"message": f"数据更新频率与预期不符",
					"details": {
						"frequency_issues": frequency_issues
					}
				})

		return {
			"issues": issues,
			"statistics": statistics
		}

	# ==================== 有效性检查函数 ====================

	def check_format_validity (
			self,
			data: pd.DataFrame,
			data_type: str,
			**kwargs
	) -> Dict[str, Any]:
		"""
		检查格式有效性

		Args:
			data: 待检查的数据
			data_type: 数据类型
			**kwargs: 额外参数

		Returns:
			检查结果
		"""
		issues = []
		statistics = {}

		format_rules = self._get_format_rules(data_type)

		if format_rules:
			format_issues = []

			for column, pattern in format_rules.items():
				if column in data.columns:
					# 检查格式
					invalid_values = data[~data[column].astype(str).str.match(pattern, na=False)]

					if not invalid_values.empty:
						format_issues.append({
							"column": column,
							"pattern": pattern,
							"invalid_count": len(invalid_values),
							"invalid_examples": invalid_values[column].head().tolist()
						})

			if format_issues:
				issues.append({
					"check_type": QualityCheckType.VALIDITY.value,
					"issue_type": "format_invalid",
					"issue_level": QualityIssueLevel.MEDIUM.value,
					"message": f"发现 {len(format_issues)} 个格式无效的列",
					"details": {
						"format_issues": format_issues
					}
				})

			statistics["format_validity"] = {
				"checked_columns": len(format_rules),
				"invalid_columns": len(format_issues)
			}

		return {
			"issues": issues,
			"statistics": statistics
		}

	def check_referential_integrity (
			self,
			data: pd.DataFrame,
			data_type: str,
			reference_data: Optional[Dict[str, List]] = None,
			**kwargs
	) -> Dict[str, Any]:
		"""
		检查引用完整性

		Args:
			data: 待检查的数据
			data_type: 数据类型
			reference_data: 参考数据字典 {column: [valid_values]}
			**kwargs: 额外参数

		Returns:
			检查结果
		"""
		issues = []
		statistics = {}

		if reference_data:
			integrity_issues = []

			for column, valid_values in reference_data.items():
				if column in data.columns:
					invalid_values = data[~data[column].isin(valid_values)]

					if not invalid_values.empty:
						integrity_issues.append({
							"column": column,
							"invalid_count": len(invalid_values),
							"unique_invalid_values": invalid_values[column].unique().tolist()[:10]  # 只显示前10个
						})

			if integrity_issues:
				issues.append({
					"check_type": QualityCheckType.VALIDITY.value,
					"issue_type": "referential_integrity_violation",
					"issue_level": QualityIssueLevel.HIGH.value,
					"message": f"发现 {len(integrity_issues)} 个引用完整性问题",
					"details": {
						"integrity_issues": integrity_issues
					}
				})

			statistics["referential_integrity"] = {
				"checked_columns": len(reference_data),
				"invalid_columns": len(integrity_issues)
			}

		return {
			"issues": issues,
			"statistics": statistics
		}

	# ==================== 辅助函数 ====================

	def _determine_missing_value_issue_level (self, missing_pct: float) -> QualityIssueLevel:
		"""根据缺失值比例确定问题等级"""
		if missing_pct >= 50:
			return QualityIssueLevel.CRITICAL
		elif missing_pct >= 20:
			return QualityIssueLevel.HIGH
		elif missing_pct >= 5:
			return QualityIssueLevel.MEDIUM
		elif missing_pct > 0:
			return QualityIssueLevel.LOW
		else:
			return QualityIssueLevel.INFO

	def _get_required_columns (self, data_type: str) -> List[str]:
		"""获取必需列"""
		# 从配置中获取
		if f"{data_type}_required_columns" in self.data_rules:
			return self.data_rules[f"{data_type}_required_columns"]

		# 默认规则
		if data_type == "stock_quote":
			return ["symbol", "date", "open", "high", "low", "close", "volume"]
		elif data_type == "financial":
			return ["symbol", "report_date", "revenue", "net_income"]
		else:
			return []

	def _get_expected_data_types (self, data_type: str) -> Dict[str, str]:
		"""获取期望的数据类型"""
		type_mapping = {
			"stock_quote": {
				"symbol": "string",
				"date": "datetime",
				"open": "float",
				"high": "float",
				"low": "float",
				"close": "float",
				"volume": "float",
				"amount": "float"
			}
		}
		return type_mapping.get(data_type, {})

	def _check_type_match (self, actual_type: str, expected_type: str) -> bool:
		"""检查类型匹配"""
		type_groups = {
			"numeric": ["float64", "int64", "float32", "int32"],
			"datetime": ["datetime64[ns]", "datetime64"],
			"string": ["object", "string"]
		}

		# 简化类型检查
		for group, types in type_groups.items():
			if expected_type == group and actual_type in types:
				return True

		return actual_type == expected_type

	def _get_value_range_rules (self, data_type: str) -> Dict[str, Dict]:
		"""获取数值范围规则"""
		if data_type == "stock_quote":
			return {
				"open": {"min": 0.01, "max": 100000},
				"high": {"min": 0.01, "max": 100000},
				"low": {"min": 0.01, "max": 100000},
				"close": {"min": 0.01, "max": 100000},
				"volume": {"min": 0, "max": 1e12},
				"change_pct": {"min": -0.3, "max": 0.3}
			}
		return {}

	def _get_unique_keys (self, data_type: str) -> List[str]:
		"""获取唯一键"""
		if data_type == "stock_quote":
			return ["symbol", "date"]
		elif data_type == "financial":
			return ["symbol", "report_date", "report_type"]
		else:
			return []

	def _detect_outliers (self, values: pd.Series, method: str, threshold: float) -> Optional[pd.Series]:
		"""检测异常值"""
		if method == "iqr":
			# IQR方法
			Q1 = values.quantile(0.25)
			Q3 = values.quantile(0.75)
			IQR = Q3 - Q1
			lower_bound = Q1 - threshold * IQR
			upper_bound = Q3 + threshold * IQR
			return values[(values < lower_bound) | (values > upper_bound)]

		elif method == "zscore":
			# Z-score方法
			mean = values.mean()
			std = values.std()
			if std > 0:
				z_scores = (values - mean) / std
				return values[abs(z_scores) > threshold]

		elif method == "percentile":
			# 百分位方法
			lower_bound = values.quantile(0.01)
			upper_bound = values.quantile(0.99)
			return values[(values < lower_bound) | (values > upper_bound)]

		return None

	def _get_business_rules (self, data_type: str) -> Dict[str, Callable]:
		"""获取业务规则"""
		rules = {}

		if data_type == "stock_quote":
			def high_low_rule (df):
				"""最高价应大于等于最低价"""
				return df[df["high"] < df["low"]]

			def close_in_range_rule (df):
				"""收盘价应在最高价和最低价之间"""
				return df[(df["close"] < df["low"]) | (df["close"] > df["high"])]

			rules["high_low_rule"] = high_low_rule
			rules["close_in_range_rule"] = close_in_range_rule

		return rules

	def _get_expected_interval_hours (self, frequency: str) -> float:
		"""获取预期时间间隔（小时）"""
		intervals = {
			"hourly": 1,
			"daily": 24,
			"weekly": 168,
			"monthly": 720,  # 30天
			"quarterly": 2160,  # 90天
			"yearly": 8760  # 365天
		}
		return intervals.get(frequency.lower(), 0)

	def _get_format_rules (self, data_type: str) -> Dict[str, str]:
		"""获取格式规则"""
		if data_type == "stock_quote":
			return {
				"symbol": r'^[0-9]{6}\.[A-Z]{2}$',  # 如: 000001.SZ
				"date": r'^\d{4}-\d{2}-\d{2}$'  # YYYY-MM-DD
			}
		return {}

	def _calculate_quality_score (self, issues: List[Dict], data: pd.DataFrame) -> float:
		"""计算质量分数"""
		if data.empty:
			return 0.0

		# 基础分数
		base_score = 100.0

		# 根据问题等级扣分
		penalty_weights = {
			QualityIssueLevel.CRITICAL: 20,
			QualityIssueLevel.HIGH: 10,
			QualityIssueLevel.MEDIUM: 5,
			QualityIssueLevel.LOW: 2,
			QualityIssueLevel.INFO: 0.5
		}

		total_penalty = 0
		for issue in issues:
			issue_level = QualityIssueLevel(issue["issue_level"])
			penalty = penalty_weights.get(issue_level, 0)
			total_penalty += penalty

		# 根据数据量调整扣分
		data_size_factor = min(1.0, 1000 / len(data)) if len(data) > 0 else 1.0
		adjusted_penalty = total_penalty * data_size_factor

		# 计算最终分数
		final_score = max(0.0, base_score - adjusted_penalty)

		return round(final_score, 2)

	def _generate_quality_report (
			self,
			data_type: str,
			issues: List[Dict],
			statistics: Dict,
			quality_score: float,
			check_types: List[QualityCheckType]
	) -> Dict[str, Any]:
		"""生成质量报告"""
		# 按问题等级统计
		issue_summary = {}
		for level in QualityIssueLevel:
			issue_summary[level.value] = sum(
				1 for issue in issues if issue["issue_level"] == level.value
			)

		# 按检查类型统计
		check_summary = {}
		for check_type in check_types:
			check_summary[check_type.value] = sum(
				1 for issue in issues if issue["check_type"] == check_type.value
			)

		# 总体评估
		overall_assessment = self._assess_quality_level(quality_score)

		report = {
			"metadata": {
				"data_type": data_type,
				"check_timestamp": datetime.now().isoformat(),
				"check_types": [ct.value for ct in check_types],
				"checker_version": "1.0"
			},
			"summary": {
				"quality_score": quality_score,
				"overall_assessment": overall_assessment,
				"total_issues": len(issues),
				"issue_summary": issue_summary,
				"check_summary": check_summary
			},
			"statistics": statistics,
			"issues": issues,
			"recommendations": self._generate_recommendations(issues, quality_score)
		}

		return report

	def _assess_quality_level (self, quality_score: float) -> str:
		"""评估质量等级"""
		if quality_score >= 90:
			return "EXCELLENT"
		elif quality_score >= 80:
			return "GOOD"
		elif quality_score >= 70:
			return "FAIR"
		elif quality_score >= 60:
			return "POOR"
		else:
			return "UNACCEPTABLE"

	def _generate_recommendations (
			self,
			issues: List[Dict],
			quality_score: float
	) -> List[str]:
		"""生成改进建议"""
		recommendations = []

		# 根据问题生成建议
		critical_issues = [issue for issue in issues if issue["issue_level"] == QualityIssueLevel.CRITICAL.value]
		high_issues = [issue for issue in issues if issue["issue_level"] == QualityIssueLevel.HIGH.value]

		if critical_issues:
			recommendations.append("立即处理严重问题，数据质量已受影响")

		if high_issues:
			recommendations.append("优先处理高优先级问题")

		# 根据分数生成通用建议
		if quality_score < 80:
			recommendations.append("建议进行数据清洗和验证")

		if quality_score < 70:
			recommendations.append("考虑重新获取数据源")

		return recommendations

	def _generate_error_report (self, error_message: str) -> Dict[str, Any]:
		"""生成错误报告"""
		return {
			"metadata": {
				"check_timestamp": datetime.now().isoformat(),
				"status": "ERROR"
			},
			"summary": {
				"quality_score": 0.0,
				"overall_assessment": "ERROR",
				"total_issues": 0,
				"error": error_message
			},
			"issues": [],
			"recommendations": ["检查数据格式和完整性后重试"]
		}

	def batch_check_quality (
			self,
			data_list: List[Tuple[pd.DataFrame, str]],
			check_types: Optional[List[QualityCheckType]] = None
	) -> Dict[str, Dict]:
		"""
		批量检查数据质量

		Args:
			data_list: 数据列表，每个元素为(数据, 数据类型)的元组
			check_types: 检查类型列表

		Returns:
			质量检查结果字典 {数据标识: 检查结果}
		"""
		results = {}

		for i, (data, data_type) in enumerate(data_list):
			try:
				result = self.check_quality(data, data_type, check_types)
				results[f"dataset_{i}"] = result
			except Exception as e:
				self.logger.error(f"批量检查数据集 {i} 失败: {e}")
				results[f"dataset_{i}"] = self._generate_error_report(str(e))

		return results

	def register_custom_check (
			self,
			check_name: str,
			check_function: Callable,
			check_type: QualityCheckType = QualityCheckType.CONSISTENCY
	) -> None:
		"""
		注册自定义检查

		Args:
			check_name: 检查名称
			check_function: 检查函数
			check_type: 检查类型
		"""
		if check_type not in self.checks_config:
			self.checks_config[check_type] = []

		if check_name not in self.checks_config[check_type]:
			self.checks_config[check_type].append(check_name)

		# 动态添加检查函数
		setattr(self, check_name, check_function)

		self.logger.info(f"注册自定义检查: {check_name} ({check_type.value})")