#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
因子归因分析器

负责执行因子模型归因分析，将超额收益分解为因子暴露贡献。
"""

from datetime import date
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
import pandas as pd


class FactorAttribution:
	"""因子归因分析器"""

	def __init__ (self):
		"""初始化因子归因分析器"""

	def perform_factor_attribution (
			self,
			portfolio_returns: pd.Series,
			factor_returns: pd.DataFrame,
			factor_model: str = 'Fama-French',
			estimation_method: str = 'ols'
	) -> Dict[str, Any]:
		"""
		执行因子归因分析

		Args:
			portfolio_returns: 组合收益率序列
			factor_returns: 因子收益率DataFrame
			factor_model: 因子模型 ('Fama-French', 'Carhart', 'Custom')
			estimation_method: 估计方法 ('ols', 'wls', 'ridge')

		Returns:
			因子归因结果
		"""
		try:
			# 对齐数据
			common_dates = portfolio_returns.index.intersection(factor_returns.index)
			if len(common_dates) < 20:
				raise ValueError(f"数据对齐失败，共同数据点不足: {len(common_dates)}")

			portfolio_aligned = portfolio_returns.loc[common_dates]
			factor_aligned = factor_returns.loc[common_dates]

			# 估计因子暴露
			factor_exposures, regression_stats = self._estimate_factor_exposures(
				portfolio_aligned, factor_aligned, estimation_method
			)

			# 计算因子贡献
			factor_contributions = self._calculate_factor_contributions(
				factor_exposures, factor_aligned
			)

			# 计算特异性收益
			specific_return = self._calculate_specific_return(
				portfolio_aligned, factor_aligned, factor_exposures
			)

			# 计算归因质量指标
			quality_metrics = self._calculate_attribution_quality(
				portfolio_aligned, factor_aligned, factor_exposures
			)

			# 构建结果
			result = {
				'factor_exposures': factor_exposures,
				'factor_contributions': factor_contributions,
				'total_factor_contribution': sum(factor_contributions.values()),
				'specific_return': specific_return,
				'portfolio_return': float(portfolio_aligned.mean() * 252),  # 年化
				'regression_statistics': regression_stats,
				'quality_metrics': quality_metrics,
				'factor_model': factor_model,
				'estimation_method': estimation_method,
				'num_observations': len(common_dates),
				'analysis_date': date.today().isoformat()
			}

			# 验证归因
			self._validate_attribution(result, portfolio_aligned)

			return result

		except Exception as e:
			raise ValueError(f"因子归因分析失败: {str(e)}")

	def perform_multifactor_attribution (
			self,
			portfolio_returns: pd.Series,
			factor_returns_dict: Dict[str, pd.DataFrame],
			factor_models: List[str] = None
	) -> Dict[str, Dict[str, Any]]:
		"""
		执行多因子模型归因比较

		Args:
			portfolio_returns: 组合收益率序列
			factor_returns_dict: 因子收益率字典 {模型名: DataFrame}
			factor_models: 因子模型列表

		Returns:
			多因子模型归因结果比较
		"""
		try:
			if factor_models is None:
				factor_models = list(factor_returns_dict.keys())

			attribution_results = {}

			for model_name in factor_models:
				if model_name not in factor_returns_dict:
					print(f"警告: 模型 {model_name} 的因子数据不存在")
					continue

				try:
					factor_returns = factor_returns_dict[model_name]

					# 执行因子归因
					result = self.perform_factor_attribution(
						portfolio_returns, factor_returns, model_name
					)

					attribution_results[model_name] = result

				except Exception as e:
					print(f"模型 {model_name} 归因失败: {str(e)}")
					continue

			# 比较 不同模型的结果
			if len(attribution_results) > 1:
				comparison = self._compare_factor_models(attribution_results)
				attribution_results['comparison'] = comparison

			return attribution_results

		except Exception as e:
			raise ValueError(f"多因子模型归因比较失败: {str(e)}")

	def perform_rolling_factor_attribution (
			self,
			portfolio_returns: pd.Series,
			factor_returns: pd.DataFrame,
			window: int = 252,
			step: int = 22
	) -> Dict[str, Any]:
		"""
		执行滚动窗口因子归因

		Args:
			portfolio_returns: 组合收益率序列
			factor_returns: 因子收益率DataFrame
			window: 滚动窗口大小（交易日）
			step: 滚动步长

		Returns:
			滚动因子归因结果
		"""
		try:
			# 对齐数据
			common_dates = portfolio_returns.index.intersection(factor_returns.index)
			if len(common_dates) < window:
				raise ValueError(f"数据不足，至少需要 {window} 个数据点")

			portfolio_aligned = portfolio_returns.loc[common_dates]
			factor_aligned = factor_returns.loc[common_dates]

			# 初始化结果存储
			rolling_exposures = {}
			rolling_contributions = {}
			rolling_stats = {}

			# 执行滚动回归
			for i in range(0, len(common_dates) - window + 1, step):
				end_idx = i + window
				window_dates = common_dates[i:end_idx]

				# 提取窗口数据
				portfolio_window = portfolio_aligned.loc[window_dates]
				factor_window = factor_aligned.loc[window_dates]
				# 存储结果
				date_key = pd.Timestamp(window_dates[-1]).strftime('%Y-%m-%d')
				# 执行因子归因
				try:
					result = self.perform_factor_attribution(
						portfolio_window, factor_window, 'Rolling'
					)
					rolling_exposures[date_key] = result['factor_exposures']
					rolling_contributions[date_key] = result['factor_contributions']
					rolling_stats[date_key] = {
						'r_squared': result['regression_statistics']['r_squared'],
						'specific_return': result['specific_return']
					}

				except Exception as e:
					print(f"窗口 {date_key} 归因失败: {str(e)}")
					continue

			return {
				'rolling_exposures': rolling_exposures,
				'rolling_contributions': rolling_contributions,
				'rolling_statistics': rolling_stats,
				'window_size': window,
				'step_size': step,
				'num_windows': len(rolling_exposures)
			}

		except Exception as e:
			raise ValueError(f"滚动因子归因失败: {str(e)}")

	def perform_barra_style_attribution (
			self,
			portfolio_returns: pd.Series,
			factor_returns: pd.DataFrame,
			specific_risk: Optional[pd.Series] = None,
			benchmark_returns: Optional[pd.Series] = None
	) -> Dict[str, Any]:
		"""
		执行Barra风格因子归因

		Args:
			portfolio_returns: 组合收益率序列
			factor_returns: 因子收益率DataFrame
			specific_risk: 特异性风险序列（可选）
			benchmark_returns: 基准收益率序列（可选）

		Returns:
			Barra风格因子归因结果
		"""
		try:
			# 对齐数据
			common_dates = portfolio_returns.index.intersection(factor_returns.index)
			if len(common_dates) < 50:
				raise ValueError("数据不足")

			portfolio_aligned = portfolio_returns.loc[common_dates]
			factor_aligned = factor_returns.loc[common_dates]

			# 如果有基准数据，计算主动收益
			if benchmark_returns is not None:
				benchmark_aligned = benchmark_returns.loc[common_dates]
				active_returns = portfolio_aligned - benchmark_aligned
				returns_to_analyze = active_returns
				analysis_type = 'active'
			else:
				returns_to_analyze = portfolio_aligned
				analysis_type = 'total'

			# 估计因子暴露（使用加权最小二 乘法）
			factor_exposures, regression_stats = self._estimate_factor_exposures_wls(
				returns_to_analyze, factor_aligned, specific_risk
			)

			# 计算因子贡献
			factor_contributions = self._calculate_factor_contributions(
				factor_exposures, factor_aligned
			)

			# 计算风险贡献
			risk_contributions = self._calculate_risk_contributions(
				factor_exposures, factor_aligned, specific_risk
			)

			# 计算归因质量
			quality_metrics = self._calculate_barra_quality_metrics(
				returns_to_analyze, factor_aligned, factor_exposures, specific_risk
			)

			return {
				'factor_exposures': factor_exposures,
				'factor_contributions': factor_contributions,
				'risk_contributions': risk_contributions,
				'total_factor_contribution': sum(factor_contributions.values()),
				'regression_statistics': regression_stats,
				'quality_metrics': quality_metrics,
				'analysis_type': analysis_type,
				'model_type': 'Barra',
				'num_factors': len(factor_exposures)
			}

		except Exception as e:
			raise ValueError(f"Barra风格因子归因失败: {str(e)}")

	def _estimate_factor_exposures (
			self,
			portfolio_returns: pd.Series,
			factor_returns: pd.DataFrame,
			method: str = 'ols'
	) -> Tuple[Dict[str, float], Dict[str, float]]:
		"""估计因子暴露"""
		try:
			X = factor_returns.values
			y = portfolio_returns.values

			# 添加截距项
			X_with_intercept = np.column_stack([np.ones(len(X)), X])
			factor_names = ['Alpha'] + factor_returns.columns.tolist()

			if method == 'ols':
				# 普通最小二 乘法
				beta = np.linalg.lstsq(X_with_intercept, y, rcond=None)[0]

			elif method == 'ridge':
				# 岭回归
				from sklearn.linear_model import Ridge
				model = Ridge(alpha=0.1)
				model.fit(X, y)
				beta = np.concatenate([[model.intercept_], model.coef_])

			elif method == 'wls':
				# 加权最小二 乘法
				weights = 1.0 / np.var(y)  # 简化权重
				W = np.diag(weights)
				beta = np.linalg.inv(X_with_intercept.T @ W @ X_with_intercept) @ X_with_intercept.T @ W @ y

			else:
				raise ValueError(f"不支持的估计方法: {method}")

			# 计算回归统计量
			y_pred = X_with_intercept @ beta
			residuals = y - y_pred

			# R-squared
			ss_total = float(np.sum((y - np.mean(y)) ** 2))
			ss_residual = float(np.sum(residuals ** 2))
			r_squared = 1.0 - ss_residual / ss_total if ss_total > 0.0 else 0.0

			# 调整R-squared
			n = len(y)
			p = len(beta) - 1  # 减去截距
			adj_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - p - 1) if n > p + 1 else r_squared

			# 因子暴露字典
			exposures = {factor_names[i]: float(beta[i]) for i in range(len(factor_names))}

			# 回归统计
			stats = {
				'r_squared': float(r_squared),
				'adj_r_squared': float(adj_r_squared),
				'residual_std': float(np.std(residuals)),
				'f_statistic': self._calculate_f_statistic(r_squared, n, p),
				'durbin_watson': self._calculate_durbin_watson(residuals)
			}

			return exposures, stats

		except Exception as e:
			raise ValueError(f"因子暴露估计失败: {str(e)}")

	@staticmethod
	def _estimate_factor_exposures_wls (
			portfolio_returns: pd.Series,
			factor_returns: pd.DataFrame,
			specific_risk: Optional[pd.Series] = None
	) -> Tuple[Dict[str, float], Dict[str, float]]:
		"""使用加权最小 二 乘法估计因子暴露"""
		try:
			X = factor_returns.values
			y = portfolio_returns.values

			# 特异性风险作为权重
			if specific_risk is not None:
				# 对齐特异性风险
				specific_aligned = specific_risk.loc[portfolio_returns.index]
				weights = 1.0 / (specific_aligned.values ** 2 + 1e-6)
			else:
				# 使用残差方差作为权重估计
				weights = np.ones(len(y))

			# 添加截距项
			X_with_intercept = np.column_stack([np.ones(len(X)), X])
			factor_names = ['Alpha'] + factor_returns.columns.tolist()

			# 加权最小二乘
			W = np.diag(weights)
			beta = np.linalg.inv(X_with_intercept.T @ W @ X_with_intercept) @ X_with_intercept.T @ W @ y

			# 计算回归统计量
			y_pred = X_with_intercept @ beta
			residuals = y - y_pred

			# R-squared
			ss_total = float(np.sum(weights * (y - np.mean(y)) ** 2))
			ss_residual = float(np.sum(weights * residuals ** 2))
			r_squared = 1.0 - ss_residual / ss_total if ss_total > 0.0 else 0.0

			# 因子暴露字典
			exposures = {factor_names[i]: float(beta[i]) for i in range(len(factor_names))}

			# 回归统计
			stats = {
				'r_squared': float(r_squared),
				'residual_std': float(np.std(residuals)),
				'weighted_residual_std': float(np.sqrt(np.mean(weights * residuals ** 2)))
			}

			return exposures, stats

		except Exception as e:
			raise ValueError(f"加权最小二乘估计失败: {str(e)}")


	@staticmethod
	def _calculate_factor_contributions (
			factor_exposures: Dict[str, float],
			factor_returns: pd.DataFrame
	) -> Dict[str, float]:
		"""计算因子贡献"""
		contributions = {}

		for factor, exposure in factor_exposures.items():
			if factor == 'Alpha':
				# Alpha是截距项
				contributions[factor] = float(exposure)
			elif factor in factor_returns.columns:
				# 因子贡献 = 暴露 * 因子收益率均值
				factor_return_mean = factor_returns[factor].mean()
				contributions[factor] = float(exposure * factor_return_mean)

		return contributions

	@staticmethod
	def _calculate_specific_return (
			portfolio_returns: pd.Series,
			factor_returns: pd.DataFrame,
			factor_exposures: Dict[str, float]
	) -> float:
		"""计算特异性收益"""
		# 计算因子模型预测收益
		predicted_returns = pd.Series(0.0, index=portfolio_returns.index)

		for factor, exposure in factor_exposures.items():
			if factor == 'Alpha':
				predicted_returns += exposure
			elif factor in factor_returns.columns:
				predicted_returns += exposure * factor_returns[factor]

		# 特异性收益 = 实际收益 - 预测收益
		specific_returns = portfolio_returns - predicted_returns
		specific_return_mean = specific_returns.mean()

		return float(specific_return_mean)

	def _calculate_attribution_quality (
			self,
			portfolio_returns: pd.Series,
			factor_returns: pd.DataFrame,
			factor_exposures: Dict[str, float]
	) -> Dict[str, float]:
		"""计算归因质量指标"""
		# 计算预测收益
		predicted_returns = pd.Series(0.0, index=portfolio_returns.index)

		for factor, exposure in factor_exposures.items():
			if factor == 'Alpha':
				predicted_returns += exposure
			elif factor in factor_returns.columns:
				predicted_returns += exposure * factor_returns[factor]

		# 计算残差
		residuals = portfolio_returns - predicted_returns

		# 计算各种质量指标
		quality = {
			'correlation': float(portfolio_returns.corr(predicted_returns)),
			'r_squared': float(portfolio_returns.corr(predicted_returns) ** 2),
			'mean_absolute_error': float(np.mean(np.abs(residuals))),
			'root_mean_squared_error': float(np.sqrt(np.mean(residuals ** 2))),
			'information_coefficient': self._calculate_information_coefficient(portfolio_returns, predicted_returns),
			'tracking_error_explained': self._calculate_tracking_error_explained(portfolio_returns, predicted_returns)
		}

		return quality

	@staticmethod
	def _calculate_risk_contributions (
			factor_exposures: Dict[str, float],
			factor_returns: pd.DataFrame,
			specific_risk: Optional[pd.Series] = None
	) -> Dict[str, float]:
		"""计算风险贡献"""
		risk_contributions = {}

		# 计算因子协方差矩阵
		factor_cov = factor_returns.cov()

		# 总风险方差
		total_variance = 0.0

		# 因子风险贡献
		for i, factor1 in enumerate(factor_returns.columns):
			factor1_name = str(factor1)
			exposure1 = float(factor_exposures.get(factor1_name, 0.0))

			for j, factor2 in enumerate(factor_returns.columns):
				factor2_name = str(factor2)
				exposure2 = float(factor_exposures.get(factor2_name, 0.0))
				covariance = float(factor_cov.iloc[i, j])

				total_variance += exposure1 * exposure2 * covariance

		# 特异性风险贡献
		if specific_risk is not None:
			specific_variance = np.mean(specific_risk ** 2)
			total_variance += specific_variance
			risk_contributions['Specific'] = float(specific_variance / total_variance if total_variance > 0 else 0)

		# 计算各因子风险贡献比例
		for factor in factor_returns.columns:
			exposure = factor_exposures.get(factor, 0.0)
			factor_variance_contribution = 0.0

			for other_factor in factor_returns.columns:
				other_exposure = factor_exposures.get(other_factor, 0.0)
				covariance = factor_returns[factor].cov(factor_returns[other_factor])
				factor_variance_contribution += exposure * other_exposure * covariance

			risk_contributions[factor] = float(
				factor_variance_contribution / total_variance if total_variance > 0 else 0)

		return risk_contributions

	def _calculate_barra_quality_metrics (
			self,
			portfolio_returns: pd.Series,
			factor_returns: pd.DataFrame,
			factor_exposures: Dict[str, float],
			specific_risk: Optional[pd.Series] = None
	) -> Dict[str, float]:
		"""计算Barra风格质量指标"""
		# 计算预测收益
		predicted_returns = pd.Series(0.0, index=portfolio_returns.index)

		for factor, exposure in factor_exposures.items():
			if factor == 'Alpha':
				predicted_returns += exposure
			elif factor in factor_returns.columns:
				predicted_returns += exposure * factor_returns[factor]

		# 计算残差
		residuals = portfolio_returns - predicted_returns

		# 计算特异性风险一致性指标（使用输入的specific_risk参数）
		specific_risk_consistency = 0.0
		if specific_risk is not None:
			residual_std = float(residuals.std())
			input_specific_std = float(specific_risk.std())
			if input_specific_std > 0.0:
				specific_risk_consistency = float(min(residual_std / input_specific_std, input_specific_std / residual_std))

		# Barra质量指标
		quality = {
			't_stat_alpha': self._calculate_t_statistic(factor_exposures.get('Alpha', 0.0), residuals.std()),
			't_stat_factors': self._calculate_factor_t_statistics(factor_exposures, factor_returns),
			'specific_risk_ratio': self._calculate_specific_risk_ratio(residuals, portfolio_returns),
			'specific_risk_consistency': specific_risk_consistency,
			'factor_stability': self._calculate_factor_stability(factor_exposures),
			'model_reliability': self._calculate_model_reliability(portfolio_returns, predicted_returns)
		}

		return quality

	@staticmethod
	def _validate_attribution (
			attribution_result: Dict[str, Any],
			portfolio_returns: pd.Series
	):
		"""验证归因结果"""
		# 计算实际平均收益
		actual_mean_return = portfolio_returns.mean()

		# 计算归因解释的收益
		explained_return = attribution_result['total_factor_contribution'] + attribution_result['specific_return']

		# 计算归因误差
		attribution_error = actual_mean_return - explained_return

		# 检查误差是否在可接受范围内
		error_tolerance = 1e-6

		if abs(attribution_error) > error_tolerance:
			print(f"警告: 归因误差较大: {attribution_error:.6f}")

		# 添加误差到结果
		attribution_result['attribution_error'] = float(attribution_error)
		attribution_result['attribution_accuracy'] = float(
			1 - abs(attribution_error) / (abs(actual_mean_return) + 1e-6))

	@staticmethod
	def _calculate_f_statistic (
			r_squared: float,
			n: int,
			p: int
	) -> float:
		"""计算F统计量"""
		if r_squared == 1 or n <= p + 1:
			return 0.0

		f_stat = (r_squared / p) / ((1 - r_squared) / (n - p - 1))
		return float(f_stat)

	@staticmethod
	def _calculate_durbin_watson (
			residuals: np.ndarray
	) -> float:
		"""计算Durbin-Watson统计量"""
		if len(residuals) < 2:
			return 2.0  # 无自相关的默认值

		diff = np.diff(residuals)
		dw = float(np.sum(diff ** 2)) / float(np.sum(residuals ** 2))
		return float(dw)

	@staticmethod
	def _calculate_information_coefficient (
			actual: pd.Series,
			predicted: pd.Series
	) -> float:
		"""计算信息系数（IC）"""
		if len(actual) < 2 or len(predicted) < 2:
			return 0.0

		ic = actual.corr(predicted)
		return float(ic)

	@staticmethod
	def _calculate_tracking_error_explained (
			actual: pd.Series,
			predicted: pd.Series
	) -> float:
		"""计算跟踪误差解释度"""
		if len(actual) < 2:
			return 0.0

		tracking_error = actual.std()
		residual_error = (actual - predicted).std()

		if tracking_error == 0:
			return 0.0

		explained = 1 - (residual_error / tracking_error) ** 2
		return float(max(0.0, explained))

	@staticmethod
	def _calculate_t_statistic (
			coefficient: float,
			std_error: float
	) -> float:
		"""计算t统计量"""
		if std_error == 0:
			return 0.0

		t_stat = coefficient / std_error
		return float(t_stat)

	def _calculate_factor_t_statistics (
			self,
			factor_exposures: Dict[str, float],
			factor_returns: pd.DataFrame
	) -> Dict[str, float]:
		"""计算因子t统计量"""
		t_stats = {}

		for factor, exposure in factor_exposures.items():
			if factor == 'Alpha':
				continue

			if factor in factor_returns.columns:
				# 简化估计标准误
				std_error = factor_returns[factor].std() / np.sqrt(len(factor_returns))
				t_stat = self._calculate_t_statistic(exposure, std_error)
				t_stats[factor] = t_stat

		return t_stats

	@staticmethod
	def _calculate_specific_risk_ratio (
			residuals: pd.Series,
			portfolio_returns: pd.Series
	) -> float:
		"""计算特异性风险比率"""
		if len(portfolio_returns) == 0:
			return 0.0

		total_risk = portfolio_returns.std()
		specific_risk = residuals.std()

		if total_risk == 0:
			return 0.0

		ratio = specific_risk / total_risk
		return float(ratio)

	@staticmethod
	def _calculate_factor_stability (
			factor_exposures: Dict[str, float]
	) -> float:
		"""计算因子稳定性"""
		# 简化实现：检查因子暴露的符号一致性
		# 实际应用中可能需要滚动窗口分析

		exposures = [exp for factor, exp in factor_exposures.items() if factor != 'Alpha']

		if len(exposures) == 0:
			return 0.0

		# 计算暴露的变异系数
		mean_exp = np.mean(np.abs(exposures))
		std_exp = np.std(exposures)

		if mean_exp == 0:
			return 0.0

		stability = 1.0 - (std_exp / mean_exp)
		return float(max(0.0, stability))

	@staticmethod
	def _calculate_model_reliability (
			actual: pd.Series,
			predicted: pd.Series
	) -> float:
		"""计算模型可靠性"""
		# 使用R-squared和残差自相关的组合
		r_squared = actual.corr(predicted) ** 2

		# 计算残差自相关
		residuals = actual - predicted
		if len(residuals) > 1:
			residual_autocorr = residuals.autocorr(lag=1)
			if pd.isna(residual_autocorr):
				residual_autocorr = 0
		else:
			residual_autocorr = 0

		# 可靠性得分
		reliability = r_squared * (1 - abs(residual_autocorr))
		return float(reliability)

	@staticmethod
	def _compare_factor_models (
			attribution_results: Dict[str, Dict[str, Any]]
	) -> Dict[str, Any]:
		"""比较 不同因子模型的结果"""
		comparison = {
			'models': list(attribution_results.keys()),
			'comparison_metrics': {},
			'best_model': None
		}

		# 收集各模型的指标
		metrics_by_model = {}

		for model_name, result in attribution_results.items():
			metrics = {
				'r_squared': result['regression_statistics']['r_squared'],
				'adj_r_squared': result['regression_statistics'].get('adj_r_squared', 0),
				'residual_std': result['regression_statistics']['residual_std'],
				'attribution_accuracy': result.get('attribution_accuracy', 0)
			}
			metrics_by_model[model_name] = metrics

		# 找出最佳模型（根据R-squared）
		if metrics_by_model:
			best_model = max(metrics_by_model.keys(),
			                 key=lambda m: metrics_by_model[m]['r_squared'])
			comparison['best_model'] = best_model

		comparison['metrics_by_model'] = metrics_by_model

		return comparison

	@staticmethod
	def create_factor_attribution_report (
			attribution_result: Dict[str, Any],
			portfolio_name: str = "组合"
	) -> Dict[str, Any]:
		"""
		创建因子归因报告

		Args:
			attribution_result: 因子归因结果
			portfolio_name: 组合名称

		Returns:
			格式化后的因子归因报告
		"""
		try:
			report = {
				'portfolio_name': portfolio_name,
				'analysis_date': attribution_result.get('analysis_date', date.today().isoformat()),
				'factor_model': attribution_result.get('factor_model', 'Unknown'),
				'summary': {
					'portfolio_return': attribution_result.get('portfolio_return', 0.0),
					'total_factor_contribution': attribution_result.get('total_factor_contribution', 0.0),
					'specific_return': attribution_result.get('specific_return', 0.0),
					'attribution_error': attribution_result.get('attribution_error', 0.0),
					'attribution_accuracy': attribution_result.get('attribution_accuracy', 0.0)
				},
				'factor_exposures': attribution_result.get('factor_exposures', {}),
				'factor_contributions': attribution_result.get('factor_contributions', {}),
				'regression_statistics': attribution_result.get('regression_statistics', {}),
				'quality_metrics': attribution_result.get('quality_metrics', {}),
				'model_metadata': {
					'estimation_method': attribution_result.get('estimation_method', 'ols'),
					'num_observations': attribution_result.get('num_observations', 0),
					'num_factors': len(attribution_result.get('factor_exposures', {})) - 1  # 减去Alpha
				}
			}

			# 计算贡献百分比
			total_contribution = attribution_result.get('total_factor_contribution', 0.0)
			if total_contribution != 0:
				contribution_percentages = {}
				for factor, contribution in attribution_result.get('factor_contributions', {}).items():
					contribution_percentages[factor] = contribution / total_contribution * 100
				report['contribution_percentages'] = contribution_percentages

			return report

		except Exception as e:
			raise ValueError(f"创建因子归因报告失败: {str(e)}")