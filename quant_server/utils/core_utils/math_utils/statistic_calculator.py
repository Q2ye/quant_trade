"""
统计计算器模块
提供基础的统计计算功能
"""

import numpy as np
import pandas as pd
from typing import Union, List, Tuple, Optional, Dict, Any
from scipy import stats
from dataclasses import dataclass
from enum import Enum


class StatisticMethod(Enum):
	"""统计方法枚举"""
	SIMPLE = "simple"
	WEIGHTED = "weighted"
	ROLLING = "rolling"
	EXPONENTIAL = "exponential"


@dataclass
class StatisticResult:
	"""统计计算结果"""
	mean: float
	std: float
	variance: float
	skewness: Optional[float] = None
	kurtosis: Optional[float] = None
	min: Optional[float] = None
	max: Optional[float] = None
	median: Optional[float] = None
	q1: Optional[float] = None
	q3: Optional[float] = None
	iqr: Optional[float] = None


class StatisticalCalculator:
	"""
	统计计算器类
	提供全面的统计计算功能
	"""

	def __init__ (self, method: StatisticMethod = StatisticMethod.SIMPLE):
		"""
		初始化统计计算器

		Args:
			method: 统计计算方法
		"""
		self.method = method

	def calculate (self, data: Union[List[float], np.ndarray, pd.Series],
	               weights: Optional[Union[List[float], np.ndarray]] = None) -> StatisticResult:
		"""
		计算基础统计量

		Args:
			data: 输入数据
			weights: 权重数据

		Returns:
			StatisticResult: 统计计算结果
		"""
		if isinstance(data, (list, pd.Series)):
			data = np.array(data)

		if weights is not None and isinstance(weights, (list, pd.Series)):
			weights = np.array(weights)

		# 基础统计量
		mean_val = self._calculate_mean(data, weights)
		std_val = self._calculate_std(data, weights, mean_val)
		var_val = self._calculate_variance(data, weights, mean_val)

		# 高阶矩
		skew_val = self._calculate_skewness(data, mean_val, std_val)
		kurt_val = self._calculate_kurtosis(data, mean_val, std_val)

		# 分位数
		min_val = np.min(data)
		max_val = np.max(data)
		median_val = np.median(data)
		q1_val = np.percentile(data, 25)
		q3_val = np.percentile(data, 75)
		iqr_val = q3_val - q1_val

		return StatisticResult(
			mean=mean_val,
			std=std_val,
			variance=var_val,
			skewness=skew_val,
			kurtosis=kurt_val,
			min=min_val,
			max=max_val,
			median=median_val,
			q1=q1_val,
			q3=q3_val,
			iqr=iqr_val
		)

	def _calculate_mean (self, data: np.ndarray,
	                     weights: Optional[np.ndarray] = None) -> float:
		"""计算均值"""
		if weights is not None:
			return np.average(data, weights=weights)
		return np.mean(data)

	def _calculate_variance (self, data: np.ndarray,
	                         weights: Optional[np.ndarray] = None,
	                         mean_val: Optional[float] = None) -> float:
		"""计算方差"""
		if mean_val is None:
			mean_val = self._calculate_mean(data, weights)

		if weights is not None:
			# 加权方差
			weighted_sq_diff = weights * (data - mean_val) ** 2
			return np.sum(weighted_sq_diff) / np.sum(weights)

		return np.var(data, ddof=1)  # 样本方差

	def _calculate_std (self, data: np.ndarray,
	                    weights: Optional[np.ndarray] = None,
	                    mean_val: Optional[float] = None) -> float:
		"""计算标准差"""
		var_val = self._calculate_variance(data, weights, mean_val)
		return np.sqrt(var_val)

	def _calculate_skewness (self, data: np.ndarray,
	                         mean_val: float, std_val: float) -> float:
		"""计算偏度"""
		if std_val == 0:
			return 0.0
		n = len(data)
		return (np.sum((data - mean_val) ** 3) / n) / (std_val ** 3)

	def _calculate_kurtosis (self, data: np.ndarray,
	                         mean_val: float, std_val: float) -> float:
		"""计算峰度"""
		if std_val == 0:
			return 0.0
		n = len(data)
		return (np.sum((data - mean_val) ** 4) / n) / (std_val ** 4) - 3

	def correlation (self, x: Union[List[float], np.ndarray, pd.Series],
	                 y: Union[List[float], np.ndarray, pd.Series],
	                 method: str = 'pearson') -> float:
		"""
		计算相关系数

		Args:
			x: 第一个序列
			y: 第二个序列
			method: 相关系数类型 ('pearson', 'spearman', 'kendall')

		Returns:
			float: 相关系数
		"""
		if isinstance(x, (list, pd.Series)):
			x = np.array(x)
		if isinstance(y, (list, pd.Series)):
			y = np.array(y)

		if len(x) != len(y):
			raise ValueError("输入序列长度必须相同")

		if method == 'pearson':
			return np.corrcoef(x, y)[0, 1]
		elif method == 'spearman':
			return stats.spearmanr(x, y)[0]
		elif method == 'kendall':
			return stats.kendalltau(x, y)[0]
		else:
			raise ValueError(f"不支持的相关系数类型: {method}")

	def covariance (self, x: Union[List[float], np.ndarray, pd.Series],
	                y: Union[List[float], np.ndarray, pd.Series]) -> float:
		"""
		计算协方差

		Args:
			x: 第一个序列
			y: 第二个序列

		Returns:
			float: 协方差
		"""
		if isinstance(x, (list, pd.Series)):
			x = np.array(x)
		if isinstance(y, (list, pd.Series)):
			y = np.array(y)

		if len(x) != len(y):
			raise ValueError("输入序列长度必须相同")

		return np.cov(x, y, ddof=1)[0, 1]

	def percentile (self, data: Union[List[float], np.ndarray, pd.Series],
	                p: float) -> float:
		"""
		计算百分位数

		Args:
			data: 输入数据
			p: 百分位数 (0-100)

		Returns:
			float: 百分位数
		"""
		if isinstance(data, (list, pd.Series)):
			data = np.array(data)

		return np.percentile(data, p)

	def rolling_statistics (self, data: Union[List[float], np.ndarray, pd.Series],
	                        window: int,
	                        statistic: str = 'mean') -> np.ndarray:
		"""
		计算滚动统计量

		Args:
			data: 输入数据
			window: 滚动窗口大小
			statistic: 统计量类型 ('mean', 'std', 'var', 'min', 'max', 'median')

		Returns:
			np.ndarray: 滚动统计量序列
		"""
		if isinstance(data, (list, pd.Series)):
			data = np.array(data)

		n = len(data)
		result = np.full(n, np.nan)

		if statistic == 'mean':
			for i in range(window - 1, n):
				result[i] = np.mean(data[i - window + 1:i + 1])
		elif statistic == 'std':
			for i in range(window - 1, n):
				result[i] = np.std(data[i - window + 1:i + 1], ddof=1)
		elif statistic == 'var':
			for i in range(window - 1, n):
				result[i] = np.var(data[i - window + 1:i + 1], ddof=1)
		elif statistic == 'min':
			for i in range(window - 1, n):
				result[i] = np.min(data[i - window + 1:i + 1])
		elif statistic == 'max':
			for i in range(window - 1, n):
				result[i] = np.max(data[i - window + 1:i + 1])
		elif statistic == 'median':
			for i in range(window - 1, n):
				result[i] = np.median(data[i - window + 1:i + 1])
		else:
			raise ValueError(f"不支持的统计量类型: {statistic}")

		return result

	def zscore (self, data: Union[List[float], np.ndarray, pd.Series]) -> np.ndarray:
		"""
		计算Z分数（标准化）

		Args:
			data: 输入数据

		Returns:
			np.ndarray: Z分数序列
		"""
		if isinstance(data, (list, pd.Series)):
			data = np.array(data)

		mean_val = np.mean(data)
		std_val = np.std(data, ddof=1)

		if std_val == 0:
			return np.zeros_like(data)

		return (data - mean_val) / std_val

	def winsorize (self, data: Union[List[float], np.ndarray, pd.Series],
	               limits: Tuple[float, float] = (0.05, 0.05)) -> np.ndarray:
		"""
		Winsorize处理（截尾处理）

		Args:
			data: 输入数据
			limits: 上下截尾比例 (lower, upper)

		Returns:
			np.ndarray: 处理后的数据
		"""
		if isinstance(data, (list, pd.Series)):
			data = np.array(data)

		lower_limit = np.percentile(data, limits[0] * 100)
		upper_limit = np.percentile(data, (1 - limits[1]) * 100)

		data_winsorized = data.copy()
		data_winsorized[data < lower_limit] = lower_limit
		data_winsorized[data > upper_limit] = upper_limit

		return data_winsorized

	def normalize (self, data: Union[List[float], np.ndarray, pd.Series],
	               method: str = 'minmax') -> np.ndarray:
		"""
		数据标准化

		Args:
			data: 输入数据
			method: 标准化方法 ('minmax', 'zscore', 'robust')

		Returns:
			np.ndarray: 标准化后的数据
		"""
		if isinstance(data, (list, pd.Series)):
			data = np.array(data)

		if method == 'minmax':
			min_val = np.min(data)
			max_val = np.max(data)
			if max_val == min_val:
				return np.zeros_like(data)
			return (data - min_val) / (max_val - min_val)

		elif method == 'zscore':
			return self.zscore(data)

		elif method == 'robust':
			median_val = np.median(data)
			iqr_val = np.percentile(data, 75) - np.percentile(data, 25)
			if iqr_val == 0:
				return np.zeros_like(data)
			return (data - median_val) / iqr_val

		else:
			raise ValueError(f"不支持的标准化方法: {method}")

	def t_statistic (self, data: Union[List[float], np.ndarray, pd.Series],
	                 hypothesized_mean: float = 0) -> Tuple[float, float]:
		"""
		计算t统计量和p值

		Args:
			data: 输入数据
			hypothesized_mean: 假设的均值

		Returns:
			Tuple[float, float]: (t统计量, p值)
		"""
		if isinstance(data, (list, pd.Series)):
			data = np.array(data)

		n = len(data)
		if n < 2:
			raise ValueError("数据长度必须至少为2")

		sample_mean = np.mean(data)
		sample_std = np.std(data, ddof=1)

		if sample_std == 0:
			t_stat = 0
		else:
			t_stat = (sample_mean - hypothesized_mean) / (sample_std / np.sqrt(n))

		p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=n - 1))

		return t_stat, p_val

	def confidence_interval (self, data: Union[List[float], np.ndarray, pd.Series],
	                         confidence: float = 0.95) -> Tuple[float, float]:
		"""
		计算置信区间

		Args:
			data: 输入数据
			confidence: 置信水平 (0-1)

		Returns:
			Tuple[float, float]: 置信区间 (下限, 上限)
		"""
		if isinstance(data, (list, pd.Series)):
			data = np.array(data)

		n = len(data)
		if n < 2:
			raise ValueError("数据长度必须至少为2")

		mean_val = np.mean(data)
		std_val = np.std(data, ddof=1)
		se = std_val / np.sqrt(n)

		# t分布的临界值
		t_critical = stats.t.ppf((1 + confidence) / 2, df=n - 1)

		lower = mean_val - t_critical * se
		upper = mean_val + t_critical * se

		return lower, upper


# 便捷函数
def mean (data: Union[List[float], np.ndarray, pd.Series]) -> float:
	"""计算均值"""
	return StatisticalCalculator()._calculate_mean(np.array(data) if isinstance(data, list) else data)


def std (data: Union[List[float], np.ndarray, pd.Series]) -> float:
	"""计算标准差"""
	return StatisticalCalculator()._calculate_std(np.array(data) if isinstance(data, list) else data)


def variance (data: Union[List[float], np.ndarray, pd.Series]) -> float:
	"""计算方差"""
	return StatisticalCalculator()._calculate_variance(np.array(data) if isinstance(data, list) else data)


def skewness (data: Union[List[float], np.ndarray, pd.Series]) -> float:
	"""计算偏度"""
	if isinstance(data, (list, pd.Series)):
		data = np.array(data)
	mean_val = mean(data)
	std_val = std(data)
	return StatisticalCalculator()._calculate_skewness(data, mean_val, std_val)


def kurtosis (data: Union[List[float], np.ndarray, pd.Series]) -> float:
	"""计算峰度"""
	if isinstance(data, (list, pd.Series)):
		data = np.array(data)
	mean_val = mean(data)
	std_val = std(data)
	return StatisticalCalculator()._calculate_kurtosis(data, mean_val, std_val)


def correlation (x: Union[List[float], np.ndarray, pd.Series],
                 y: Union[List[float], np.ndarray, pd.Series],
                 method: str = 'pearson') -> float:
	"""计算相关系数"""
	return StatisticalCalculator().correlation(x, y, method)


def covariance (x: Union[List[float], np.ndarray, pd.Series],
                y: Union[List[float], np.ndarray, pd.Series]) -> float:
	"""计算协方差"""
	return StatisticalCalculator().covariance(x, y)


def percentile (data: Union[List[float], np.ndarray, pd.Series],
                p: float) -> float:
	"""计算百分位数"""
	return StatisticalCalculator().percentile(data, p)


def rolling_mean (data: Union[List[float], np.ndarray, pd.Series],
                  window: int) -> np.ndarray:
	"""计算滚动均值"""
	return StatisticalCalculator().rolling_statistics(data, window, 'mean')


def rolling_std (data: Union[List[float], np.ndarray, pd.Series],
                 window: int) -> np.ndarray:
	"""计算滚动标准差"""
	return StatisticalCalculator().rolling_statistics(data, window, 'std')


def rolling_correlation (x: Union[List[float], np.ndarray, pd.Series],
                         y: Union[List[float], np.ndarray, pd.Series],
                         window: int) -> np.ndarray:
	"""计算滚动相关系数"""
	if isinstance(x, (list, pd.Series)):
		x = np.array(x)
	if isinstance(y, (list, pd.Series)):
		y = np.array(y)

	n = len(x)
	if len(y) != n:
		raise ValueError("输入序列长度必须相同")

	result = np.full(n, np.nan)
	for i in range(window - 1, n):
		result[i] = correlation(x[i - window + 1:i + 1], y[i - window + 1:i + 1])

	return result


def zscore (data: Union[List[float], np.ndarray, pd.Series]) -> np.ndarray:
	"""计算Z分数"""
	return StatisticalCalculator().zscore(data)


def winsorize (data: Union[List[float], np.ndarray, pd.Series],
               limits: Tuple[float, float] = (0.05, 0.05)) -> np.ndarray:
	"""Winsorize处理"""
	return StatisticalCalculator().winsorize(data, limits)


def normalize (data: Union[List[float], np.ndarray, pd.Series],
               method: str = 'minmax') -> np.ndarray:
	"""数据标准化"""
	return StatisticalCalculator().normalize(data, method)


def t_statistic (data: Union[List[float], np.ndarray, pd.Series],
                 hypothesized_mean: float = 0) -> Tuple[float, float]:
	"""计算t统计量和p值"""
	return StatisticalCalculator().t_statistic(data, hypothesized_mean)


def p_value (data: Union[List[float], np.ndarray, pd.Series],
             hypothesized_mean: float = 0) -> float:
	"""计算p值"""
	return StatisticalCalculator().t_statistic(data, hypothesized_mean)[1]


def confidence_interval (data: Union[List[float], np.ndarray, pd.Series],
                         confidence: float = 0.95) -> Tuple[float, float]:
	"""计算置信区间"""
	return StatisticalCalculator().confidence_interval(data, confidence)