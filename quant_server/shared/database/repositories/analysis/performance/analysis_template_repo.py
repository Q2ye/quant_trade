# quant_server/shared/database/repositories/analysis/performance/analysis_template_repository.py
"""
分析模板Repository
负责AnalysisTemplate表的数据访问操作

继承自BaseRepository，提供分析模板的管理功能
包括模板创建、查询、验证、渲染等业务方法
"""

from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_, or_, func, desc, case
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.business_models import AnalysisTemplate, AnalysisTask
from quant_server.shared.database.repositories.base.repository_base import BaseRepository, RepositoryError


class AnalysisTemplateRepository(BaseRepository[AnalysisTemplate]):
	"""
	分析模板Repository
	继承自BaseRepository，提供分析模板的数据访问方法
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化分析模板Repository

		Args:
			session: 数据库会话
		"""
		super().__init__(session, AnalysisTemplate)

	async def create_template (
			self,
			template_name: str,
			template_type: str,
			config_template: Dict[str, Any],
			output_format: str = "json",
			description: Optional[str] = None,
			is_public: bool = True,
			created_by: Optional[int] = None
	) -> AnalysisTemplate:
		"""
		创建分析模板

		Args:
			template_name: 模板名称
			template_type: 模板类型
			config_template: 配置模板
			output_format: 输出格式（json, html, pdf, excel）
			description: 模板描述（可选）
			is_public: 是否公开
			created_by: 创建人ID（可选）

		Returns:
			AnalysisTemplate: 创建的模板对象
		"""
		try:
			template_data = {
				'template_name': template_name,
				'template_type': template_type,
				'config_template': config_template,
				'output_format': output_format,
				'description': description,
				'is_public': is_public,
				'created_by': created_by
			}

			return await self.create(template_data)
		except Exception as e:
			raise RepositoryError(f"创建分析模板失败: {str(e)}")

	async def get_template_by_type_name (
			self,
			template_type: str,
			template_name: str
	) -> Optional[AnalysisTemplate]:
		"""
		根据类型和名称获取模板

		Args:
			template_type: 模板类型
			template_name: 模板名称

		Returns:
			Optional[AnalysisTemplate]: 模板对象或None
		"""
		try:
			return await self.get_by(
				template_type=template_type,
				template_name=template_name
			)
		except Exception as e:
			raise RepositoryError(f"获取类型名称模板失败: {str(e)}")

	async def get_public_templates (
			self,
			template_type: Optional[str] = None,
			limit: int = 100
	) -> List[AnalysisTemplate]:
		"""
		获取公开模板

		Args:
			template_type: 模板类型过滤（可选）
			limit: 限制记录数

		Returns:
			List[AnalysisTemplate]: 公开模板列表
		"""
		try:
			filters = {'is_public': "True"}

			if template_type:
				filters['template_type'] = template_type

			return await self.get_many(limit=limit, **filters)
		except Exception as e:
			raise RepositoryError(f"获取公开模板失败: {str(e)}")

	async def get_user_templates (
			self,
			user_id: str,
			include_public: bool = True,
			template_type: Optional[str] = None,
			limit: int = 100
	) -> List[AnalysisTemplate]:
		"""
		获取用户可用的模板（自己创建的或公开的）

		Args:
			user_id: 用户ID
			include_public: 是否包含公开模板
			template_type: 模板类型过滤（可选）
			limit: 限制记录数

		Returns:
			List[AnalysisTemplate]: 用户可用模板列表
		"""
		try:
			conditions = []

			# 用户自己创建的模板
			user_condition = self.model.created_by == user_id

			if include_public:
				# 或者公开模板
				conditions.append(or_(user_condition, self.model.is_public == True))
			else:
				conditions.append(user_condition)

			if template_type:
				conditions.append(self.model.template_type == template_type)

			query = select(self.model).where(
				and_(*conditions)
			).order_by(
				desc(self.model.created_at)
			).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取用户模板失败: {str(e)}")

	async def render_template (
			self,
			template_id: str,
			context: Dict[str, Any]
	) -> Dict[str, Any]:
		"""
		渲染模板

		Args:
			template_id: 模板ID
			context: 模板上下文数据

		Returns:
			Dict[str, Any]: 渲染后的配置
		"""
		try:
			template = await self.get(template_id)

			if not template:
				raise RepositoryError(f"模板不存在: {template_id}")

			# 简单的模板渲染 - 替换 {key} 为 context[key]
			def render_config (config: Any) -> Any:
				if isinstance(config, dict):
					return {k: render_config(v) for k, v in config.items()}
				elif isinstance(config, list):
					return [render_config(item) for item in config]
				elif isinstance(config, str):
					# 替换占位符
					import re

					def replace_placeholder (match):
						placeholder = match.group(1)
						if placeholder in context:
							return str(context[placeholder])
						else:
							# 保持原样
							return match.group(0)

					pattern = r'\{(\w+)\}'
					return re.sub(pattern, replace_placeholder, config)
				else:
					return config

			rendered_config = render_config(template.config_template)

			return {
				'template_id': template_id,
				'template_name': template.template_name,
				'template_type': template.template_type,
				'output_format': template.output_format,
				'rendered_config': rendered_config,
				'context_used': list(context.keys())
			}
		except Exception as e:
			raise RepositoryError(f"渲染模板失败: {str(e)}")

	async def validate_template_config (
			self,
			config_template: Any,
			required_fields: Optional[List[str]] = None,
			context: Optional[Dict[str, Any]] = None,
			template_type: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		验证模板配置的完整性和有效性

		Args:
			config_template: 配置模板
			required_fields: 必填字段列表（可选）
			context: 测试上下文数据（可选）
			template_type: 模板类型（用于类型特定的验证）

		Returns:
			Dict[str, Any]: 验证结果
		"""
		try:
			validation_result = {
				'valid': True,
				'errors': [],
				'warnings': [],
				'required_fields_missing': [],
				'placeholder_warnings': [],
				'type_errors': [],
				'rendered_config': None,
				'validation_summary': {}
			}

			# 1. 基础结构验证
			if not isinstance(config_template, dict):
				validation_result['errors'].append("配置模板必须是字典格式")
				validation_result['valid'] = False
				return validation_result

			# 2. 必填字段检查
			if required_fields:
				for field in required_fields:
					if field not in config_template:
						validation_result['required_fields_missing'].append(field)
						validation_result['valid'] = False

			# 3. 模板类型特定的验证规则
			if template_type:
				type_validation = self._validate_by_template_type(config_template, template_type)
				validation_result['errors'].extend(type_validation.get('errors', []))
				validation_result['warnings'].extend(type_validation.get('warnings', []))
				validation_result['type_errors'].extend(type_validation.get('type_errors', []))
				validation_result['valid'] = validation_result['valid'] and type_validation.get('valid', True)

			# 4. 占位符验证和渲染测试
			if context:
				rendered_result = self._render_and_validate_placeholders(config_template, context)
				validation_result['rendered_config'] = rendered_result.get('rendered_config')
				validation_result['placeholder_warnings'].extend(rendered_result.get('warnings', []))
				validation_result['errors'].extend(rendered_result.get('errors', []))
				validation_result['valid'] = validation_result['valid'] and rendered_result.get('valid', True)
			else:
				# 即使没有上下文，也检查占位符语法
				placeholder_check = self._validate_placeholder_syntax(config_template)
				validation_result['warnings'].extend(placeholder_check.get('warnings', []))

			# 5. 数据格式验证
			format_validation = self._validate_data_formats(config_template)
			validation_result['errors'].extend(format_validation.get('errors', []))
			validation_result['valid'] = validation_result['valid'] and format_validation.get('valid', True)

			# 6. 生成验证摘要
			validation_result['validation_summary'] = {
				'total_errors': len(validation_result['errors']),
				'total_warnings': len(validation_result['warnings']),
				'has_placeholder_issues': len(validation_result['placeholder_warnings']) > 0,
				'has_type_issues': len(validation_result['type_errors']) > 0,
				'config_size': len(str(config_template))
			}

			return validation_result
		except Exception as e:
			raise RepositoryError(f"验证模板配置失败: {str(e)}")

	@staticmethod
	def _validate_by_template_type (config: Dict[str, Any], template_type: str) -> Dict[str, Any]:
		"""根据模板类型进行特定验证"""
		result = {'valid': True, 'errors': [], 'warnings': [], 'type_errors': []}

		# 性能分析模板验证
		if template_type == 'performance':
			required_performance_fields = ['time_range', 'benchmarks', 'metrics']
			for field in required_performance_fields:
				if field not in config:
					result['errors'].append(f"性能分析模板必须包含 '{field}' 字段")
					result['valid'] = False

			# 验证时间范围格式
			if 'time_range' in config:
				time_range = config['time_range']
				if not isinstance(time_range, dict):
					result['errors'].append("时间范围必须是字典格式")
					result['valid'] = False
				elif 'start_date' not in time_range or 'end_date' not in time_range:
					result['errors'].append("时间范围必须包含 start_date 和 end_date")
					result['valid'] = False

		# 风险分析模板验证
		elif template_type == 'risk':
			required_risk_fields = ['risk_metrics', 'thresholds']
			for field in required_risk_fields:
				if field not in config:
					result['warnings'].append(f"风险分析模板建议包含 '{field}' 字段")

			# 验证阈值设置
			if 'thresholds' in config:
				thresholds = config['thresholds']
				if not isinstance(thresholds, dict):
					result['errors'].append("阈值设置必须是字典格式")
					result['valid'] = False

		# 归因分析模板验证
		elif template_type == 'attribution':
			required_attribution_fields = ['factors', 'method']
			for field in required_attribution_fields:
				if field not in config:
					result['errors'].append(f"归因分析模板必须包含 '{field}' 字段")
					result['valid'] = False

		return result

	@staticmethod
	def _render_and_validate_placeholders (config: Any, context: Dict[str, Any]) -> Dict[str, Any]:
		"""渲染配置并验证占位符"""
		result = {'valid': True, 'errors': [], 'warnings': [], 'rendered_config': None}

		def render_config (config_item: Any) -> Any:
			if isinstance(config_item, dict):
				return {k: render_config(v) for k, v in config_item.items()}
			elif isinstance(config_item, list):
				return [render_config(item) for item in config_item]
			elif isinstance(config_item, str):
				import re

				# 查找所有占位符
				pattern = r'\{(\w+)\}'
				matches = re.findall(pattern, config_item)

				# 验证占位符
				for placeholder in matches:
					if placeholder not in context:
						result['warnings'].append(f"占位符 '{placeholder}' 在上下文中未定义")
						result['valid'] = False

				# 渲染占位符
				def replace_placeholder (match):
					placeholder_str: str = match.group(1)
					if placeholder_str in context:
						return str(context[placeholder_str])
					else:
						return match.group(0)  # 保持原样

				try:
					return re.sub(pattern, replace_placeholder, config_item)
				except Exception as exw:
					result['errors'].append(f"渲染占位符失败: {str(exw)}")
					result['valid'] = False
					return config_item
			else:
				return config_item

		try:
			result['rendered_config'] = render_config(config)
		except Exception as ex:
			result['errors'].append(f"渲染配置失败: {str(ex)}")
			result['valid'] = False

		return result

	@staticmethod
	def _validate_placeholder_syntax (config: Any) -> Dict[str, Any]:
		"""验证占位符语法"""
		result = {'warnings': []}

		def check_syntax (config_item: Any):
			if isinstance(config_item, dict):
				for v in config_item.values():
					check_syntax(v)
			elif isinstance(config_item, list):
				for item in config_item:
					check_syntax(item)
			elif isinstance(config_item, str):
				import re
				# 检查无效的占位符语法
				invalid_patterns = [
					(r'\{\{.*\}\}', "双重花括号"),
					(r'\{.*\{.*\}.*\}', "嵌套花括号"),
					(r'\{.*\s+.*\}', "占位符包含空格")
				]

				for pattern, description in invalid_patterns:
					if re.search(pattern, config_item):
						result['warnings'].append(f"检测到可能的占位符语法问题: {description}")

		check_syntax(config)
		return result

	@staticmethod
	def _validate_data_formats (config: Any) -> Dict[str, Any]:
		"""验证数据格式"""
		result = {'valid': True, 'errors': []}

		def validate_format (config_item: Any, path: str = ""):
			if isinstance(config_item, dict):
				for k, v in config_item.items():
					validate_format(v, f"{path}.{k}" if path else k)
			elif isinstance(config_item, list):
				for i, item in enumerate(config_item):
					validate_format(item, f"{path}[{i}]")
			elif isinstance(config_item, str):
				# 验证日期格式
				if 'date' in path.lower():
					import re
					date_patterns = [
						r'^\d{4}-\d{2}-\d{2}$',  # YYYY-MM-DD
						r'^\d{8}$'  # YYYYMMDD
					]

					if not any(re.match(pattern, config_item) for pattern in date_patterns):
						result['warnings'].append(f"字段 '{path}' 的值可能不是标准日期格式")

				# 验证数值格式
				elif any(keyword in path.lower() for keyword in ['value', 'amount', 'price', 'rate']):
					try:
						float(config_item)
					except ValueError:
						result['warnings'].append(f"字段 '{path}' 的值可能不是有效数值")

		validate_format(config)
		return result

	async def update_template (
			self,
			template_id: str,
			template_name: Optional[str] = None,
			config_template: Optional[Dict[str, Any]] = None,
			output_format: Optional[str] = None,
			description: Optional[str] = None,
			is_public: Optional[bool] = None
	) -> Optional[AnalysisTemplate]:
		"""
		更新模板

		Args:
			template_id: 模板ID
			template_name: 模板名称（可选）
			config_template: 配置模板（可选）
			output_format: 输出格式（可选）
			description: 描述（可选）
			is_public: 是否公开（可选）

		Returns:
			Optional[AnalysisTemplate]: 更新后的模板对象
		"""
		try:
			update_data = {}

			if template_name is not None:
				update_data['template_name'] = template_name

			if config_template is not None:
				update_data['config_template'] = config_template

			if output_format is not None:
				update_data['output_format'] = output_format

			if description is not None:
				update_data['description'] = description

			if is_public is not None:
				update_data['is_public'] = is_public

			return await self.update(template_id, update_data)
		except Exception as e:
			raise RepositoryError(f"更新模板失败: {str(e)}")

	async def search_templates (
			self,
			keyword: str,
			template_type: Optional[str] = None,
			is_public: Optional[bool] = None,
			created_by: Optional[int] = None,
			limit: int = 50
	) -> List[AnalysisTemplate]:
		"""
		搜索模板

		Args:
			keyword: 搜索关键词
			template_type: 模板类型过滤（可选）
			is_public: 是否公开过滤（可选）
			created_by: 创建人过滤（可选）
			limit: 限制记录数

		Returns:
			List[AnalysisTemplate]: 搜索结果的模板列表
		"""
		try:
			conditions = []

			if keyword:
				conditions.append(
					or_(
						self.model.template_name.ilike(f'%{keyword}%'),
						self.model.description.ilike(f'%{keyword}%') if self.model.description else False
					)
				)

			if template_type:
				conditions.append(self.model.template_type == template_type)

			if is_public is not None:
				conditions.append(self.model.is_public == is_public)

			if created_by:
				conditions.append(self.model.created_by == created_by)

			query = select(self.model)

			if conditions:
				query = query.where(and_(*conditions))

			query = query.order_by(desc(self.model.created_at)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"搜索模板失败: {str(e)}")

	async def get_template_statistics (
			self,
			created_by: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		获取模板统计信息

		Args:
			created_by: 创建人过滤（可选）

		Returns:
			Dict[str, Any]: 模板统计信息
		"""
		try:
			# 构建基础查询
			query = select(
				self.model.template_type,
				func.count(self.model.id).label('count'),
				func.sum(func.cast(self.model.is_public, func.Integer)).label('public_count')
			)

			if created_by:
				query = query.where(self.model.created_by == created_by)

			query = query.group_by(self.model.template_type)

			result = await self.session.execute(query)

			stats = {
				'total': 0,
				'public': 0,
				'private': 0,
				'by_type': {}
			}

			for template_type, count, public_count in result.all():
				stats['by_type'][template_type] = {
					'total': count,
					'public': public_count or 0,
					'private': count - (public_count or 0)
				}
				stats['total'] += count
				stats['public'] += public_count or 0

			stats['private'] = stats['total'] - stats['public']

			return stats
		except Exception as e:
			raise RepositoryError(f"获取模板统计失败: {str(e)}")

	async def duplicate_template (
			self,
			template_id: str,
			new_template_name: str,
			created_by: int,
			is_public: Optional[bool] = None
	) -> Optional[AnalysisTemplate]:
		"""
		复制模板

		Args:
			template_id: 模板ID
			new_template_name: 新模板名称
			created_by: 创建人ID
			is_public: 是否公开（可选）

		Returns:
			Optional[AnalysisTemplate]: 复制的模板对象
		"""
		try:
			template = await self.get(template_id)

			if not template:
				return None

			# 创建新模板
			new_template_data = {
				'template_name': new_template_name,
				'template_type': template.template_type,
				'config_template': template.config_template.copy() if template.config_template else {},
				'output_format': template.output_format,
				'description': f"复制自: {template.template_name}",
				'is_public': is_public if is_public is not None else template.is_public,
				'created_by': created_by
			}

			return await self.create(new_template_data)
		except Exception as e:
			raise RepositoryError(f"复制模板失败: {str(e)}")

	async def get_template_usage_count (
			self,
			template_id: str,
			days: int = 30
	) -> Dict[str, Any]:
		"""
		获取模板使用统计（通过关联的任务统计）

		Args:
			template_id: 模板ID
			days: 时间范围（天数）

		Returns:
			Dict[str, Any]: 使用统计信息
		"""
		try:
			from datetime import datetime, timedelta
			from sqlalchemy import func, select

			# 计算时间范围
			start_date = datetime.now() - timedelta(days=days)

			# 查询使用该模板的任务数量

			query = select(
				func.count(AnalysisTask.id).label('total_count'),
				func.count(func.distinct(AnalysisTask.created_by)).label('unique_users'),
				func.avg(AnalysisTask.progress).label('avg_progress'),
				func.sum(case((AnalysisTask.status == 'completed', 1), else_=0)).label('completed_count'),
				func.sum(case((AnalysisTask.status == 'failed', 1), else_=0)).label('failed_count')
			).where(
				and_(
					AnalysisTask.created_at >= start_date,
					# 通过参数中的template_id字段进行关联（需要先添加该字段）
					AnalysisTask.parameters['template_id'].astext == template_id
				)
			)

			result = await self.session.execute(query)
			row = result.fetchone()

			# 如果没有找到关联字段，尝试通过模板名称匹配
			if row.total_count == 0:
				# 获取模板名称
				template = await self.get(template_id)
				if template:
					# 通过任务参数中的模板名称进行模糊匹配
					query2 = select(
						func.count(AnalysisTask.id).label('total_count')
					).where(
						and_(
							AnalysisTask.created_at >= start_date,
							AnalysisTask.parameters['template_name'].astext.ilike(f"%{template.template_name}%")
						)
					)

					result2 = await self.session.execute(query2)
					row2 = result2.fetchone()

					return {
						'total_count': row2.total_count or 0,
						'unique_users': 0,  # 无法通过名称匹配统计用户数
						'avg_progress': 0.0,
						'completed_count': 0,
						'failed_count': 0,
						'statistics_method': 'template_name_match'
					}

			return {
				'total_count': row.total_count or 0,
				'unique_users': row.unique_users or 0,
				'avg_progress': round(float(row.avg_progress or 0), 2),
				'completed_count': row.completed_count or 0,
				'failed_count': row.failed_count or 0,
				'statistics_method': 'template_id_direct'
			}
		except Exception as e:
			raise RepositoryError(f"获取模板使用统计失败: {str(e)}")

	async def set_template_visibility (
			self,
			template_id: str,
			is_public: bool
	) -> bool:
		"""
		设置模板可见性

		Args:
			template_id: 模板ID
			is_public: 是否公开

		Returns:
			bool: 设置是否成功
		"""
		try:
			update_data = {'is_public': is_public}

			# 如果需要记录更新人，可以在这里添加
			# 注意：模型目前没有updated_by字段

			return await self.update(template_id, update_data) is not None
		except Exception as e:
			raise RepositoryError(f"设置模板可见性失败: {str(e)}")
