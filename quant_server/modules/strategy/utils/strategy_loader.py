# -*- coding: utf-8 -*-
"""
策略加载器
负责加载和管理策略类，支持从不同来源加载策略
"""

import importlib
import importlib.util
import logging
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Type

from quant_server.modules.strategy.constants import StrategyType
from quant_server.modules.strategy.strategies.base.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


@dataclass
class StrategyInfo:
	"""策略信息"""
	name: str
	strategy_type: StrategyType
	class_name: str
	module_path: str
	file_path: Optional[str] = None
	description: str = ""
	parameters: Dict[str, Any] = None

	def __post_init__ (self):
		if self.parameters is None:
			self.parameters = {}


class StrategyLoader:
	"""
	策略加载器

	负责加载和管理策略类，支持：
	- 从文件系统加载策略
	- 从模块路径加载策略
	- 动态加载策略类
	- 策略类的缓存管理
	- 策略的依赖管理
	"""

	def __init__ (self):
		"""初始化策略加载器"""
		self._strategy_cache: Dict[str, Type[BaseStrategy]] = {}
		self._strategy_info_cache: Dict[str, StrategyInfo] = {}
		self._search_paths: List[str] = []

		# 预定义的策略路径
		self._predefined_paths = {
			'technical': {
				'MACrossStrategy': 'quant_server.modules.strategy.strategies.technical.ma_cross_strategy',
				'MACDStrategy': 'quant_server.modules.strategy.strategies.technical.macd_strategy'
			},
			'alpha': {
				'FactorStrategy': 'quant_server.modules.strategy.strategies.alpha.factor_strategy',
				'MeanReversionStrategy': 'quant_server.modules.strategy.strategies.alpha.mean_reversion_strategy'
			},
			'ai': {
				'MLStrategy': 'quant_server.modules.strategy.strategies.ai.ml_strategy',
				'DLStrategy': 'quant_server.modules.strategy.strategies.ai.dl_strategy'
			}
		}

		logger.info("策略加载器初始化完成")

	def add_search_path (self, path: str) -> None:
		"""
		添加策略搜索路径

		Args:
			path: 搜索路径
		"""
		if path not in self._search_paths:
			self._search_paths.append(path)
			logger.info(f"添加策略搜索路径: {path}")

	def load_strategy (self, strategy_name: str, strategy_type: Optional[StrategyType] = None) -> Optional[
		Type[BaseStrategy]]:
		"""
		加载策略类

		Args:
			strategy_name: 策略名称
			strategy_type: 策略类型（可选）

		Returns:
			策略类或None
		"""
		try:
			# 检查缓存
			if strategy_name in self._strategy_cache:
				logger.info(f"从缓存加载策略: {strategy_name}")
				return self._strategy_cache[strategy_name]

			# 尝试从预定义路径加载
			strategy_class = self._load_from_predefined(strategy_name, strategy_type)
			if strategy_class:
				self._strategy_cache[strategy_name] = strategy_class
				return strategy_class

			# 尝试从搜索路径加载
			strategy_class = self._load_from_search_paths(strategy_name)
			if strategy_class:
				self._strategy_cache[strategy_name] = strategy_class
				return strategy_class

			# 尝试动态加载
			strategy_class = self._load_dynamic(strategy_name)
			if strategy_class:
				self._strategy_cache[strategy_name] = strategy_class
				return strategy_class

			logger.warning(f"策略加载失败: {strategy_name}")
			return None

		except Exception as e:
			logger.error(f"加载策略时发生错误: {e}")
			return None

	def _load_from_predefined (self, strategy_name: str, strategy_type: Optional[StrategyType] = None) -> Optional[
		Type[BaseStrategy]]:
		"""
		从预定义路径加载策略

		Args:
			strategy_name: 策略名称
			strategy_type: 策略类型

		Returns:
			策略类或None
		"""
		try:
			# 如果指定了策略类型，从对应类型的预定义路径加载
			if strategy_type:
				type_key = strategy_type.value
				if type_key in self._predefined_paths:
					if strategy_name in self._predefined_paths[type_key]:
						module_path = self._predefined_paths[type_key][strategy_name]
						return self._load_from_module(module_path, strategy_name)
			else:
				# 遍历所有预定义路径
				for type_key, strategies in self._predefined_paths.items():
					if strategy_name in strategies:
						module_path = strategies[strategy_name]
						return self._load_from_module(module_path, strategy_name)

			return None

		except Exception as e:
			logger.error(f"从预定义路径加载策略失败: {e}")
			return None

	@staticmethod
	def _load_from_module (module_path: str, class_name: str) -> Optional[Type[BaseStrategy]]:
		"""
		从模块路径加载策略

		Args:
			module_path: 模块路径
			class_name: 类名

		Returns:
			策略类或None
		"""
		try:
			logger.info(f"从模块加载策略: {module_path}.{class_name}")

			# 导入模块
			module = importlib.import_module(module_path)

			# 获取类
			strategy_class = getattr(module, class_name, None)

			if strategy_class and issubclass(strategy_class, BaseStrategy):
				return strategy_class

			logger.warning(f"模块 {module_path} 中未找到策略类 {class_name}")
			return None

		except Exception as e:
			logger.error(f"从模块加载策略失败: {e}")
			return None

	def _load_from_search_paths (self, strategy_name: str) -> Optional[Type[BaseStrategy]]:
		"""
		从搜索路径加载策略

		Args:
			strategy_name: 策略名称

		Returns:
			策略类或None
		"""
		try:
			for search_path in self._search_paths:
				if not os.path.exists(search_path):
					continue

				# 遍历搜索路径
				for root, dirs, files in os.walk(search_path):
					for file in files:
						if file.endswith('.py') and not file.startswith('__'):
							file_path = os.path.join(root, file)
							module_name = self._get_module_name(file_path, search_path)

							# 尝试加载模块
							try:
								spec = importlib.util.spec_from_file_location(module_name, file_path)
								if spec and spec.loader:
									module = importlib.util.module_from_spec(spec)
									sys.modules[module_name] = module
									spec.loader.exec_module(module)

									# 检查模块中是否有指定的策略类
									if hasattr(module, strategy_name):
										strategy_class = getattr(module, strategy_name)
										if issubclass(strategy_class, BaseStrategy):
											logger.info(f"从搜索路径加载策略: {file_path}")
											return strategy_class
							except Exception as e:
								logger.debug(f"加载文件 {file_path} 失败: {e}")

			return None

		except Exception as e:
			logger.error(f"从搜索路径加载策略失败: {e}")
			return None


	@staticmethod
	def _get_module_name ( file_path: str, search_path: str) -> str:
		"""
		获取模块名称

		Args:
			file_path: 文件路径
			search_path: 搜索路径

		Returns:
			模块名称
		"""
		relative_path = os.path.relpath(file_path, search_path)
		module_name = relative_path.replace(os.path.sep, '.').rstrip('.py')
		return module_name

	def _load_dynamic (self, strategy_name: str) -> Optional[Type[BaseStrategy]]:
		"""
		动态加载策略

		Args:
			strategy_name: 策略名称

		Returns:
			策略类或None
		"""
		try:
			# 尝试直接导入策略名称
			if '.' in strategy_name:
				# 包含模块路径的策略名称
				parts = strategy_name.split('.')
				class_name = parts[-1]
				module_path = '.'.join(parts[:-1])
				return self._load_from_module(module_path, class_name)

			return None

		except Exception as e:
			logger.error(f"动态加载策略失败: {e}")
			return None

	def get_strategy_info (self, strategy_name: str) -> Optional[StrategyInfo]:
		"""
		获取策略信息

		Args:
			strategy_name: 策略名称

		Returns:
			策略信息或None
		"""
		try:
			if strategy_name in self._strategy_info_cache:
				return self._strategy_info_cache[strategy_name]

			# 尝试从预定义路径获取信息
			for type_key, strategies in self._predefined_paths.items():
				if strategy_name in strategies:
					module_path = strategies[strategy_name]
					strategy_type = StrategyType(type_key)

					info = StrategyInfo(
						name=strategy_name,
						strategy_type=strategy_type,
						class_name=strategy_name,
						module_path=module_path
					)

					self._strategy_info_cache[strategy_name] = info
					return info

			return None

		except Exception as e:
			logger.error(f"获取策略信息失败: {e}")
			return None

	def list_available_strategies (self) -> List[StrategyInfo]:
		"""
		列出所有可用的策略

		Returns:
			策略信息列表
		"""
		strategies = []

		try:
			# 从预定义路径获取策略
			for type_key, strategy_map in self._predefined_paths.items():
				strategy_type = StrategyType(type_key)
				for strategy_name, module_path in strategy_map.items():
					info = StrategyInfo(
						name=strategy_name,
						strategy_type=strategy_type,
						class_name=strategy_name,
						module_path=module_path
					)
					strategies.append(info)

			# 从搜索路径获取策略
			for search_path in self._search_paths:
				if not os.path.exists(search_path):
					continue

				for root, dirs, files in os.walk(search_path):
					for file in files:
						if file.endswith('.py') and not file.startswith('__'):
							file_path = os.path.join(root, file)
							module_name = self._get_module_name(file_path, search_path)

							try:
								spec = importlib.util.spec_from_file_location(module_name, file_path)
								if spec and spec.loader:
									module = importlib.util.module_from_spec(spec)
									sys.modules[module_name] = module
									spec.loader.exec_module(module)

									# 检查模块中的策略类
									for name, obj in module.__dict__.items():
										if isinstance(obj, type) and issubclass(obj,
										                                        BaseStrategy) and obj != BaseStrategy:
											info = StrategyInfo(
												name=name,
												strategy_type=StrategyType.CUSTOM,
												class_name=name,
												module_path=module_name,
												file_path=file_path
											)
											strategies.append(info)
							except Exception as e:
								logger.debug(f"加载文件 {file_path} 失败: {e}")

			logger.info(f"找到 {len(strategies)} 个可用策略")
			return strategies

		except Exception as e:
			logger.error(f"列出可用策略失败: {e}")
			return []

	def create_strategy_instance (self, strategy_name: str, strategy_type: Optional[StrategyType] = None,
	                              parameters: Optional[Dict[str, Any]] = None) -> Optional[BaseStrategy]:
		"""
		创建策略实例

		Args:
			strategy_name: 策略名称
			strategy_type: 策略类型
			parameters: 策略参数

		Returns:
			策略实例或None
		"""
		try:
			# 加载策略类
			strategy_class = self.load_strategy(strategy_name, strategy_type)
			if not strategy_class:
				return None

			# 创建策略实例
			if parameters is None:
				parameters = {}

			strategy_instance = strategy_class(
				name=strategy_name,
				strategy_type=strategy_type if strategy_type is not None else StrategyType.CUSTOM,

				parameters=parameters
			)

			logger.info(f"创建策略实例: {strategy_name}")
			return strategy_instance

		except Exception as e:
			logger.error(f"创建策略实例失败: {e}")
			return None

	def clear_cache (self) -> None:
		"""
		清除缓存
		"""
		self._strategy_cache.clear()
		self._strategy_info_cache.clear()
		logger.info("策略加载器缓存已清除")

	def get_strategy_cache (self) -> Dict[str, Type[BaseStrategy]]:
		"""
		获取策略缓存

		Returns:
			策略缓存
		"""
		return self._strategy_cache


# 全局策略加载器实例
strategy_loader = StrategyLoader()


def get_strategy_loader () -> StrategyLoader:
	"""
	获取策略加载器实例

	Returns:
		策略加载器实例
	"""
	return strategy_loader