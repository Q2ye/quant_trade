# quant_server/shared/database/repositories/analysis/performance/analysis_benchmark_repository.py
"""
分析基准Repository
负责AnalysisBenchmark表的数据访问操作

继承自BaseRepository，提供分析基准的管理功能
包括基准创建、查询、验证、组件管理等业务方法
"""

from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.business_models import AnalysisBenchmark
from shared.database.repositories.base.repository_base import BaseRepository, RepositoryError


class AnalysisBenchmarkRepository(BaseRepository[AnalysisBenchmark]):
	"""
	分析基准Repository
	继承自BaseRepository，提供分析基准的数据访问方法
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化分析基准Repository

		Args:
			session: 数据库会话
		"""
		super().__init__(session, AnalysisBenchmark)

	async def create_benchmark (
			self,
			benchmark_code: str,
			benchmark_name: str,
			benchmark_type: str,
			description: Optional[str] = None,
			components: Optional[List[Dict[str, Any]]] = None,
			is_active: bool = True
	) -> AnalysisBenchmark:
		"""
		创建分析基准

		Args:
			benchmark_code: 基准代码
			benchmark_name: 基准名称
			benchmark_type: 基准类型（index/custom/portfolio）
			description: 描述（可选）
			components: 成分股数据（可选）
			is_active: 是否激活

		Returns:
			AnalysisBenchmark: 创建的基准对象
		"""
		try:
			# 检查基准代码是否唯一
			existing = await self.get_by(benchmark_code=benchmark_code)
			if existing:
				raise RepositoryError(f"基准代码已存在: {benchmark_code}")

			benchmark_data = {
				'benchmark_code': benchmark_code,
				'benchmark_name': benchmark_name,
				'benchmark_type': benchmark_type,
				'description': description,
				'components': components or [],
				'is_active': is_active
			}

			return await self.create(benchmark_data)
		except RepositoryError:
			raise
		except Exception as e:
			raise RepositoryError(f"创建分析基准失败: {str(e)}")

	async def get_benchmark_by_code (
			self,
			benchmark_code: str
	) -> Optional[AnalysisBenchmark]:
		"""
		根据基准代码获取基准

		Args:
			benchmark_code: 基准代码

		Returns:
			Optional[AnalysisBenchmark]: 基准对象或None
		"""
		try:
			return await self.get_by(benchmark_code=benchmark_code)
		except Exception as e:
			raise RepositoryError(f"获取基准失败: {str(e)}")

	async def get_active_benchmarks (
			self,
			benchmark_type: Optional[str] = None,
			limit: int = 100
	) -> List[AnalysisBenchmark]:
		"""
		获取活跃的基准

		Args:
			benchmark_type: 基准类型过滤（可选）
			limit: 限制记录数

		Returns:
			List[AnalysisBenchmark]: 活跃基准列表
		"""
		try:
			filters: Dict[str, Any] = {'is_active': True}

			if benchmark_type:
				filters['benchmark_type'] = benchmark_type

			return await self.get_many(limit=limit, **filters)
		except Exception as e:
			raise RepositoryError(f"获取活跃基准失败: {str(e)}")

	async def get_benchmarks_by_type (
			self,
			benchmark_type: str,
			include_inactive: bool = False,
			limit: int = 100
	) -> List[AnalysisBenchmark]:
		"""
		根据类型获取基准

		Args:
			benchmark_type: 基准类型
			include_inactive: 是否包含非活跃基准
			limit: 限制记录数

		Returns:
			List[AnalysisBenchmark]: 基准列表
		"""
		try:
			filters: Dict[str, Any] = {'benchmark_type': benchmark_type}

			if not include_inactive:
				filters['is_active'] = True

			return await self.get_many(limit=limit, **filters)
		except Exception as e:
			raise RepositoryError(f"获取类型基准失败: {str(e)}")

	async def update_benchmark_components (
			self,
			benchmark_id: str,
			components: List[Dict[str, Any]],
			update_description: Optional[str] = None
	) -> bool:
		"""
		更新基准成分股

		Args:
			benchmark_id: 基准ID
			components: 新的成分股列表
			update_description: 更新描述（可选）

		Returns:
			bool: 更新是否成功
		"""
		try:
			update_data: Dict[str, Any] = {'components': components}

			if update_description:
				# 更新描述
				benchmark = await self.get(benchmark_id)
				if benchmark:
					new_description = f"{benchmark.description or ''}\n\n{update_description}"
					update_data['description'] = new_description.strip()

			return await self.update(benchmark_id, update_data) is not None
		except Exception as e:
			raise RepositoryError(f"更新基准成分失败: {str(e)}")

	async def add_component_to_benchmark (
			self,
			benchmark_id: str,
			component: Dict[str, Any],
			update_if_exists: bool = True
	) -> bool:
		"""
		向基准添加成分股

		Args:
			benchmark_id: 基准ID
			component: 成分股数据
			update_if_exists: 如果已存在是否更新

		Returns:
			bool: 添加是否成功
		"""
		try:
			benchmark = await self.get(benchmark_id)

			if not benchmark:
				return False

			components = benchmark.components or []

			# 检查是否已存在（根据股票代码）
			component_code = component.get('ts_code') or component.get('symbol')

			if component_code:
				existing_index = -1
				for i, comp in enumerate(components):
					if (comp.get('ts_code') == component_code or
							comp.get('symbol') == component_code):
						existing_index = i
						break

				if existing_index >= 0:
					if update_if_exists:
						# 更新现有成分股
						components[existing_index] = component
					else:
						# 不更新，直接返回成功
						return True
				else:
					# 添加新成分股
					components.append(component)
			else:
				# 没有股票代码，直接添加
				components.append(component)

			return await self.update(benchmark_id, {'components': components}) is not None
		except Exception as e:
			raise RepositoryError(f"添加基准成分失败: {str(e)}")

	async def remove_component_from_benchmark (
			self,
			benchmark_id: str,
			component_code: str
	) -> bool:
		"""
		从基准移除成分股

		Args:
			benchmark_id: 基准ID
			component_code: 成分股代码

		Returns:
			bool: 移除是否成功
		"""
		try:
			benchmark = await self.get(benchmark_id)

			if not benchmark:
				return False

			components = benchmark.components or []

			# 查找并移除
			new_components = []
			removed = False

			for comp in components:
				if (comp.get('ts_code') != component_code and
						comp.get('symbol') != component_code):
					new_components.append(comp)
				else:
					removed = True

			if removed:
				return await self.update(benchmark_id, {'components': new_components}) is not None

			return True
		except Exception as e:
			raise RepositoryError(f"移除基准成分失败: {str(e)}")

	async def get_benchmark_components (
			self,
			benchmark_id: str
	) -> List[Dict[str, Any]]:
		"""
		获取基准成分股

		Args:
			benchmark_id: 基准ID

		Returns:
			List[Dict[str, Any]]: 成分股列表
		"""
		try:
			benchmark = await self.get(benchmark_id)

			if not benchmark:
				return []

			return benchmark.components or []
		except Exception as e:
			raise RepositoryError(f"获取基准成分失败: {str(e)}")

	@staticmethod
	async def validate_benchmark_components (
			components: List[Dict[str, Any]]
	) -> Dict[str, Any]:
		"""
		验证基准成分股数据

		Args:
			components: 成分股列表

		Returns:
			Dict[str, Any]: 验证结果
		"""
		try:
			validation_result = {
				'valid': True,
				'errors': [],
				'warnings': [],
				'component_count': len(components),
				'unique_codes': set(),
				'duplicate_codes': []
			}

			if not isinstance(components, list):
				validation_result['valid'] = False
				validation_result['errors'].append("成分股必须是列表格式")
				return validation_result

			seen_codes = set()

			for i, component in enumerate(components):
				if not isinstance(component, dict):
					validation_result['errors'].append(f"第{i + 1}个成分股不是字典格式")
					validation_result['valid'] = False
					continue

				# 检查必要字段
				component_code = component.get('ts_code') or component.get('symbol')

				if not component_code:
					validation_result['warnings'].append(f"第{i + 1}个成分股缺少股票代码")
				else:
					if component_code in seen_codes:
						validation_result['duplicate_codes'].append(component_code)
						validation_result['warnings'].append(f"重复的股票代码: {component_code}")
					else:
						seen_codes.add(component_code)
						validation_result['unique_codes'].add(component_code)

				# 检查权重字段
				weight = component.get('weight')
				if weight is not None:
					try:
						weight_float = float(weight)
						if weight_float < 0 or weight_float > 1:
							validation_result['warnings'].append(
								f"第{i + 1}个成分股权重 {weight} 超出范围 [0, 1]"
							)
					except ValueError:
						validation_result['warnings'].append(
							f"第{i + 1}个成分股权重 {weight} 不是有效数字"
						)

			return validation_result
		except Exception as e:
			raise RepositoryError(f"验证基准成分失败: {str(e)}")

	async def calculate_benchmark_statistics (
			self,
			benchmark_id: str
	) -> Dict[str, Any]:
		"""
		计算基准统计信息

		Args:
			benchmark_id: 基准ID

		Returns:
			Dict[str, Any]: 基准统计信息
		"""
		try:
			benchmark = await self.get(benchmark_id)

			if not benchmark:
				return {}

			components = benchmark.components or []

			total_components = len(components)

			# 计算权重统计
			weights = []
			for comp in components:
				weight = comp.get('weight')
				if weight is not None:
					try:
						weights.append(float(weight))
					except (ValueError, TypeError):
						pass

			if weights:
				total_weight = sum(weights)
				avg_weight = total_weight / len(weights) if weights else 0
				max_weight = max(weights) if weights else 0
				min_weight = min(weights) if weights else 0

				# 检查权重总和
				weight_sum_valid = 0.99 <= total_weight <= 1.01
			else:
				total_weight = 0
				avg_weight = 0
				max_weight = 0
				min_weight = 0
				weight_sum_valid = True  # 没有权重字段，视为有效

			# 获取股票代码
			ts_codes = []
			for comp in components:
				code = comp.get('ts_code') or comp.get('symbol')
				if code:
					ts_codes.append(code)

			return {
				'benchmark_id': benchmark_id,
				'benchmark_code': benchmark.benchmark_code,
				'benchmark_name': benchmark.benchmark_name,
				'benchmark_type': benchmark.benchmark_type,
				'total_components': total_components,
				'unique_codes': len(set(ts_codes)),
				'weight_stats': {
					'total': total_weight,
					'average': avg_weight,
					'max': max_weight,
					'min': min_weight,
					'sum_valid': weight_sum_valid
				},
				'component_codes': ts_codes[:20]  # 只返回前20个
			}
		except Exception as e:
			raise RepositoryError(f"计算基准统计失败: {str(e)}")

	async def search_benchmarks (
			self,
			keyword: str,
			benchmark_type: Optional[str] = None,
			is_active: Optional[bool] = None,
			limit: int = 50
	) -> List[AnalysisBenchmark]:
		"""
		搜索基准

		Args:
			keyword: 搜索关键词
			benchmark_type: 基准类型过滤（可选）
			is_active: 是否活跃过滤（可选）
			limit: 限制记录数

		Returns:
			List[AnalysisBenchmark]: 搜索结果的基准列表
		"""
		try:
			conditions = []

			if keyword:
				conditions.append(
					or_(
						self.model.benchmark_code.ilike(f'%{keyword}%'),
						self.model.benchmark_name.ilike(f'%{keyword}%'),
						self.model.description.ilike(f'%{keyword}%') if self.model.description else False
					)
				)

			if benchmark_type:
				conditions.append(self.model.benchmark_type == benchmark_type)

			if is_active is not None:
				conditions.append(self.model.is_active == is_active)

			query = select(self.model)

			if conditions:
				query = query.where(and_(*conditions))

			query = query.order_by(desc(self.model.created_at)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"搜索基准失败: {str(e)}")

	async def get_benchmark_statistics (self) -> Dict[str, Any]:
		"""
		获取基准统计信息

		Returns:
			Dict[str, Any]: 基准统计信息
		"""
		try:
			# 统计各类型基准数量
			query = select(
				self.model.benchmark_type,
				func.count(self.model.id).label('count'),
				func.sum(func.cast(self.model.is_active, func.Integer)).label('active_count'),
				func.avg(
					func.json_array_length(self.model.components)
				).label('avg_components')
			).group_by(self.model.benchmark_type)

			result = await self.session.execute(query)

			stats = {
				'total': 0,
				'active': 0,
				'by_type': {}
			}

			for benchmark_type, count, active_count, avg_components in result.all():
				stats['by_type'][benchmark_type] = {
					'total': count,
					'active': active_count or 0,
					'inactive': count - (active_count or 0),
					'avg_components': float(avg_components) if avg_components else 0
				}
				stats['total'] += count
				stats['active'] += active_count or 0

			stats['inactive'] = stats['total'] - stats['active']

			return stats
		except Exception as e:
			raise RepositoryError(f"获取基准统计失败: {str(e)}")

	async def deactivate_benchmark (
			self,
			benchmark_id: str
	) -> bool:
		"""
		停用基准

		Args:
			benchmark_id: 基准ID

		Returns:
			bool: 停用是否成功
		"""
		try:
			return await self.update(benchmark_id, {'is_active': False}) is not None
		except Exception as e:
			raise RepositoryError(f"停用基准失败: {str(e)}")

	async def activate_benchmark (
			self,
			benchmark_id: str
	) -> bool:
		"""
		激活基准

		Args:
			benchmark_id: 基准ID

		Returns:
			bool: 激活是否成功
		"""
		try:
			return await self.update(benchmark_id, {'is_active': True}) is not None
		except Exception as e:
			raise RepositoryError(f"激活基准失败: {str(e)}")

	async def duplicate_benchmark (
			self,
			benchmark_id: str,
			new_benchmark_code: str,
			new_benchmark_name: str,
			description_suffix: str = " (复制)"
	) -> Optional[AnalysisBenchmark]:
		"""
		复制基准

		Args:
			benchmark_id: 基准ID
			new_benchmark_code: 新基准代码
			new_benchmark_name: 新基准名称
			description_suffix: 描述后缀

		Returns:
			Optional[AnalysisBenchmark]: 复制的基准对象
		"""
		try:
			benchmark = await self.get(benchmark_id)

			if not benchmark:
				return None

			# 检查新基准代码是否唯一
			existing = await self.get_by(benchmark_code=new_benchmark_code)
			if existing:
				raise RepositoryError(f"基准代码已存在: {new_benchmark_code}")

			# 创建新基准
			new_benchmark_data = {
				'benchmark_code': new_benchmark_code,
				'benchmark_name': new_benchmark_name,
				'benchmark_type': benchmark.benchmark_type,
				'description': f"{benchmark.description or ''}{description_suffix}".strip(),
				'components': benchmark.components.copy() if benchmark.components else [],
				'is_active': benchmark.is_active
			}

			return await self.create(new_benchmark_data)
		except RepositoryError:
			raise
		except Exception as e:
			raise RepositoryError(f"复制基准失败: {str(e)}")

	async def get_benchmarks_with_components_count (
			self,
			min_components: int = 1,
			max_components: Optional[int] = None,
			benchmark_type: Optional[str] = None
	) -> List[AnalysisBenchmark]:
		"""
		根据成分股数量获取基准

		Args:
			min_components: 最小成分股数量
			max_components: 最大成分股数量（可选）
			benchmark_type: 基准类型过滤（可选）

		Returns:
			List[AnalysisBenchmark]: 符合条件的基准列表
		"""
		try:
			# 获取所有活跃基准
			benchmarks = await self.get_active_benchmarks(benchmark_type=benchmark_type)

			filtered_benchmarks = []

			for benchmark in benchmarks:
				component_count = len(benchmark.components or [])

				if component_count >= min_components:
					if max_components is None or component_count <= max_components:
						filtered_benchmarks.append(benchmark)

			return filtered_benchmarks
		except Exception as e:
			raise RepositoryError(f"获取成分股数量基准失败: {str(e)}")
