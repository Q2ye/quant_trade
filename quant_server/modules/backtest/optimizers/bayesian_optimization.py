# -*- coding: utf-8 -*-
"""
贝叶斯优化器

负责使用贝叶斯优化方法优化策略参数
"""
import logging
from typing import Dict, List, Any, Callable, Tuple

import numpy as np
from scipy.stats import norm

logger = logging.getLogger(__name__)


class BayesianOptimization:
	"""
	贝叶斯优化器

	使用贝叶斯优化方法优化策略参数
	"""

	def __init__ (self, n_iter: int = 50, acquisition_function: str = "ucb"):
		"""
		初始化贝叶斯优化器

		Args:
			n_iter: 迭代次数
			acquisition_function:  Acquisition函数 (ucb/ei/poi)
		"""
		self.n_iter = n_iter
		self.acquisition_function = acquisition_function
		self.samples = []
		self.scores = []

	async def optimize (self, objective: Callable, parameters: Dict[str, List[Any]]) -> Tuple[Dict[str, Any], float]:
		"""
		执行贝叶斯优化

		Args:
			objective: 目标函数
			parameters: 参数范围 {param_name: [values]}

		Returns:
			(最佳参数, 最佳得分)
		"""
		try:
			logger.info(f"开始贝叶斯优化，迭代次数: {self.n_iter}")

			# 初始化样本
			await self._initialize_samples(parameters, objective)

			best_params = None
			best_score = -float('inf')

			# 迭代优化
			for i in range(self.n_iter):
				# 构建代理模型
				model = self._build_model()

				# 选择下一个样本点
				next_params = self._select_next_point(parameters, model)

				# 评估目标函数
				score = await objective(**next_params)

				# 更新样本
				self.samples.append(next_params)
				self.scores.append(score)

				# 更新最佳参数
				if score > best_score:
					best_score = score
					best_params = next_params
					logger.info(f"第 {i} 次迭代找到更优参数: {best_params}, 得分: {best_score}")

				logger.info(f"贝叶斯优化进度: {i + 1}/{self.n_iter}")

			logger.info(f"贝叶斯优化完成，最佳参数: {best_params}, 最佳得分: {best_score}")

			return best_params, best_score
		except Exception as e:
			logger.error(f"贝叶斯优化失败: {str(e)}")
			raise

	async def _initialize_samples (self, parameters: Dict[str, List[Any]], objective: Callable):
		"""
		初始化样本

		Args:
			parameters: 参数范围
			objective: 目标函数
		"""
		# 随机初始化3个样本
		param_names = list(parameters.keys())
		for _ in range(3):
			sample = {}
			for param_name in param_names:
				sample[param_name] = np.random.choice(parameters[param_name])

			score = await objective(**sample)
			self.samples.append(sample)
			self.scores.append(score)

	def _build_model (self):
		"""
		构建代理模型

		Returns:
			代理模型
		"""

		# 这里使用简单的线性模型作为代理模型
		# 实际应用中可以使用高斯过程等更复杂的模型
		class SimpleModel:
			def __init__ (self, scores):
				self.scores = scores

			def predict (self):
				# 简单的均值预测
				return np.mean(self.scores), np.std(self.scores)

		model = SimpleModel(self.scores)
		return model

	def _select_next_point (self, parameters: Dict[str, List[Any]], model: Any) -> Dict[str, Any]:
		"""
		选择下一个样本点

		Args:
			parameters: 参数范围
			model: 代理模型

		Returns:
			下一个样本点
		"""
		param_names = list(parameters.keys())
		best_score = -float('inf')
		best_params = None

		# 随机采样100个点，选择acquisition function值最大的点
		for _ in range(100):
			candidate = {}
			for param_name in param_names:
				candidate[param_name] = np.random.choice(parameters[param_name])

			# 计算acquisition function值
			acq_value = self._calculate_acquisition(candidate, model)

			if acq_value > best_score:
				best_score = acq_value
				best_params = candidate

		return best_params

	def _calculate_acquisition (self, params: Dict[str, Any], model: Any) -> float:
		"""
		计算acquisition function值

		Args:
			params: 参数
			model: 代理模型

		Returns:
			acquisition function值
		"""
		mean, std = model.predict(params)

		if self.acquisition_function == "ucb":
			# Upper Confidence Bound
			kappa = 2.576  # 99% confidence interval
			return mean + kappa * std
		elif self.acquisition_function == "ei":
			# Expected Improvement
			best_y = max(self.scores)
			if std == 0:
				return 0
			z = (mean - best_y) / std
			return (mean - best_y) * norm.cdf(z) + std * norm.pdf(z)
		elif self.acquisition_function == "poi":
			# Probability of Improvement
			best_y = max(self.scores)
			if std == 0:
				return 0
			z = (mean - best_y) / std
			return norm.cdf(z)
		else:
			raise ValueError(f"不支持的acquisition function: {self.acquisition_function}")
