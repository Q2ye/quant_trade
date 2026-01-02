"""
策略模式实现

定义一系列算法，将它们封装起来，并使它们可以相互替换。
策略模式让算法的变化独立于使用算法的客户端。

在量化交易系统中的典型应用：
1. 不同的指标计算算法
2. 多种风险控制规则
3. 多种订单执行算法
4. 不同的成本计算方式
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
from decimal import Decimal
from enum import Enum


class Strategy(ABC):
	"""
	策略接口

	所有具体策略必须实现此接口。
	"""

	@abstractmethod
	def execute (self, data: Any, context: Dict[str, Any]) -> Any:
		"""
		执行策略

		Args:
			data: 输入数据
			context: 执行上下文

		Returns:
			Any: 策略执行结果
		"""
		pass

	@abstractmethod
	def get_strategy_name (self) -> str:
		"""获取策略名称"""
		pass

	@abstractmethod
	def validate_parameters (self, parameters: Dict[str, Any]) -> bool:
		"""验证策略参数"""
		pass


class Context:
	"""
	策略上下文

	维护对策略对象的引用，并可以动态切换策略。
	"""

	def __init__ (self, strategy: Optional[Strategy] = None):
		"""
		初始化上下文

		Args:
			strategy: 初始策略
		"""
		self._strategy = strategy
		self._context_data: Dict[str, Any] = {}

	def set_strategy (self, strategy: Strategy) -> None:
		"""设置策略"""
		self._strategy = strategy

	def get_strategy (self) -> Optional[Strategy]:
		"""获取当前策略"""
		return self._strategy

	def set_context_data (self, key: str, value: Any) -> None:
		"""设置上下文数据"""
		self._context_data[key] = value

	def get_context_data (self, key: str, default: Any = None) -> Any:
		"""获取上下文数据"""
		return self._context_data.get(key, default)

	def execute_strategy (self, data: Any) -> Any:
		"""
		执行当前策略

		Args:
			data: 输入数据

		Returns:
			Any: 策略执行结果

		Raises:
			ValueError: 如果未设置策略
		"""
		if not self._strategy:
			raise ValueError("未设置策略")

		return self._strategy.execute(data, self._context_data)

	def switch_strategy (self, strategy: Strategy) -> None:
		"""切换策略并返回原策略"""
		old_strategy = self._strategy
		self._strategy = strategy
		return old_strategy


class StrategyRegistry:
	"""
	策略注册器

	管理可用策略的注册和发现。
	"""

	def __init__ (self):
		self._strategies: Dict[str, Type[Strategy]] = {}
		self._strategy_instances: Dict[str, Strategy] = {}

	def register_strategy (self, strategy_name: str, strategy_class: Type[Strategy]) -> None:
		"""注册策略类"""
		self._strategies[strategy_name] = strategy_class

	def create_strategy (self, strategy_name: str, parameters: Dict[str, Any]) -> Strategy:
		"""创建策略实例"""
		if strategy_name not in self._strategies:
			raise ValueError(f"策略未注册: {strategy_name}")

		strategy_class = self._strategies[strategy_name]
		strategy = strategy_class()

		if not strategy.validate_parameters(parameters):
			raise ValueError(f"策略参数验证失败: {strategy_name}")

		# 缓存策略实例（如果需要）
		cache_key = f"{strategy_name}_{hash(frozenset(parameters.items()))}"
		if cache_key not in self._strategy_instances:
			self._strategy_instances[cache_key] = strategy

		return strategy

	def get_available_strategies (self) -> List[str]:
		"""获取可用策略列表"""
		return list(self._strategies.keys())

	def get_strategy_info (self, strategy_name: str) -> Dict[str, Any]:
		"""获取策略信息"""
		if strategy_name not in self._strategies:
			return {}

		strategy_class = self._strategies[strategy_name]
		strategy = strategy_class()

		return {
			"name": strategy.get_strategy_name(),
			"class": strategy_class.__name__,
			"module": strategy_class.__module__
		}


class CompositeStrategy(Strategy):
	"""
	组合策略

	将多个策略组合成一个策略。
	"""

	def __init__ (self, strategies: List[Strategy], combination_rule: str = "sequential"):
		"""
		初始化组合策略

		Args:
			strategies: 策略列表
			combination_rule: 组合规则（sequential, parallel, weighted）
		"""
		self._strategies = strategies
		self._combination_rule = combination_rule
		self._weights = []  # 用于加权组合

	def get_strategy_name (self) -> str:
		"""获取策略名称"""
		names = [s.get_strategy_name() for s in self._strategies]
		return f"CompositeStrategy[{','.join(names)}]"

	def validate_parameters (self, parameters: Dict[str, Any]) -> bool:
		"""验证所有子策略的参数"""
		for strategy in self._strategies:
			if not strategy.validate_parameters(parameters):
				return False
		return True

	def execute (self, data: Any, context: Dict[str, Any]) -> Any:
		"""执行组合策略"""
		if self._combination_rule == "sequential":
			return self._execute_sequential(data, context)
		elif self._combination_rule == "parallel":
			return self._execute_parallel(data, context)
		elif self._combination_rule == "weighted":
			return self._execute_weighted(data, context)
		else:
			raise ValueError(f"不支持的组合规则: {self._combination_rule}")

	def _execute_sequential (self, data: Any, context: Dict[str, Any]) -> Any:
		"""顺序执行策略"""
		result = data
		for strategy in self._strategies:
			result = strategy.execute(result, context)
		return result

	def _execute_parallel (self, data: Any, context: Dict[str, Any]) -> Any:
		"""并行执行策略"""
		results = []
		for strategy in self._strategies:
			result = strategy.execute(data, context)
			results.append(result)
		return results

	def _execute_weighted (self, data: Any, context: Dict[str, Any]) -> Any:
		"""加权执行策略"""
		if not self._weights or len(self._weights) != len(self._strategies):
			# 如果没有设置权重，使用等权重
			self._weights = [1.0 / len(self._strategies)] * len(self._strategies)

		weighted_results = []
		for strategy, weight in zip(self._strategies, self._weights):
			result = strategy.execute(data, context)
			if isinstance(result, (int, float, Decimal)):
				weighted_results.append(result * weight)
			else:
				weighted_results.append(result)

		return weighted_results