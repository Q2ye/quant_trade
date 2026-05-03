"""
因子计算器

负责计算各种金融因子，包括：
1. 技术指标因子
2. 基本面因子
3. 风险因子
4. 量价因子

设计原则：
- 模块化：每个因子独立计算
- 可配置：支持参数化计算
- 高性能：支持向量化计算
- 可扩展：易于添加新因子
"""

import logging
import warnings
from enum import Enum
from typing import Dict, List, Optional, Union, Tuple, Callable

import numpy as np
import pandas as pd
import pandas_ta_classic

logger = logging.getLogger(__name__)

# 忽略警告
warnings.filterwarnings('ignore')


class FactorCategory(str, Enum):
	"""因子类别枚举"""
	TECHNICAL = "technical"  # 技术指标
	FUNDAMENTAL = "fundamental"  # 基本面
	VOLUME = "volume"  # 成交量
	VOLATILITY = "volatility"  # 波动率
	MOMENTUM = "momentum"  # 动量
	VALUE = "value"  # 价值
	GROWTH = "growth"  # 成长
	QUALITY = "quality"  # 质量


class FactorCalculator:
	"""
	因子计算器

	提供统一的因子计算接口，支持多种类型的因子计算
	"""

	# 因子配置
	FACTOR_CONFIGS = {
		# 技术指标因子
		"ma": {
			"category": FactorCategory.TECHNICAL,
			"description": "移动平均线",
			"parameters": {"period": [5, 10, 20, 60]},
			"function": "calculate_ma"
		},
		"rsi": {
			"category": FactorCategory.TECHNICAL,
			"description": "相对强弱指数",
			"parameters": {"period": [6, 12, 24]},
			"function": "calculate_rsi"
		},
		"macd": {
			"category": FactorCategory.TECHNICAL,
			"description": "移动平均收敛发散",
			"parameters": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
			"function": "calculate_macd"
		},
		"bollinger": {
			"category": FactorCategory.TECHNICAL,
			"description": "布林带",
			"parameters": {"period": 20, "std_dev": 2.0},
			"function": "calculate_bollinger_bands"
		},

		# 动量因子
		"momentum": {
			"category": FactorCategory.MOMENTUM,
			"description": "价格动量",
			"parameters": {"period": [1, 5, 10, 20, 60]},
			"function": "calculate_momentum"
		},
		"roc": {
			"category": FactorCategory.MOMENTUM,
			"description": "价格变化率",
			"parameters": {"period": [5, 10, 20]},
			"function": "calculate_roc"
		},

		# 波动率因子
		"volatility": {
			"category": FactorCategory.VOLATILITY,
			"description": "波动率",
			"parameters": {"period": [5, 10, 20, 60]},
			"function": "calculate_volatility"
		},
		"atr": {
			"category": FactorCategory.VOLATILITY,
			"description": "平均真实波幅",
			"parameters": {"period": 14},
			"function": "calculate_atr"
		},

		# 成交量因子
		"volume_ratio": {
			"category": FactorCategory.VOLUME,
			"description": "量比",
			"parameters": {"period": 5},
			"function": "calculate_volume_ratio"
		},
		"obv": {
			"category": FactorCategory.VOLUME,
			"description": "能量潮",
			"function": "calculate_obv"
		},

		# 基本面因子（简化）
		"pe_ratio": {
			"category": FactorCategory.VALUE,
			"description": "市盈率",
			"function": "calculate_pe_ratio"
		},
		"pb_ratio": {
			"category": FactorCategory.VALUE,
			"description": "市净率",
			"function": "calculate_pb_ratio"
		},
		"roe": {
			"category": FactorCategory.QUALITY,
			"description": "净资产收益率",
			"function": "calculate_roe"
		}
	}

	def __init__ (self, config: Optional[Dict] = None):
		"""
		初始化因子计算器

		Args:
			config: 配置参数
		"""
		self.config = config or {}
		self.logger = logger

		# 加载自定义因子配置
		self.factor_configs = self.FACTOR_CONFIGS.copy()
		if "factor_configs" in self.config:
			self.factor_configs.update(self.config["factor_configs"])

	def calculate_factor (
			self,
			data: pd.DataFrame,
			factor_name: str,
			**kwargs
	) -> pd.DataFrame:
		"""
		计算单个因子

		Args:
			data: 原始数据，必须包含OHLCV等必要字段
			factor_name: 因子名称
			**kwargs: 因子参数

		Returns:
			包含因子值的DataFrame

		Raises:
			ValueError: 不支持的因子或缺少必要数据
		"""
		try:
			self.logger.debug(f"开始计算因子: {factor_name}")

			# 检查因子配置
			if factor_name not in self.factor_configs:
				raise ValueError(f"不支持的因子: {factor_name}")

			# 获取因子配置
			factor_config = self.factor_configs[factor_name]

			# 检查必要数据
			self._validate_data_for_factor(data, factor_name)

			# 合并参数
			params = factor_config.get("parameters", {})
			params.update(kwargs)

			# 获取计算函数
			function_name = factor_config["function"]
			if hasattr(self, function_name):
				calc_function = getattr(self, function_name)
			else:
				raise ValueError(f"找不到计算函数: {function_name}")

			# 执行计算
			result = calc_function(data, **params)

			# 确保结果是DataFrame
			if isinstance(result, pd.Series):
				result = pd.DataFrame({factor_name: result})
			elif isinstance(result, tuple):
				# 多个返回值的处理（如MACD返回多个序列）
				result_dict = {}
				for i, value in enumerate(result):
					if isinstance(value, pd.Series):
						suffix = f"_{i}" if i > 0 else ""
						result_dict[f"{factor_name}{suffix}"] = value
				result = pd.DataFrame(result_dict)

			self.logger.debug(f"因子计算完成: {factor_name}")
			return result

		except Exception as e:
			self.logger.error(f"计算因子失败 {factor_name}: {e}", exc_info=True)
			raise

	def calculate_factors (
			self,
			data: pd.DataFrame,
			factor_names: List[str],
			**kwargs
	) -> Dict[str, pd.DataFrame]:
		"""
		批量计算多个因子

		Args:
			data: 原始数据
			factor_names: 因子名称列表
			**kwargs: 全局参数

		Returns:
			因子计算结果字典
		"""
		results = {}

		for factor_name in factor_names:
			try:
				factor_result = self.calculate_factor(data, factor_name, **kwargs)
				results[factor_name] = factor_result
			except Exception as e:
				self.logger.warning(f"计算因子 {factor_name} 失败: {e}")
				results[factor_name] = None

		return results

	def calculate_factor_group (
			self,
			data: pd.DataFrame,
			category: FactorCategory,
			**kwargs
	) -> Dict[str, pd.DataFrame]:
		"""
		计算指定类别的所有因子

		Args:
			data: 原始数据
			category: 因子类别
			**kwargs: 参数

		Returns:
			因子计算结果字典
		"""
		# 获取指定类别的所有因子
		factor_names = [
			name for name, config in self.factor_configs.items()
			if config["category"] == category
		]

		return self.calculate_factors(data, factor_names, **kwargs)

	@staticmethod
	def _validate_data_for_factor (data: pd.DataFrame, factor_name: str) -> None:
		"""
		验证因子计算所需的数据

		Args:
			data: 数据DataFrame
			factor_name: 因子名称

		Raises:
			ValueError: 数据不完整
		"""
		# 定义各因子所需的字段
		required_fields_map = {
			"ma": ["close"],
			"rsi": ["close"],
			"macd": ["close"],
			"bollinger": ["close"],
			"momentum": ["close"],
			"roc": ["close"],
			"volatility": ["close"],
			"atr": ["high", "low", "close"],
			"volume_ratio": ["volume"],
			"obv": ["close", "volume"],
			"pe_ratio": ["close", "eps"],
			"pb_ratio": ["close", "bvps"],
			"roe": ["net_income", "equity"]
		}

		required_fields = required_fields_map.get(factor_name, [])

		missing_fields = [field for field in required_fields if field not in data.columns]
		if missing_fields:
			raise ValueError(f"计算因子 {factor_name} 缺少字段: {missing_fields}")

	# ==================== 技术指标因子计算函数 ====================

	@staticmethod
	def calculate_ma (data: pd.DataFrame, period: Union[int, List[int]] = 20) -> Union[pd.Series, pd.DataFrame]:
		"""
		计算移动平均线

		Args:
			data: 数据DataFrame
			period: 移动平均周期，可以是单个值或列表

		Returns:
			移动平均线值
		"""
		close = data["close"]

		if isinstance(period, list):
			result = {}
			for p in period:
				result[f"ma{p}"] = close.rolling(window=p).mean()
			return pd.DataFrame(result)
		else:
			return close.rolling(window=period).mean()

	@staticmethod
	def calculate_rsi (data: pd.DataFrame, period: Union[int, List[int]] = 14) -> Union[pd.Series, pd.DataFrame]:
		"""
		计算RSI指标

		Args:
			data: 数据DataFrame
			period: RSI周期，可以是单个值或列表

		Returns:
			RSI值
		"""
		close = data["close"]

		if isinstance(period, list):
			result = {}
			for p in period:
				delta = close.diff()
				gain = (delta.where(delta > 0, 0)).rolling(window=p).mean()
				loss = (-delta.where(delta < 0, 0)).rolling(window=p).mean()
				rs = gain / loss
				rsi = 100 - (100 / (1 + rs))
				result[f"rsi{p}"] = rsi
			return pd.DataFrame(result)
		else:
			return pandas_ta_classic.rsi(close, length=period)

	@staticmethod
	def calculate_macd (
			data: pd.DataFrame,
			fast_period: int = 12,
			slow_period: int = 26,
			signal_period: int = 9
	) -> Tuple[pd.Series, pd.Series, pd.Series]:
		"""
		计算MACD指标

		Args:
			data: 数据DataFrame
			fast_period: 快线周期
			slow_period: 慢线周期
			signal_period: 信号线周期

		Returns:
			(MACD线, 信号线, 柱状图)
		"""
		close = data["close"]

		macd_df = pandas_ta_classic.macd(
			close,
			fast=fast_period,
			slow=slow_period,
			signal=signal_period
		)
		# pandas_ta_classic 列序: MACD(快线), MACDh(柱), MACDs(信号)
		return macd_df.iloc[:, 0], macd_df.iloc[:, 2], macd_df.iloc[:, 1]

	@staticmethod
	def calculate_bollinger_bands (
			data: pd.DataFrame,
			period: int = 20,
			std_dev: float = 2.0
	) -> Tuple[pd.Series, pd.Series, pd.Series]:
		"""
		计算布林带

		Args:
			data: 数据DataFrame
			period: 移动平均周期
			std_dev: 标准差倍数

		Returns:
			(上轨, 中轨, 下轨)
		"""
		close = data["close"]

		bb_df = pandas_ta_classic.bbands(close, length=period, std=std_dev)
		# pandas_ta_classic 列序: BBU(上轨), BBM(中轨), BBL(下轨)
		return bb_df.iloc[:, 0], bb_df.iloc[:, 1], bb_df.iloc[:, 2]

	# ==================== 动量因子计算函数 ====================

	@staticmethod
	def calculate_momentum (
			data: pd.DataFrame,
			period: Union[int, List[int]] = 10
	) -> Union[pd.Series, pd.DataFrame]:
		"""
		计算动量因子

		Args:
			data: 数据DataFrame
			period: 动量周期，可以是单个值或列表

		Returns:
			动量值
		"""
		close = data["close"]

		if isinstance(period, list):
			result = {}
			for p in period:
				momentum = close / close.shift(p) - 1
				result[f"momentum{p}"] = momentum
			return pd.DataFrame(result)
		else:
			return close / close.shift(period) - 1

	@staticmethod
	def calculate_roc (
			data: pd.DataFrame,
			period: Union[int, List[int]] = 10
	) -> Union[pd.Series, pd.DataFrame]:
		"""
		计算价格变化率

		Args:
			data: 数据DataFrame
			period: 变化率周期，可以是单个值或列表

		Returns:
			价格变化率
		"""
		close = data["close"]

		if isinstance(period, list):
			result = {}
			for p in period:
				result[f"roc{p}"] = pandas_ta_classic.roc(close, length=p)
			return pd.DataFrame(result)
		else:
			return pandas_ta_classic.roc(close, length=period)

	# ==================== 波动率因子计算函数 ====================

	@staticmethod
	def calculate_volatility (
			data: pd.DataFrame,
			period: Union[int, List[int]] = 20
	) -> Union[pd.Series, pd.DataFrame]:
		"""
		计算波动率

		Args:
			data: 数据DataFrame
			period: 波动率计算周期，可以是单个值或列表

		Returns:
			波动率值
		"""
		close = data["close"]
		returns = close.pct_change()

		if isinstance(period, list):
			result = {}
			for p in period:
				volatility = returns.rolling(window=p).std() * np.sqrt(252)  # 年化波动率
				result[f"volatility{p}"] = volatility
			return pd.DataFrame(result)
		else:
			return returns.rolling(window=period).std() * np.sqrt(252)

	@staticmethod
	def calculate_atr (data: pd.DataFrame, period: int = 14) -> pd.Series:
		"""
		计算平均真实波幅

		Args:
			data: 数据DataFrame，需包含high, low, close
			period: ATR周期

		Returns:
			ATR值
		"""
		high = data["high"]
		low = data["low"]
		close = data["close"]

		return pandas_ta_classic.atr(high, low, close, length=period)

	# ==================== 成交量因子计算函数 ====================

	@staticmethod
	def calculate_volume_ratio (data: pd.DataFrame, period: int = 5) -> pd.Series:
		"""
		计算量比

		Args:
			data: 数据DataFrame
			period: 平均成交量计算周期

		Returns:
			量比值
		"""
		volume = data["volume"]

		# 当日成交量
		current_volume = volume

		# 过去period日的平均成交量
		avg_volume = volume.rolling(window=period).mean()

		# 量比 = 当日成交量 / 平均成交量
		volume_ratio = current_volume / avg_volume

		return volume_ratio

	@staticmethod
	def calculate_obv (data: pd.DataFrame) -> pd.Series:
		"""
		计算能量潮

		Args:
			data: 数据DataFrame

		Returns:
			OBV值
		"""
		close = data["close"]
		volume = data["volume"]

		return pandas_ta_classic.obv(close, volume)

	# ==================== 基本面因子计算函数 ====================

	@staticmethod
	def calculate_pe_ratio (data: pd.DataFrame) -> pd.Series:
		"""
		计算市盈率

		Args:
			data: 数据DataFrame，需包含close和eps

		Returns:
			市盈率
		"""
		if "close" not in data.columns or "eps" not in data.columns:
			raise ValueError("计算市盈率需要close和eps字段")

		# 市盈率 = 股价 / 每股收益
		pe_ratio = data["close"] / data["eps"]

		return pe_ratio

	@staticmethod
	def calculate_pb_ratio (data: pd.DataFrame) -> pd.Series:
		"""
		计算市净率

		Args:
			data: 数据DataFrame，需包含close和bvps

		Returns:
			市净率
		"""
		if "close" not in data.columns or "bvps" not in data.columns:
			raise ValueError("计算市净率需要close和bvps字段")

		# 市净率 = 股价 / 每股净资产
		pb_ratio = data["close"] / data["bvps"]

		return pb_ratio

	@staticmethod
	def calculate_roe (data: pd.DataFrame) -> pd.Series:
		"""
		计算净资产收益率

		Args:
			data: 数据DataFrame，需包含net_income和equity

		Returns:
			净资产收益率
		"""
		if "net_income" not in data.columns or "equity" not in data.columns:
			raise ValueError("计算ROE需要net_income和equity字段")

		# ROE = 净利润 / 净资产
		roe = data["net_income"] / data["equity"]

		return roe

	# ==================== 因子组合和衍生计算 ====================

	def calculate_factor_composite (
			self,
			data: pd.DataFrame,
			factor_weights: Dict[str, float],
			normalization: bool = True,
			**kwargs
	) -> pd.Series:
		"""
		计算因子组合

		Args:
			data: 原始数据
			factor_weights: 因子权重字典 {因子名: 权重}
			normalization: 是否标准化因子值
			**kwargs: 额外参数

		Returns:
			因子组合值
		"""
		# 计算各个因子
		factor_values = {}

		for factor_name, weight in factor_weights.items():
			try:
				factor_result = self.calculate_factor(data, factor_name, **kwargs)
				# 取第一个因子序列（有些因子会返回多个序列）
				factor_series = factor_result.iloc[:, 0]

				factor_values[factor_name] = factor_series
			except Exception as e:
				self.logger.warning(f"计算因子 {factor_name} 失败: {e}")
				factor_values[factor_name] = pd.Series(np.nan, index=data.index)

		# 创建DataFrame
		factor_df = pd.DataFrame(factor_values)

		# 标准化处理
		if normalization:
			factor_df = self._normalize_factors(factor_df)

		# 计算加权组合
		composite = pd.Series(0.0, index=data.index)
		total_weight = 0

		for factor_name, weight in factor_weights.items():
			if factor_name in factor_df.columns:
				composite = composite.add(factor_df[factor_name] * weight, fill_value=0)
				total_weight += abs(weight)

		if total_weight > 0:
			composite = composite / total_weight

		return composite

	@staticmethod
	def _normalize_factors (factor_df: pd.DataFrame) -> pd.DataFrame:
		"""
		标准化因子值

		Args:
			factor_df: 因子值DataFrame

		Returns:
			标准化后的因子值
		"""
		normalized_df = factor_df.copy()

		for column in normalized_df.columns:
			series = normalized_df[column]

			# 移除极端值
			if series.notna().sum() > 0:
				# Winsorization: 将极端值缩放到分位数
				q_low = series.quantile(0.01)
				q_high = series.quantile(0.99)
				series = series.clip(lower=q_low, upper=q_high)

				# Z-score标准化
				mean = series.mean()
				std = series.std()
				if std > 0:
					series = (series - mean) / std

				normalized_df[column] = series

		return normalized_df

	def calculate_factor_rank (
			self,
			data: pd.DataFrame,
			factor_name: str,
			ascending: bool = True,
			**kwargs
	) -> pd.Series:
		"""
		计算因子排名

		Args:
			data: 原始数据
			factor_name: 因子名称
			ascending: 是否升序排名
			**kwargs: 因子参数

		Returns:
			因子排名（百分位）
		"""
		# 计算因子值
		factor_values = self.calculate_factor(data, factor_name, **kwargs)

		# 取第一个因子序列（有些因子会返回多个序列）
		factor_series = factor_values.iloc[:, 0]

		# 计算百分位排名
		rank_pct = factor_series.rank(pct=True, ascending=ascending)

		return rank_pct

	def calculate_factor_correlation (
			self,
			data: pd.DataFrame,
			factor_names: List[str],
			**kwargs
	) -> pd.DataFrame:
		"""
		计算因子相关性矩阵

		Args:
			data: 原始数据
			factor_names: 因子名称列表
			**kwargs: 因子参数

		Returns:
			因子相关性矩阵
		"""
		# 计算所有因子值
		factor_values = {}

		for factor_name in factor_names:
			try:
				factor_result = self.calculate_factor(data, factor_name, **kwargs)
				# 取第一个因子序列（有些因子会返回多个序列）
				factor_series = factor_result.iloc[:, 0]

				factor_values[factor_name] = factor_series
			except Exception as e:
				self.logger.warning(f"计算因子 {factor_name} 失败: {e}")

		# 创建DataFrame并计算相关性
		if factor_values:
			factor_df = pd.DataFrame(factor_values)
			correlation_matrix = factor_df.corr()
			return correlation_matrix
		else:
			return pd.DataFrame()

	def get_factor_info (self, factor_name: str) -> Dict:
		"""
		获取因子信息

		Args:
			factor_name: 因子名称

		Returns:
			因子信息字典
		"""
		if factor_name in self.factor_configs:
			return self.factor_configs[factor_name]
		else:
			return {}

	def list_factors (self, category: Optional[FactorCategory] = None) -> List[str]:
		"""
		列出所有因子

		Args:
			category: 因子类别过滤器

		Returns:
			因子名称列表
		"""
		if category:
			return [
				name for name, config in self.factor_configs.items()
				if config["category"] == category
			]
		else:
			return list(self.factor_configs.keys())

	def register_custom_factor (
			self,
			factor_name: str,
			calculation_function: Callable,
			category: FactorCategory = FactorCategory.TECHNICAL,
			description: str = "",
			parameters: Dict = None
	) -> None:
		"""
		注册自定义因子

		Args:
			factor_name: 因子名称
			calculation_function: 计算函数
			category: 因子类别
			description: 因子描述
			parameters: 参数配置
		"""
		self.factor_configs[factor_name] = {
			"category": category,
			"description": description,
			"parameters": parameters or {},
			"function": calculation_function.__name__ if hasattr(calculation_function, '__name__') else factor_name
		}

		# 动态添加计算函数
		setattr(self, calculation_function.__name__, calculation_function)

		self.logger.info(f"注册自定义因子: {factor_name}")