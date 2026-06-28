# quant_server/shared/security/audit.py
"""
审计日志模块
记录系统安全相关操作和事件，支持操作审计、数据变更审计和安全事件记录
"""

import inspect
import json
import logging
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Optional, Dict, Any, List, Union

from pydantic import BaseModel

from ..config.config_manager import config
from ..database.models.system_models import AuditLog


class AuditAction(str, Enum):
	"""审计操作类型枚举"""
	LOGIN = "login"
	LOGOUT = "logout"
	CREATE = "create"
	READ = "read"
	UPDATE = "update"
	DELETE = "delete"
	EXECUTE = "execute"
	ACCESS = "access"
	AUTHORIZE = "authorize"
	CONFIG_CHANGE = "config_change"
	SECURITY_EVENT = "security_event"
	SYSTEM_EVENT = "system_event"


class AuditLevel(str, Enum):
	"""审计日志级别"""
	DEBUG = "debug"
	INFO = "info"
	WARNING = "warning"
	ERROR = "error"
	CRITICAL = "critical"


class AuditResult(str, Enum):
	"""审计操作结果"""
	SUCCESS = "success"
	FAILURE = "failure"
	PARTIAL = "partial"


class AuditLogEntry(BaseModel):
	"""审计日志条目模型"""
	user_id: Optional[str] = None
	username: Optional[str] = None
	action: AuditAction
	resource_type: str
	resource_id: Optional[str] = None
	description: str
	details: Optional[Dict[str, Any]] = None
	ip_address: Optional[str] = None
	user_agent: Optional[str] = None
	level: AuditLevel = AuditLevel.INFO
	result: AuditResult = AuditResult.SUCCESS
	timestamp: datetime = None

	class Config:
		use_enum_values = True


class AuditLogger:
	"""审计日志记录器"""

	def __init__ (
			self,
			repo: Optional[Any] = None,
			enable_console: bool = True,
			enable_database: bool = True):
		"""
		初始化审计日志记录器

		Args:
			repo: 审计日志仓库
			enable_console: 是否启用控制台输出
			enable_database: 是否启用数据库存储
		"""
		self.repo = repo
		self.enable_console = enable_console
		self.enable_database = enable_database
		self._audit_session_factory = None  # 独立 session factory（延迟初始化）
		self._repo_available = False
		self.settings = config.settings
		self.audit_enabled = True
		self.audit_retention_days = 30

	async def log (self, entry: AuditLogEntry) -> Optional[AuditLog]:
		"""
		记录审计日志

		Args:
			entry: 审计日志条目

		Returns:
			创建的审计日志记录（如果保存到数据库）
		"""
		if not self.audit_enabled:
			return None

		# 确保有时间戳
		if entry.timestamp is None:
			entry.timestamp = datetime.now()

		audit_record = None

		try:
			# 控制台输出
			if self.enable_console:
				self._log_to_console(entry)

			# 数据库存储
			if self.enable_database:
				audit_record = await self._log_to_database(entry)

			return audit_record

		except Exception as e:
			# 审计日志记录失败时，至少输出到控制台
			print(f"审计日志记录失败: {str(e)}")
			self._log_to_console(entry)
			return None

	async def log_simple (
			self,
			user_id: Optional[str] = None,
			username: Optional[str] = None,
			action: Union[str, AuditAction] = AuditAction.SYSTEM_EVENT,
			resource_type: str = "system",
			resource_id: Optional[str] = None,
			description: str = "",
			details: Optional[Dict[str, Any]] = None,
			ip_address: Optional[str] = None,
			user_agent: Optional[str] = None,
			level: Union[str, AuditLevel] = AuditLevel.INFO,
			result: Union[str, AuditResult] = AuditResult.SUCCESS
	) -> Optional[AuditLog]:
		"""
		记录简单审计日志

		Args:
			user_id: 用户ID
			username: 用户名
			action: 操作类型
			resource_type: 资源类型
			resource_id: 资源ID
			description: 描述
			details: 详细信息
			ip_address: IP地址
			user_agent: 用户代理
			level: 日志级别
			result: 操作结果

		Returns:
			创建的审计日志记录（如果保存到数据库）
		"""
		entry = AuditLogEntry(
			user_id=user_id,
			username=username,
			action=action,
			resource_type=resource_type,
			resource_id=resource_id,
			description=description,
			details=details,
			ip_address=ip_address,
			user_agent=user_agent,
			level=level,
			result=result
		)

		return await self.log(entry)

	async def log_security_event (
			self,
			event_type: str,
			user_id: Optional[str] = None,
			username: Optional[str] = None,
			description: str = "",
			details: Optional[Dict[str, Any]] = None,
			ip_address: Optional[str] = None,
			user_agent: Optional[str] = None,
			level: AuditLevel = AuditLevel.WARNING
	) -> Optional[AuditLog]:
		"""
		记录安全事件

		Args:
			event_type: 安全事件类型
			user_id: 用户ID
			username: 用户名
			description: 描述
			details: 详细信息
			ip_address: IP地址
			user_agent: 用户代理
			level: 日志级别

		Returns:
			创建的审计日志记录
		"""
		return await self.log_simple(
			user_id=user_id,
			username=username,
			action=AuditAction.SECURITY_EVENT,
			resource_type="security",
			description=f"安全事件: {event_type} - {description}",
			details=details,
			ip_address=ip_address,
			user_agent=user_agent,
			level=level
		)

	async def log_user_action (
			self,
			action: Union[str, AuditAction],
			user_id: Optional[str] = None,
			username: Optional[str] = None,
			resource_type: str = "user",
			resource_id: Optional[str] = None,
			description: str = "",
			details: Optional[Dict[str, Any]] = None,
			ip_address: Optional[str] = None,
			user_agent: Optional[str] = None,
			result: AuditResult = AuditResult.SUCCESS
	) -> Optional[AuditLog]:
		"""
		记录用户操作

		Args:
			action: 操作类型
			user_id: 用户ID
			username: 用户名
			resource_type: 资源类型
			resource_id: 资源ID
			description: 描述
			details: 详细信息
			ip_address: IP地址
			user_agent: 用户代理
			result: 操作结果

		Returns:
			创建的审计日志记录
		"""
		return await self.log_simple(
			user_id=user_id,
			username=username,
			action=action,
			resource_type=resource_type,
			resource_id=resource_id,
			description=description,
			details=details,
			ip_address=ip_address,
			user_agent=user_agent,
			result=result
		)

	async def log_data_change (
			self,
			action: Union[str, AuditAction],
			user_id: Optional[str] = None,
			username: Optional[str] = None,
			resource_type: str = "data",
			resource_id: Optional[str] = None,
			old_data: Optional[Dict[str, Any]] = None,
			new_data: Optional[Dict[str, Any]] = None,
			description: str = "",
			ip_address: Optional[str] = None,
			user_agent: Optional[str] = None
	) -> Optional[AuditLog]:
		"""
		记录数据变更

		Args:
			action: 操作类型
			user_id: 用户ID
			username: 用户名
			resource_type: 资源类型
			resource_id: 资源ID
			old_data: 变更前的数据
			new_data: 变更后的数据
			description: 描述
			ip_address: IP地址
			user_agent: 用户代理

		Returns:
			创建的审计日志记录
		"""
		details = {}
		if old_data:
			details['old_data'] = old_data
		if new_data:
			details['new_data'] = new_data

		return await self.log_simple(
			user_id=user_id,
			username=username,
			action=action,
			resource_type=resource_type,
			resource_id=resource_id,
			description=description,
			details=details,
			ip_address=ip_address,
			user_agent=user_agent,
			level=AuditLevel.INFO
		)

	async def get_user_logs (
			self,
			user_id: str,
			action: Optional[Union[str, AuditAction]] = None,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			limit: int = 100
	) -> List[AuditLog]:
		"""
		获取用户的审计日志

		Args:
			user_id: 用户ID
			action: 操作类型（可选）
			start_time: 开始时间（可选）
			end_time: 结束时间（可选）
			limit: 返回数量限制

		Returns:
			审计日志列表
		"""
		if not self.repo:
			await self._init_repository()

		try:
			# 调用 AuditRepository 的 search_audit_logs 方法
			result = await self.repo.search_audit_logs(
				user_id=user_id,
				action=action,
				start_date=start_time,
				end_date=end_time,
				limit=limit,
				offset=0
			)
			return result.get('audit_logs', [])

		except Exception as e:
			print(f"获取用户审计日志失败: {str(e)}")
			return []

	async def search_logs (
			self,
			resource_type: Optional[str] = None,
			resource_id: Optional[str] = None,
			action: Optional[Union[str, AuditAction]] = None,
			level: Optional[Union[str, AuditLevel]] = None,
			start_time: Optional[datetime] = None,
			end_time: Optional[datetime] = None,
			limit: int = 100,
			offset: int = 0
	) -> Dict[str, Any]:
		"""
		搜索审计日志

		Args:
			resource_type: 资源类型
			resource_id: 资源ID
			action: 操作类型
			level: 日志级别
			start_time: 开始时间
			end_time: 结束时间
			limit: 返回数量限制
			offset: 偏移量

		Returns:
			包含日志列表和总数的字典
		"""
		if not self.repo:
			await self._init_repository()

		try:
			# 调用 AuditRepository 的 search_audit_logs 方法
			result = await self.repo.search_audit_logs(
				start_date=start_time,
				end_date=end_time,
				action=action,
				resource_type=resource_type,
				resource_id=resource_id,
				level=level,
				limit=limit,
				offset=offset
			)

			return {
				'total': result.get('total', 0),
				'logs': result.get('audit_logs', []),
				'limit': limit,
				'offset': offset
			}

		except Exception as e:
			print(f"搜索审计日志失败: {str(e)}")
			return {'total': 0, 'logs': [], 'limit': limit, 'offset': offset}

	async def cleanup_old_logs (self, retention_days: Optional[int] = None) -> int:
		"""
		清理旧的审计日志

		Args:
			retention_days: 保留天数，如果为None则使用配置值

		Returns:
			删除的日志数量
		"""
		if not self.repo:
			await self._init_repository()

		try:
			if retention_days is None:
				retention_days = self.audit_retention_days

			# 调用 AuditRepository 的 clean_old_audit_logs 方法
			deleted_count = await self.repo.clean_old_audit_logs(days=retention_days)

			# 记录清理操作
			await self.log_simple(
				action=AuditAction.SYSTEM_EVENT,
				resource_type="audit",
				description=f"清理了{deleted_count}条超过{retention_days}天的审计日志",
				level=AuditLevel.INFO
			)

			return deleted_count

		except Exception as e:
			print(f"清理审计日志失败: {str(e)}")
			return 0

	@staticmethod
	def _log_to_console (entry: AuditLogEntry):
		"""输出审计日志到控制台"""
		timestamp = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
		user_info = f"用户[{entry.user_id or '未知'}:{entry.username or '未知'}]"
		action_info = f"操作[{entry.action}]"
		resource_info = f"资源[{entry.resource_type}:{entry.resource_id or '所有'}]"
		result_info = f"结果[{entry.result}]"
		level_info = f"级别[{entry.level.upper()}]"

		log_message = f"[审计] {timestamp} {level_info} {user_info} {action_info} {resource_info} {result_info}: {entry.description}"

		if entry.details:
			details_str = json.dumps(entry.details, ensure_ascii=False, indent=2)
			log_message += f"\n详情: {details_str}"

		print(log_message)

	async def _log_to_database (self, entry: AuditLogEntry) -> Optional[AuditLog]:
		"""保存审计日志到数据库 —— 使用独立 session 避免生命周期冲突"""
		if not self._audit_session_factory:
			await self._init_repository()
		if not self._audit_session_factory:
			logging.getLogger(__name__).debug("审计仓库未初始化，跳过数据库持久化")
			return None

		try:
			async with self._audit_session_factory() as session:
				from shared.database.repositories.system.config.audit_repo import AuditRepository
				repo = AuditRepository(session)

				audit_data = {
					'user_id': entry.user_id,
					'username': entry.username,
					'action_type': entry.action,
					'resource_type': entry.resource_type,
					'resource_id': entry.resource_id,
					'resource_name': entry.description,
					'new_values': json.dumps(entry.details) if entry.details else None,
					'ip_address': entry.ip_address,
					'user_agent': entry.user_agent,
					'status': entry.result,
					'created_at': entry.timestamp
				}

				result = await repo.create(audit_data)
				await session.commit()
				return result

		except Exception as e:
			logging.getLogger(__name__).error(f"保存审计日志到数据库失败: {str(e)}")
			return None

	async def _init_repository (self):
		"""初始化仓库（延迟加载）—— 使用独立 session_factory 避免生命周期冲突"""
		try:
			from shared.database.session.session_manager import get_session_manager
			session_mgr = get_session_manager()
			self._audit_session_factory = session_mgr.create_async_session_factory()

			# 验证 session 可用性
			from sqlalchemy import text as sa_text
			async with self._audit_session_factory() as session:
				from shared.database.repositories.system.config.audit_repo import AuditRepository
				self.repo = AuditRepository(session)
				await session.execute(sa_text("SELECT 1"))
				self._repo_available = True
			logging.getLogger(__name__).info("审计日志仓库初始化成功（独立 session factory）")
		except Exception as e:
			logging.getLogger(__name__).warning(
				f"审计日志仓库初始化失败，仅控制台输出: {e}"
			)
			self.repo = None
			self._audit_session_factory = None


# 审计日志装饰器
def audit_log (
		action: Union[str, AuditAction],
		resource_type: str = "system",
		resource_id_param: Optional[str] = None,
		capture_result: bool = True,
		capture_args: bool = True
):
	"""
	审计日志装饰器

	Args:
		action: 操作类型
		resource_type: 资源类型
		resource_id_param: 资源ID参数名
		capture_result: 是否捕获函数返回结果
		capture_args: 是否捕获函数参数
	"""

	def decorator (func):
		@wraps(func)
		async def wrapper (*args, **kwargs):
			# 获取调用上下文信息
			frame = inspect.currentframe()
			caller_info = {}

			if frame and frame.f_back:
				caller_frame = frame.f_back
				caller_info = {
					'file': caller_frame.f_code.co_filename,
					'line': caller_frame.f_lineno,
					'function': caller_frame.f_code.co_name
				}

			# 获取资源ID
			resource_id = None
			if resource_id_param and resource_id_param in kwargs:
				resource_id = str(kwargs[resource_id_param])

			# 获取用户信息（从参数或请求上下文）
			user_id = None
			username = None

			# 尝试从参数获取
			for arg in args:
				if hasattr(arg, 'id') and hasattr(arg, 'username'):
					user_id = arg.id
					username = arg.username
					break

			# 尝试从kwargs获取
			if not user_id:
				for key, value in kwargs.items():
					if hasattr(value, 'id') and hasattr(value, 'username'):
						user_id = value.id
						username = value.username
						break

			# 获取请求信息（如果可用）
			ip_address = None
			user_agent = None

			for arg in args:
				if hasattr(arg, 'client_host'):
					ip_address = arg.client_host
					break
				elif hasattr(arg, 'headers'):
					# FastAPI Request对象
					ip_address = arg.client.host if hasattr(arg.client, 'host') else None
					user_agent = arg.headers.get('user-agent')
					break

			# 执行函数前记录（如果是操作开始）
			if action in [AuditAction.LOGIN, AuditAction.EXECUTE]:
				audit_logger = get_audit_logger()
				await audit_logger.log_simple(
					user_id=user_id,
					username=username,
					action=f"{action}_start",
					resource_type=resource_type,
					resource_id=resource_id,
					description=f"开始执行: {func.__name__}",
					ip_address=ip_address,
					user_agent=user_agent,
					level=AuditLevel.INFO
				)

			# 捕获函数参数（如果启用）
			captured_args = {}
			if capture_args:
				# 获取函数参数名
				sig = inspect.signature(func)
				param_names = list(sig.parameters.keys())

				# 映射参数值
				for i, arg_value in enumerate(args):
					if i < len(param_names):
						param_name = param_names[i]
						# 排除敏感参数
						if 'password' not in param_name.lower() and 'token' not in param_name.lower():
							try:
								captured_args[param_name] = str(arg_value)[:500]  # 限制长度
							except (TypeError, ValueError):
								captured_args[param_name] = '<unserializable>'

				# 添加kwargs参数
				for key, value in kwargs.items():
					if 'password' not in key.lower() and 'token' not in key.lower():
						try:
							captured_args[key] = str(value)[:500]
						except (TypeError, ValueError):
								captured_args[key] = '<unserializable>'

			try:
				# 执行原函数
				result = await func(*args, **kwargs)

				# 记录成功日志
				audit_logger = get_audit_logger()

				details = {
					'function': func.__name__,
					'module': func.__module__,
					'caller': caller_info
				}

				if captured_args:
					details['arguments'] = captured_args

				if capture_result and result is not None:
					try:
						details['result'] = str(result)[:1000]  # 限制长度
					except (TypeError, ValueError):
						details['result'] = '<unserializable>'

				await audit_logger.log_simple(
					user_id=user_id,
					username=username,
					action=action,
					resource_type=resource_type,
					resource_id=resource_id,
					description=f"执行成功: {func.__name__}",
					details=details,
					ip_address=ip_address,
					user_agent=user_agent,
					level=AuditLevel.INFO,
					result=AuditResult.SUCCESS
				)

				return result

			except Exception as e:
				# 记录失败日志
				audit_logger = get_audit_logger()

				details = {
					'function': func.__name__,
					'module': func.__module__,
					'caller': caller_info,
					'error': str(e),
					'error_type': type(e).__name__
				}

				if captured_args:
					details['arguments'] = captured_args

				await audit_logger.log_simple(
					user_id=user_id,
					username=username,
					action=action,
					resource_type=resource_type,
					resource_id=resource_id,
					description=f"执行失败: {func.__name__} - {str(e)}",
					details=details,
					ip_address=ip_address,
					user_agent=user_agent,
					level=AuditLevel.ERROR,
					result=AuditResult.FAILURE
				)

				raise

		return wrapper

	return decorator


# 全局审计日志记录器实例
_audit_logger = None


def get_audit_logger (
		repo: Optional[Any] = None,
		enable_console: Optional[bool] = None,
		enable_database: Optional[bool] = None
) -> AuditLogger:
	"""
	获取全局审计日志记录器

	Args:
		repo: 审计日志仓库
		enable_console: 是否启用控制台输出
		enable_database: 是否启用数据库存储

	Returns:
		AuditLogger实例
	"""
	global _audit_logger

	if _audit_logger is None:
		if enable_console is None:
			enable_console = True

		if enable_database is None:
			enable_database = True

		_audit_logger = AuditLogger(
			repo=repo,
			enable_console=enable_console,
			enable_database=enable_database
		)

	return _audit_logger


# 便捷函数
async def log_audit (
		action: Union[str, AuditAction],
		resource_type: str = "system",
		resource_id: Optional[str] = None,
		description: str = "",
		**kwargs
) -> Optional[AuditLog]:
	"""记录审计日志的便捷函数"""
	return await get_audit_logger().log_simple(
		action=action,
		resource_type=resource_type,
		resource_id=resource_id,
		description=description,
		**kwargs
	)