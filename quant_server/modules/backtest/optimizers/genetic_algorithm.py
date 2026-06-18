# -*- coding: utf-8 -*-
"""
遗传算法优化器

负责使用遗传算法优化策略参数
"""
import logging
import random
from typing import Dict, List, Any, Callable, Tuple

logger = logging.getLogger(__name__)


class GeneticAlgorithm:
	"""
	遗传算法优化器

	使用遗传算法优化策略参数
	"""

	def __init__ (self, population_size: int = 50, generations: int = 100, mutation_rate: float = 0.1,
	              crossover_rate: float = 0.8):
		"""
		初始化遗传算法优化器

		Args:
			population_size: 种群大小
			generations: 迭代代数
			mutation_rate: 变异率
			crossover_rate: 交叉率
		"""
		self.population_size = population_size
		self.generations = generations
		self.mutation_rate = mutation_rate
		self.crossover_rate = crossover_rate

	async def optimize (self, objective: Callable, parameters: Dict[str, List[Any]]) -> Tuple[Dict[str, Any], float]:
		"""
		执行遗传算法优化

		Args:
			objective: 目标函数
			parameters: 参数范围 {param_name: [values]}

		Returns:
			(最佳参数, 最佳得分)
		"""
		try:
			logger.info(f"开始遗传算法优化，种群大小: {self.population_size}, 迭代代数: {self.generations}")

			# 规范化参数：标量值包装为单元素列表
			normalized = {
				k: v if isinstance(v, (list, tuple)) else [v]
				for k, v in parameters.items()
			}

			# 初始化种群
			population = self._initialize_population(normalized)

			best_params = None
			best_score = -float('inf')

			# 迭代进化
			for generation in range(self.generations):
				# 计算适应度
				fitness_scores = []
				for individual in population:
					score = await objective(**individual)
					fitness_scores.append(score)

					# 更新最佳参数
					if score > best_score:
						best_score = score
						best_params = individual
						logger.info(f"第 {generation} 代找到更优参数: {best_params}, 得分: {best_score}")

				# 选择
				selected = self._select(population, fitness_scores)

				# 交叉
				offspring = self._crossover(selected, normalized)

				# 变异
				population = self._mutate(offspring, normalized)

				logger.info(f"第 {generation} 代进化完成")

			logger.info(f"遗传算法完成，最佳参数: {best_params}, 最佳得分: {best_score}")

			return best_params, best_score
		except Exception as e:
			logger.error(f"遗传算法优化失败: {str(e)}")
			raise

	def _initialize_population (self, parameters: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
		"""
		初始化种群

		Args:
			parameters: 参数范围

		Returns:
			初始种群
		"""
		population = []
		param_names = list(parameters.keys())

		for _ in range(self.population_size):
			individual = {}
			for param_name in param_names:
				# 随机选择参数值
				individual[param_name] = random.choice(parameters[param_name])
			population.append(individual)

		return population

	@staticmethod
	def _select (population: List[Dict[str, Any]], fitness_scores: List[float]) -> List[Dict[str, Any]]:
		"""
		选择操作

		Args:
			population: 种群
			fitness_scores: 适应度得分

		Returns:
			选择后的种群
		"""
		# 使用轮盘赌选择
		total_fitness = float(sum(max(0.0, score) for score in fitness_scores))
		if total_fitness == 0:
			# 如果所有得分都是负数，随机选择
			return random.choices(population, k=len(population))

		probabilities = [float(max(0.0, score) / total_fitness) for score in fitness_scores]
		selected = random.choices(population, weights=probabilities, k=len(population))

		return selected

	def _crossover (self, population: List[Dict[str, Any]], parameters: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
		"""
		交叉操作

		Args:
			population: 种群
			parameters: 参数范围

		Returns:
			交叉后的种群
		"""
		offspring = []
		param_names = list(parameters.keys())

		for i in range(0, len(population), 2):
			parent1 = population[i]
			parent2 = population[i + 1] if i + 1 < len(population) else population[0]

			if random.random() < self.crossover_rate:
				# 单点交叉
				crossover_point = random.randint(1, len(param_names) - 1)
				child1 = {**parent1}
				child2 = {**parent2}

				for j in range(crossover_point, len(param_names)):
					child1[param_names[j]] = parent2[param_names[j]]
					child2[param_names[j]] = parent1[param_names[j]]

				offspring.extend([child1, child2])
			else:
				# 不交叉，直接复制
				offspring.extend([parent1, parent2])

		return offspring[:len(population)]

	def _mutate (self, population: List[Dict[str, Any]], parameters: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
		"""
		变异操作

		Args:
			population: 种群
			parameters: 参数范围

		Returns:
			变异后的种群
		"""
		param_names = list(parameters.keys())

		for individual in population:
			for param_name in param_names:
				if random.random() < self.mutation_rate:
					# 随机变异为其他值
					current_value = individual[param_name]
					possible_values = [v for v in parameters[param_name] if v != current_value]
					if possible_values:
						individual[param_name] = random.choice(possible_values)

		return population