#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
收益分析器

负责计算和分析各种收益指标，包括总收益、年化收益、复合收益等。
"""

from datetime import date
from typing import Dict, List, Any

import numpy as np
import pandas as pd
from scipy import stats


class ReturnAnalyzer:
	"""收益分析器"""

	def __init__ (self):
		"""初始化收益分析器"""

	def analyze_returns (
			self,
			equity_curve: List[Dict[str, Any]],
			start_date: date,
			end_date: date,
			initial_capital: float = 1.0
	) -> Dict[str, Any]:
		"""
		分析收益指标

		Args:
			equity_curve: 净值曲线数据
			start_date: 开始日期
			end_date: 结束日期
			initial_capital: 初始资金

		Returns:
			收益分析结果
		"""
		try:
			if not equity_curve or len(equity_curve) < 2:
				raise ValueError("净值曲线数据不足")

			# 转换为DataFrame
			df = pd.DataFrame(equity_curve)
			df['date'] = pd.to_datetime(df['date'])
			df.set_index('date', inplace=True)

			# 确保数据按日期排序
			df = df.sort_index()

			# 计算总收益（考虑初始资金）
			total_return = ReturnAnalyzer._calculate_total_return(df['equity'].iloc[0], df['equity'].iloc[-1]) * initial_capital

			# 计算日收益率序列
			daily_returns = df['equity'].pct_change().dropna()

			# 计算年化收益率
			annual_return = ReturnAnalyzer._calculate_annual_return(daily_returns)

			# 计算年复合增长率（CAGR）
			cagr = ReturnAnalyzer._calculate_cagr(
				df['equity'].iloc[0],
				df['equity'].iloc[-1],
				start_date,
				end_date
			)

			# 计算月度收益
			monthly_returns = ReturnAnalyzer._calculate_monthly_returns(df)

			# 计算年度收益
			annual_returns = ReturnAnalyzer._calculate_annual_returns(df)

			# 计算滚动收益
			rolling_returns = ReturnAnalyzer._calculate_rolling_returns(daily_returns)

			# 计算收益的统计特征
			return_statistics = ReturnAnalyzer._calculate_return_statistics(daily_returns)

			# 计算收益的分布特征
			return_distribution = self._analyze_return_distribution(daily_returns)

			# 计算收益的稳定性指标
			stability_metrics = self._calculate_stability_metrics(daily_returns)

			# 计算收益的周期性
			periodicity_analysis = self._analyze_periodicity(daily_returns)

			return {
				'total_return': total_return,
				'annual_return': annual_return,
				'cagr': cagr,
				'monthly_returns': monthly_returns,
				'annual_returns': annual_returns,
				'rolling_returns': rolling_returns,
				'return_statistics': return_statistics,
				'return_distribution': return_distribution,
				'stability_metrics': stability_metrics,
				'periodicity_analysis': periodicity_analysis
			}

		except Exception as e:
			raise ValueError(f"收益分析失败: {str(e)}")

	@staticmethod
	def compare_returns_with_benchmark (
			strategy_returns: pd.Series,
			benchmark_returns: pd.Series
	) -> Dict[str, Any]:
		"""
		比较策略收益与基准收益

		Args:
			strategy_returns: 策略收益率序列
			benchmark_returns: 基准收益率序列

		Returns:
			收益比较结果
		"""
		try:
			# 对齐数据
			common_dates = strategy_returns.index.intersection(benchmark_returns.index)
			if len(common_dates) < 10:
				raise ValueError("数据日期对齐失败，共同数据点不足")

			strategy_aligned = strategy_returns.loc[common_dates]
			benchmark_aligned = benchmark_returns.loc[common_dates]

			# 计算超额收益
			excess_returns = strategy_aligned - benchmark_aligned

			# 计算信息比率
			information_ratio = ReturnAnalyzer._calculate_information_ratio(excess_returns)

			# 计算跟踪误差
			tracking_error = ReturnAnalyzer._calculate_tracking_error(excess_returns)

			# 计算相对收益
			relative_performance = ReturnAnalyzer._calculate_relative_performance(
				strategy_aligned, benchmark_aligned
			)

			# 计算收益相关性
			correlation = ReturnAnalyzer._calculate_correlation(strategy_aligned, benchmark_aligned)

			# 计算Beta系数
			beta = ReturnAnalyzer._calculate_beta(strategy_aligned, benchmark_aligned)

			# 计算Alpha系数
			alpha = ReturnAnalyzer._calculate_alpha(strategy_aligned, benchmark_aligned, beta)

			# 计算R-squared
			r_squared = ReturnAnalyzer._calculate_r_squared(strategy_aligned, benchmark_aligned)

			# 计算收益差值的统计检验
			statistical_test = ReturnAnalyzer._perform_statistical_test(
				strategy_aligned, benchmark_aligned
			)

			return {
				'excess_returns': excess_returns.tolist(),
				'information_ratio': information_ratio,
				'tracking_error': tracking_error,
				'relative_performance': relative_performance,
				'correlation': correlation,
				'beta': beta,
				'alpha': alpha,
				'r_squared': r_squared,
				'statistical_test': statistical_test,
				'summary': {
					'strategy_mean': float(strategy_aligned.mean()),
					'benchmark_mean': float(benchmark_aligned.mean()),
					'strategy_std': float(strategy_aligned.std()),
					'benchmark_std': float(benchmark_aligned.std()),
					'excess_mean': float(excess_returns.mean()),
					'excess_std': float(excess_returns.std())
				}
			}

		except Exception as e:
			raise ValueError(f"收益比较失败: {str(e)}")

	@staticmethod
	def analyze_return_consistency (
			returns: pd.Series,
			window_sizes: List[int] = None
	) -> Dict[str, Any]:
		"""
		分析收益一致性

		Args:
			returns: 收益率序列
			window_sizes: 窗口大小列表

		Returns:
			收益一致性分析结果
		"""
		if window_sizes is None:
			window_sizes = [30, 60, 90, 180, 360]  # 30天、60天、90天、半年、一年

		try:
			consistency_metrics = {}

			for window in window_sizes:
				if len(returns) >= window:
					# 计算滚动窗口收益
					rolling_returns = returns.rolling(window=window).apply(
						lambda x: np.prod(1 + x) - 1, raw=False
					).dropna()

					if len(rolling_returns) > 0:
						# 计算窗口内收益的统计特征
						window_metrics = {
							'mean': float(rolling_returns.mean()),
							'std': float(rolling_returns.std()),
							'min': float(rolling_returns.min()),
							'max': float(rolling_returns.max()),
							'positive_ratio': float((rolling_returns > 0).mean()),
							'consistency_score': ReturnAnalyzer._calculate_consistency_score(rolling_returns)
						}

						consistency_metrics[f'{window}d'] = window_metrics

			# 整体一致性分析
			overall_consistency = {
				'positive_months': ReturnAnalyzer._count_positive_months(returns),
				'winning_streak': ReturnAnalyzer._calculate_winning_streak(returns),
				'losing_streak': ReturnAnalyzer._calculate_losing_streak(returns),
				'consistency_index': ReturnAnalyzer._calculate_consistency_index(returns)
			}

			return {
				'window_metrics': consistency_metrics,
				'overall_consistency': overall_consistency
			}

		except Exception as e:
			raise ValueError(f"收益一致性分析失败: {str(e)}")

	@staticmethod
	def _calculate_total_return (
			start_value: float,
			end_value: float
	) -> float:
		"""计算总收益率"""
		if start_value == 0:
			return 0.0
		return (end_value - start_value) / start_value

	@staticmethod
	def _calculate_annual_return (
			daily_returns: pd.Series
	) -> float:
		"""计算年化收益率"""
		if len(daily_returns) == 0:
			return 0.0

		# 使用几何平均计算年化收益
		cumulative_return = np.prod(1 + daily_returns.values) - 1
		trading_days = len(daily_returns)

		if trading_days == 0:
			return 0.0

		# 假设一年有252个交易日
		annual_trading_days = 252
		years = trading_days / annual_trading_days

		if years > 0:
			annual_return = (1 + cumulative_return) ** (1 / years) - 1
		else:
			annual_return = 0.0

		return annual_return

	@staticmethod
	def _calculate_cagr (
			start_value: float,
			end_value: float,
			start_date: date,
			end_date: date
	) -> float:
		"""计算年复合增长率（CAGR）"""
		if start_value == 0:
			return 0.0

		# 计算总年数
		total_days = (end_date - start_date).days
		years = total_days / 365.25

		if years > 0:
			cagr = (end_value / start_value) ** (1 / years) - 1
		else:
			cagr = 0.0

		return cagr

	@staticmethod
	def _calculate_monthly_returns (
			df: pd.DataFrame
	) -> Dict[str, float]:
		"""计算月度收益率"""
		if len(df) == 0:
			return {}

		# 重采样到月度
		monthly_equity = df['equity'].resample('ME').last()

		if len(monthly_equity) < 2:
			return {}

		# 计算月度收益率
		monthly_returns = monthly_equity.pct_change().dropna()

		# 转换为字典
		result = {}
		for idx, ret in monthly_returns.items():
			month_key = pd.Timestamp(idx).strftime('%Y-%m')
			result[month_key] = float(ret)

		return result

	@staticmethod
	def _calculate_annual_returns (
			df: pd.DataFrame
	) -> Dict[int, float]:
		"""计算年度收益率"""
		if len(df) == 0:
			return {}

		# 重采样到年度
		annual_equity = df['equity'].resample('YE').last()

		if len(annual_equity) < 2:
			return {}

		# 计算年度收益率
		annual_returns = annual_equity.pct_change().dropna()

		# 转换为字典
		result = {}
		for idx, ret in annual_returns.items():
			year = pd.Timestamp(idx).year
			result[year] = float(ret)

		return result

	@staticmethod
	def _calculate_rolling_returns (
			returns: pd.Series,
			windows: List[int] = None
	) -> Dict[str, List[float]]:
		"""计算滚动收益"""
		if windows is None:
			windows = [30, 60, 90, 180, 360]

		rolling_results = {}

		for window in windows:
			if len(returns) >= window:
				rolling_ret = returns.rolling(window=window).apply(
					lambda x: np.prod(1 + x) - 1, raw=False
				).dropna()

				rolling_results[f'{window}d'] = rolling_ret.tolist()

		return rolling_results

	@staticmethod
	def _calculate_return_statistics (
			returns: pd.Series
	) -> Dict[str, float]:
		"""计算收益统计特征"""
		if len(returns) == 0:
			return {}

		return {
			'mean': float(returns.mean()),
			'median': float(returns.median()),
			'std': float(returns.std()),
			'skewness': float(returns.skew()),
			'kurtosis': float(returns.kurtosis()),
			'min': float(returns.min()),
			'max': float(returns.max()),
			'q1': float(returns.quantile(0.25)),
			'q3': float(returns.quantile(0.75)),
			'positive_ratio': float((returns > 0).mean()),
			'negative_ratio': float((returns < 0).mean()),
			'zero_ratio': float((returns == 0).mean())
		}

	@staticmethod
	def _analyze_return_distribution (
			returns: pd.Series
	) -> Dict[str, Any]:
		"""分析收益分布"""
		if len(returns) == 0:
			return {}

		# 正态性检验
		_, normal_pvalue = stats.normaltest(returns.dropna())

		# 峰度检验
		kurtosis = float(returns.kurtosis())

		# 偏度检验
		skewness = float(returns.skew())

		# 分位数分析
		quantiles = {
			'p1': float(returns.quantile(0.01)),
			'p5': float(returns.quantile(0.05)),
			'p25': float(returns.quantile(0.25)),
			'p50': float(returns.quantile(0.50)),
			'p75': float(returns.quantile(0.75)),
			'p95': float(returns.quantile(0.95)),
			'p99': float(returns.quantile(0.99))
		}

		return {
			'is_normal': normal_pvalue > 0.05,  # 5%显著性水平
			'normal_pvalue': float(normal_pvalue),
			'kurtosis': kurtosis,
			'skewness': skewness,
			'quantiles': quantiles,
			'distribution_type': ReturnAnalyzer._identify_distribution_type(returns)
		}

	@staticmethod
	def _calculate_stability_metrics (
			returns: pd.Series
	) -> Dict[str, float]:
		"""计算收益稳定性指标"""
		if len(returns) == 0:
			return {}

		# 计算收益波动率
		volatility = returns.std() * np.sqrt(252)  # 年化波动率

		# 计算收益变异系数
		mean_return = returns.mean()
		if mean_return != 0:
			coefficient_of_variation = volatility / abs(mean_return)
		else:
			coefficient_of_variation = 0

		# 计算收益稳定性指数
		stability_index = ReturnAnalyzer._calculate_stability_index(returns)

		# 计算下行风险
		downside_risk = ReturnAnalyzer._calculate_downside_risk(returns)

		return {
			'annual_volatility': float(volatility),
			'coefficient_of_variation': float(coefficient_of_variation),
			'stability_index': float(stability_index),
			'downside_risk': float(downside_risk)
		}

	@staticmethod
	def _analyze_periodicity (
			returns: pd.Series
	) -> Dict[str, Any]:
		"""分析收益周期性"""
		if len(returns) < 50:
			return {'insufficient_data': True}

		try:
			# 使用傅里叶变换分析周期性
			from scipy import fftpack

			# 计算收益序列的FFT
			fft_values = fftpack.fft(returns.values)
			fft_freq = fftpack.fftfreq(len(returns))

			# 找出主要频率
			idx = np.argsort(np.abs(fft_values))[::-1]
			dominant_freqs = fft_freq[idx[:5]]  # 前5个主要频率
			dominant_amps = np.abs(fft_values[idx[:5]])

			# 转换为周期（交易日）
			periods = []
			for freq in dominant_freqs:
				if freq != 0:
					period = 1 / abs(freq)
					if 2 <= period <= len(returns) / 2:  # 合理的周期范围
						periods.append(period)

			# 计算自相关
			autocorr = ReturnAnalyzer._calculate_autocorrelation(returns, max_lag=50)

			return {
				'dominant_frequencies': dominant_freqs.tolist(),
				'dominant_amplitudes': dominant_amps.tolist(),
				'dominant_periods': periods,
				'autocorrelation': autocorr,
				'has_seasonality': len(periods) > 0
			}

		except ValueError as e:
			return {
				'error': str(e),
				'autocorrelation': ReturnAnalyzer._calculate_autocorrelation(returns, max_lag=20)
			}

	@staticmethod
	def _calculate_information_ratio (
			excess_returns: pd.Series
	) -> float:
		"""计算信息比率"""
		if len(excess_returns) == 0:
			return 0.0

		mean_excess = excess_returns.mean()
		std_excess = excess_returns.std()

		if std_excess == 0:
			return 0.0

		# 年化信息比率
		info_ratio = mean_excess / std_excess * np.sqrt(252)
		return float(info_ratio)

	@staticmethod
	def _calculate_tracking_error (
			excess_returns: pd.Series
	) -> float:
		"""计算跟踪误差"""
		if len(excess_returns) == 0:
			return 0.0

		# 年化跟踪误差
		tracking_error = excess_returns.std() * np.sqrt(252)
		return float(tracking_error)

	@staticmethod
	def _calculate_relative_performance (
			strategy_returns: pd.Series,
			benchmark_returns: pd.Series
	) -> Dict[str, float]:
		"""计算相对收益表现"""
		# 计算相对收益序列
		relative_returns = (1 + strategy_returns) / (1 + benchmark_returns) - 1

		return {
			'mean_relative_return': float(relative_returns.mean()),
			'median_relative_return': float(relative_returns.median()),
			'std_relative_return': float(relative_returns.std()),
			'cumulative_relative_return': float(np.prod(1 + relative_returns) - 1)
		}

	@staticmethod
	def _calculate_correlation (
			strategy_returns: pd.Series,
			benchmark_returns: pd.Series
	) -> float:
		"""计算相关性"""
		if len(strategy_returns) == 0 or len(benchmark_returns) == 0:
			return 0.0

		correlation = strategy_returns.corr(benchmark_returns)
		return float(correlation)

	@staticmethod
	def _calculate_beta (
			strategy_returns: pd.Series,
			benchmark_returns: pd.Series
	) -> float:
		"""计算Beta系数"""
		if len(strategy_returns) < 2 or len(benchmark_returns) < 2:
			return 0.0

		covariance = strategy_returns.cov(benchmark_returns)
		benchmark_variance = benchmark_returns.var()

		if benchmark_variance == 0:
			return 0.0

		beta = covariance / benchmark_variance
		return float(beta)

	@staticmethod
	def _calculate_alpha (
			strategy_returns: pd.Series,
			benchmark_returns: pd.Series,
			beta: float
	) -> float:
		"""计算Alpha系数"""
		if len(strategy_returns) == 0 or len(benchmark_returns) == 0:
			return 0.0

		# 年化Alpha
		strategy_annual = (1 + strategy_returns.mean()) ** 252 - 1
		benchmark_annual = (1 + benchmark_returns.mean()) ** 252 - 1

		alpha = strategy_annual - beta * benchmark_annual
		return float(alpha)

	@staticmethod
	def _calculate_r_squared (
			strategy_returns: pd.Series,
			benchmark_returns: pd.Series
	) -> float:
		"""计算R-squared"""
		correlation = ReturnAnalyzer._calculate_correlation(strategy_returns, benchmark_returns)
		r_squared = correlation ** 2
		return float(r_squared)

	@staticmethod
	def _perform_statistical_test (
			strategy_returns: pd.Series,
			benchmark_returns: pd.Series
	) -> Dict[str, Any]:
		"""执行统计检验"""
		if len(strategy_returns) < 2 or len(benchmark_returns) < 2:
			return {'insufficient_data': True}

		# 配对t检验（检验均值差异）
		from scipy import stats as scipy_stats

		diff = strategy_returns - benchmark_returns

		# 正态性检验
		_, normal_pvalue = scipy_stats.normaltest(diff.dropna())

		# 配对t检验
		if len(diff) >= 2:
			t_stat, p_value = scipy_stats.ttest_rel(strategy_returns, benchmark_returns)
		else:
			t_stat, p_value = 0, 1

		# Wilcoxon符号秩检验（非参数检验）
		if len(diff) >= 10:
			try:
				_, wilcoxon_pvalue = scipy_stats.wilcoxon(diff)
			except ValueError:
				wilcoxon_pvalue = 1
		else:
			wilcoxon_pvalue = 1

		return {
			't_test': {
				't_statistic': float(t_stat),
				'p_value': float(p_value),
				'significant': p_value < 0.05
			},
			'wilcoxon_test': {
				'p_value': float(wilcoxon_pvalue),
				'significant': wilcoxon_pvalue < 0.05
			},
			'normality_test': {
				'p_value': float(normal_pvalue),
				'is_normal': normal_pvalue > 0.05
			}
		}

	@staticmethod
	def _calculate_consistency_score (
			rolling_returns: pd.Series
	) -> float:
		"""计算一致性分数"""
		if len(rolling_returns) == 0:
			return 0.0

		# 正收益的比例
		positive_ratio = (rolling_returns > 0).mean()

		# 收益的稳定性（变异系数的倒数）
		mean_return = rolling_returns.mean()
		std_return = rolling_returns.std()

		if mean_return != 0 and std_return != 0:
			stability = abs(mean_return) / std_return
		else:
			stability = 0

		# 综合一致性分数
		consistency_score = 0.6 * positive_ratio + 0.4 * stability / (1 + stability)
		return float(consistency_score)

	@staticmethod
	def _count_positive_months (
			returns: pd.Series
	) -> int:
		"""计算正收益月数"""
		if len(returns) == 0:
			return 0

		# 重采样到月度
		if isinstance(returns.index, pd.DatetimeIndex):
			monthly_returns = returns.resample('ME').apply(lambda x: np.prod(1 + x) - 1)
			positive_months = (monthly_returns > 0).sum()
		else:
			positive_months = 0

		return int(positive_months)

	@staticmethod
	def _calculate_winning_streak (
			returns: pd.Series
	) -> int:
		"""计算最长连续盈利天数"""
		if len(returns) == 0:
			return 0

		winning_streak = 0
		current_streak = 0

		for ret in returns:
			if ret > 0:
				current_streak += 1
				winning_streak = max(winning_streak, current_streak)
			else:
				current_streak = 0

		return winning_streak

	@staticmethod
	def _calculate_losing_streak (
			returns: pd.Series
	) -> int:
		"""计算最长连续亏损天数"""
		if len(returns) == 0:
			return 0

		losing_streak = 0
		current_streak = 0

		for ret in returns:
			if ret < 0:
				current_streak += 1
				losing_streak = max(losing_streak, current_streak)
			else:
				current_streak = 0

		return losing_streak

	@staticmethod
	def _calculate_consistency_index (
			returns: pd.Series
	) -> float:
		"""计算一致性指数"""
		if len(returns) < 2:
			return 0.0

		# 计算收益序列的自相关性
		autocorr = returns.autocorr(lag=1)

		if pd.isna(autocorr):
			autocorr = 0

		# 正收益比例
		positive_ratio = (returns > 0).mean()

		# 收益稳定性（变异系数的倒数）
		mean_return = returns.mean()
		std_return = returns.std()

		if mean_return != 0 and std_return != 0:
			stability = abs(mean_return) / std_return
		else:
			stability = 0

		# 综合一致性指数
		consistency_index = 0.4 * (1 + autocorr) + 0.4 * positive_ratio + 0.2 * stability / (1 + stability)
		return float(consistency_index)

	@staticmethod
	def _identify_distribution_type (
			returns: pd.Series
	) -> str:
		"""识别收益分布类型"""
		if len(returns) < 50:
			return "insufficient_data"

		from scipy import stats as scipy_stats

		# 正态分布检验
		_, normal_pvalue = scipy_stats.normaltest(returns.dropna())

		# t分布拟合
		try:
			df, loc, scale = scipy_stats.t.fit(returns.dropna())
			t_likelihood = scipy_stats.t.logpdf(returns.dropna(), df, loc, scale).sum()
		except ValueError:
			t_likelihood = -np.inf

		# 正态分布似然
		normal_likelihood = scipy_stats.norm.logpdf(
			returns.dropna(),
			returns.mean(),
			returns.std()
		).sum()

		# 判断分布类型
		if normal_pvalue > 0.05:
			return "normal"
		elif t_likelihood > normal_likelihood:
			return "student_t"
		else:
			# 检查是否厚尾
			kurtosis = returns.kurtosis()
			if kurtosis > 3:
				return "fat_tailed"
			else:
				return "unknown"

	@staticmethod
	def _calculate_stability_index (
			returns: pd.Series
	) -> float:
		"""计算稳定性指数"""
		if len(returns) < 2:
			return 0.0

		# 计算滚动窗口收益的波动性
		window_size = min(30, len(returns) // 2)

		if window_size < 5:
			return 0.0

		rolling_vol = returns.rolling(window=window_size).std().dropna()

		if len(rolling_vol) == 0:
			return 0.0

		# 波动率的稳定性（变异系数的倒数）
		mean_vol = rolling_vol.mean()
		std_vol = rolling_vol.std()

		if mean_vol != 0 and std_vol != 0:
			stability = mean_vol / std_vol
		else:
			stability = 0

		return float(stability)

	@staticmethod
	def _calculate_downside_risk (
			returns: pd.Series,
			mar: float = 0.0  # 最小可接受收益
	) -> float:
		"""计算下行风险"""
		if len(returns) == 0:
			return 0.0

		# 计算低于MAR的收益
		downside_returns = returns[returns < mar]

		if len(downside_returns) == 0:
			return 0.0

		# 计算下行标准差
		downside_risk = np.sqrt(np.mean((downside_returns - mar) ** 2)) * np.sqrt(252)
		return float(downside_risk)

	@staticmethod
	def _calculate_autocorrelation (
			returns: pd.Series,
			max_lag: int = 20
	) -> Dict[int, float]:
		"""计算自相关系数"""
		autocorr = {}

		for lag in range(1, min(max_lag, len(returns)) + 1):
			try:
				corr = returns.autocorr(lag=lag)
				if not pd.isna(corr):
					autocorr[lag] = float(corr)
			except ValueError:
				pass

		return autocorr