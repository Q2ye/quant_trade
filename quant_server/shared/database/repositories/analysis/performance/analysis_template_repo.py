# quant_server/shared/database/repositories/analysis/performance/analysis_template_repository.py
"""
分析模板Repository
负责AnalysisTemplate表的数据访问操作

继承自BaseRepository，提供分析模板的管理功能
包括模板创建、查询、验证、渲染等业务方法
"""

from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func, desc, asc

from quant_server.shared.database.models.business_models import AnalysisTemplate
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
			filters = {'is_public': True}

			if template_type:
				filters['template_type'] = template_type

			return await self.get_many(limit=limit, **filters)
		except Exception as e:
			raise RepositoryError(f"获取公开模板失败: {str(e)}")

	async def get_user_templates (
			self,
			user_id: int,
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
			template_id: int,
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
			config_template: Dict[str, Any],
			required_fields: Optional[List[str]] = None,
			context: Optional[Dict[str, Any]] = None
	) -> Dict[str, Any]:
		"""
		验证模板配置

		Args:
			config_template: 配置模板
			required_fields: 必填字段列表（可选）
			context: 测试上下文数据（可选）

		Returns:
			Dict[str, Any]: 验证结果
		"""
		try:
			validation_result = {
				'valid': True,
				'errors': [],
				'warnings': [],
				'required_fields_missing': [],
				'rendered_config': None
			}

			# 检查必填字段
			if required_fields:
				for field in required_fields:
					if field not in config_template:
						validation_result['required_fields_missing'].append(field)
						validation_result['valid'] = False

			# 尝试渲染模板（如果有上下文）
			if context:
				try:
					# 使用简化渲染逻辑
					def render_config (config: Any) -> Any:
						if isinstance(config, dict):
							return {k: render_config(v) for k, v in config.items()}
						elif isinstance(config, list):
							return [render_config(item) for item in config]
						elif isinstance(config, str):
							import re
							pattern = r'\{(\w+)\}'
							matches = re.findall(pattern, config)

							# 检查所有占位符是否都有对应的上下文值
							for placeholder in matches:
								if placeholder not in context:
									validation_result['warnings'].append(
										f"占位符 '{placeholder}' 在上下文中未定义"
									)

							return config
						else:
							return config

					validation_result['rendered_config'] = render_config(config_template)
				except Exception as e:
					validation_result['errors'].append(f"渲染失败: {str(e)}")
					validation_result['valid'] = False

			# 检查配置结构
			if not isinstance(config_template, dict):
				validation_result['errors'].append("配置模板必须是字典格式")
				validation_result['valid'] = False

			return validation_result
		except Exception as e:
			raise RepositoryError(f"验证模板配置失败: {str(e)}")

	async def update_template (
			self,
			template_id: int,
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
			template_id: int,
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
			template_id: int,
			days: int = 30
	) -> int:
		"""
		获取模板使用次数（通过关联的任务统计）

		Args:
			template_id: 模板ID
			days: 时间范围（天数）

		Returns:
			int: 使用次数
		"""
		try:
			# 这里需要关联AnalysisTask表进行统计
			# 由于模板和任务之间没有直接关联，需要通过其他方式统计
			# 这里简化实现，返回0

			# 实际实现可能需要添加模板ID到任务表的关联字段
			# 或者通过其他方式追踪模板使用情况

			return 0
		except Exception as e:
			raise RepositoryError(f"获取模板使用次数失败: {str(e)}")

	async def set_template_visibility (
			self,
			template_id: int,
			is_public: bool,
			updated_by: Optional[int] = None
	) -> bool:
		"""
		设置模板可见性

		Args:
			template_id: 模板ID
			is_public: 是否公开
			updated_by: 更新人ID（可选）

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