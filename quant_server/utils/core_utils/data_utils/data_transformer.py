"""
数据转换器 - 提供数据格式转换、标准化、规范化功能

职责：
1. 数据类型转换（字符串转数值、日期格式转换等）
2. 数据标准化（归一化、标准化）
3. 数据编码（独热编码、标签编码）
4. 数据规范化（单位转换、格式统一）
5. 数据衍生（特征工程、指标计算）

设计原则：
1. 可逆性：尽可能支持逆向转换
2. 可配置：转换规则可动态配置
3. 高性能：支持批量转换和缓存
4. 可组合：转换器可组合使用
5. 可监控：记录转换过程和统计信息
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union, Callable, TypeVar
from datetime import datetime, date, timedelta
from decimal import Decimal
import re
import json
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import hashlib
from collections import defaultdict
import warnings

T = TypeVar('T')


class TransformationType(Enum):
	"""转换类型枚举"""
	TYPE_CAST = "type_cast"  # 类型转换
	NORMALIZATION = "normalization"  # 归一化
	STANDARDIZATION = "standardization"  # 标准化
	ENCODING = "encoding"  # 编码
	SCALING = "scaling"  # 缩放
	DISCRETIZATION = "discretization"  # 离散化
	DERIVATION = "derivation"  # 衍生
	CLEANING = "cleaning"  # 清洗
	AGGREGATION = "aggregation"  # 聚合


@dataclass
class TransformationResult:
	"""转换结果数据结构"""
	original_value: Any  # 原始值
	transformed_value: Any  # 转换后的值
	transformation_type: TransformationType  # 转换类型
	field_name: str  # 字段名
	transformer_name: str  # 转换器名称
	metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
	timestamp: datetime = field(default_factory=datetime.now)  # 转换时间

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典格式"""
		return {
			"field_name": self.field_name,
			"transformation_type": self.transformation_type.value,
			"transformer_name": self.transformer_name,
			"original_value": self.original_value,
			"transformed_value": self.transformed_value,
			"metadata": self.metadata,
			"timestamp": self.timestamp.isoformat()
		}


@dataclass
class TransformationReport:
	"""转换报告"""
	total_records: int = 0  # 总记录数
	transformed_fields: List[str] = field(default_factory=list)  # 转换字段列表
	transformation_results: List[TransformationResult] = field(default_factory=list)  # 详细结果
	summary: Dict[str, Any] = field(default_factory=dict)  # 汇总信息
	execution_time: float = 0.0  # 执行时间(秒)

	def add_result (self, result: TransformationResult):
		"""添加转换结果"""
		self.transformation_results.append(result)
		if result.field_name not in self.transformed_fields:
			self.transformed_fields.append(result.field_name)

	def calculate_summary (self):
		"""计算汇总信息"""
		# 按转换类型统计
		type_stats = defaultdict(int)
		for result in self.transformation_results:
			type_stats[result.transformation_type.value] += 1

		# 按字段统计
		field_stats = defaultdict(int)
		for result in self.transformation_results:
			field_stats[result.field_name] += 1

		self.summary = {
			"total_transformations": len(self.transformation_results),
			"transformed_fields": len(self.transformed_fields),
			"by_transformation_type": dict(type_stats),
			"by_field": dict(field_stats),
			"start_time": min([r.timestamp for r in self.transformation_results],
			                  default=datetime.now()).isoformat(),
			"end_time": max([r.timestamp for r in self.transformation_results],
			                default=datetime.now()).isoformat()
		}

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典格式"""
		self.calculate_summary()
		return {
			"summary": self.summary,
			"results": [result.to_dict() for result in self.transformation_results],
			"execution_time": self.execution_time
		}


class DataTransformer(ABC):
	"""数据转换器基类"""

	def __init__ (self, field_name: str, transformer_name: str = None):
		"""
		初始化数据转换器

		Args:
			field_name: 字段名
			transformer_name: 转换器名称
		"""
		self.field_name = field_name
		self.transformer_name = transformer_name or self.__class__.__name__
		self.transformation_type = TransformationType.TYPE_CAST  # 默认类型
		self._fitted = False  # 是否已拟合

	@abstractmethod
	def fit (self, data: List[Any]) -> 'DataTransformer':
		"""
		拟合转换器（学习数据特征）

		Args:
			data: 训练数据

		Returns:
			DataTransformer: 拟合后的转换器
		"""
		pass

	@abstractmethod
	def transform (self, value: Any) -> Any:
		"""
		转换单个值

		Args:
			value: 要转换的值

		Returns:
			Any: 转换后的值
		"""
		pass

	@abstractmethod
	def inverse_transform (self, value: Any) -> Any:
		"""
		逆向转换（如果支持）

		Args:
			value: 转换后的值

		Returns:
			Any: 原始值
		"""
		pass

	def fit_transform (self, data: List[Any]) -> List[Any]:
		"""
		拟合并转换数据

		Args:
			data: 数据列表

		Returns:
			List[Any]: 转换后的数据列表
		"""
		self.fit(data)
		return [self.transform(x) for x in data]

	def is_fitted (self) -> bool:
		"""检查是否已拟合"""
		return self._fitted


class TypeCaster(DataTransformer):
	"""类型转换器"""

	def __init__ (self, field_name: str, target_type: type,
	              format_string: str = None, **kwargs):
		"""
		初始化类型转换器

		Args:
			field_name: 字段名
			target_type: 目标类型
			format_string: 日期时间格式字符串
			**kwargs: 其他参数
		"""
		super().__init__(field_name, **kwargs)
		self.target_type = target_type
		self.format_string = format_string
		self.transformation_type = TransformationType.TYPE_CAST

		# 类型转换函数映射
		self.type_converters = {
			int: self._to_int,
			float: self._to_float,
			str: self._to_str,
			bool: self._to_bool,
			Decimal: self._to_decimal,
			datetime: self._to_datetime,
			date: self._to_date
		}

	def fit (self, data: List[Any]) -> 'TypeCaster':
		"""拟合转换器（类型转换器无需拟合）"""
		self._fitted = True
		return self

	def transform (self, value: Any) -> Any:
		"""
		转换单个值

		Args:
			value: 要转换的值

		Returns:
			Any: 转换后的值

		Raises:
			ValueError: 转换失败时抛出
		"""
		if value is None:
			return None

		# 如果已经是目标类型，直接返回
		if isinstance(value, self.target_type):
			return value

		# 获取转换函数
		converter = self.type_converters.get(self.target_type)
		if not converter:
			raise ValueError(f"不支持的转换类型: {self.target_type}")

		try:
			return converter(value)
		except Exception as e:
			# 尝试通用转换
			try:
				return self.target_type(value)
			except:
				raise ValueError(f"无法将值 {value} 转换为 {self.target_type}: {str(e)}")

	def inverse_transform (self, value: Any) -> Any:
		"""逆向转换"""
		return value  # 类型转换通常是可逆的

	def _to_int (self, value: Any) -> int:
		"""转换为整数"""
		if isinstance(value, str):
			# 尝试去除千分位分隔符
			value = value.replace(',', '')
		return int(float(value)) if '.' in str(value) else int(value)

	def _to_float (self, value: Any) -> float:
		"""转换为浮点数"""
		if isinstance(value, str):
			value = value.replace(',', '').replace(' ', '')
		return float(value)

	def _to_str (self, value: Any) -> str:
		"""转换为字符串"""
		if pd.isna(value):
			return ""
		return str(value)

	def _to_bool (self, value: Any) -> bool:
		"""转换为布尔值"""
		if isinstance(value, str):
			value_lower = value.lower().strip()
			if value_lower in ('true', 'yes', 'y', '1', 't'):
				return True
			elif value_lower in ('false', 'no', 'n', '0', 'f'):
				return False

		return bool(value)

	def _to_decimal (self, value: Any) -> Decimal:
		"""转换为Decimal"""
		if isinstance(value, str):
			value = value.replace(',', '').replace(' ', '')
		return Decimal(str(value))

	def _to_datetime (self, value: Any) -> datetime:
		"""转换为datetime"""
		if isinstance(value, datetime):
			return value

		if isinstance(value, date):
			return datetime.combine(value, datetime.min.time())

		if isinstance(value, (int, float)):
			# 可能是时间戳
			try:
				return datetime.fromtimestamp(value)
			except:
				# 可能是Excel日期
				return datetime(1899, 12, 30) + timedelta(days=value)

		if isinstance(value, str):
			# 尝试解析字符串
			value = str(value).strip()

			# 尝试使用提供的格式字符串
			if self.format_string:
				try:
					return datetime.strptime(value, self.format_string)
				except:
					pass

			# 尝试常见格式
			formats = [
				'%Y-%m-%d %H:%M:%S',
				'%Y/%m/%d %H:%M:%S',
				'%Y-%m-%d',
				'%Y/%m/%d',
				'%Y%m%d',
				'%Y-%m-%d %H:%M',
				'%Y/%m/%d %H:%M'
			]

			for fmt in formats:
				try:
					return datetime.strptime(value, fmt)
				except:
					continue

			# 尝试去除时区信息
			if 'T' in value:
				value = value.split('T')[0]
				return self._to_datetime(value)

		raise ValueError(f"无法将值 {value} 转换为 datetime")

	def _to_date (self, value: Any) -> date:
		"""转换为date"""
		if isinstance(value, date):
			return value

		dt = self._to_datetime(value)
		return dt.date()


class Normalizer(DataTransformer):
	"""归一化转换器（将值缩放到[0,1]范围）"""

	def __init__ (self, field_name: str, min_value: float = None,
	              max_value: float = None, **kwargs):
		"""
		初始化归一化转换器

		Args:
			field_name: 字段名
			min_value: 最小值（如果为None，则从数据中学习）
			max_value: 最大值（如果为None，则从数据中学习）
			**kwargs: 其他参数
		"""
		super().__init__(field_name, **kwargs)
		self.min_value = min_value
		self.max_value = max_value
		self.transformation_type = TransformationType.NORMALIZATION
		self.original_min = None
		self.original_max = None

	def fit (self, data: List[Any]) -> 'Normalizer':
		"""
		拟合转换器（计算最小值和最大值）

		Args:
			data: 训练数据（数值列表）

		Returns:
			Normalizer: 拟合后的转换器
		"""
		if not data:
			raise ValueError("数据不能为空")

		# 转换为数值列表
		numeric_data = []
		for value in data:
			if value is not None:
				try:
					numeric_data.append(float(value))
				except:
					pass

		if not numeric_data:
			raise ValueError("数据中没有有效的数值")

		# 计算最小值和最大值
		self.original_min = min(numeric_data) if self.min_value is None else self.min_value
		self.original_max = max(numeric_data) if self.max_value is None else self.max_value

		# 避免除零
		if self.original_max == self.original_min:
			self.original_max = self.original_min + 1

		self._fitted = True
		return self

	def transform (self, value: Any) -> Any:
		"""
		归一化单个值

		Args:
			value: 要归一化的值

		Returns:
			float: 归一化后的值（0到1之间）
		"""
		if not self._fitted:
			raise RuntimeError("转换器未拟合，请先调用fit()方法")

		if value is None:
			return None

		try:
			numeric_value = float(value)
		except (ValueError, TypeError):
			return None

		# 归一化公式: (x - min) / (max - min)
		normalized = (numeric_value - self.original_min) / (self.original_max - self.original_min)

		# 限制在[0,1]范围内（处理超出训练数据范围的值）
		return max(0.0, min(1.0, normalized))

	def inverse_transform (self, value: Any) -> Any:
		"""
		逆向归一化

		Args:
			value: 归一化后的值

		Returns:
			float: 原始值
		"""
		if not self._fitted:
			raise RuntimeError("转换器未拟合，请先调用fit()方法")

		if value is None:
			return None

		try:
			normalized = float(value)
		except (ValueError, TypeError):
			return None

		# 限制在[0,1]范围内
		normalized = max(0.0, min(1.0, normalized))

		# 逆向归一化公式: x * (max - min) + min
		original = normalized * (self.original_max - self.original_min) + self.original_min

		return original


class StandardScaler(DataTransformer):
	"""标准化转换器（Z-score标准化）"""

	def __init__ (self, field_name: str, mean: float = None,
	              std: float = None, **kwargs):
		"""
		初始化标准化转换器

		Args:
			field_name: 字段名
			mean: 均值（如果为None，则从数据中学习）
			std: 标准差（如果为None，则从数据中学习）
			**kwargs: 其他参数
		"""
		super().__init__(field_name, **kwargs)
		self.mean = mean
		self.std = std
		self.transformation_type = TransformationType.STANDARDIZATION
		self.original_mean = None
		self.original_std = None

	def fit (self, data: List[Any]) -> 'StandardScaler':
		"""
		拟合转换器（计算均值和标准差）

		Args:
			data: 训练数据（数值列表）

		Returns:
			StandardScaler: 拟合后的转换器
		"""
		if not data:
			raise ValueError("数据不能为空")

		# 转换为数值列表
		numeric_data = []
		for value in data:
			if value is not None:
				try:
					numeric_data.append(float(value))
				except:
					pass

		if not numeric_data:
			raise ValueError("数据中没有有效的数值")

		# 计算均值和标准差
		self.original_mean = np.mean(numeric_data) if self.mean is None else self.mean
		self.original_std = np.std(numeric_data) if self.std is None else self.std

		# 避免除零
		if self.original_std == 0:
			self.original_std = 1.0

		self._fitted = True
		return self

	def transform (self, value: Any) -> Any:
		"""
		标准化单个值

		Args:
			value: 要标准化的值

		Returns:
			float: 标准化后的值（Z-score）
		"""
		if not self._fitted:
			raise RuntimeError("转换器未拟合，请先调用fit()方法")

		if value is None:
			return None

		try:
			numeric_value = float(value)
		except (ValueError, TypeError):
			return None

		# 标准化公式: (x - mean) / std
		standardized = (numeric_value - self.original_mean) / self.original_std

		return standardized

	def inverse_transform (self, value: Any) -> Any:
		"""
		逆向标准化

		Args:
			value: 标准化后的值

		Returns:
			float: 原始值
		"""
		if not self._fitted:
			raise RuntimeError("转换器未拟合，请先调用fit()方法")

		if value is None:
			return None

		try:
			standardized = float(value)
		except (ValueError, TypeError):
			return None

		# 逆向标准化公式: x * std + mean
		original = standardized * self.original_std + self.original_mean

		return original


class OneHotEncoder(DataTransformer):
	"""独热编码器"""

	def __init__ (self, field_name: str, categories: List[Any] = None,
	              drop_first: bool = False, **kwargs):
		"""
		初始化独热编码器

		Args:
			field_name: 字段名
			categories: 类别列表（如果为None，则从数据中学习）
			drop_first: 是否删除第一列（避免多重共线性）
			**kwargs: 其他参数
		"""
		super().__init__(field_name, **kwargs)
		self.categories = categories
		self.drop_first = drop_first
		self.transformation_type = TransformationType.ENCODING
		self.category_to_index = {}
		self.index_to_category = {}
		self.num_categories = 0

	def fit (self, data: List[Any]) -> 'OneHotEncoder':
		"""
		拟合编码器（学习所有类别）

		Args:
			data: 训练数据

		Returns:
			OneHotEncoder: 拟合后的编码器
		"""
		if not data:
			raise ValueError("数据不能为空")

		# 获取所有唯一类别
		unique_categories = set()
		for value in data:
			if value is not None:
				unique_categories.add(str(value))

		# 使用提供的类别或学习的类别
		if self.categories is None:
			self.categories = sorted(list(unique_categories))

		# 创建映射
		for i, category in enumerate(self.categories):
			self.category_to_index[category] = i
			self.index_to_category[i] = category

		self.num_categories = len(self.categories)

		self._fitted = True
		return self

	def transform (self, value: Any) -> List[int]:
		"""
		独热编码单个值

		Args:
			value: 要编码的值

		Returns:
			List[int]: 独热编码向量
		"""
		if not self._fitted:
			raise RuntimeError("编码器未拟合，请先调用fit()方法")

		if value is None:
			# 返回全零向量或None
			if self.drop_first:
				return [0] * (self.num_categories - 1)
			else:
				return [0] * self.num_categories

		str_value = str(value)

		# 检查是否在已知类别中
		if str_value not in self.category_to_index:
			# 未知类别，返回全零向量
			if self.drop_first:
				return [0] * (self.num_categories - 1)
			else:
				return [0] * self.num_categories

		index = self.category_to_index[str_value]

		if self.drop_first:
			# 删除第一列，所以索引要减1
			if index == 0:
				# 属于第一个类别，所有位都为0
				return [0] * (self.num_categories - 1)
			else:
				# 创建独热向量
				one_hot = [0] * (self.num_categories - 1)
				one_hot[index - 1] = 1
				return one_hot
		else:
			# 完整的独热向量
			one_hot = [0] * self.num_categories
			one_hot[index] = 1
			return one_hot

	def inverse_transform (self, value: List[int]) -> Any:
		"""
		逆向独热编码

		Args:
			value: 独热编码向量

		Returns:
			Any: 原始类别值
		"""
		if not self._fitted:
			raise RuntimeError("编码器未拟合，请先调用fit()方法")

		if value is None:
			return None

		# 找到值为1的索引
		if self.drop_first:
			# 如果删除了第一列
			if all(v == 0 for v in value):
				# 全零表示第一个类别
				return self.index_to_category[0]
			else:
				for i, v in enumerate(value):
					if v == 1:
						# 索引要加1，因为删除了第一列
						return self.index_to_category[i + 1]
		else:
			# 完整的独热向量
			for i, v in enumerate(value):
				if v == 1:
					return self.index_to_category[i]

		# 如果没有找到1，返回None或第一个类别
		return None


class MinMaxScaler(DataTransformer):
	"""最小最大缩放器（将值缩放到指定范围）"""

	def __init__ (self, field_name: str, feature_range: Tuple[float, float] = (0, 1),
	              min_value: float = None, max_value: float = None, **kwargs):
		"""
		初始化最小最大缩放器

		Args:
			field_name: 字段名
			feature_range: 目标范围（最小值，最大值）
			min_value: 最小值（如果为None，则从数据中学习）
			max_value: 最大值（如果为None，则从数据中学习）
			**kwargs: 其他参数
		"""
		super().__init__(field_name, **kwargs)
		self.feature_range = feature_range
		self.min_value = min_value
		self.max_value = max_value
		self.transformation_type = TransformationType.SCALING
		self.data_min = None
		self.data_max = None
		self.scale = None
		self.min = None

	def fit (self, data: List[Any]) -> 'MinMaxScaler':
		"""
		拟合缩放器

		Args:
			data: 训练数据

		Returns:
			MinMaxScaler: 拟合后的缩放器
		"""
		if not data:
			raise ValueError("数据不能为空")

		# 转换为数值列表
		numeric_data = []
		for value in data:
			if value is not None:
				try:
					numeric_data.append(float(value))
				except:
					pass

		if not numeric_data:
			raise ValueError("数据中没有有效的数值")

		# 计算数据的最小值和最大值
		self.data_min = min(numeric_data) if self.min_value is None else self.min_value
		self.data_max = max(numeric_data) if self.max_value is None else self.max_value

		# 避免除零
		if self.data_max == self.data_min:
			self.data_max = self.data_min + 1

		# 计算缩放参数
		self.scale = (self.feature_range[1] - self.feature_range[0]) / (self.data_max - self.data_min)
		self.min = self.feature_range[0] - self.data_min * self.scale

		self._fitted = True
		return self

	def transform (self, value: Any) -> Any:
		"""
		缩放单个值

		Args:
			value: 要缩放的值

		Returns:
			float: 缩放后的值
		"""
		if not self._fitted:
			raise RuntimeError("缩放器未拟合，请先调用fit()方法")

		if value is None:
			return None

		try:
			numeric_value = float(value)
		except (ValueError, TypeError):
			return None

		# 缩放公式: X_std = (X - X.min) / (X.max - X.min)
		# X_scaled = X_std * (max - min) + min
		X_std = (numeric_value - self.data_min) / (self.data_max - self.data_min)
		X_scaled = X_std * (self.feature_range[1] - self.feature_range[0]) + self.feature_range[0]

		# 或者使用：X_scaled = X * scale + min
		# X_scaled = numeric_value * self.scale + self.min

		return X_scaled

	def inverse_transform (self, value: Any) -> Any:
		"""
		逆向缩放

		Args:
			value: 缩放后的值

		Returns:
			float: 原始值
		"""
		if not self._fitted:
			raise RuntimeError("缩放器未拟合，请先调用fit()方法")

		if value is None:
			return None

		try:
			scaled_value = float(value)
		except (ValueError, TypeError):
			return None

		# 逆向缩放公式
		X_std = (scaled_value - self.feature_range[0]) / (self.feature_range[1] - self.feature_range[0])
		original = X_std * (self.data_max - self.data_min) + self.data_min

		return original


class DataDeriver(DataTransformer):
	"""数据衍生器（特征工程）"""

	def __init__ (self, field_name: str, derivation_func: Callable[[Any], Any],
	              new_field_name: str = None, **kwargs):
		"""
		初始化数据衍生器

		Args:
			field_name: 原始字段名
			derivation_func: 衍生函数
			new_field_name: 新字段名（如果为None，则使用原始字段名加后缀）
			**kwargs: 其他参数
		"""
		super().__init__(field_name, **kwargs)
		self.derivation_func = derivation_func
		self.new_field_name = new_field_name or f"{field_name}_derived"
		self.transformation_type = TransformationType.DERIVATION

	def fit (self, data: List[Any]) -> 'DataDeriver':
		"""拟合衍生器（无需拟合）"""
		self._fitted = True
		return self

	def transform (self, value: Any) -> Any:
		"""
		衍生新特征

		Args:
			value: 原始值

		Returns:
			Any: 衍生值
		"""
		try:
			return self.derivation_func(value)
		except Exception as e:
			warnings.warn(f"衍生函数执行失败: {str(e)}")
			return None

	def inverse_transform (self, value: Any) -> Any:
		"""逆向衍生（通常不支持）"""
		raise NotImplementedError("数据衍生通常不支持逆向转换")


class DataTransformerPipeline:
	"""
	数据转换器管道

	支持多个转换器的链式执行
	"""

	def __init__ (self, transformers: List[DataTransformer] = None):
		"""
		初始化转换器管道

		Args:
			transformers: 转换器列表
		"""
		self.transformers = transformers or []
		self.report = TransformationReport()

	def add_transformer (self, transformer: DataTransformer):
		"""添加转换器到管道"""
		self.transformers.append(transformer)

	def fit (self, data: Dict[str, List[Any]]):
		"""
		拟合所有转换器

		Args:
			data: 训练数据字典，格式为 {字段名: 值列表}
		"""
		for transformer in self.transformers:
			field_data = data.get(transformer.field_name, [])
			if field_data:
				transformer.fit(field_data)

	def transform_record (self, record: Dict[str, Any]) -> Dict[str, Any]:
		"""
		转换单条记录

		Args:
			record: 原始记录

		Returns:
			Dict[str, Any]: 转换后的记录
		"""
		transformed_record = record.copy()

		for transformer in self.transformers:
			field_name = transformer.field_name
			if field_name in transformed_record:
				original_value = transformed_record[field_name]
				transformed_value = transformer.transform(original_value)

				# 记录转换结果
				result = TransformationResult(
					original_value=original_value,
					transformed_value=transformed_value,
					transformation_type=transformer.transformation_type,
					field_name=field_name,
					transformer_name=transformer.transformer_name,
					metadata={"fitted": transformer.is_fitted()}
				)
				self.report.add_result(result)

				# 更新记录
				if isinstance(transformer, DataDeriver):
					# 衍生器创建新字段
					transformed_record[transformer.new_field_name] = transformed_value
				else:
					# 其他转换器修改原字段
					transformed_record[field_name] = transformed_value

		return transformed_record

	def transform_batch (self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		"""
		批量转换多条记录

		Args:
			records: 原始记录列表

		Returns:
			List[Dict[str, Any]]: 转换后的记录列表
		"""
		start_time = datetime.now()
		self.report = TransformationReport(total_records=len(records))

		transformed_records = []
		for record in records:
			transformed_record = self.transform_record(record)
			transformed_records.append(transformed_record)

		self.report.execution_time = (datetime.now() - start_time).total_seconds()
		return transformed_records

	def transform_dataframe (self, df: pd.DataFrame) -> pd.DataFrame:
		"""
		转换Pandas DataFrame

		Args:
			df: 原始DataFrame

		Returns:
			pd.DataFrame: 转换后的DataFrame
		"""
		records = df.to_dict('records')
		transformed_records = self.transform_batch(records)
		return pd.DataFrame(transformed_records)


# 预定义转换器工厂
class TransformationFactory:
	"""转换器工厂类"""

	@staticmethod
	def create_stock_transformation_pipeline () -> DataTransformerPipeline:
		"""创建股票数据转换管道"""
		pipeline = DataTransformerPipeline()

		# 日期字段转换
		pipeline.add_transformer(
			TypeCaster("trade_date", date, format_string="%Y%m%d")
		)

		# 价格字段转换（字符串转浮点数）
		price_fields = ["open", "high", "low", "close", "pre_close"]
		for field in price_fields:
			pipeline.add_transformer(
				TypeCaster(field, float)
			)

		# 成交量转换
		pipeline.add_transformer(
			TypeCaster("vol", float)
		)

		# 成交额转换（处理可能的大数字和逗号分隔）
		pipeline.add_transformer(
			TypeCaster("amount", float)
		)

		# 涨跌幅转换（百分比字符串转浮点数）
		def pct_to_float (value):
			if isinstance(value, str):
				if '%' in value:
					return float(value.replace('%', '')) / 100
				elif value.endswith('%%'):
					return float(value.replace('%%', '')) / 10000
			return float(value)

		pipeline.add_transformer(
			DataDeriver("pct_chg", pct_to_float, new_field_name="pct_chg_float")
		)

		return pipeline

	@staticmethod
	def create_financial_transformation_pipeline () -> DataTransformerPipeline:
		"""创建财务数据转换管道"""
		pipeline = DataTransformerPipeline()

		# 基本字段转换
		pipeline.add_transformer(
			TypeCaster("end_date", date, format_string="%Y%m%d")
		)

		# 财务指标转换（处理可能为字符串的大数字）
		financial_fields = [
			"total_revenue", "net_profit", "total_assets",
			"total_liabilities", "equity"
		]

		for field in financial_fields:
			pipeline.add_transformer(
				TypeCaster(field, float)
			)

		# 比率字段转换（百分比转小数）
		ratio_fields = ["roe", "roa", "gross_margin", "net_margin"]

		for field in ratio_fields:
			def create_pct_converter ():
				def converter (value):
					if isinstance(value, str):
						if '%' in value:
							return float(value.replace('%', ''))
						elif value.endswith('%%'):
							return float(value.replace('%%', '')) / 100
					return float(value)

				return converter

			pipeline.add_transformer(
				DataDeriver(field, create_pct_converter(), new_field_name=f"{field}_value")
			)

		return pipeline

	@staticmethod
	def create_normalization_pipeline (fields: List[str]) -> DataTransformerPipeline:
		"""创建归一化管道"""
		pipeline = DataTransformerPipeline()

		for field in fields:
			pipeline.add_transformer(
				Normalizer(field)
			)

		return pipeline

	@staticmethod
	def create_standardization_pipeline (fields: List[str]) -> DataTransformerPipeline:
		"""创建标准化管道"""
		pipeline = DataTransformerPipeline()

		for field in fields:
			pipeline.add_transformer(
				StandardScaler(field)
			)

		return pipeline


# 使用示例
if __name__ == "__main__":
	# 示例：转换股票数据
	stock_data = [
		{
			"ts_code": "000001.SZ",
			"trade_date": "20231201",
			"open": "10.50",
			"high": "11.20",
			"low": "10.30",
			"close": "11.00",
			"pre_close": "10.80",
			"vol": "1,000,000",
			"amount": "11,000,000",
			"pct_chg": "1.85%"
		},
		{
			"ts_code": "000002.SZ",
			"trade_date": "20231201",
			"open": "20.10",
			"high": "21.50",
			"low": "19.80",
			"close": "21.00",
			"pre_close": "20.50",
			"vol": "1,500,000",
			"amount": "31,500,000",
			"pct_chg": "2.44%"
		}
	]

	# 创建转换管道
	pipeline = TransformationFactory.create_stock_transformation_pipeline()

	# 拟合转换器（需要训练数据）
	train_data = {
		"trade_date": ["20231201", "20231201"],
		"open": ["10.50", "20.10"],
		"high": ["11.20", "21.50"],
		"low": ["10.30", "19.80"],
		"close": ["11.00", "21.00"],
		"pre_close": ["10.80", "20.50"],
		"vol": ["1,000,000", "1,500,000"],
		"amount": ["11,000,000", "31,500,000"],
		"pct_chg": ["1.85%", "2.44%"]
	}
	pipeline.fit(train_data)

	# 执行转换
	transformed_data = pipeline.transform_batch(stock_data)

	# 输出转换结果
	print("原始数据:")
	print(json.dumps(stock_data[0], indent=2, default=str))

	print("\n转换后数据:")
	print(json.dumps(transformed_data[0], indent=2, default=str))

	print("\n转换报告:")
	report_dict = pipeline.report.to_dict()
	print(f"总记录数: {pipeline.report.total_records}")
	print(f"转换字段数: {len(pipeline.report.transformed_fields)}")
	print(f"总转换次数: {report_dict['summary']['total_transformations']}")
	print(f"执行时间: {pipeline.report.execution_time:.4f}秒")

	# 示例：归一化转换
	print("\n--- 归一化示例 ---")
	price_data = [
		{"price": 10.5},
		{"price": 20.1},
		{"price": 15.8},
		{"price": 25.3},
		{"price": 18.7}
	]

	# 创建归一化转换器
	normalizer = Normalizer("price")
	normalizer.fit([d["price"] for d in price_data])

	print("原始价格:", [d["price"] for d in price_data])
	print("归一化后:", [normalizer.transform(d["price"]) for d in price_data])
	print("逆向转换:", [normalizer.inverse_transform(normalizer.transform(d["price"])) for d in price_data])