# quant_server/shared/database/repositories/analysis/monitor/alert_template_repo.py
"""
报警模板Repository
负责AlertTemplate表的数据访问操作

继承自BaseRepository，提供报警模板的管理功能
包括模板查询、渲染、验证等
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func

from quant_server.shared.database.models.business_models import AlertTemplate
from quant_server.shared.database.repositories.base.repository_base import BaseRepository, RepositoryError


class AlertTemplateRepository(BaseRepository[AlertTemplate]):
	"""
	报警模板Repository
	继承自BaseRepository，提供报警模板的数据访问方法
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化报警模板Repository

		Args:
			session: 数据库会话
		"""
		super().__init__(session, AlertTemplate)

	async def create_template (
			self,
			template_name: str,
			alert_type: str,
			alert_level: str,
			title_template: str,
			message_template: str,
			notification_channels: Optional[List[str]] = None,
			is_active: bool = True
	) -> AlertTemplate:
		"""
		创建报警模板

		Args:
			template_name: 模板名称
			alert_type: 报警类型
			alert_level: 报警级别
			title_template: 标题模板
			message_template: 消息模板
			notification_channels: 通知渠道（可选）
			is_active: 是否激活

		Returns:
			AlertTemplate: 创建的模板对象
		"""
		try:
			template_data = {
				'template_name': template_name,
				'alert_type': alert_type,
				'alert_level': alert_level,
				'title_template': title_template,
				'message_template': message_template,
				'notification_channels': notification_channels or ["email"],
				'is_active': is_active
			}

			return await self.create(template_data)
		except Exception as e:
			raise RepositoryError(f"创建报警模板失败: {str(e)}")

	async def get_template_by_type_level (
			self,
			alert_type: str,
			alert_level: str
	) -> Optional[AlertTemplate]:
		"""
		根据报警类型和级别获取模板

		Args:
			alert_type: 报警类型
			alert_level: 报警级别

		Returns:
			Optional[AlertTemplate]: 模板对象或None
		"""
		try:
			return await self.get_by(
				alert_type=alert_type,
				alert_level=alert_level,
				is_active=True
			)
		except Exception as e:
			raise RepositoryError(f"获取类型级别模板失败: {str(e)}")

	async def get_active_templates (
			self,
			alert_type: Optional[str] = None,
			alert_level: Optional[str] = None
	) -> List[AlertTemplate]:
		"""
		获取活跃的模板

		Args:
			alert_type: 报警类型过滤（可选）
			alert_level: 报警级别过滤（可选）

		Returns:
			List[AlertTemplate]: 活跃模板列表
		"""
		try:
			filters = {'is_active': True}

			if alert_type:
				filters['alert_type'] = alert_type
			if alert_level:
				filters['alert_level'] = alert_level

			return await self.get_all(**filters)
		except Exception as e:
			raise RepositoryError(f"获取活跃模板失败: {str(e)}")

	async def render_template (
			self,
			template_id: int,
			context: Dict[str, Any]
	) -> Dict[str, str]:
		"""
		渲染模板

		Args:
			template_id: 模板ID
			context: 模板上下文数据

		Returns:
			Dict[str, str]: 渲染后的标题和消息
		"""
		try:
			template = await self.get(template_id)

			if not template:
				raise RepositoryError(f"模板不存在: {template_id}")

			# 简单的模板渲染 - 替换 {key} 为 context[key]
			def render_text (text: str) -> str:
				if not text:
					return ""

				result = text
				for key, value in context.items():
					placeholder = f"{{{key}}}"
					if placeholder in result:
						result = result.replace(placeholder, str(value))

				return result

			rendered_title = render_text(template.title_template)
			rendered_message = render_text(template.message_template)

			return {
				'title': rendered_title,
				'message': rendered_message,
				'channels': template.notification_channels or ["email"],
				'template_type': template.alert_type,
				'template_level': template.alert_level
			}
		except Exception as e:
			raise RepositoryError(f"渲染模板失败: {str(e)}")

	async def render_by_type_level (
			self,
			alert_type: str,
			alert_level: str,
			context: Dict[str, Any]
	) -> Optional[Dict[str, str]]:
		"""
		根据类型和级别渲染模板

		Args:
			alert_type: 报警类型
			alert_level: 报警级别
			context: 模板上下文数据

		Returns:
			Optional[Dict[str, str]]: 渲染结果或None
		"""
		try:
			template = await self.get_template_by_type_level(alert_type, alert_level)

			if not template:
				return None

			return await self.render_template(template.id, context)
		except Exception as e:
			raise RepositoryError(f"按类型级别渲染模板失败: {str(e)}")

	async def validate_template (
			self,
			title_template: str,
			message_template: str,
			context: Dict[str, Any]
	) -> Dict[str, Any]:
		"""
		验证模板有效性

		Args:
			title_template: 标题模板
			message_template: 消息模板
			context: 测试上下文数据

		Returns:
			Dict[str, Any]: 验证结果
		"""
		try:
			# 检查模板中的占位符
			import re

			def extract_placeholders (text: str) -> List[str]:
				pattern = r'\{(\w+)\}'
				return re.findall(pattern, text)

			title_placeholders = set(extract_placeholders(title_template))
			message_placeholders = set(extract_placeholders(message_template))
			all_placeholders = title_placeholders.union(message_placeholders)

			# 检查上下文是否包含所有占位符
			missing_placeholders = []
			for placeholder in all_placeholders:
				if placeholder not in context:
					missing_placeholders.append(placeholder)

			# 渲染测试
			test_template = AlertTemplate(
				template_name="test",
				alert_type="test",
				alert_level="test",
				title_template=title_template,
				message_template=message_template
			)

			# 临时保存模板并渲染
			temp_id = 999999  # 虚拟ID

			result = {
				'valid': len(missing_placeholders) == 0,
				'missing_placeholders': missing_placeholders,
				'total_placeholders': len(all_placeholders),
				'title_placeholders': list(title_placeholders),
				'message_placeholders': list(message_placeholders),
				'rendered_title': None,
				'rendered_message': None
			}

			if result['valid']:
				# 简单渲染
				def render_text (text: str) -> str:
					result = text
					for key, value in context.items():
						placeholder = f"{{{key}}}"
						if placeholder in result:
							result = result.replace(placeholder, str(value))
					return result

				result['rendered_title'] = render_text(title_template)
				result['rendered_message'] = render_text(message_template)

			return result
		except Exception as e:
			raise RepositoryError(f"验证模板失败: {str(e)}")

	async def update_template (
			self,
			template_id: int,
			template_name: Optional[str] = None,
			title_template: Optional[str] = None,
			message_template: Optional[str] = None,
			notification_channels: Optional[List[str]] = None,
			is_active: Optional[bool] = None
	) -> Optional[AlertTemplate]:
		"""
		更新模板

		Args:
			template_id: 模板ID
			template_name: 模板名称（可选）
			title_template: 标题模板（可选）
			message_template: 消息模板（可选）
			notification_channels: 通知渠道（可选）
			is_active: 是否激活（可选）

		Returns:
			Optional[AlertTemplate]: 更新后的模板对象
		"""
		try:
			update_data = {}

			if template_name is not None:
				update_data['template_name'] = template_name
			if title_template is not None:
				update_data['title_template'] = title_template
			if message_template is not None:
				update_data['message_template'] = message_template
			if notification_channels is not None:
				update_data['notification_channels'] = notification_channels
			if is_active is not None:
				update_data['is_active'] = is_active

			return await self.update(template_id, update_data)
		except Exception as e:
			raise RepositoryError(f"更新模板失败: {str(e)}")

	async def search_templates (
			self,
			keyword: str,
			alert_type: Optional[str] = None,
			only_active: bool = True,
			limit: int = 50
	) -> List[AlertTemplate]:
		"""
		搜索模板

		Args:
			keyword: 搜索关键词
			alert_type: 报警类型过滤（可选）
			only_active: 是否只搜索活跃模板
			limit: 限制记录数

		Returns:
			List[AlertTemplate]: 搜索结果的模板列表
		"""
		try:
			query = select(self.model).where(
				or_(
					self.model.template_name.ilike(f'%{keyword}%'),
					self.model.title_template.ilike(f'%{keyword}%'),
					self.model.message_template.ilike(f'%{keyword}%')
				)
			)

			if alert_type:
				query = query.where(self.model.alert_type == alert_type)

			if only_active:
				query = query.where(self.model.is_active == True)

			query = query.limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"搜索模板失败: {str(e)}")

	async def get_template_summary (self) -> Dict[str, Any]:
		"""
		获取模板摘要

		Returns:
			Dict[str, Any]: 模板摘要信息
		"""
		try:
			# 统计各类型模板数量
			query = select(
				self.model.alert_type,
				func.count(self.model.id).label('count'),
				func.sum(func.cast(self.model.is_active, func.Integer)).label('active_count')
			).group_by(self.model.alert_type)

			result = await self.session.execute(query)

			summary = {
				'total': 0,
				'active': 0,
				'by_type': {}
			}

			for alert_type, count, active_count in result.all():
				summary['by_type'][alert_type] = {
					'total': count,
					'active': active_count,
					'inactive': count - active_count
				}
				summary['total'] += count
				summary['active'] += active_count

			summary['inactive'] = summary['total'] - summary['active']

			return summary
		except Exception as e:
			raise RepositoryError(f"获取模板摘要失败: {str(e)}")