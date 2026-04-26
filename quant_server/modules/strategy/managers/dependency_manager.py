# -*- coding: utf-8 -*-
"""
策略依赖管理器
管理策略间的依赖关系和数据依赖
"""
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Set, Optional

logger = logging.getLogger(__name__)


class DependencyType(str, Enum):
	"""依赖类型"""
	# 策略依赖：策略A依赖策略B的结果
	STRATEGY = "strategy"

	# 数据依赖：策略依赖特定数据
	DATA = "data"

	# 信号依赖：策略依赖其他策略的信号
	SIGNAL = "signal"

	# 资源依赖：策略依赖特定资源
	RESOURCE = "resource"


class DependencyState(str, Enum):
	"""依赖状态"""
	PENDING = "pending"
	RESOLVED = "resolved"
	FAILED = "failed"
	CIRCULAR = "circular"


class Dependency:
	"""依赖项"""

	def __init__ (
			self,
			source_strategy_id: str,
			target_strategy_id: Optional[str] = None,
			dependency_type: DependencyType = DependencyType.STRATEGY,
			resource_key: Optional[str] = None,
	):
		self.source_strategy_id = source_strategy_id
		self.target_strategy_id = target_strategy_id
		self.dependency_type = dependency_type
		self.resource_key = resource_key
		self.state = DependencyState.PENDING
		self.resolved_at: Optional[datetime] = None


class DependencyManager:
	"""
	策略依赖管理器

	负责：
	- 策略间依赖关系管理
	- 依赖解析和排序
	- 循环依赖检测
	- 依赖状态跟踪
	"""

	def __init__ (self):
		"""初始化依赖管理器"""
		# 依赖图 {strategy_id: {dependent_strategy_id: Dependency}}
		self._dependency_graph: Dict[str, Dict[str, Dependency]] = {}

		# 逆向依赖图 {strategy_id: {dependency_strategy_id}}
		self._reverse_graph: Dict[str, Set[str]] = {}

		# 策略加载顺序
		self._load_order: List[str] = []

	def add_dependency (
			self,
			source_strategy_id: str,
			target_strategy_id: str,
			dependency_type: DependencyType = DependencyType.STRATEGY,
			resource_key: Optional[str] = None,
	) -> None:
		"""
		添加依赖关系

		Args:
			source_strategy_id: 源策略ID（依赖者）
			target_strategy_id: 目标策略ID（被依赖者）
			dependency_type: 依赖类型
			resource_key: 资源键
		"""
		# 初始化策略节点
		if source_strategy_id not in self._dependency_graph:
			self._dependency_graph[source_strategy_id] = {}
		if target_strategy_id not in self._reverse_graph:
			self._reverse_graph[target_strategy_id] = set()

		# 创建依赖
		dependency = Dependency(
			source_strategy_id=source_strategy_id,
			target_strategy_id=target_strategy_id,
			dependency_type=dependency_type,
			resource_key=resource_key,
		)

		self._dependency_graph[source_strategy_id][target_strategy_id] = dependency
		self._reverse_graph[target_strategy_id].add(source_strategy_id)

		logger.info(
			f"添加依赖: 策略 {source_strategy_id} -> "
			f"策略 {target_strategy_id} ({dependency_type.value})"
		)

	def remove_dependency (
			self,
			source_strategy_id: str,
			target_strategy_id: str,
	) -> None:
		"""
		移除依赖关系

		Args:
			source_strategy_id: 源策略ID
			target_strategy_id: 目标策略ID
		"""
		if source_strategy_id in self._dependency_graph:
			if target_strategy_id in self._dependency_graph[source_strategy_id]:
				del self._dependency_graph[source_strategy_id][target_strategy_id]

		if target_strategy_id in self._reverse_graph:
			self._reverse_graph[target_strategy_id].discard(source_strategy_id)

		logger.info(f"移除依赖: 策略 {source_strategy_id} -> {target_strategy_id}")

	def get_dependencies (
			self,
			strategy_id: str,
	) -> List[Dependency]:
		"""
		获取策略的所有依赖

		Args:
			strategy_id: 策略ID

		Returns:
			依赖列表
		"""
		return list(self._dependency_graph.get(strategy_id, {}).values())

	def get_dependents (
			self,
			strategy_id: str,
	) -> List[str]:
		"""
		获取依赖该策略的所有策略

		Args:
			strategy_id: 策略ID

		Returns:
			策略ID列表
		"""
		return list(self._reverse_graph.get(strategy_id, set()))

	def resolve_load_order (self) -> List[str]:
		"""
		解析策略加载顺序（拓扑排序）

		Returns:
			策略ID列表（按加载顺序）

		Raises:
			ValueError: 存在循环依赖
		"""
		# 检测循环依赖
		if self._has_circular_dependency():
			raise ValueError("存在循环依赖，无法解析加载顺序")

		# 拓扑排序
		in_degree = self._calculate_in_degree()
		queue = [sid for sid, degree in in_degree.items() if degree == 0]
		load_order = []

		while queue:
			# 选择一个入度为0的节点
			current = queue.pop(0)
			load_order.append(current)

			# 减少相邻节点的入度
			for dependent in self._reverse_graph.get(current, set()):
				in_degree[dependent] -= 1
				if in_degree[dependent] == 0:
					queue.append(dependent)

		self._load_order = load_order
		return load_order

	def can_start_strategy (
			self,
			strategy_id: str,
			running_strategies: Set[str],
	) -> tuple:
		"""
		检查策略是否可以启动

		Args:
			strategy_id: 策略ID
			running_strategies: 当前运行中的策略ID集合

		Returns:
			(是否可以启动, 错误信息)
		"""
		dependencies = self.get_dependencies(strategy_id)

		for dep in dependencies:
			if dep.dependency_type == DependencyType.STRATEGY:
				target_id = dep.target_strategy_id
				if target_id and target_id not in running_strategies:
					return False, f"依赖的策略 {target_id} 未运行"

		return True, ""

	def get_startup_requirements (
			self,
			strategy_id: str,
	) -> List[str]:
		"""
		获取策略启动所需的前置策略

		Args:
			strategy_id: 策略ID

		Returns:
			需要先启动的策略ID列表
		"""
		requirements = []
		dependencies = self.get_dependencies(strategy_id)

		for dep in dependencies:
			if dep.dependency_type == DependencyType.STRATEGY:
				if dep.target_strategy_id:
					requirements.append(dep.target_strategy_id)

		return requirements

	def _calculate_in_degree (self) -> Dict[str, int]:
		"""
		计算每个节点的入度

		Returns:
			入度字典
		"""
		in_degree = {}

		# 初始化所有策略的入度
		all_strategies = set(self._dependency_graph.keys())
		all_strategies.update(self._reverse_graph.keys())

		for strategy_id in all_strategies:
			in_degree[strategy_id] = len(
				self._dependency_graph.get(strategy_id, {})
			)

		return in_degree

	def _has_circular_dependency (self) -> bool:
		"""
		检测是否存在循环依赖

		Returns:
			是否存在循环依赖
		"""
		visited = set()
		rec_stack = set()

		def visit (sid: str) -> bool:
			visited.add(sid)
			rec_stack.add(sid)

			# 访问依赖
			for dependent_id in self._reverse_graph.get(sid, set()):
				if dependent_id not in visited:
					if visit(dependent_id):
						return True
				elif dependent_id in rec_stack:
					# 发现循环
					logger.error(f"发现循环依赖: {sid} -> {dependent_id}")
					return True

			rec_stack.remove(sid)
			return False

		# 遍历所有策略
		for strategy_id in self._dependency_graph.keys():
			if strategy_id not in visited:
				if visit(strategy_id):
					return True

		return False

	def clear (self) -> None:
		"""清除所有依赖关系"""
		self._dependency_graph.clear()
		self._reverse_graph.clear()
		self._load_order.clear()
		logger.info("依赖关系已清除")

	def get_dependency_chain (
			self,
			strategy_id: str,
	) -> List[str]:
		"""
		获取依赖链

		Args:
			strategy_id: 策略ID

		Returns:
			依赖链（从最底层到顶层）
		"""
		chain = []
		visited = set()

		def build_chain (sid: str):
			if sid in visited:
				return
			visited.add(sid)

			# 先添加依赖
			dependencies = self.get_dependencies(sid)
			for dep in dependencies:
				if dep.target_strategy_id:
					build_chain(dep.target_strategy_id)

			chain.append(sid)

		build_chain(strategy_id)
		return chain