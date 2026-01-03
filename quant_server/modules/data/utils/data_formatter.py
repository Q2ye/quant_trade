"""
数据格式化工具

负责将原始数据转换为标准格式，包括：
1. 数据结构标准化
2. 数据类型转换
3. 数据清洗和规整
4. 时间序列处理

设计原则：
- 纯函数：无状态，输入相同输出相同
- 可配置：支持不同格式的转换规则
- 可扩展：易于添加新的格式化规则
- 高性能：支持批量数据处理
"""

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
import re
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class DataFormat(str, Enum):
	"""数据格式枚举"""
	RAW = "raw"  # 原始格式
	STANDARD = "standard"  # 标准格式
	ANALYSIS = "analysis"  # 分析格式
	STORAGE = "storage"  # 存储格式
	API_RESPONSE = "api_response"  # API响应格式


class DataType(str, Enum):
	"""数据类型枚举"""
	STOCK_QUOTE = "stock_quote"  # 股票行情
	FINANCIAL = "financial"  # 财务数据
	FUNDAMENTAL = "fundamental"  # 基本面数据
	TRADE = "trade"  # 交易数据
	INDEX = "index"  # 指数数据
	MACRO = "macro"  # 宏观经济数据


class DataFormatter:
	"""
	数据格式化器

	提供统一的数据格式转换功能，确保数据在整个系统中使用一致的格式
	"""

	# 标准字段映射配置
	FIELD_MAPPINGS = {
		DataType.STOCK_QUOTE: {
			"ts_code": "symbol",
			"trade_date": "date",
			"open": "open",
			"high": "high",
			"low": "low",
			"close": "close",
			"pre_close": "pre_close",
			"change": "change",
			"pct_chg": "change_pct",
			"vol": "volume",
			"amount": "amount"
		},
		DataType.FINANCIAL: {
			"ts_code": "symbol",
			"ann_date": "announce_date",
			"end_date": "period_end",
			"revenue": "revenue",
			"n_income": "net_income",
			"total_assets": "total_assets",
			"total_liab": "total_liabilities",
			"eps": "eps"
		}
	}

	# 数据类型转换规则
	TYPE_CONVERSIONS = {
		"date": lambda x: pd.to_datetime(x).date() if pd.notna(x) else None,
		"datetime": lambda x: pd.to_datetime(x) if pd.notna(x) else None,
		"float": lambda x: float(x) if pd.notna(x) else None,
		"int": lambda x: int(x) if pd.notna(x) else None,
		"string": lambda x: str(x) if pd.notna(x) else None
	}

	def __init__ (self, config: Optional[Dict] = None):
		"""
		初始化数据格式化器

		Args:
			config: 格式化配置
		"""
		self.config = config or {}
		self.logger = logger

		# 加载自定义映射
		self.field_mappings = self.FIELD_MAPPINGS.copy()
		if "field_mappings" in self.config:
			self.field_mappings.update(self.config["field_mappings"])

	def format_data (
			self,
			data: Union[pd.DataFrame, List[Dict], Dict],
			data_type: DataType,
			target_format: DataFormat = DataFormat.STANDARD,
			**kwargs
	) -> Union[pd.DataFrame, List[Dict], Dict]:
		"""
		格式化数据

		Args:
			data: 原始数据，可以是DataFrame、字典列表或单个字典
			data_type: 数据类型
			target_format: 目标格式
			**kwargs: 额外参数

		Returns:
			格式化后的数据

		Raises:
			ValueError: 不支持的格式或数据类型
		"""
		try:
			self.logger.debug(f"开始格式化数据: {data_type} -> {target_format}")

			# 转换为DataFrame以便处理
			if isinstance(data, dict):
				df = pd.DataFrame([data])
			elif isinstance(data, list):
				df = pd.DataFrame(data)
			else:
				df = data.copy()

			# 根据目标格式选择格式化方法
			if target_format == DataFormat.STANDARD:
				result = self._format_to_standard(df, data_type, **kwargs)
			elif target_format == DataFormat.ANALYSIS:
				result = self._format_to_analysis(df, data_type, **kwargs)
			elif target_format == DataFormat.STORAGE:
				result = self._format_to_storage(df, data_type, **kwargs)
			elif target_format == DataFormat.API_RESPONSE:
				result = self._format_to_api_response(df, data_type, **kwargs)
			else:
				raise ValueError(f"不支持的格式: {target_format}")

			# 根据输入类型返回相应格式
			if isinstance(data, dict):
				return result.iloc[0].to_dict() if not result.empty else {}
			elif isinstance(data, list):
				return result.to_dict('records')
			else:
				return result

		except Exception as e:
			self.logger.error(f"格式化数据失败: {e}", exc_info=True)
			raise

	def _format_to_standard (
			self,
			df: pd.DataFrame,
			data_type: DataType,
			**kwargs
	) -> pd.DataFrame:
		"""
		格式化为标准格式

		Args:
			df: 原始DataFrame
			data_type: 数据类型
			**kwargs: 额外参数

		Returns:
			标准格式的DataFrame
		"""
		# 获取字段映射
		field_map = self.field_mappings.get(data_type, {})

		# 重命名列
		result_df = df.rename(columns=field_map)

		# 应用数据类型转换
		result_df = self._apply_type_conversions(result_df, data_type)

		# 标准化日期时间字段
		result_df = self._standardize_datetime_fields(result_df, data_type)

		# 处理缺失值
		result_df = self._handle_missing_values(result_df, data_type)

		# 排序
		if "date" in result_df.columns:
			result_df = result_df.sort_values("date", ascending=True)

		# 重置索引
		result_df = result_df.reset_index(drop=True)

		return result_df

	def _format_to_analysis (
			self,
			df: pd.DataFrame,
			data_type: DataType,
			**kwargs
	) -> pd.DataFrame:
		"""
		格式化为分析格式

		Args:
			df: 原始DataFrame
			data_type: 数据类型
			**kwargs: 额外参数

		Returns:
			分析格式的DataFrame
		"""
		# 先转换为标准格式
		standard_df = self._format_to_standard(df, data_type, **kwargs)

		# 根据数据类型添加分析字段
		if data_type == DataType.STOCK_QUOTE:
			analysis_df = self._add_technical_indicators(standard_df)
		elif data_type == DataType.FINANCIAL:
			analysis_df = self._add_financial_ratios(standard_df)
		else:
			analysis_df = standard_df

		# 转换为时间序列格式（如果需要）
		if "date" in analysis_df.columns and "symbol" in analysis_df.columns:
			analysis_df = self._convert_to_time_series(analysis_df)

		return analysis_df

	def _format_to_storage (
			self,
			df: pd.DataFrame,
			data_type: DataType,
			**kwargs
	) -> pd.DataFrame:
		"""
		格式化为存储格式

		Args:
			df: 原始DataFrame
			data_type: 数据类型
			**kwargs: 额外参数

		Returns:
			存储格式的DataFrame
		"""
		# 使用标准格式作为基础
		standard_df = self._format_to_standard(df, data_type, **kwargs)

		# 添加元数据
		storage_df = standard_df.copy()
		storage_df["_data_type"] = data_type.value
		storage_df["_formatted_at"] = datetime.now()
		storage_df["_format_version"] = "1.0"

		# 确保列名符合数据库要求（小写、下划线）
		storage_df.columns = [self._normalize_column_name(col) for col in storage_df.columns]

		# 转换数据类型为数据库友好类型
		storage_df = self._convert_to_storage_types(storage_df)

		return storage_df

	def _format_to_api_response (
			self,
			df: pd.DataFrame,
			data_type: DataType,
			**kwargs
	) -> pd.DataFrame:
		"""
		格式化为API响应格式

		Args:
			df: 原始DataFrame
			data_type: 数据类型
			**kwargs: 额外参数

		Returns:
			API响应格式的DataFrame
		"""
		# 使用标准格式作为基础
		standard_df = self._format_to_standard(df, data_type, **kwargs)

		# 转换为嵌套结构（如果需要）
		api_df = self._convert_to_nested_structure(standard_df, data_type)

		# 添加分页信息等元数据
		if "pagination" in kwargs:
			api_df = self._add_pagination_info(api_df, kwargs["pagination"])

		return api_df

	def _apply_type_conversions (
			self,
			df: pd.DataFrame,
			data_type: DataType
	) -> pd.DataFrame:
		"""
		应用数据类型转换

		Args:
			df: 原始DataFrame
			data_type: 数据类型

		Returns:
			转换类型后的DataFrame
		"""
		result_df = df.copy()

		# 根据数据类型定义转换规则
		type_rules = self._get_type_rules(data_type)

		for column, dtype in type_rules.items():
			if column in result_df.columns:
				if dtype in self.TYPE_CONVERSIONS:
					result_df[column] = result_df[column].apply(
						self.TYPE_CONVERSIONS[dtype]
					)

		return result_df

	def _get_type_rules (self, data_type: DataType) -> Dict[str, str]:
		"""
		获取数据类型转换规则

		Args:
			data_type: 数据类型

		Returns:
			类型转换规则字典
		"""
		type_rules = {
			DataType.STOCK_QUOTE: {
				"date": "date",
				"open": "float",
				"high": "float",
				"low": "float",
				"close": "float",
				"pre_close": "float",
				"volume": "float",
				"amount": "float",
				"change_pct": "float"
			},
			DataType.FINANCIAL: {
				"announce_date": "date",
				"period_end": "date",
				"revenue": "float",
				"net_income": "float",
				"total_assets": "float",
				"total_liabilities": "float",
				"eps": "float"
			}
		}

		return type_rules.get(data_type, {})

	def _standardize_datetime_fields (
			self,
			df: pd.DataFrame,
			data_type: DataType
	) -> pd.DataFrame:
		"""
		标准化日期时间字段

		Args:
			df: 原始DataFrame
			data_type: 数据类型

		Returns:
			标准化后的DataFrame
		"""
		result_df = df.copy()

		# 识别日期时间字段
		date_columns = []
		for col in result_df.columns:
			col_lower = col.lower()
			if any(keyword in col_lower for keyword in ['date', 'time', 'timestamp']):
				date_columns.append(col)

		# 转换日期时间字段
		for col in date_columns:
			if col in result_df.columns:
				try:
					result_df[col] = pd.to_datetime(result_df[col])
				except Exception as e:
					self.logger.warning(f"转换日期字段失败 {col}: {e}")

		return result_df

	def _handle_missing_values (
			self,
			df: pd.DataFrame,
			data_type: DataType
	) -> pd.DataFrame:
		"""
		处理缺失值

		Args:
			df: 原始DataFrame
			data_type: 数据类型

		Returns:
			处理缺失值后的DataFrame
		"""
		result_df = df.copy()

		# 根据数据类型定义处理策略
		if data_type == DataType.STOCK_QUOTE:
			# 对于行情数据，数值字段用前向填充
			numeric_cols = result_df.select_dtypes(include=[np.number]).columns
			result_df[numeric_cols] = result_df[numeric_cols].ffill()
		elif data_type == DataType.FINANCIAL:
			# 对于财务数据，用0填充缺失的数值
			numeric_cols = result_df.select_dtypes(include=[np.number]).columns
			result_df[numeric_cols] = result_df[numeric_cols].fillna(0)

		return result_df

	def _add_technical_indicators (self, df: pd.DataFrame) -> pd.DataFrame:
		"""
		添加技术指标

		Args:
			df: 标准格式的DataFrame

		Returns:
			添加技术指标后的DataFrame
		"""
		if "close" not in df.columns or "volume" not in df.columns:
			return df

		result_df = df.copy()

		# 计算移动平均线
		result_df["ma5"] = result_df["close"].rolling(window=5).mean()
		result_df["ma10"] = result_df["close"].rolling(window=10).mean()
		result_df["ma20"] = result_df["close"].rolling(window=20).mean()

		# 计算RSI
		result_df["rsi"] = self._calculate_rsi(result_df["close"])

		# 计算MACD
		macd, signal, hist = self._calculate_macd(result_df["close"])
		result_df["macd"] = macd
		result_df["macd_signal"] = signal
		result_df["macd_hist"] = hist

		# 计算布林带
		result_df["bb_upper"], result_df["bb_middle"], result_df["bb_lower"] = \
			self._calculate_bollinger_bands(result_df["close"])

		return result_df

	def _add_financial_ratios (self, df: pd.DataFrame) -> pd.DataFrame:
		"""
		添加财务比率

		Args:
			df: 标准格式的DataFrame

		Returns:
			添加财务比率后的DataFrame
		"""
		required_cols = ["revenue", "net_income", "total_assets", "total_liabilities"]
		if not all(col in df.columns for col in required_cols):
			return df

		result_df = df.copy()

		# 计算利润率
		result_df["profit_margin"] = result_df["net_income"] / result_df["revenue"]

		# 计算资产收益率
		result_df["roa"] = result_df["net_income"] / result_df["total_assets"]

		# 计算负债率
		result_df["debt_ratio"] = result_df["total_liabilities"] / result_df["total_assets"]

		return result_df

	def _convert_to_time_series (self, df: pd.DataFrame) -> pd.DataFrame:
		"""
		转换为时间序列格式

		Args:
			df: 原始DataFrame

		Returns:
			时间序列格式的DataFrame
		"""
		if "symbol" not in df.columns or "date" not in df.columns:
			return df

		# 设置多级索引
		result_df = df.set_index(["symbol", "date"]).sort_index()

		return result_df

	def _normalize_column_name (self, column_name: str) -> str:
		"""
		规范化列名

		Args:
			column_name: 原始列名

		Returns:
			规范化后的列名
		"""
		# 转换为小写
		normalized = column_name.lower()

		# 替换特殊字符为下划线
		normalized = re.sub(r'[^a-z0-9_]', '_', normalized)

		# 移除连续的下划线
		normalized = re.sub(r'_+', '_', normalized)

		# 移除首尾下划线
		normalized = normalized.strip('_')

		return normalized

	def _convert_to_storage_types (self, df: pd.DataFrame) -> pd.DataFrame:
		"""
		转换为存储类型

		Args:
			df: 原始DataFrame

		Returns:
			转换类型后的DataFrame
		"""
		result_df = df.copy()

		# 将datetime转换为字符串
		datetime_cols = result_df.select_dtypes(include=['datetime64']).columns
		for col in datetime_cols:
			result_df[col] = result_df[col].dt.strftime('%Y-%m-%d %H:%M:%S')

		# 将date转换为字符串
		date_cols = result_df.select_dtypes(include=['object']).columns
		for col in date_cols:
			if col.endswith('_date') or col == 'date':
				result_df[col] = pd.to_datetime(result_df[col]).dt.strftime('%Y-%m-%d')

		return result_df

	def _convert_to_nested_structure (
			self,
			df: pd.DataFrame,
			data_type: DataType
	) -> pd.DataFrame:
		"""
		转换为嵌套结构

		Args:
			df: 原始DataFrame
			data_type: 数据类型

		Returns:
			嵌套结构的DataFrame
		"""
		# 如果有多只股票，按股票分组
		if "symbol" in df.columns and len(df["symbol"].unique()) > 1:
			grouped = df.groupby("symbol")

			# 创建嵌套结构
			nested_data = []
			for symbol, group in grouped:
				symbol_data = {
					"symbol": symbol,
					"data": group.drop(columns=["symbol"]).to_dict('records')
				}
				nested_data.append(symbol_data)

			return pd.DataFrame(nested_data)

		return df

	def _add_pagination_info (
			self,
			df: pd.DataFrame,
			pagination: Dict
	) -> pd.DataFrame:
		"""
		添加分页信息

		Args:
			df: 原始DataFrame
			pagination: 分页信息

		Returns:
			添加分页信息后的DataFrame
		"""
		result = {
			"data": df.to_dict('records') if not df.empty else [],
			"pagination": pagination,
			"timestamp": datetime.now().isoformat()
		}

		return pd.DataFrame([result])

	@staticmethod
	def _calculate_rsi (prices: pd.Series, period: int = 14) -> pd.Series:
		"""
		计算RSI指标

		Args:
			prices: 价格序列
			period: RSI周期

		Returns:
			RSI序列
		"""
		delta = prices.diff()
		gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
		loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

		rs = gain / loss
		rsi = 100 - (100 / (1 + rs))

		return rsi

	@staticmethod
	def _calculate_macd (
			prices: pd.Series,
			fast_period: int = 12,
			slow_period: int = 26,
			signal_period: int = 9
	) -> Tuple[pd.Series, pd.Series, pd.Series]:
		"""
		计算MACD指标

		Args:
			prices: 价格序列
			fast_period: 快线周期
			slow_period: 慢线周期
			signal_period: 信号线周期

		Returns:
			(MACD线, 信号线, 柱状图)
		"""
		ema_fast = prices.ewm(span=fast_period, adjust=False).mean()
		ema_slow = prices.ewm(span=slow_period, adjust=False).mean()

		macd_line = ema_fast - ema_slow
		signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
		histogram = macd_line - signal_line

		return macd_line, signal_line, histogram

	@staticmethod
	def _calculate_bollinger_bands (
			prices: pd.Series,
			period: int = 20,
			num_std: float = 2.0
	) -> Tuple[pd.Series, pd.Series, pd.Series]:
		"""
		计算布林带

		Args:
			prices: 价格序列
			period: 移动平均周期
			num_std: 标准差倍数

		Returns:
			(上轨, 中轨, 下轨)
		"""
		middle_band = prices.rolling(window=period).mean()
		std = prices.rolling(window=period).std()

		upper_band = middle_band + (std * num_std)
		lower_band = middle_band - (std * num_std)

		return upper_band, middle_band, lower_band

	def batch_format (
			self,
			data_list: List[Tuple[Union[pd.DataFrame, List[Dict], Dict], DataType]],
			target_format: DataFormat = DataFormat.STANDARD,
			**kwargs
	) -> List[Any]:
		"""
		批量格式化数据

		Args:
			data_list: 数据列表，每个元素为(数据, 数据类型)的元组
			target_format: 目标格式
			**kwargs: 额外参数

		Returns:
			格式化后的数据列表
		"""
		formatted_results = []

		for data, data_type in data_list:
			try:
				formatted = self.format_data(
					data=data,
					data_type=data_type,
					target_format=target_format,
					**kwargs
				)
				formatted_results.append(formatted)
			except Exception as e:
				self.logger.error(f"批量格式化数据失败: {e}")
				formatted_results.append(None)

		return formatted_results

	def validate_format (
			self,
			data: Any,
			data_type: DataType,
			expected_format: DataFormat
	) -> Tuple[bool, List[str]]:
		"""
		验证数据格式

		Args:
			data: 待验证的数据
			data_type: 数据类型
			expected_format: 期望格式

		Returns:
			(是否有效, 错误消息列表)
		"""
		errors = []

		# 检查数据类型
		if not isinstance(data, (dict, list, pd.DataFrame)):
			errors.append(f"不支持的数据类型: {type(data)}")
			return False, errors

		# 根据期望格式进行验证
		if expected_format == DataFormat.STANDARD:
			return self._validate_standard_format(data, data_type)
		elif expected_format == DataFormat.ANALYSIS:
			return self._validate_analysis_format(data, data_type)
		elif expected_format == DataFormat.STORAGE:
			return self._validate_storage_format(data, data_type)
		elif expected_format == DataFormat.API_RESPONSE:
			return self._validate_api_response_format(data, data_type)
		else:
			errors.append(f"不支持的格式: {expected_format}")
			return False, errors

	def _validate_standard_format (
			self,
			data: Any,
			data_type: DataType
	) -> Tuple[bool, List[str]]:
		"""
		验证标准格式

		Args:
			data: 待验证的数据
			data_type: 数据类型

		Returns:
			(是否有效, 错误消息列表)
		"""
		errors = []

		# 获取必需字段
		required_fields = self._get_required_fields(data_type)

		# 转换为DataFrame进行检查
		try:
			if isinstance(data, dict):
				df = pd.DataFrame([data])
			elif isinstance(data, list):
				df = pd.DataFrame(data)
			else:
				df = data

			# 检查必需字段
			missing_fields = [field for field in required_fields if field not in df.columns]
			if missing_fields:
				errors.append(f"缺少必需字段: {missing_fields}")

			# 检查数据类型
			for field in required_fields:
				if field in df.columns:
					# 检查是否有NaN值
					if df[field].isna().any():
						errors.append(f"字段 {field} 包含空值")

		except Exception as e:
			errors.append(f"验证格式时发生错误: {e}")

		return len(errors) == 0, errors

	def _validate_analysis_format (
			self,
			data: Any,
			data_type: DataType
	) -> Tuple[bool, List[str]]:
		"""
		验证分析格式

		Args:
			data: 待验证的数据
			data_type: 数据类型

		Returns:
			(是否有效, 错误消息列表)
		"""
		errors = []

		# 先验证标准格式
		is_valid, std_errors = self._validate_standard_format(data, data_type)
		if not is_valid:
			errors.extend(std_errors)

		# 根据数据类型检查分析字段
		if data_type == DataType.STOCK_QUOTE:
			analysis_fields = ["ma5", "ma10", "ma20", "rsi"]
		elif data_type == DataType.FINANCIAL:
			analysis_fields = ["profit_margin", "roa", "debt_ratio"]
		else:
			analysis_fields = []

		# 检查分析字段（如果有的话）
		try:
			if isinstance(data, dict):
				df = pd.DataFrame([data])
			elif isinstance(data, list):
				df = pd.DataFrame(data)
			else:
				df = data

			for field in analysis_fields:
				if field in df.columns and df[field].isna().all():
					errors.append(f"分析字段 {field} 全部为空")

		except Exception as e:
			errors.append(f"验证分析格式时发生错误: {e}")

		return len(errors) == 0, errors

	def _validate_storage_format (
			self,
			data: Any,
			data_type: DataType
	) -> Tuple[bool, List[str]]:
		"""
		验证存储格式

		Args:
			data: 待验证的数据
			data_type: 数据类型

		Returns:
			(是否有效, 错误消息列表)
		"""
		errors = []

		try:
			if isinstance(data, dict):
				df = pd.DataFrame([data])
			elif isinstance(data, list):
				df = pd.DataFrame(data)
			else:
				df = data

			# 检查元数据字段
			meta_fields = ["_data_type", "_formatted_at", "_format_version"]
			missing_meta = [field for field in meta_fields if field not in df.columns]
			if missing_meta:
				errors.append(f"缺少元数据字段: {missing_meta}")

			# 检查列名规范化
			for col in df.columns:
				normalized = self._normalize_column_name(col)
				if col != normalized:
					errors.append(f"列名未规范化: {col} -> {normalized}")

		except Exception as e:
			errors.append(f"验证存储格式时发生错误: {e}")

		return len(errors) == 0, errors

	def _validate_api_response_format (
			self,
			data: Any,
			data_type: DataType
	) -> Tuple[bool, List[str]]:
		"""
		验证API响应格式

		Args:
			data: 待验证的数据
			data_type: 数据类型

		Returns:
			(是否有效, 错误消息列表)
		"""
		errors = []

		try:
			if isinstance(data, dict):
				# 检查API响应结构
				required_keys = ["data", "timestamp"]
				missing_keys = [key for key in required_keys if key not in data]
				if missing_keys:
					errors.append(f"缺少API响应字段: {missing_keys}")

				# 检查分页信息
				if "pagination" in data:
					pagination = data["pagination"]
					required_pagination = ["page", "page_size", "total"]
					missing_pagination = [
						key for key in required_pagination
						if key not in pagination
					]
					if missing_pagination:
						errors.append(f"缺少分页信息字段: {missing_pagination}")

		except Exception as e:
			errors.append(f"验证API响应格式时发生错误: {e}")

		return len(errors) == 0, errors

	def _get_required_fields (self, data_type: DataType) -> List[str]:
		"""
		获取必需字段

		Args:
			data_type: 数据类型

		Returns:
			必需字段列表
		"""
		required_fields_map = {
			DataType.STOCK_QUOTE: ["symbol", "date", "open", "high", "low", "close", "volume"],
			DataType.FINANCIAL: ["symbol", "period_end", "revenue", "net_income"],
			DataType.INDEX: ["symbol", "date", "close"],
			DataType.TRADE: ["symbol", "trade_time", "price", "volume"]
		}

		return required_fields_map.get(data_type, [])