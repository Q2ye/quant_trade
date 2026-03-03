# # quant_server/shared/database/repositories/strategy/management/strategy_dependency_repository.py
# """
# StrategyDependencyRepository - 策略依赖关系数据访问仓库
#
# 基于 BaseRepository 实现，提供对策略依赖关系的 CRUD 操作
# 位置：quant_server/shared/database/repositories/strategy/management/strategy_dependency_repository.py
#
# 表说明：strategy_dependencies 表存储策略之间的依赖关系（如果模型未定义，此文件作为占位符）
# 典型场景：策略A依赖策略B的输出，或者策略共享数据源等
#
# 设计原则：
# 1. 纯数据访问：只做 CRUD，不做业务逻辑
# 2. 异步支持：完全异步化设计
# 3. 类型安全：使用泛型确保类型一致性
# 4. 关系管理：提供依赖关系查询和验证方法
# """
#
# from typing import Optional, List, Dict, Any, Union, Set
# from datetime import datetime
# from sqlalchemy import select, update, delete, and_, or_, func
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.orm import aliased
#
# # 注意：StrategyDependency 模型可能尚未在 business_models.py 中定义
# # 这里我们假设一个可能的模型结构，实际使用时需要根据真实模型调整
#
# # 假设的模型导入（实际使用时取消注释并根据实际模型调整）
# # from ....models.business_models import StrategyDependency
# # from ..base import BaseRepository, RepositoryResult, PaginationParams, PaginationResult
#
#
# class StrategyDependencyRepository(BaseRepository):
# 	"""
# 	策略依赖关系仓库类
#
# 	继承自 BaseRepository，提供对策略依赖关系的专用数据访问方法
# 	注意：如果 StrategyDependency 模型未定义，此实现可能无法直接使用
# 	"""
#
# 	def __init__ (self, session: AsyncSession):
# 		"""
# 		初始化 StrategyDependencyRepository
#
# 		Args:
# 			session: 数据库会话，提供数据访问上下文
# 		"""
# 		# 注意：由于 StrategyDependency 模型可能未定义，这里先使用 None
# 		# 实际使用时需要传入正确的模型类
# 		try:
# 			from ....models.business_models import StrategyDependency
# 			model = StrategyDependency
# 		except ImportError:
# 			# 如果模型未定义，我们可以创建一个占位符实现
# 			model = None
#
# 		super().__init__(session, model)
#
# 	# ==================== 专用查询方法 ====================
#
# 	async def get_dependencies_by_strategy (self, strategy_id: str) -> List:
# 		"""
# 		获取策略的所有依赖项
#
# 		Args:
# 			strategy_id: 策略ID
#
# 		Returns:
# 			依赖项列表
# 		"""
# 		if not self.model:
# 			raise NotImplementedError("StrategyDependency 模型未定义")
#
# 		try:
# 			query = (
# 				select(self.model)
# 				.where(self.model.strategy_id == strategy_id)
# 				.order_by(self.model.created_at)
# 			)
# 			result = await self.session.execute(query)
# 			return result.scalars().all()
# 		except Exception as e:
# 			raise RepositoryError(f"获取策略依赖失败: {str(e)}")
#
# 	async def get_dependents_of (self, dependency_id: str, dependency_type: Optional[str] = None) -> List:
# 		"""
# 		获取依赖项的依赖者（哪些策略依赖于此项）
#
# 		Args:
# 			dependency_id: 依赖项ID
# 			dependency_type: 可选的依赖类型过滤
#
# 		Returns:
# 			依赖此项目的策略列表
# 		"""
# 		if not self.model:
# 			raise NotImplementedError("StrategyDependency 模型未定义")
#
# 		try:
# 			query = select(self.model).where(self.model.dependency_id == dependency_id)
#
# 			if dependency_type:
# 				query = query.where(self.model.dependency_type == dependency_type)
#
# 			query = query.order_by(self.model.created_at)
# 			result = await self.session.execute(query)
# 			return result.scalars().all()
# 		except Exception as e:
# 			raise RepositoryError(f"获取依赖者失败: {str(e)}")
#
# 	async def get_dependency_chain (self, strategy_id: str, max_depth: int = 10) -> Dict[str, Any]:
# 		"""
# 		获取策略的依赖链（递归查询）
#
# 		Args:
# 			strategy_id: 起始策略ID
# 			max_depth: 最大递归深度
#
# 		Returns:
# 			依赖链结构
# 		"""
# 		if not self.model:
# 			raise NotImplementedError("StrategyDependency 模型未定义")
#
# 		try:
# 			# 使用递归CTE查询依赖链
# 			# 注意：具体实现取决于数据库支持
# 			# 这里提供简化的非递归版本
# 			dependencies = await self.get_dependencies_by_strategy(strategy_id)
#
# 			result = {
# 				'strategy_id': strategy_id,
# 				'direct_dependencies': [],
# 				'all_dependencies': set(),
# 				'has_circular': False,
# 				'depth': 0
# 			}
#
# 			# 收集直接依赖
# 			for dep in dependencies:
# 				result['direct_dependencies'].append({
# 					'dependency_id': dep.dependency_id,
# 					'dependency_type': dep.dependency_type,
# 					'description': dep.description
# 				})
# 				result['all_dependencies'].add(dep.dependency_id)
#
# 			# 简单实现：只获取一层依赖
# 			# 复杂的递归查询需要数据库支持CTE
# 			result['depth'] = 1
# 			result['dependency_count'] = len(result['all_dependencies'])
#
# 			return result
# 		except Exception as e:
# 			raise RepositoryError(f"获取依赖链失败: {str(e)}")
#
# 	async def check_circular_dependency (self, strategy_id: str, dependency_id: str) -> bool:
# 		"""
# 		检查是否存在循环依赖
#
# 		Args:
# 			strategy_id: 策略ID
# 			dependency_id: 要检查的依赖项ID
#
# 		Returns:
# 			是否存在循环依赖
# 		"""
# 		if not self.model:
# 			raise NotImplementedError("StrategyDependency 模型未定义")
#
# 		try:
# 			# 简单实现：检查如果 dependency_id 也是一个策略，它是否依赖 strategy_id
# 			# 这里假设 dependency_type 可以标识是否为策略
#
# 			# 检查依赖项是否也依赖原始策略
# 			reverse_deps = await self.get_dependents_of(strategy_id)
#
# 			for dep in reverse_deps:
# 				# 这里需要根据实际模型结构判断
# 				# 假设 dependency_id 字段存储依赖目标的ID
# 				if hasattr(dep, 'strategy_id') and dep.strategy_id == dependency_id:
# 					return True
#
# 			return False
# 		except Exception as e:
# 			raise RepositoryError(f"检查循环依赖失败: {str(e)}")
#
# 	async def add_dependency (
# 			self,
# 			strategy_id: str,
# 			dependency_id: str,
# 			dependency_type: str,
# 			description: Optional[str] = None
# 	) -> Any:
# 		"""
# 		添加策略依赖
#
# 		Args:
# 			strategy_id: 策略ID
# 			dependency_id: 依赖项ID
# 			dependency_type: 依赖类型
# 			description: 依赖描述
#
# 		Returns:
# 			创建的依赖记录
# 		"""
# 		if not self.model:
# 			raise NotImplementedError("StrategyDependency 模型未定义")
#
# 		try:
# 			# 检查循环依赖
# 			if dependency_type == 'strategy':
# 				has_circular = await self.check_circular_dependency(strategy_id, dependency_id)
# 				if has_circular:
# 					raise RepositoryError("检测到循环依赖", "CIRCULAR_DEPENDENCY")
#
# 			# 检查是否已存在相同依赖
# 			existing = await self.get_by(
# 				strategy_id=strategy_id,
# 				dependency_id=dependency_id,
# 				dependency_type=dependency_type
# 			)
#
# 			if existing:
# 				return existing
#
# 			# 创建新依赖
# 			dependency_data = {
# 				'strategy_id': strategy_id,
# 				'dependency_id': dependency_id,
# 				'dependency_type': dependency_type,
# 				'description': description,
# 				'created_at': datetime.now()
# 			}
#
# 			return await self.create(dependency_data)
# 		except RepositoryError:
# 			raise
# 		except Exception as e:
# 			raise RepositoryError(f"添加策略依赖失败: {str(e)}")
#
# 	async def remove_dependency (
# 			self,
# 			strategy_id: str,
# 			dependency_id: str,
# 			dependency_type: Optional[str] = None
# 	) -> bool:
# 		"""
# 		移除策略依赖
#
# 		Args:
# 			strategy_id: 策略ID
# 			dependency_id: 依赖项ID
# 			dependency_type: 可选的依赖类型过滤
#
# 		Returns:
# 			是否成功移除
# 		"""
# 		if not self.model:
# 			raise NotImplementedError("StrategyDependency 模型未定义")
#
# 		try:
# 			filters = {
# 				'strategy_id': strategy_id,
# 				'dependency_id': dependency_id
# 			}
#
# 			if dependency_type:
# 				filters['dependency_type'] = dependency_type
#
# 			return await self.delete_by(**filters) > 0
# 		except Exception as e:
# 			raise RepositoryError(f"移除策略依赖失败: {str(e)}")
#
# 	async def update_dependency_description (
# 			self,
# 			strategy_id: str,
# 			dependency_id: str,
# 			description: str,
# 			dependency_type: Optional[str] = None
# 	) -> Any:
# 		"""
# 		更新依赖描述
#
# 		Args:
# 			strategy_id: 策略ID
# 			dependency_id: 依赖项ID
# 			description: 新的描述
# 			dependency_type: 可选的依赖类型过滤
#
# 		Returns:
# 			更新后的依赖记录
# 		"""
# 		if not self.model:
# 			raise NotImplementedError("StrategyDependency 模型未定义")
#
# 		try:
# 			# 查找现有记录
# 			filters = {
# 				'strategy_id': strategy_id,
# 				'dependency_id': dependency_id
# 			}
#
# 			if dependency_type:
# 				filters['dependency_type'] = dependency_type
#
# 			existing = await self.get_by(**filters)
#
# 			if not existing:
# 				raise RepositoryError("依赖记录不存在", "DEPENDENCY_NOT_FOUND")
#
# 			# 更新描述
# 			update_data = {
# 				'description': description,
# 				'updated_at': datetime.now()
# 			}
#
# 			return await self.update(existing.id, update_data)
# 		except RepositoryError:
# 			raise
# 		except Exception as e:
# 			raise RepositoryError(f"更新依赖描述失败: {str(e)}")
#
# 	async def get_dependency_graph (self, strategy_ids: List[str]) -> Dict[str, Any]:
# 		"""
# 		获取多个策略的依赖关系图
#
# 		Args:
# 			strategy_ids: 策略ID列表
#
# 		Returns:
# 			依赖关系图结构
# 		"""
# 		if not self.model:
# 			raise NotImplementedError("StrategyDependency 模型未定义")
#
# 		try:
# 			if not strategy_ids:
# 				return {'nodes': [], 'edges': [], 'isolated': []}
#
# 			# 查询所有相关依赖
# 			query = select(self.model).where(
# 				self.model.strategy_id.in_(strategy_ids)
# 			).order_by(self.model.strategy_id, self.model.dependency_type)
#
# 			result = await self.session.execute(query)
# 			dependencies = result.scalars().all()
#
# 			# 构建图结构
# 			nodes = set(strategy_ids)
# 			edges = []
#
# 			for dep in dependencies:
# 				# 添加依赖项作为节点
# 				nodes.add(dep.dependency_id)
#
# 				# 添加边
# 				edges.append({
# 					'source': dep.strategy_id,
# 					'target': dep.dependency_id,
# 					'type': dep.dependency_type,
# 					'description': dep.description
# 				})
#
# 			# 识别孤立节点（没有依赖关系）
# 			connected_nodes = set()
# 			for edge in edges:
# 				connected_nodes.add(edge['source'])
# 				connected_nodes.add(edge['target'])
#
# 			isolated = list(nodes - connected_nodes)
#
# 			return {
# 				'nodes': list(nodes),
# 				'edges': edges,
# 				'isolated': isolated,
# 				'total_nodes': len(nodes),
# 				'total_edges': len(edges),
# 				'isolated_count': len(isolated)
# 			}
# 		except Exception as e:
# 			raise RepositoryError(f"获取依赖关系图失败: {str(e)}")
#
# 	async def batch_add_dependencies (
# 			self,
# 			strategy_id: str,
# 			dependencies: List[Dict[str, str]]
# 	) -> List[Any]:
# 		"""
# 		批量添加策略依赖
#
# 		Args:
# 			strategy_id: 策略ID
# 			dependencies: 依赖列表，每个元素包含 dependency_id, dependency_type, description
#
# 		Returns:
# 			创建的依赖记录列表
# 		"""
# 		if not self.model:
# 			raise NotImplementedError("StrategyDependency 模型未定义")
#
# 		try:
# 			results = []
#
# 			for dep in dependencies:
# 				try:
# 					dependency_record = await self.add_dependency(
# 						strategy_id=strategy_id,
# 						dependency_id=dep['dependency_id'],
# 						dependency_type=dep['dependency_type'],
# 						description=dep.get('description')
# 					)
# 					results.append(dependency_record)
# 				except RepositoryError as e:
# 					if e.code == "CIRCULAR_DEPENDENCY":
# 						# 跳过循环依赖
# 						continue
# 					else:
# 						raise
#
# 			return results
# 		except Exception as e:
# 			raise RepositoryError(f"批量添加依赖失败: {str(e)}")
#
# 	async def validate_dependencies (self, strategy_id: str) -> Dict[str, Any]:
# 		"""
# 		验证策略的所有依赖项是否可用
#
# 		Args:
# 			strategy_id: 策略ID
#
# 		Returns:
# 			验证结果
# 		"""
# 		if not self.model:
# 			raise NotImplementedError("StrategyDependency 模型未定义")
#
# 		try:
# 			dependencies = await self.get_dependencies_by_strategy(strategy_id)
#
# 			validation_results = {
# 				'strategy_id': strategy_id,
# 				'total_dependencies': len(dependencies),
# 				'valid': [],
# 				'invalid': [],
# 				'warnings': [],
# 				'has_circular': False,
# 				'all_valid': True
# 			}
#
# 			# 简单验证：检查是否存在循环依赖
# 			for dep in dependencies:
# 				if dep.dependency_type == 'strategy':
# 					is_circular = await self.check_circular_dependency(strategy_id, dep.dependency_id)
# 					if is_circular:
# 						validation_results['has_circular'] = True
# 						validation_results['invalid'].append({
# 							'dependency_id': dep.dependency_id,
# 							'dependency_type': dep.dependency_type,
# 							'reason': '循环依赖',
# 							'description': dep.description
# 						})
# 						validation_results['all_valid'] = False
# 					else:
# 						validation_results['valid'].append({
# 							'dependency_id': dep.dependency_id,
# 							'dependency_type': dep.dependency_type,
# 							'description': dep.description
# 						})
# 				else:
# 					# 其他类型的依赖可以添加特定验证逻辑
# 					validation_results['valid'].append({
# 						'dependency_id': dep.dependency_id,
# 						'dependency_type': dep.dependency_type,
# 						'description': dep.description
# 					})
#
# 			return validation_results
# 		except Exception as e:
# 			raise RepositoryError(f"验证依赖失败: {str(e)}")
#
#
# class RepositoryError(Exception):
# 	"""Repository异常基类"""
#
# 	def __init__ (self, message: str, code: str = "STRATEGY_DEPENDENCY_REPOSITORY_ERROR"):
# 		self.message = message
# 		self.code = code
# 		super().__init__(self.message)
#
#
# # 导出实现
# __all__ = ['StrategyDependencyRepository', 'RepositoryError']